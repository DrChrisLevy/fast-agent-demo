"""Tests for agents/tools.py — liteagent-based architecture."""

import asyncio
from unittest.mock import MagicMock, patch

from liteagent import Tool, ToolResult

import agents.tools as tools_module
from agents.tools import (
    get_agent,
    get_sandbox,
    init_sandbox,
    make_run_code_tool,
    reset_agent,
    reset_sandbox,
)

# Test user ID
TEST_USER_ID = "test-user-123"


class TestSandboxManagement:
    """Tests for sandbox lifecycle management."""

    def setup_method(self):
        """Reset sandbox state before each test."""
        tools_module.user_sandboxes.clear()

    def teardown_method(self):
        """Clean up sandbox state after each test."""
        tools_module.user_sandboxes.clear()

    @patch("agents.tools.ModalSandbox")
    def test_get_sandbox_creates_new_sandbox(self, mock_sandbox_class):
        """get_sandbox should create a new sandbox when none exists."""
        mock_instance = MagicMock()
        mock_sandbox_class.return_value = mock_instance

        result = get_sandbox(TEST_USER_ID)

        mock_sandbox_class.assert_called_once()
        assert result is mock_instance

    @patch("agents.tools.ModalSandbox")
    def test_get_sandbox_returns_existing_sandbox(self, mock_sandbox_class):
        """get_sandbox should return existing sandbox if already created."""
        mock_instance = MagicMock()
        mock_sandbox_class.return_value = mock_instance

        first_call = get_sandbox(TEST_USER_ID)
        second_call = get_sandbox(TEST_USER_ID)

        # Should only create once
        mock_sandbox_class.assert_called_once()
        assert first_call is second_call

    @patch("agents.tools.ModalSandbox")
    def test_get_sandbox_creates_separate_sandboxes_per_user(self, mock_sandbox_class):
        """get_sandbox should create different sandboxes for different users."""
        sandbox_a = MagicMock()
        sandbox_b = MagicMock()
        mock_sandbox_class.side_effect = [sandbox_a, sandbox_b]

        result_a = get_sandbox("user-a")
        result_b = get_sandbox("user-b")

        assert result_a is sandbox_a
        assert result_b is sandbox_b
        assert mock_sandbox_class.call_count == 2

    @patch("agents.tools.ModalSandbox")
    def test_reset_sandbox_terminates_and_clears(self, mock_sandbox_class):
        """reset_sandbox should terminate existing sandbox and clear reference."""
        mock_instance = MagicMock()
        mock_sandbox_class.return_value = mock_instance

        get_sandbox(TEST_USER_ID)
        assert TEST_USER_ID in tools_module.user_sandboxes

        reset_sandbox(TEST_USER_ID)

        mock_instance.terminate.assert_called_once()
        assert TEST_USER_ID not in tools_module.user_sandboxes

    def test_reset_sandbox_when_none_exists(self):
        """reset_sandbox should handle case when no sandbox exists."""
        assert TEST_USER_ID not in tools_module.user_sandboxes
        reset_sandbox(TEST_USER_ID)  # Should not raise
        assert TEST_USER_ID not in tools_module.user_sandboxes

    @patch("agents.tools.ModalSandbox")
    def test_reset_sandbox_ignores_termination_errors(self, mock_sandbox_class):
        """reset_sandbox should ignore errors during termination."""
        mock_instance = MagicMock()
        mock_instance.terminate.side_effect = Exception("Termination failed")
        mock_sandbox_class.return_value = mock_instance

        get_sandbox(TEST_USER_ID)
        reset_sandbox(TEST_USER_ID)  # Should not raise despite termination error

        assert TEST_USER_ID not in tools_module.user_sandboxes

    @patch("agents.tools.ModalSandbox")
    def test_init_sandbox_creates_new_sandbox(self, mock_sandbox_class):
        """init_sandbox should create a new sandbox for a user."""
        mock_instance = MagicMock()
        mock_sandbox_class.return_value = mock_instance

        asyncio.run(init_sandbox(TEST_USER_ID))

        mock_sandbox_class.assert_called_once()
        assert TEST_USER_ID in tools_module.user_sandboxes

    @patch("agents.tools.ModalSandbox")
    def test_init_sandbox_terminates_existing_sandbox(self, mock_sandbox_class):
        """init_sandbox should terminate existing sandbox before creating new one."""
        old_instance = MagicMock()
        new_instance = MagicMock()
        mock_sandbox_class.side_effect = [old_instance, new_instance]

        # Create an existing sandbox first
        get_sandbox(TEST_USER_ID)

        # Now init should terminate old and create new
        asyncio.run(init_sandbox(TEST_USER_ID))

        old_instance.terminate.assert_called_once()
        assert tools_module.user_sandboxes[TEST_USER_ID] is new_instance

    @patch("agents.tools.ModalSandbox")
    def test_init_sandbox_ignores_termination_errors(self, mock_sandbox_class):
        """init_sandbox should ignore errors during termination of existing sandbox."""
        old_instance = MagicMock()
        old_instance.terminate.side_effect = Exception("Termination failed")
        new_instance = MagicMock()
        mock_sandbox_class.side_effect = [old_instance, new_instance]

        # Create an existing sandbox first
        get_sandbox(TEST_USER_ID)

        # Should not raise despite termination error
        asyncio.run(init_sandbox(TEST_USER_ID))

        assert tools_module.user_sandboxes[TEST_USER_ID] is new_instance


