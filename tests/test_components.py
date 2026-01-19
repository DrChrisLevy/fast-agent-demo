"""Tests for UI components."""

from fasthtml.common import to_xml
from agents.ui.components import (
    ChatMessage,
    TraceMessage,
    TraceView,
    ChatInput,
    ThinkingIndicator,
    TraceUpdate,
)


def render(component):
    """Helper to render a FastHTML component to string."""
    return to_xml(component)


class TestChatMessage:
    """Tests for ChatMessage component."""

    def test_user_message_has_chat_end(self):
        html = render(ChatMessage("user", "Hello"))
        assert "chat-end" in html
        assert "chat-bubble-primary" in html

    def test_assistant_message_has_chat_start(self):
        html = render(ChatMessage("assistant", "Hi there"))
        assert "chat-start" in html
        assert "chat-bubble-primary" not in html

    def test_renders_content(self):
        html = render(ChatMessage("user", "Test message"))
        assert "Test message" in html

    def test_shows_role_header(self):
        html = render(ChatMessage("user", "Hello"))
        assert "User" in html

    def test_has_unique_id(self):
        html = render(ChatMessage("user", "Hello"))
        assert 'id="msg-' in html


class TestTraceMessage:
    """Tests for TraceMessage component."""

    def test_system_message_badge(self):
        msg = {"role": "system", "content": "You are helpful"}
        html = render(TraceMessage(msg))
        assert "SYSTEM" in html
        assert "badge-warning" in html

    def test_user_message_badge(self):
        msg = {"role": "user", "content": "Hello"}
        html = render(TraceMessage(msg))
        assert "USER" in html
        assert "badge-primary" in html

    def test_assistant_message_badge(self):
        msg = {"role": "assistant", "content": "Hi"}
        html = render(TraceMessage(msg))
        assert "ASSISTANT" in html
        assert "badge-secondary" in html

    def test_tool_message_badge(self):
        msg = {"role": "tool", "tool_call_id": "123", "content": "result"}
        html = render(TraceMessage(msg))
        assert "TOOL" in html
        assert "badge-accent" in html
        assert "tool_call_id: 123" in html

    def test_tool_message_with_image_content_blocks(self):
        """Tool results with image content blocks should render images."""
        msg = {
            "role": "tool",
            "tool_call_id": "call_456",
            "content": [
                {"type": "text", "text": "Plot created"},
                {"type": "image_url", "image_url": "data:image/png;base64,ABC123"},
            ],
        }
        html = render(TraceMessage(msg))
        assert "TOOL" in html
        assert "Plot created" in html
        assert "<img" in html
        assert "data:image/png;base64,ABC123" in html

    def test_tool_message_with_text_only_content_blocks(self):
        """Tool results with only text content blocks should render text."""
        msg = {
            "role": "tool",
            "tool_call_id": "call_789",
            "content": [
                {"type": "text", "text": "stdout:\nHello World"},
            ],
        }
        html = render(TraceMessage(msg))
        assert "Hello World" in html
        assert "<img" not in html

    def test_tool_message_with_multiple_images(self):
        """Tool results with multiple images should render all of them."""
        msg = {
            "role": "tool",
            "tool_call_id": "call_multi",
            "content": [
                {"type": "text", "text": "Two plots"},
                {"type": "image_url", "image_url": "data:image/png;base64,IMG1"},
                {"type": "image_url", "image_url": "data:image/png;base64,IMG2"},
            ],
        }
        html = render(TraceMessage(msg))
        # Each image has a thumbnail and a modal image (2 images * 2 = 4 img tags)
        assert html.count("<img") == 4
        assert "IMG1" in html
        assert "IMG2" in html

    def test_assistant_with_tool_calls(self, sample_tool_call_message):
        html = render(TraceMessage(sample_tool_call_message))
        assert "run_code" in html
        assert "call_123" in html

    def test_unknown_role_uses_ghost_badge(self):
        msg = {"role": "custom", "content": "test"}
        html = render(TraceMessage(msg))
        assert "badge-ghost" in html


class TestTraceView:
    """Tests for TraceView component."""

    def test_empty_messages_shows_placeholder(self):
        html = render(TraceView([]))
        assert "No messages yet" in html

    def test_renders_all_messages(self, sample_messages):
        html = render(TraceView(sample_messages))
        assert "SYSTEM" in html
        assert "USER" in html
        assert "ASSISTANT" in html

    def test_none_messages_shows_placeholder(self):
        html = render(TraceView(None))
        assert "No messages yet" in html


class TestChatInput:
    """Tests for ChatInput component."""

    def test_has_textarea(self):
        html = render(ChatInput())
        assert "<textarea" in html
        assert 'name="message"' in html

    def test_has_send_button(self):
        html = render(ChatInput())
        assert "Send" in html
        assert "btn-primary" in html

    def test_has_htmx_attributes(self):
        html = render(ChatInput())
        assert 'hx-post="/chat"' in html

    def test_has_keyboard_shortcut_trigger(self):
        html = render(ChatInput())
        assert "metaKey" in html or "ctrlKey" in html


class TestThinkingIndicator:
    """Tests for ThinkingIndicator component."""

    def test_has_loading_spinner(self):
        html = render(ThinkingIndicator())
        assert "loading" in html

    def test_has_thinking_text(self):
        html = render(ThinkingIndicator())
        assert "thinking" in html.lower()


class TestTraceUpdate:
    """Tests for TraceUpdate component."""

    def test_has_oob_swap(self, sample_messages):
        html = render(TraceUpdate(sample_messages))
        assert 'hx-swap-oob="true"' in html

    def test_has_trace_container_id(self, sample_messages):
        html = render(TraceUpdate(sample_messages))
        assert 'id="trace-container"' in html
