"""Tests for web routes/endpoints."""

import importlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient


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
        # Add a message first
        web_app.MESSAGES.append({"role": "user", "content": "test"})
        assert len(web_app.MESSAGES) == 1

        # Loading index should clear messages
        client.get("/")
        assert len(web_app.MESSAGES) == 0

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
        web_app.MESSAGES.append({"role": "user", "content": "test"})
        client.post("/clear")
        assert len(web_app.MESSAGES) == 0

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
        client.get("/")  # Clear messages first
        client.post("/chat", data={"message": "Hello agent"})
        # Should have system prompt + user message
        assert len(web_app.MESSAGES) == 2
        assert web_app.MESSAGES[0]["role"] == "system"
        assert web_app.MESSAGES[1]["role"] == "user"
        assert web_app.MESSAGES[1]["content"] == "Hello agent"

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

    return mock_response


class TestAgentStreamRoute:
    """Tests for GET /agent-stream (SSE endpoint)"""

    def test_agent_stream_returns_event_stream(self, web_app, client):
        """Test SSE endpoint with mocked LLM."""
        web_app.MESSAGES.append({"role": "user", "content": "Hello"})

        with patch("agents.agent.litellm.completion") as mock_completion:
            mock_completion.return_value = _mock_llm_response("Hello! How can I help?")

            resp = client.get("/agent-stream")
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers.get("content-type", "")

    def test_agent_stream_includes_response_content(self, web_app, client):
        """Test that SSE stream includes the agent's response."""
        web_app.MESSAGES.append({"role": "user", "content": "Hi"})

        with patch("agents.agent.litellm.completion") as mock_completion:
            mock_completion.return_value = _mock_llm_response("Mocked agent response")

            resp = client.get("/agent-stream")
            assert "Mocked agent response" in resp.text

    def test_agent_stream_handles_tool_calls(self, web_app, client):
        """Test SSE with tool calls (mocked)."""
        web_app.MESSAGES.append({"role": "user", "content": "What's the weather?"})

        # First call returns tool call, second returns final response
        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_123"
        mock_tool_call.function.name = "get_weather"
        mock_tool_call.function.arguments = '{"city": "London"}'

        with patch("agents.agent.litellm.completion") as mock_completion:
            mock_completion.side_effect = [
                _mock_llm_response(content=None, tool_calls=[mock_tool_call]),
                _mock_llm_response("The weather in London is sunny!"),
            ]

            resp = client.get("/agent-stream")
            assert resp.status_code == 200
            assert "sunny" in resp.text


@pytest.mark.slow
class TestAgentStreamIntegration:
    """Integration tests that hit real LLM - skipped by default."""

    def test_real_agent_response(self, web_app, client):
        """Test the full agent flow with real LLM."""
        web_app.MESSAGES.append({"role": "user", "content": "What is 2+2? Reply with just the number."})

        resp = client.get("/agent-stream")
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")
        # The response should contain "4" somewhere
        assert "4" in resp.text
