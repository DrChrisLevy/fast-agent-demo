"""Tests for UI components."""

from fasthtml.common import to_xml
from agents.ui.components import (
    ChatMessage,
    ChatInput,
    TokenCountUpdate,
    ToolExecutionBlock,
    ToolResultBlock,
    make_render_state,
    render_event,
    render_history,
)


def render(component):
    """Helper to render a FastHTML component to string."""
    return to_xml(component)


# ============ ChatMessage ============


class TestChatMessage:
    """Tests for ChatMessage component."""

    def test_user_message_has_you_header(self):
        html = render(ChatMessage("user", "Hello"))
        assert "You" in html

    def test_assistant_message_has_assistant_header(self):
        html = render(ChatMessage("assistant", "Hi there"))
        assert "Assistant" in html

    def test_assistant_message_has_prose_class(self):
        html = render(ChatMessage("assistant", "Hi there"))
        assert "prose" in html

    def test_user_message_does_not_have_prose_class(self):
        html = render(ChatMessage("user", "Hello"))
        assert "prose" not in html

    def test_renders_user_content(self):
        html = render(ChatMessage("user", "Test message"))
        assert "Test message" in html

    def test_renders_assistant_content(self):
        html = render(ChatMessage("assistant", "Response text"))
        assert "Response text" in html

    def test_user_message_has_border(self):
        html = render(ChatMessage("user", "Hello"))
        assert "border-b" in html

    def test_assistant_message_has_border(self):
        html = render(ChatMessage("assistant", "Hello"))
        assert "border-b" in html


# ============ ChatInput ============


class TestChatInput:
    """Tests for ChatInput component."""

    def test_has_textarea_with_message_name(self):
        html = render(ChatInput())
        assert "<textarea" in html
        assert 'name="message"' in html

    def test_has_send_button(self):
        html = render(ChatInput())
        assert "Send" in html
        assert "btn-primary" in html

    def test_has_htmx_post_chat(self):
        html = render(ChatInput())
        assert 'hx-post="/chat"' in html

    def test_has_keyboard_shortcut_trigger(self):
        html = render(ChatInput())
        assert "metaKey" in html
        assert "ctrlKey" in html

    def test_has_autofocus(self):
        html = render(ChatInput())
        assert "autofocus" in html

    def test_disables_elements_during_request(self):
        html = render(ChatInput())
        assert "hx-disabled-elt" in html
        assert "send-btn" in html
        assert "message-input" in html


# ============ TokenCountUpdate ============


class TestTokenCountUpdate:
    """Tests for TokenCountUpdate component."""

    def test_renders_formatted_token_count(self):
        html = render(TokenCountUpdate(1234))
        assert "1,234 tokens" in html

    def test_large_number_formatting(self):
        html = render(TokenCountUpdate(1000000))
        assert "1,000,000 tokens" in html

    def test_has_oob_swap_attribute(self):
        html = render(TokenCountUpdate(100))
        assert 'hx-swap-oob="true"' in html

    def test_has_correct_id(self):
        html = render(TokenCountUpdate(100))
        assert 'id="token-count"' in html

    def test_zero_tokens(self):
        html = render(TokenCountUpdate(0))
        assert "0 tokens" in html


# ============ ToolExecutionBlock ============


class TestToolExecutionBlock:
    """Tests for ToolExecutionBlock component."""

    def test_renders_tool_name(self):
        event = {"tool_name": "run_code", "args": {"code": "print(1)"}, "tool_call_id": "tc_1"}
        html = render(ToolExecutionBlock(event))
        assert "run_code" in html

    def test_shows_running_spinner(self):
        event = {"tool_name": "search", "args": {}, "tool_call_id": "tc_2"}
        html = render(ToolExecutionBlock(event))
        assert "loading-spinner" in html
        assert "Running..." in html

    def test_has_correct_id_based_on_tool_call_id(self):
        event = {"tool_name": "search", "args": {}, "tool_call_id": "tc_abc"}
        html = render(ToolExecutionBlock(event))
        assert 'id="tool-block-tc_abc"' in html

    def test_has_tool_status_id(self):
        event = {"tool_name": "search", "args": {}, "tool_call_id": "tc_xyz"}
        html = render(ToolExecutionBlock(event))
        assert 'id="tool-status-tc_xyz"' in html

    def test_renders_args_dict(self):
        event = {"tool_name": "search", "args": {"query": "hello"}, "tool_call_id": "tc_3"}
        html = render(ToolExecutionBlock(event))
        assert "hello" in html


