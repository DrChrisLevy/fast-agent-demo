"""Tests for web routes/endpoints."""

import importlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient

import agents.tools as tools_module


@pytest.fixture
def mock_init_sandbox():
    """Mock init_sandbox to avoid creating real Modal sandboxes during tests."""
    return AsyncMock()


@pytest.fixture
def web_app(monkeypatch, mock_init_sandbox):
    """Create a fresh app instance for testing."""
    monkeypatch.setenv("FAST_APP_SECRET", "test-secret")
    monkeypatch.setattr("agents.tools.init_sandbox", mock_init_sandbox)

    import main as main_module

    importlib.reload(main_module)
    main_module._mock_init_sandbox = mock_init_sandbox  # Expose for assertions
    return main_module


@pytest.fixture
def client(web_app):
    """Create a test client."""
    # Clear all user data before each test
    tools_module.user_sandboxes.clear()
    tools_module.user_messages.clear()
    return TestClient(web_app.app)


class TestIndexRoute:
    """Tests for GET /"""

    def test_index_returns_200(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_index_has_title(self, client):
        resp = client.get("/")
        assert "Agent Chat" in resp.text

    def test_index_has_chat_container(self, client):
        resp = client.get("/")
        assert 'id="chat-container"' in resp.text

    def test_index_has_trace_container(self, client):
        resp = client.get("/")
        assert 'id="trace-container"' in resp.text

    def test_index_has_input_form(self, client):
        resp = client.get("/")
        assert 'name="message"' in resp.text

    def test_index_has_clear_button(self, client):
        resp = client.get("/")
        assert "Clear" in resp.text

    def test_index_clears_messages_on_load(self, web_app, client):
        # First request to establish session and get user_id
        client.get("/")
        # Get the user_id from the cache (there's only one user in tests)
        user_id = list(tools_module.user_messages.keys())[0]
        messages = tools_module.get_messages(user_id)

        # Add a message
        messages.append({"role": "user", "content": "test"})
        assert len(messages) == 1

        # Loading index should clear messages
        client.get("/")
        messages = tools_module.get_messages(user_id)
        assert len(messages) == 0

    def test_index_initializes_sandbox(self, web_app, client):
        web_app._mock_init_sandbox.reset_mock()
        client.get("/")
        web_app._mock_init_sandbox.assert_called_once()


class TestClearRoute:
    """Tests for POST /clear"""

    def test_clear_returns_200(self, client):
        resp = client.post("/clear")
        assert resp.status_code == 200

    def test_clear_empties_messages(self, web_app, client):
        # First request to establish session
        client.get("/")
        user_id = list(tools_module.user_messages.keys())[0]
        messages = tools_module.get_messages(user_id)

        messages.append({"role": "user", "content": "test"})
        client.post("/clear")
        messages = tools_module.get_messages(user_id)
        assert len(messages) == 0

    def test_clear_initializes_sandbox(self, web_app, client):
        web_app._mock_init_sandbox.reset_mock()
        client.post("/clear")
        web_app._mock_init_sandbox.assert_called_once()

    def test_clear_returns_empty_trace(self, client):
        resp = client.post("/clear")
        assert "No messages yet" in resp.text


class TestChatRoute:
    """Tests for POST /chat"""

    def test_empty_message_returns_empty(self, client):
        resp = client.post("/chat", data={"message": ""})
        assert resp.status_code == 200
        assert resp.text == ""

    def test_whitespace_message_returns_empty(self, client):
        resp = client.post("/chat", data={"message": "   "})
        assert resp.status_code == 200
        assert resp.text == ""

    def test_valid_message_adds_to_history(self, web_app, client):
        client.get("/")  # Clear messages first and establish session
        user_id = list(tools_module.user_messages.keys())[0]

        client.post("/chat", data={"message": "Hello agent"})
        messages = tools_module.get_messages(user_id)
        # Should have system prompt + user message
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Hello agent"

    def test_valid_message_returns_chat_bubble(self, client):
        client.get("/")  # Clear first
        resp = client.post("/chat", data={"message": "Hello"})
        assert "Hello" in resp.text
        assert "chat-bubble" in resp.text

    def test_valid_message_returns_sse_container(self, client):
        client.get("/")
        resp = client.post("/chat", data={"message": "Hello"})
        assert 'sse-connect="/agent-stream"' in resp.text

    def test_valid_message_returns_thinking_indicator(self, client):
        client.get("/")
        resp = client.post("/chat", data={"message": "Hello"})
        assert "thinking" in resp.text.lower()

    def test_valid_message_returns_trace_update(self, client):
        client.get("/")
        resp = client.post("/chat", data={"message": "Hello"})
        assert 'id="trace-container"' in resp.text
        assert 'hx-swap-oob="true"' in resp.text


def _mock_llm_response(content="This is a mock response.", tool_calls=None):
    """Create a mock litellm completion response."""
    mock_message = MagicMock()
    mock_message.content = content
    mock_message.tool_calls = tool_calls

    mock_choice = MagicMock()
    mock_choice.message = mock_message

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    # Mock usage with real integer for token count formatting
    mock_response.usage.total_tokens = 100

    return mock_response


class TestAgentStreamRoute:
    """Tests for GET /agent-stream (SSE endpoint)"""

    def test_agent_stream_returns_event_stream(self, web_app, client):
        """Test SSE endpoint with mocked LLM."""
        # Establish session first
        client.get("/")
        user_id = list(tools_module.user_messages.keys())[0]
        messages = tools_module.get_messages(user_id)
        messages.append({"role": "user", "content": "Hello"})

        with patch("agents.agent.litellm.completion") as mock_completion:
            mock_completion.return_value = _mock_llm_response("Hello! How can I help?")

            resp = client.get("/agent-stream")
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers.get("content-type", "")

    def test_agent_stream_includes_response_content(self, web_app, client):
        """Test that SSE stream includes the agent's response."""
        # Establish session first
        client.get("/")
        user_id = list(tools_module.user_messages.keys())[0]
        messages = tools_module.get_messages(user_id)
        messages.append({"role": "user", "content": "Hi"})

        with patch("agents.agent.litellm.completion") as mock_completion:
            mock_completion.return_value = _mock_llm_response("Mocked agent response")

            resp = client.get("/agent-stream")
            assert "Mocked agent response" in resp.text

    def test_agent_stream_handles_tool_calls(self, web_app, client):
        """Test SSE with tool calls (mocked)."""
        # Establish session first
        client.get("/")
        user_id = list(tools_module.user_messages.keys())[0]
        messages = tools_module.get_messages(user_id)
        messages.append({"role": "user", "content": "Run some code"})

        # First call returns tool call, second returns final response
        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_123"
        mock_tool_call.function.name = "run_code"
        mock_tool_call.function.arguments = '{"code": "print(42)"}'

        with patch("agents.agent.litellm.completion") as mock_completion:
            mock_completion.side_effect = [
                _mock_llm_response(content=None, tool_calls=[mock_tool_call]),
                _mock_llm_response("The result is 42!"),
            ]

            resp = client.get("/agent-stream")
            assert resp.status_code == 200
            assert "42" in resp.text


class TestImageHelpers:
    """Tests for image extraction and rendering helpers."""

    def test_get_images_from_tool_result_extracts_urls(self):
        """get_images_from_tool_result should extract image URLs from content blocks."""
        from agents.ui import get_images_from_tool_result

        msg = {
            "role": "tool",
            "content": [
                {"type": "text", "text": "Plot created"},
                {"type": "image_url", "image_url": "data:image/png;base64,ABC123"},
                {"type": "image_url", "image_url": "data:image/png;base64,DEF456"},
            ],
        }
        images = get_images_from_tool_result(msg)
        assert len(images) == 2
        assert "ABC123" in images[0]
        assert "DEF456" in images[1]

    def test_get_images_from_tool_result_returns_empty_for_string_content(self):
        """get_images_from_tool_result should return empty list for string content."""
        from agents.ui import get_images_from_tool_result

        msg = {"role": "tool", "content": "Just a string result"}
        images = get_images_from_tool_result(msg)
        assert images == []

    def test_get_images_from_tool_result_returns_empty_for_no_images(self):
        """get_images_from_tool_result should return empty list when no images in blocks."""
        from agents.ui import get_images_from_tool_result

        msg = {
            "role": "tool",
            "content": [{"type": "text", "text": "No images here"}],
        }
        images = get_images_from_tool_result(msg)
        assert images == []

    def test_chat_images_returns_none_for_empty(self):
        """ChatImages should return None for empty image list."""
        from agents.ui import ChatImages

        result = ChatImages([])
        assert result is None

    def test_chat_images_returns_none_for_none(self):
        """ChatImages should return None for None input."""
        from agents.ui import ChatImages

        result = ChatImages(None)
        assert result is None

    def test_chat_images_renders_images(self):
        """ChatImages should render img tags for provided URLs."""
        from fasthtml.common import to_xml
        from agents.ui import ChatImages

        result = ChatImages(["data:image/png;base64,IMG1", "data:image/png;base64,IMG2"])
        html = to_xml(result)
        # Each image has a thumbnail and a modal image (2 images * 2 = 4 img tags)
        assert html.count("<img") == 4
        assert "IMG1" in html
        assert "IMG2" in html
        assert "chat-start" in html


class TestPlotlyHelpers:
    """Tests for Plotly extraction and rendering helpers."""

    def test_get_plotly_htmls_from_tool_result_extracts_html(self):
        """get_plotly_htmls_from_tool_result should extract HTML from content blocks."""
        from agents.ui import get_plotly_htmls_from_tool_result

        msg = {
            "role": "tool",
            "content": [
                {"type": "text", "text": "(no output)"},
                {"type": "plotly_html", "html": "<div>chart1</div>"},
                {"type": "plotly_html", "html": "<div>chart2</div>"},
            ],
        }
        htmls = get_plotly_htmls_from_tool_result(msg)
        assert len(htmls) == 2
        assert "chart1" in htmls[0]
        assert "chart2" in htmls[1]

    def test_get_plotly_htmls_from_tool_result_returns_empty_for_string_content(self):
        """get_plotly_htmls_from_tool_result should return empty list for string content."""
        from agents.ui import get_plotly_htmls_from_tool_result

        msg = {"role": "tool", "content": "Just a string result"}
        htmls = get_plotly_htmls_from_tool_result(msg)
        assert htmls == []

    def test_get_plotly_htmls_from_tool_result_returns_empty_for_no_plotly(self):
        """get_plotly_htmls_from_tool_result should return empty list when no plotly in blocks."""
        from agents.ui import get_plotly_htmls_from_tool_result

        msg = {
            "role": "tool",
            "content": [{"type": "text", "text": "No plotly here"}],
        }
        htmls = get_plotly_htmls_from_tool_result(msg)
        assert htmls == []

    def test_chat_plotly_returns_none_for_empty(self):
        """ChatPlotly should return None for empty list."""
        from agents.ui import ChatPlotly

        result = ChatPlotly([])
        assert result is None

    def test_chat_plotly_returns_none_for_none(self):
        """ChatPlotly should return None for None input."""
        from agents.ui import ChatPlotly

        result = ChatPlotly(None)
        assert result is None

    def test_chat_plotly_renders_iframes(self):
        """ChatPlotly should render iframes for provided HTML."""
        from fasthtml.common import to_xml
        from agents.ui import ChatPlotly

        result = ChatPlotly(["<div>chart1</div>", "<div>chart2</div>"])
        html = to_xml(result)
        assert html.count("<iframe") == 2
        assert "chart1" in html
        assert "chart2" in html

    def test_chat_plotly_not_in_chat_bubble(self):
        """ChatPlotly should render full-width, not in chat bubble."""
        from fasthtml.common import to_xml
        from agents.ui import ChatPlotly

        result = ChatPlotly(["<div>chart</div>"])
        html = to_xml(result)
        # Should NOT have chat-start class (not in chat bubble)
        assert "chat-start" not in html
        assert "chat-end" not in html


@pytest.mark.slow
class TestAgentStreamIntegration:
    """Integration tests that hit real LLM - skipped by default."""

    def test_real_agent_response(self, web_app, client):
        """Test the full agent flow with real LLM."""
        # Establish session first
        client.get("/")
        user_id = list(tools_module.user_messages.keys())[0]
        messages = tools_module.get_messages(user_id)
        messages.append({"role": "user", "content": "What is 2+2? Reply with just the number."})

        resp = client.get("/agent-stream")
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")
        # The response should contain "4" somewhere
        assert "4" in resp.text
