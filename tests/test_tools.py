"""Tests for agents/tools.py."""

import json
from unittest.mock import MagicMock, patch

import agents.tools as tools_module
from agents.tools import (
    TOOL_FUNCTIONS,
    TOOLS,
    get_sandbox,
    get_weather,
    reset_sandbox,
    run_code,
)


class TestToolDefinitions:
    """Tests for tool definitions."""

    def test_tools_list_contains_expected_tools(self):
        """TOOLS list should contain get_weather and run_code."""
        tool_names = [t["function"]["name"] for t in TOOLS]
        assert "get_weather" in tool_names
        assert "run_code" in tool_names

    def test_tool_functions_mapping(self):
        """TOOL_FUNCTIONS should map names to implementations."""
        assert TOOL_FUNCTIONS["get_weather"] is get_weather
        assert TOOL_FUNCTIONS["run_code"] is run_code


class TestGetWeather:
    """Tests for get_weather function."""

    def test_get_weather_returns_weather_string(self):
        """get_weather should return formatted weather string."""
        result = get_weather("London")
        assert "London" in result
        assert "72°F" in result
        assert "sunny" in result

    def test_get_weather_with_different_cities(self):
        """get_weather should work with any city name."""
        for city in ["New York", "Tokyo", "Paris"]:
            result = get_weather(city)
            assert city in result


class TestSandboxManagement:
    """Tests for sandbox lifecycle management."""

    def setup_method(self):
        """Reset sandbox state before each test."""
        tools_module._sandbox = None

    def teardown_method(self):
        """Clean up sandbox state after each test."""
        tools_module._sandbox = None

    @patch("agents.tools.ModalSandbox")
    def test_get_sandbox_creates_new_sandbox(self, mock_sandbox_class):
        """get_sandbox should create a new sandbox when none exists."""
        mock_instance = MagicMock()
        mock_sandbox_class.return_value = mock_instance

        result = get_sandbox()

        mock_sandbox_class.assert_called_once()
        assert result is mock_instance

    @patch("agents.tools.ModalSandbox")
    def test_get_sandbox_returns_existing_sandbox(self, mock_sandbox_class):
        """get_sandbox should return existing sandbox if already created."""
        mock_instance = MagicMock()
        mock_sandbox_class.return_value = mock_instance

        first_call = get_sandbox()
        second_call = get_sandbox()

        # Should only create once
        mock_sandbox_class.assert_called_once()
        assert first_call is second_call

    @patch("agents.tools.ModalSandbox")
    def test_reset_sandbox_terminates_and_clears(self, mock_sandbox_class):
        """reset_sandbox should terminate existing sandbox and clear reference."""
        mock_instance = MagicMock()
        mock_sandbox_class.return_value = mock_instance

        # Create a sandbox
        get_sandbox()
        assert tools_module._sandbox is not None

        # Reset it
        reset_sandbox()

        mock_instance.terminate.assert_called_once()
        assert tools_module._sandbox is None

    def test_reset_sandbox_when_none_exists(self):
        """reset_sandbox should handle case when no sandbox exists."""
        assert tools_module._sandbox is None
        reset_sandbox()  # Should not raise
        assert tools_module._sandbox is None

    @patch("agents.tools.ModalSandbox")
    def test_reset_sandbox_ignores_termination_errors(self, mock_sandbox_class):
        """reset_sandbox should ignore errors during termination."""
        mock_instance = MagicMock()
        mock_instance.terminate.side_effect = Exception("Termination failed")
        mock_sandbox_class.return_value = mock_instance

        get_sandbox()
        reset_sandbox()  # Should not raise despite termination error

        assert tools_module._sandbox is None


class TestRunCode:
    """Tests for run_code function."""

    def setup_method(self):
        """Reset sandbox state before each test."""
        tools_module._sandbox = None

    def teardown_method(self):
        """Clean up sandbox state after each test."""
        tools_module._sandbox = None

    @patch("agents.tools.ModalSandbox")
    def test_run_code_returns_json_result(self, mock_sandbox_class):
        """run_code should return JSON-encoded sandbox output."""
        mock_instance = MagicMock()
        mock_instance.run_code.return_value = {"stdout": "Hello\n", "stderr": ""}
        mock_sandbox_class.return_value = mock_instance

        result = run_code('print("Hello")')

        assert json.loads(result) == {"stdout": "Hello\n", "stderr": ""}
        mock_instance.run_code.assert_called_once_with('print("Hello")')

    @patch("agents.tools.ModalSandbox")
    def test_run_code_handles_sandbox_exception(self, mock_sandbox_class):
        """run_code should return error JSON when sandbox raises exception."""
        mock_sandbox_class.side_effect = Exception("Sandbox creation failed")

        result = run_code("print('test')")

        parsed = json.loads(result)
        assert parsed["stdout"] == ""
        assert "Sandbox creation failed" in parsed["stderr"]

    @patch("agents.tools.ModalSandbox")
    def test_run_code_handles_execution_exception(self, mock_sandbox_class):
        """run_code should return error JSON when code execution raises exception."""
        mock_instance = MagicMock()
        mock_instance.run_code.side_effect = Exception("Execution error")
        mock_sandbox_class.return_value = mock_instance

        result = run_code("invalid code")

        parsed = json.loads(result)
        assert parsed["stdout"] == ""
        assert "Execution error" in parsed["stderr"]
