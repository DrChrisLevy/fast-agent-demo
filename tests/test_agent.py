"""Tests for the agent loop."""

from unittest.mock import MagicMock, patch


from agents.agent import run_agent


def _mock_llm_response(content="Mock response", tool_calls=None):
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

    return mock_response


def _mock_tool_call(call_id, name, arguments):
    """Create a mock tool call object."""
    mock_tc = MagicMock()
    mock_tc.id = call_id
    mock_tc.function.name = name
    mock_tc.function.arguments = arguments
    return mock_tc


class TestRunAgentYieldFormat:
    """Tests for run_agent yield format - should yield standard Chat Completions messages."""

    def test_final_response_yields_assistant_message(self):
        """Final response should yield a dict with role='assistant' and content."""
        with patch("agents.agent.litellm.completion") as mock_completion:
            mock_completion.return_value = _mock_llm_response("Hello there!")

            messages = [{"role": "user", "content": "Hi"}]
            events = list(run_agent(messages))

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
                events = list(run_agent(messages))

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
                events = list(run_agent(messages))

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
            events = list(run_agent(messages))

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
