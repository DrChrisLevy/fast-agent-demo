"""Tests for the agent loop."""

from unittest.mock import MagicMock, patch


from agents.agent import run_agent


def _mock_llm_response(content="Mock response", tool_calls=None, total_tokens=100):
    """Create a mock litellm completion response."""
    mock_message = MagicMock()
    mock_message.content = content
    mock_message.tool_calls = tool_calls

    # Make it behave like a dict for .get() calls
    mock_message.get = lambda k, d=None: {"role": "assistant", "content": content}.get(k, d)

    mock_choice = MagicMock()
    mock_choice.message = mock_message

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    # Mock usage with real integer for token count formatting
    mock_response.usage.total_tokens = total_tokens

    return mock_response


def _mock_tool_call(call_id, name, arguments):
    """Create a mock tool call object."""
    mock_tc = MagicMock()
    mock_tc.id = call_id
    mock_tc.function.name = name
    mock_tc.function.arguments = arguments
    return mock_tc


def _filter_message_events(events):
    """Filter out usage events, keeping only message events."""
    return [e for e in events if not (isinstance(e, dict) and e.get("type") == "usage")]


def _filter_usage_events(events):
    """Filter to only usage events."""
    return [e for e in events if isinstance(e, dict) and e.get("type") == "usage"]


class TestRunAgentYieldFormat:
    """Tests for run_agent yield format - should yield standard Chat Completions messages."""

    def test_final_response_yields_assistant_message(self):
        """Final response should yield a dict with role='assistant' and content."""
        with patch("agents.agent.litellm.completion") as mock_completion:
            mock_completion.return_value = _mock_llm_response("Hello there!")

            messages = [{"role": "user", "content": "Hi"}]
            events = _filter_message_events(list(run_agent(messages)))

            assert len(events) == 1
            assert events[0]["role"] == "assistant"
            assert events[0]["content"] == "Hello there!"
            assert "tool_calls" not in events[0]

    def test_tool_call_yields_assistant_message_with_tool_calls(self):
        """Tool call should yield the assistant message object with tool_calls."""
        mock_tc = _mock_tool_call("call_123", "run_code", '{"code": "print(1)"}')

        with patch("agents.agent.litellm.completion") as mock_completion:
            with patch("agents.agent.TOOL_FUNCTIONS", {"run_code": lambda **kwargs: "1"}):
                mock_completion.side_effect = [
                    _mock_llm_response(content=None, tool_calls=[mock_tc]),
                    _mock_llm_response("Done!"),
                ]

                messages = [{"role": "user", "content": "Run some code"}]
                events = _filter_message_events(list(run_agent(messages)))

                # Should yield: assistant with tool_calls, tool result, final assistant
                assert len(events) == 3

                # First: assistant message with tool_calls
                assert hasattr(events[0], "tool_calls") or events[0].get("tool_calls")
                tool_calls = getattr(events[0], "tool_calls", None) or events[0].get("tool_calls")
                assert tool_calls is not None
                assert len(tool_calls) == 1

                # Second: tool result message
                assert events[1]["role"] == "tool"
                assert events[1]["tool_call_id"] == "call_123"
                assert events[1]["content"] == "1"

                # Third: final response
                assert events[2]["role"] == "assistant"
                assert events[2]["content"] == "Done!"

    def test_multiple_tool_calls_yield_multiple_tool_results(self):
        """Multiple parallel tool calls should yield multiple tool result messages."""
        mock_tc1 = _mock_tool_call("call_1", "run_code", '{"code": "1+1"}')
        mock_tc2 = _mock_tool_call("call_2", "run_code", '{"code": "2+2"}')

        with patch("agents.agent.litellm.completion") as mock_completion:
            with patch("agents.agent.TOOL_FUNCTIONS", {"run_code": lambda **kwargs: "result"}):
                mock_completion.side_effect = [
                    _mock_llm_response(content=None, tool_calls=[mock_tc1, mock_tc2]),
                    _mock_llm_response("All done!"),
                ]

                messages = [{"role": "user", "content": "Run two things"}]
                events = _filter_message_events(list(run_agent(messages)))

                # Should yield: assistant with tool_calls, tool result 1, tool result 2, final
                assert len(events) == 4

                # First: assistant with tool_calls
                tool_calls = getattr(events[0], "tool_calls", None) or events[0].get("tool_calls")
                assert len(tool_calls) == 2

                # Second and third: tool results
                assert events[1]["role"] == "tool"
                assert events[1]["tool_call_id"] == "call_1"
                assert events[2]["role"] == "tool"
                assert events[2]["tool_call_id"] == "call_2"

                # Fourth: final response
                assert events[3]["role"] == "assistant"
                assert events[3]["content"] == "All done!"

    def test_messages_list_updated_with_same_format(self):
        """Messages list should contain the same objects that were yielded."""
        with patch("agents.agent.litellm.completion") as mock_completion:
            mock_completion.return_value = _mock_llm_response("Hello!")

            messages = [{"role": "user", "content": "Hi"}]
            events = _filter_message_events(list(run_agent(messages)))

            # Messages should have: system, user, assistant
            assert len(messages) == 3
            assert messages[0]["role"] == "system"
            assert messages[1]["role"] == "user"
            assert messages[2]["role"] == "assistant"
            assert messages[2]["content"] == "Hello!"

            # The yielded event should be the same dict added to messages
            assert events[0] is messages[2]