class TestMakeRunCodeTool:
    """Tests for the make_run_code_tool factory."""

    def setup_method(self):
        tools_module.user_sandboxes.clear()

    def teardown_method(self):
        tools_module.user_sandboxes.clear()

    def test_returns_tool_instance(self):
        """make_run_code_tool should return a liteagent Tool."""
        tool = make_run_code_tool(TEST_USER_ID)
        assert isinstance(tool, Tool)

    def test_tool_has_correct_name(self):
        """Tool should be named 'run_code'."""
        tool = make_run_code_tool(TEST_USER_ID)
        assert tool.name == "run_code"

    def test_tool_has_correct_parameters_schema(self):
        """Tool should have a parameters schema with 'code' as a required string."""
        tool = make_run_code_tool(TEST_USER_ID)
        params = tool.parameters
        assert params["type"] == "object"
        assert "code" in params["properties"]
        assert params["properties"]["code"]["type"] == "string"
        assert "code" in params["required"]

    def test_tool_has_description(self):
        """Tool should have a description."""
        tool = make_run_code_tool(TEST_USER_ID)
        assert tool.description
        assert "code" in tool.description.lower() or "sandbox" in tool.description.lower()

    @patch("agents.tools.ModalSandbox")
    def test_execute_calls_sandbox_run_code(self, mock_sandbox_class):
        """Tool execute should call sandbox.run_code with the provided code."""
        mock_instance = MagicMock()
        mock_instance.run_code.return_value = {"stdout": "42\n", "stderr": "", "images": []}
        mock_sandbox_class.return_value = mock_instance

        tool = make_run_code_tool(TEST_USER_ID)

        result = asyncio.run(tool.execute("call-1", {"code": "print(42)"}))

        mock_instance.run_code.assert_called_once_with("print(42)")
        assert isinstance(result, ToolResult)

    @patch("agents.tools.ModalSandbox")
    def test_execute_returns_stdout_content(self, mock_sandbox_class):
        """Tool execute should return stdout in content text block."""
        mock_instance = MagicMock()
        mock_instance.run_code.return_value = {"stdout": "Hello\n", "stderr": "", "images": []}
        mock_sandbox_class.return_value = mock_instance

        tool = make_run_code_tool(TEST_USER_ID)
        result = asyncio.run(tool.execute("call-1", {"code": "print('Hello')"}))

        assert isinstance(result, ToolResult)
        assert len(result.content) >= 1
        assert result.content[0]["type"] == "text"
        assert "stdout:\nHello\n" in result.content[0]["text"]

    @patch("agents.tools.ModalSandbox")
    def test_execute_returns_stderr_content(self, mock_sandbox_class):
        """Tool execute should include stderr in text content."""
        mock_instance = MagicMock()
        mock_instance.run_code.return_value = {"stdout": "", "stderr": "Error occurred\n", "images": []}
        mock_sandbox_class.return_value = mock_instance

        tool = make_run_code_tool(TEST_USER_ID)
        result = asyncio.run(tool.execute("call-1", {"code": "bad code"}))

        text = result.content[0]["text"]
        assert "stderr:\nError occurred\n" in text

    @patch("agents.tools.ModalSandbox")
    def test_execute_returns_no_output_when_empty(self, mock_sandbox_class):
        """Tool execute should return '(no output)' when stdout and stderr are empty."""
        mock_instance = MagicMock()
        mock_instance.run_code.return_value = {"stdout": "", "stderr": "", "images": []}
        mock_sandbox_class.return_value = mock_instance

        tool = make_run_code_tool(TEST_USER_ID)
        result = asyncio.run(tool.execute("call-1", {"code": "x = 1"}))

        assert result.content[0]["text"] == "(no output)"

    @patch("agents.tools.ModalSandbox")
    def test_execute_handles_png_images(self, mock_sandbox_class):
        """Tool execute should detect PNG images and return image_url blocks."""
        mock_instance = MagicMock()
        mock_instance.run_code.return_value = {
            "stdout": "Plot created\n",
            "stderr": "",
            "images": ["iVBORbase64img1", "iVBORbase64img2"],
        }
        mock_sandbox_class.return_value = mock_instance

        tool = make_run_code_tool(TEST_USER_ID)
        result = asyncio.run(tool.execute("call-1", {"code": "plot()"}))

        assert len(result.content) == 3  # 1 text + 2 images
        assert result.content[1]["type"] == "image_url"
        assert result.content[1]["image_url"] == "data:image/png;base64,iVBORbase64img1"
        assert result.content[2]["type"] == "image_url"
        assert result.content[2]["image_url"] == "data:image/png;base64,iVBORbase64img2"

    @patch("agents.tools.ModalSandbox")
    def test_execute_handles_jpeg_images(self, mock_sandbox_class):
        """Tool execute should detect JPEG images (non-PNG prefix) and use image/jpeg."""
        mock_instance = MagicMock()
        mock_instance.run_code.return_value = {
            "stdout": "",
            "stderr": "",
            "images": ["/9j/base64img"],
        }
        mock_sandbox_class.return_value = mock_instance

        tool = make_run_code_tool(TEST_USER_ID)
        result = asyncio.run(tool.execute("call-1", {"code": "plot()"}))

        assert result.content[1]["type"] == "image_url"
        assert result.content[1]["image_url"] == "data:image/jpeg;base64,/9j/base64img"

    @patch("agents.tools.ModalSandbox")
    def test_execute_handles_plotly_htmls_in_details(self, mock_sandbox_class):
        """Tool execute should put plotly_htmls in details (not content)."""
        mock_instance = MagicMock()
        mock_instance.run_code.return_value = {
            "stdout": "",
            "stderr": "",
            "images": [],
            "plotly_htmls": ["<div>chart1</div>", "<div>chart2</div>"],
        }
        mock_sandbox_class.return_value = mock_instance

        tool = make_run_code_tool(TEST_USER_ID)
        result = asyncio.run(tool.execute("call-1", {"code": "plotly_fig()"}))

        # Content should only have text (no plotly blocks)
        assert len(result.content) == 1
        assert result.content[0]["type"] == "text"

        # Plotly should be in details
        assert result.details is not None
        assert "plotly_htmls" in result.details
        assert len(result.details["plotly_htmls"]) == 2
        assert result.details["plotly_htmls"][0] == "<div>chart1</div>"

    @patch("agents.tools.ModalSandbox")
    def test_execute_no_details_when_no_plotly(self, mock_sandbox_class):
        """Tool execute should return None details when there are no plotly_htmls."""
        mock_instance = MagicMock()
        mock_instance.run_code.return_value = {"stdout": "ok\n", "stderr": "", "images": []}
        mock_sandbox_class.return_value = mock_instance

        tool = make_run_code_tool(TEST_USER_ID)
        result = asyncio.run(tool.execute("call-1", {"code": "print('ok')"}))

        assert result.details is None

    @patch("agents.tools.ModalSandbox")
    def test_execute_mixed_images_and_plotly(self, mock_sandbox_class):
        """Tool execute should handle images in content and plotly in details."""
        mock_instance = MagicMock()
        mock_instance.run_code.return_value = {
            "stdout": "Mixed output\n",
            "stderr": "",
            "images": ["/9j/base64img"],
            "plotly_htmls": ["<div>plotly</div>"],
        }
        mock_sandbox_class.return_value = mock_instance

        tool = make_run_code_tool(TEST_USER_ID)
        result = asyncio.run(tool.execute("call-1", {"code": "create_both()"}))

        # Content: 1 text + 1 image
        assert len(result.content) == 2
        assert result.content[0]["type"] == "text"
        assert result.content[1]["type"] == "image_url"
        assert "image/jpeg" in result.content[1]["image_url"]

        # Details: plotly
        assert result.details["plotly_htmls"] == ["<div>plotly</div>"]


