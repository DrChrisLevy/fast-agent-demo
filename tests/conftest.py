"""Shared test fixtures."""

import pytest


@pytest.fixture
def sample_messages():
    """Sample message history for testing."""
    return [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"},
        {"role": "assistant", "content": "Hi there! How can I help you today?"},
    ]


@pytest.fixture
def sample_tool_call_message():
    """Sample assistant message with tool calls."""
    return {
        "role": "assistant",
        "tool_calls": [
            {
                "id": "call_123",
                "function": {
                    "name": "run_code",
                    "arguments": '{"code": "print(42)"}',
                },
            }
        ],
    }


@pytest.fixture
def sample_tool_result_message():
    """Sample tool result message."""
    return {
        "role": "tool",
        "tool_call_id": "call_123",
        "content": "stdout:\n42",
    }
