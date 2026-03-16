"""Tests for per-user agent management in agents.tools."""

from unittest.mock import patch

from liteagent import Agent, Tool

from agents.tools import (
    get_agent,
    reset_agent,
    make_run_code_tool,
    user_agents,
    user_token_totals,
)

# Test user IDs
USER_A = "test-user-a"
USER_B = "test-user-b"


def _clear_caches():
    """Clear all TTL caches so tests are isolated."""
    user_agents.clear()
    user_token_totals.clear()


class TestGetAgent:
    """Tests for get_agent — per-user Agent creation and caching."""

    def setup_method(self):
        _clear_caches()

    def teardown_method(self):
        _clear_caches()

    def test_creates_agent_with_correct_model(self):
        """get_agent should create an Agent with the expected model."""
        agent = get_agent(USER_A)
        assert isinstance(agent, Agent)
        assert "claude" in agent.state.model  # Model may change; just verify it's set

    def test_creates_agent_with_system_prompt(self):
        """get_agent should set a non-empty system prompt from build_system_prompt."""
        agent = get_agent(USER_A)
        assert agent.state.system_prompt
        assert len(agent.state.system_prompt) > 0

    def test_creates_agent_with_run_code_tool(self):
        """get_agent should attach a run_code tool."""
        agent = get_agent(USER_A)
        assert len(agent.state.tools) == 1
        assert agent.state.tools[0].name == "run_code"

    def test_sets_thinking_level(self):
        """get_agent should set a thinking level."""
        agent = get_agent(USER_A)
        assert agent.state.thinking_level in ("low", "medium", "high")

    def test_returns_same_agent_for_same_user(self):
        """get_agent should return the cached Agent for repeat calls with the same user."""
        agent1 = get_agent(USER_A)
        agent2 = get_agent(USER_A)
        assert agent1 is agent2

    def test_returns_different_agents_for_different_users(self):
        """get_agent should create separate Agents for different user IDs."""
        agent_a = get_agent(USER_A)
        agent_b = get_agent(USER_B)
        assert agent_a is not agent_b

    def test_stores_agent_in_cache(self):
        """get_agent should store the Agent in the user_agents TTL cache."""
        assert USER_A not in user_agents
        agent = get_agent(USER_A)
        assert USER_A in user_agents
        assert user_agents[USER_A] is agent


class TestResetAgent:
    """Tests for reset_agent — removing agents and clearing token totals."""

    def setup_method(self):
        _clear_caches()

    def teardown_method(self):
        _clear_caches()

    def test_removes_agent_from_cache(self):
        """reset_agent should remove the Agent from user_agents."""
        get_agent(USER_A)
        assert USER_A in user_agents
        reset_agent(USER_A)
        assert USER_A not in user_agents

    def test_clears_token_totals(self):
        """reset_agent should remove token totals for the user."""
        get_agent(USER_A)
        user_token_totals[USER_A] = 12345
        reset_agent(USER_A)
        assert USER_A not in user_token_totals

    def test_calls_agent_reset(self):
        """reset_agent should call agent.reset() before removing it."""
        agent = get_agent(USER_A)
        with patch.object(agent, "reset") as mock_reset:
            reset_agent(USER_A)
            mock_reset.assert_called_once()

    def test_safe_when_no_agent_exists(self):
        """reset_agent should not raise when called for a nonexistent user."""
        reset_agent("nonexistent-user")  # should not raise

    def test_safe_when_no_token_totals_exist(self):
        """reset_agent should not raise when there are no token totals to clear."""
        get_agent(USER_A)
        # No token totals set
        reset_agent(USER_A)  # should not raise
        assert USER_A not in user_token_totals

    def test_clears_token_totals_even_without_agent(self):
        """reset_agent should clear token totals even if no agent is cached."""
        user_token_totals[USER_A] = 9999
        reset_agent(USER_A)
        assert USER_A not in user_token_totals

    def test_does_not_affect_other_users(self):
        """reset_agent for one user should not affect another user's agent."""
        get_agent(USER_A)
        agent_b = get_agent(USER_B)
        user_token_totals[USER_A] = 100
        user_token_totals[USER_B] = 200

        reset_agent(USER_A)

        assert USER_A not in user_agents
        assert USER_B in user_agents
        assert user_agents[USER_B] is agent_b
        assert user_token_totals[USER_B] == 200


class TestMakeRunCodeTool:
    """Tests for make_run_code_tool — the tool factory."""

    def test_returns_tool_instance(self):
        """make_run_code_tool should return a liteagent Tool."""
        tool = make_run_code_tool(USER_A)
        assert isinstance(tool, Tool)

    def test_tool_name_is_run_code(self):
        """The tool should be named 'run_code'."""
        tool = make_run_code_tool(USER_A)
        assert tool.name == "run_code"

    def test_tool_has_description(self):
        """The tool should have a non-empty description."""
        tool = make_run_code_tool(USER_A)
        assert tool.description
        assert len(tool.description) > 0

    def test_tool_parameters_require_code(self):
        """The tool parameters should require a 'code' string."""
        tool = make_run_code_tool(USER_A)
        params = tool.parameters
        assert params["type"] == "object"
        assert "code" in params["properties"]
        assert params["properties"]["code"]["type"] == "string"
        assert "code" in params["required"]

    def test_tool_has_execute_callable(self):
        """The tool should have an execute function."""
        tool = make_run_code_tool(USER_A)
        assert callable(tool.execute)

    def test_different_users_get_independent_tools(self):
        """Tools for different users should be distinct instances."""
        tool_a = make_run_code_tool(USER_A)
        tool_b = make_run_code_tool(USER_B)
        assert tool_a is not tool_b
        # Both should have the same schema but different closures
        assert tool_a.name == tool_b.name
        assert tool_a.execute is not tool_b.execute
