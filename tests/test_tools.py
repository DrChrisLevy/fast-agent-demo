"""Tests for agents/tools.py."""

from unittest.mock import MagicMock, patch

import agents.tools as tools_module
from agents.tools import (
    TOOL_FUNCTIONS,
    TOOLS,
    current_user_id,
    get_sandbox,
    reset_sandbox,
    run_code,
)

# Test user ID
TEST_USER_ID = "test-user-123"


class TestToolDefinitions:
    """Tests for tool definitions."""

    def test_tools_list_contains_expected_tools(self):
        """TOOLS list should contain run_code."""
        tool_names = [t["function"]["name"] for t in TOOLS]
        assert "run_code" in tool_names

    def test_tool_functions_mapping(self):
        """TOOL_FUNCTIONS should map names to implementations."""
        assert TOOL_FUNCTIONS["run_code"] is run_code


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
    def test_reset_sandbox_terminates_and_clears(self, mock_sandbox_class):
        """reset_sandbox should terminate existing sandbox and clear reference."""
        mock_instance = MagicMock()
        mock_sandbox_class.return_value = mock_instance

        # Create a sandbox
        get_sandbox(TEST_USER_ID)
        assert TEST_USER_ID in tools_module.user_sandboxes

        # Reset it
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


class TestRunCode:
    """Tests for run_code function."""

    def setup_method(self):
        """Reset sandbox state and set user context before each test."""
        tools_module.user_sandboxes.clear()
        current_user_id.set(TEST_USER_ID)

    def teardown_method(self):
        """Clean up sandbox state after each test."""
        tools_module.user_sandboxes.clear()

    @patch("agents.tools.ModalSandbox")
    def test_run_code_returns_content_blocks(self, mock_sandbox_class):
        """run_code should return content blocks with text."""
        mock_instance = MagicMock()
        mock_instance.run_code.return_value = {"stdout": "Hello\n", "stderr": "", "images": []}
        mock_sandbox_class.return_value = mock_instance

        result = run_code('print("Hello")')

        assert isinstance(result, list)
        assert result[0] == {"type": "text", "text": "stdout:\nHello\n"}
        mock_instance.run_code.assert_called_once_with('print("Hello")')

    @patch("agents.tools.ModalSandbox")
    def test_run_code_handles_sandbox_exception(self, mock_sandbox_class):
        """run_code should return error content blocks when sandbox raises exception."""
        mock_sandbox_class.side_effect = Exception("Sandbox creation failed")

        result = run_code("print('test')")

        assert isinstance(result, list)
        assert result[0]["type"] == "text"
        assert "Sandbox creation failed" in result[0]["text"]

    @patch("agents.tools.ModalSandbox")
    def test_run_code_handles_execution_exception(self, mock_sandbox_class):
        """run_code should return error content blocks when code execution raises exception."""
        mock_instance = MagicMock()
        mock_instance.run_code.side_effect = Exception("Execution error")
        mock_sandbox_class.return_value = mock_instance

        result = run_code("invalid code")

        assert isinstance(result, list)
        assert result[0]["type"] == "text"
        assert "Execution error" in result[0]["text"]

    @patch("agents.tools.ModalSandbox")
    def test_run_code_returns_images(self, mock_sandbox_class):
        """run_code should include image content blocks when images are present."""
        mock_instance = MagicMock()
        mock_instance.run_code.return_value = {
            "stdout": "Plot created\n",
            "stderr": "",
            "images": ["base64img1", "base64img2"],
        }
        mock_sandbox_class.return_value = mock_instance

        result = run_code("import matplotlib.pyplot as plt; plt.plot([1,2,3])")

        assert isinstance(result, list)
        assert len(result) == 3  # 1 text + 2 images
        assert result[0] == {"type": "text", "text": "stdout:\nPlot created\n"}
        assert result[1] == {"type": "image_url", "image_url": "data:image/png;base64,base64img1"}
        assert result[2] == {"type": "image_url", "image_url": "data:image/png;base64,base64img2"}