class TestRunAgentMessageHistory:
    """Tests for message history management."""

    def test_adds_system_prompt_if_missing(self):
        """Should prepend system prompt if not present."""
        with patch("agents.agent.litellm.completion") as mock_completion:
            mock_completion.return_value = _mock_llm_response("Hi")

            messages = [{"role": "user", "content": "Hello"}]
            list(run_agent(messages))

            assert messages[0]["role"] == "system"

    def test_preserves_existing_system_prompt(self):
        """Should not add system prompt if already present."""
        with patch("agents.agent.litellm.completion") as mock_completion:
            mock_completion.return_value = _mock_llm_response("Hi")

            messages = [
                {"role": "system", "content": "Custom system prompt"},
                {"role": "user", "content": "Hello"},
            ]
            list(run_agent(messages))

            assert messages[0]["role"] == "system"
            assert messages[0]["content"] == "Custom system prompt"
            assert len([m for m in messages if m.get("role") == "system"]) == 1


class TestRunAgentUsageTracking:
    """Tests for token usage tracking."""

    def test_yields_usage_event_with_correct_structure(self):
        """Usage events should have type='usage' and a 'total' field."""
        with patch("agents.agent.litellm.completion") as mock_completion:
            mock_completion.return_value = _mock_llm_response("Hi", total_tokens=150)

            messages = [{"role": "user", "content": "Hello"}]
            events = list(run_agent(messages))
            usage_events = _filter_usage_events(events)

            assert len(usage_events) == 1
            assert usage_events[0]["type"] == "usage"
            assert usage_events[0]["total"] == 150

    def test_usage_yielded_after_each_llm_call(self):
        """Each LLM call should yield a usage event."""
        mock_tc = _mock_tool_call("call_1", "run_code", '{"code": "1"}')

        with patch("agents.agent.litellm.completion") as mock_completion:
            with patch("agents.agent.TOOL_FUNCTIONS", {"run_code": lambda **kwargs: "1"}):
                mock_completion.side_effect = [
                    _mock_llm_response(content=None, tool_calls=[mock_tc], total_tokens=50),
                    _mock_llm_response("Done!", total_tokens=75),
                ]

                messages = [{"role": "user", "content": "Run code"}]
                events = list(run_agent(messages))
                usage_events = _filter_usage_events(events)

                # Should have 2 usage events (one per LLM call)
                assert len(usage_events) == 2

    def test_usage_accumulates_across_tool_calls(self):
        """Token usage should accumulate across multiple LLM calls."""
        mock_tc = _mock_tool_call("call_1", "run_code", '{"code": "1"}')

        with patch("agents.agent.litellm.completion") as mock_completion:
            with patch("agents.agent.TOOL_FUNCTIONS", {"run_code": lambda **kwargs: "1"}):
                mock_completion.side_effect = [
                    _mock_llm_response(content=None, tool_calls=[mock_tc], total_tokens=100),
                    _mock_llm_response("Done!", total_tokens=50),
                ]

                messages = [{"role": "user", "content": "Run code"}]
                events = list(run_agent(messages))
                usage_events = _filter_usage_events(events)

                # First usage: 100 tokens
                assert usage_events[0]["total"] == 100
                # Second usage: 100 + 50 = 150 tokens (cumulative)
                assert usage_events[1]["total"] == 150

    def test_usage_accumulates_across_multiple_tool_loops(self):
        """Token usage should accumulate across multiple tool call loops."""
        mock_tc1 = _mock_tool_call("call_1", "run_code", '{"code": "1"}')
        mock_tc2 = _mock_tool_call("call_2", "run_code", '{"code": "2"}')

        with patch("agents.agent.litellm.completion") as mock_completion:
            with patch("agents.agent.TOOL_FUNCTIONS", {"run_code": lambda **kwargs: "result"}):
                mock_completion.side_effect = [
                    _mock_llm_response(content=None, tool_calls=[mock_tc1], total_tokens=100),
                    _mock_llm_response(content=None, tool_calls=[mock_tc2], total_tokens=80),
                    _mock_llm_response("All done!", total_tokens=60),
                ]

                messages = [{"role": "user", "content": "Run code"}]
                events = list(run_agent(messages))
                usage_events = _filter_usage_events(events)

                # Should have 3 usage events
                assert len(usage_events) == 3
                # Cumulative: 100, 180, 240
                assert usage_events[0]["total"] == 100
                assert usage_events[1]["total"] == 180
                assert usage_events[2]["total"] == 240

    def test_usage_handles_none_total_tokens(self):
        """Usage tracking should handle None total_tokens gracefully."""
        with patch("agents.agent.litellm.completion") as mock_completion:
            mock_response = _mock_llm_response("Hi", total_tokens=None)
            mock_completion.return_value = mock_response

            messages = [{"role": "user", "content": "Hello"}]
            events = list(run_agent(messages))
            usage_events = _filter_usage_events(events)

            # Should still yield a usage event with 0 total
            assert len(usage_events) == 1
            assert usage_events[0]["total"] == 0