class TestAgentManagement:
    """Tests for per-user Agent management."""

    def setup_method(self):
        tools_module.user_agents.clear()
        tools_module.user_sandboxes.clear()
        tools_module.user_token_totals.clear()

    def teardown_method(self):
        tools_module.user_agents.clear()
        tools_module.user_sandboxes.clear()
        tools_module.user_token_totals.clear()

    @patch("agents.tools.Agent")
    @patch("agents.tools.build_system_prompt", return_value="system prompt")
    def test_get_agent_creates_new_agent(self, mock_prompt, mock_agent_class):
        """get_agent should create a new Agent when none exists."""
        mock_agent_instance = MagicMock()
        mock_agent_class.return_value = mock_agent_instance

        result = get_agent(TEST_USER_ID)

        mock_agent_class.assert_called_once()
        assert result is mock_agent_instance

    @patch("agents.tools.Agent")
    @patch("agents.tools.build_system_prompt", return_value="system prompt")
    def test_get_agent_returns_existing_agent(self, mock_prompt, mock_agent_class):
        """get_agent should return existing Agent if already created."""
        mock_agent_instance = MagicMock()
        mock_agent_class.return_value = mock_agent_instance

        first = get_agent(TEST_USER_ID)
        second = get_agent(TEST_USER_ID)

        mock_agent_class.assert_called_once()
        assert first is second

    @patch("agents.tools.Agent")
    @patch("agents.tools.build_system_prompt", return_value="system prompt")
    def test_reset_agent_resets_and_removes(self, mock_prompt, mock_agent_class):
        """reset_agent should call agent.reset() and remove from cache."""
        mock_agent_instance = MagicMock()
        mock_agent_class.return_value = mock_agent_instance

        get_agent(TEST_USER_ID)
        assert TEST_USER_ID in tools_module.user_agents

        reset_agent(TEST_USER_ID)

        mock_agent_instance.reset.assert_called_once()
        assert TEST_USER_ID not in tools_module.user_agents

    @patch("agents.tools.Agent")
    @patch("agents.tools.build_system_prompt", return_value="system prompt")
    def test_reset_agent_clears_token_totals(self, mock_prompt, mock_agent_class):
        """reset_agent should also clear token totals for the user."""
        mock_agent_instance = MagicMock()
        mock_agent_class.return_value = mock_agent_instance

        get_agent(TEST_USER_ID)
        tools_module.user_token_totals[TEST_USER_ID] = 5000

        reset_agent(TEST_USER_ID)

        assert TEST_USER_ID not in tools_module.user_token_totals

    def test_reset_agent_when_none_exists(self):
        """reset_agent should handle case when no agent exists."""
        assert TEST_USER_ID not in tools_module.user_agents
        reset_agent(TEST_USER_ID)  # Should not raise
        assert TEST_USER_ID not in tools_module.user_agents