# ============ ToolResultBlock ============


class TestToolResultBlock:
    """Tests for ToolResultBlock component."""

    def test_renders_text_content(self):
        event = {
            "tool_call_id": "tc_1",
            "result": {"content": [{"type": "text", "text": "stdout:\n42"}]},
        }
        html = render(ToolResultBlock(event))
        assert "42" in html

    def test_skips_no_output_text(self):
        event = {
            "tool_call_id": "tc_2",
            "result": {"content": [{"type": "text", "text": "(no output)"}]},
        }
        html = render(ToolResultBlock(event))
        # Should not render a Pre block with the text, but shows the placeholder span
        assert "<pre" not in html.lower() or "(no output)" not in html.split("<pre")[0]
        # The fallback span should show
        assert "no output" in html

    def test_renders_images_with_modal(self):
        event = {
            "tool_call_id": "tc_3",
            "result": {"content": [{"type": "image_url", "image_url": "data:image/png;base64,ABC123"}]},
        }
        html = render(ToolResultBlock(event))
        assert "<img" in html
        assert "data:image/png;base64,ABC123" in html
        assert "modal" in html

    def test_renders_multiple_images(self):
        event = {
            "tool_call_id": "tc_4",
            "result": {
                "content": [
                    {"type": "image_url", "image_url": "data:image/png;base64,IMG1"},
                    {"type": "image_url", "image_url": "data:image/png;base64,IMG2"},
                ]
            },
        }
        html = render(ToolResultBlock(event))
        assert "IMG1" in html
        assert "IMG2" in html

    def test_renders_plotly_iframes_from_details(self):
        event = {
            "tool_call_id": "tc_5",
            "result": {
                "content": [{"type": "text", "text": "(no output)"}],
                "details": {"plotly_htmls": ["<div>chart1</div>"]},
            },
        }
        html = render(ToolResultBlock(event))
        assert "<iframe" in html
        assert "chart1" in html

    def test_renders_multiple_plotly_charts(self):
        event = {
            "tool_call_id": "tc_6",
            "result": {
                "content": [],
                "details": {"plotly_htmls": ["<div>chart1</div>", "<div>chart2</div>"]},
            },
        }
        html = render(ToolResultBlock(event))
        assert html.count("<iframe") == 2

    def test_error_styling_when_is_error(self):
        event = {
            "tool_call_id": "tc_7",
            "result": {"content": [{"type": "text", "text": "Error: something broke"}]},
            "is_error": True,
        }
        html = render(ToolResultBlock(event))
        assert "text-error" in html

    def test_no_error_styling_when_not_error(self):
        event = {
            "tool_call_id": "tc_8",
            "result": {"content": [{"type": "text", "text": "Success"}]},
            "is_error": False,
        }
        html = render(ToolResultBlock(event))
        assert "text-error" not in html

    def test_clears_spinner_for_tool(self):
        event = {
            "tool_call_id": "tc_9",
            "result": {"content": []},
        }
        html = render(ToolResultBlock(event))
        assert 'id="tool-status-tc_9"' in html
        assert "hx-swap-oob" in html

    def test_empty_content_shows_no_output_placeholder(self):
        event = {
            "tool_call_id": "tc_10",
            "result": {"content": []},
        }
        html = render(ToolResultBlock(event))
        assert "(no output)" in html


# ============ make_render_state ============


class TestMakeRenderState:
    """Tests for make_render_state."""

    def test_default_initial_tokens_is_zero(self):
        state = make_render_state()
        assert state["total_tokens"] == 0

    def test_accepts_initial_tokens_param(self):
        state = make_render_state(initial_tokens=500)
        assert state["total_tokens"] == 500

    def test_has_turn_key(self):
        state = make_render_state()
        assert "turn" in state


# ============ render_event ============


class TestRenderEvent:
    """Tests for render_event."""

    def test_text_delta_appends_to_streaming_text(self):
        state = make_render_state()
        event = {
            "type": "message_update",
            "delta_type": "text_delta",
            "delta": {"content": "hello"},
        }
        result = render_event(event, state)
        html = render(result)
        assert 'id="streaming-text"' in html
        assert "beforeend" in html
        assert "hello" in html

    def test_text_delta_empty_returns_none(self):
        state = make_render_state()
        event = {
            "type": "message_update",
            "delta_type": "text_delta",
            "delta": {"content": ""},
        }
        result = render_event(event, state)
        assert result is None

    def test_thinking_delta_creates_container_lazily(self):
        state = make_render_state()
        state["thinking_created"] = False
        event = {
            "type": "message_update",
            "delta_type": "thinking_delta",
            "delta": {"reasoning_content": "Let me think..."},
        }
        result = render_event(event, state)
        html = render(result)
        assert 'id="chat-container"' in html
        assert "Let me think..." in html
        assert state["thinking_created"] is True

    def test_thinking_delta_subsequent_appends(self):
        state = make_render_state()
        state["thinking_created"] = True
        turn = state["turn"]
        event = {
            "type": "message_update",
            "delta_type": "thinking_delta",
            "delta": {"reasoning_content": "more thinking"},
        }
        result = render_event(event, state)
        html = render(result)
        assert f'id="thinking-{turn}"' in html
        assert "beforeend" in html
        assert "more thinking" in html

    def test_message_end_final_renders_chat_message_and_clears_streaming(self):
        state = make_render_state()
        event = {
            "type": "message_end",
            "message": {
                "role": "assistant",
                "content": "Final answer",
                "stop_reason": "end_turn",
                "usage": {"total_tokens": 100},
            },
        }
        result = render_event(event, state)
        html = render(result)
        assert "Assistant" in html
        assert "Final answer" in html
        # Should clear streaming-text
        assert 'id="streaming-text"' in html
        assert "innerHTML" in html

    def test_message_end_accumulates_tokens_from_usage(self):
        state = make_render_state(initial_tokens=200)
        event = {
            "type": "message_end",
            "message": {
                "role": "assistant",
                "content": "Done",
                "stop_reason": "end_turn",
                "usage": {"total_tokens": 150},
            },
        }
        render_event(event, state)
        assert state["total_tokens"] == 350

    def test_message_end_tool_calls_clears_streaming(self):
        state = make_render_state()
        event = {
            "type": "message_end",
            "message": {
                "role": "assistant",
                "content": "",
                "stop_reason": "tool_calls",
                "usage": {"total_tokens": 50},
            },
        }
        result = render_event(event, state)
        html = render(result)
        assert 'id="streaming-text"' in html
        assert "innerHTML" in html

    def test_tool_execution_start_renders_tool_block_no_streaming(self):
        state = make_render_state()
        event = {
            "type": "tool_execution_start",
            "tool_call_id": "tc_100",
            "tool_name": "run_code",
            "args": {"code": "print(1)"},
        }
        result = render_event(event, state)
        html = render(result)
        assert "run_code" in html
        assert 'id="chat-container"' in html
        assert "beforeend" in html

    def test_tool_execution_start_replaces_streamed_block(self):
        state = make_render_state()
        state["current_tc_id"] = "tc_200"
        state["streamed_tc_ids"] = {"tc_200"}
        event = {
            "type": "tool_execution_start",
            "tool_call_id": "tc_200",
            "tool_name": "run_code",
            "args": {"code": "x = 1"},
        }
        result = render_event(event, state)
        html = render(result)
        assert "run_code" in html
        assert "Running..." in html
        assert 'hx-swap-oob="outerHTML"' in html
        assert 'id="tc-block-tc_200"' in html

    def test_tool_execution_end_renders_result(self):
        state = make_render_state()
        event = {
            "type": "tool_execution_end",
            "tool_call_id": "tc_300",
            "result": {"content": [{"type": "text", "text": "output here"}]},
        }
        result = render_event(event, state)
        html = render(result)
        assert "output here" in html
        assert 'id="chat-container"' in html

    def test_tool_execution_end_clears_spinner(self):
        state = make_render_state()
        event = {
            "type": "tool_execution_end",
            "tool_call_id": "tc_400",
            "result": {"content": []},
        }
        result = render_event(event, state)
        html = render(result)
        assert 'id="tool-status-tc_400"' in html
        assert "hx-swap-oob" in html

    def test_agent_end_hides_stop_button(self):
        state = make_render_state()
        event = {"type": "agent_end"}
        result = render_event(event, state)
        html = render(result)
        assert 'id="stop-btn"' in html
        assert "hidden" in html

    def test_agent_end_clears_streaming_text(self):
        state = make_render_state()
        event = {"type": "agent_end"}
        result = render_event(event, state)
        html = render(result)
        assert 'id="streaming-text"' in html
        assert "innerHTML" in html

    def test_returns_none_for_unhandled_events(self):
        state = make_render_state()
        event = {"type": "some_unknown_event"}
        result = render_event(event, state)
        assert result is None

    def test_returns_none_for_empty_event(self):
        state = make_render_state()
        result = render_event({}, state)
        assert result is None

    def test_tool_call_delta_first_creates_block(self):
        state = make_render_state()
        event = {
            "type": "message_update",
            "delta_type": "tool_call_delta",
            "delta": {
                "tool_calls": [
                    {
                        "id": "tc_500",
                        "function": {"name": "search", "arguments": ""},
                    }
                ]
            },
        }
        result = render_event(event, state)
        html = render(result)
        assert "search" in html
        assert 'id="tc-block-tc_500"' in html
        assert state["current_tc_id"] == "tc_500"

    def test_tool_call_delta_subsequent_appends_args(self):
        state = make_render_state()
        state["current_tc_id"] = "tc_600"
        event = {
            "type": "message_update",
            "delta_type": "tool_call_delta",
            "delta": {
                "tool_calls": [
                    {
                        "id": "",
                        "function": {"name": "", "arguments": '{"query":'},
                    }
                ]
            },
        }
        result = render_event(event, state)
        html = render(result)
        assert 'id="tc-args-tc_600"' in html
        assert "beforeend" in html
        assert '{"query":' in html

    def test_message_start_increments_turn_counter(self):
        state = make_render_state()
        initial_turn = state["turn"]
        event = {
            "type": "message_start",
            "message": {"role": "assistant"},
        }
        render_event(event, state)
        assert state["turn"] > initial_turn
        assert state.get("thinking_created") is False


# ============ render_history ============


class TestRenderHistory:
    """Tests for render_history — renders agent message history on page load."""

    def test_empty_messages_returns_empty_list(self):
        assert render_history([]) == []

    def test_user_message_string_content(self):
        messages = [{"role": "user", "content": "Hello"}]
        parts = render_history(messages)
        assert len(parts) == 1
        html = render(parts[0])
        assert "You" in html
        assert "Hello" in html

    def test_user_message_list_content(self):
        """User messages with multimodal content blocks should extract text."""
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe this"},
                    {"type": "image_url", "image_url": {"url": "data:image/png;base64,ABC"}},
                ],
            }
        ]
        parts = render_history(messages)
        assert len(parts) == 1
        html = render(parts[0])
        assert "Describe this" in html

    def test_assistant_message_with_text(self):
        messages = [{"role": "assistant", "content": "Here is your answer"}]
        parts = render_history(messages)
        assert len(parts) == 1
        html = render(parts[0])
        assert "Assistant" in html
        assert "Here is your answer" in html

    def test_assistant_message_with_reasoning(self):
        messages = [{"role": "assistant", "content": "Answer", "reasoning_content": "Let me think about this"}]
        parts = render_history(messages)
        assert len(parts) == 2  # thinking + response
        thinking_html = render(parts[0])
        assert "Let me think about this" in thinking_html
        assert "opacity-40" in thinking_html
        response_html = render(parts[1])
        assert "Answer" in response_html

    def test_assistant_message_with_tool_calls(self):
        messages = [
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [{"id": "tc_1", "function": {"name": "run_code", "arguments": '{"code": "print(1)"}'}}],
            }
        ]
        parts = render_history(messages)
        assert len(parts) == 1
        html = render(parts[0])
        assert "run_code" in html
        assert "tc_1" in html

    def test_assistant_message_with_text_and_tool_calls(self):
        """Assistant message with both text content and tool calls renders both."""
        messages = [
            {
                "role": "assistant",
                "content": "Let me run that",
                "tool_calls": [{"id": "tc_1", "function": {"name": "run_code", "arguments": '{"code": "x=1"}'}}],
            }
        ]
        parts = render_history(messages)
        assert len(parts) == 2  # text + tool call
        assert "Let me run that" in render(parts[0])
        assert "run_code" in render(parts[1])

    def test_tool_result_with_text(self):
        messages = [
            {
                "role": "tool",
                "tool_call_id": "tc_1",
                "name": "run_code",
                "content": [{"type": "text", "text": "stdout:\n42"}],
                "is_error": False,
            }
        ]
        parts = render_history(messages)
        assert len(parts) == 1
        html = render(parts[0])
        assert "42" in html

    def test_tool_result_with_error(self):
        messages = [
            {
                "role": "tool",
                "tool_call_id": "tc_1",
                "name": "run_code",
                "content": [{"type": "text", "text": "NameError: x not defined"}],
                "is_error": True,
            }
        ]
        parts = render_history(messages)
        html = render(parts[0])
        assert "text-error" in html

    def test_tool_result_with_image(self):
        messages = [
            {
                "role": "tool",
                "tool_call_id": "tc_1",
                "name": "run_code",
                "content": [{"type": "image_url", "image_url": "data:image/png;base64,ABC123"}],
                "is_error": False,
            }
        ]
        parts = render_history(messages)
        assert len(parts) == 1
        html = render(parts[0])
        assert "<img" in html
        assert "ABC123" in html
        assert "modal" in html

    def test_tool_result_with_image_dict_format(self):
        """Tool results in stored messages may have image_url as a dict with url key."""
        messages = [
            {
                "role": "tool",
                "tool_call_id": "tc_1",
                "name": "run_code",
                "content": [{"type": "image_url", "image_url": {"url": "data:image/png;base64,XYZ"}}],
                "is_error": False,
            }
        ]
        parts = render_history(messages)
        html = render(parts[0])
        assert "<img" in html
        assert "XYZ" in html

    def test_tool_result_with_plotly(self):
        messages = [
            {
                "role": "tool",
                "tool_call_id": "tc_1",
                "name": "run_code",
                "content": [{"type": "text", "text": "(no output)"}],
                "details": {"plotly_htmls": ["<div>my chart</div>"]},
                "is_error": False,
            }
        ]
        parts = render_history(messages)
        assert len(parts) == 1
        html = render(parts[0])
        assert "<iframe" in html
        assert "my chart" in html

    def test_tool_result_no_output_skipped(self):
        """Tool results with only '(no output)' text should not render."""
        messages = [
            {
                "role": "tool",
                "tool_call_id": "tc_1",
                "name": "run_code",
                "content": [{"type": "text", "text": "(no output)"}],
                "is_error": False,
            }
        ]
        parts = render_history(messages)
        assert len(parts) == 0

    def test_full_conversation(self):
        """A realistic multi-turn conversation with tool use renders all parts."""
        messages = [
            {"role": "user", "content": "Plot a sine wave"},
            {
                "role": "assistant",
                "content": None,
                "reasoning_content": "I need to use matplotlib",
                "tool_calls": [{"id": "tc_1", "function": {"name": "run_code", "arguments": '{"code": "import matplotlib"}'}}],
            },
            {
                "role": "tool",
                "tool_call_id": "tc_1",
                "name": "run_code",
                "content": [
                    {"type": "text", "text": "stdout:\nok"},
                    {"type": "image_url", "image_url": "data:image/png;base64,PLOT"},
                ],
                "is_error": False,
            },
            {"role": "assistant", "content": "Here is your sine wave plot!"},
        ]
        parts = render_history(messages)
        # user + thinking + tool_call + tool_result + assistant
        assert len(parts) == 5
        full_html = "".join(render(p) for p in parts)
        assert "Plot a sine wave" in full_html
        assert "matplotlib" in full_html
        assert "run_code" in full_html
        assert "PLOT" in full_html
        assert "sine wave plot" in full_html
