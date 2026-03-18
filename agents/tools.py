"""
Tool definitions, per-user Agent management, and sandbox lifecycle.
"""

import asyncio
import threading

from cachetools import TTLCache
from liteagent import Agent, Tool, ToolResult

from agents.coding_sandbox import ModalSandbox
from agents.prompts import build_system_prompt

# Available models for the UI selector
MODELS = [
    {"id": "anthropic/claude-opus-4-6", "label": "Claude Opus 4.6"},
    {"id": "anthropic/claude-sonnet-4-6", "label": "Claude Sonnet 4.6"},
    {"id": "gemini/gemini-3-flash-preview", "label": "Gemini 3 Flash"},
    {"id": "gemini/gemini-3-pro-preview", "label": "Gemini 3 Pro"},
    {"id": "gemini/gemini-3.1-pro-preview", "label": "Gemini 3.1 Pro"},
]

DEFAULT_MODEL = MODELS[0]["id"]

# TTL caches for per-user isolation (30 min TTL matches Modal's idle timeout)
user_agents: TTLCache[str, Agent] = TTLCache(maxsize=1000, ttl=1800)
user_sandboxes: TTLCache[str, ModalSandbox] = TTLCache(maxsize=1000, ttl=1800)
user_token_totals: TTLCache[str, int] = TTLCache(maxsize=1000, ttl=1800)
_sandbox_lock = threading.Lock()

# Init script to download data/files or define functions etc..
INIT_SCRIPT = """"""


# ============ Sandbox Management ============


def get_sandbox(user_id: str) -> ModalSandbox:
    """Get or create the sandbox for a user."""
    with _sandbox_lock:
        if user_id not in user_sandboxes:
            user_sandboxes[user_id] = ModalSandbox(init_script=INIT_SCRIPT)
        return user_sandboxes[user_id]


def reset_sandbox(user_id: str) -> None:
    """Terminate and clear the sandbox for a specific user."""
    with _sandbox_lock:
        if user_id in user_sandboxes:
            try:
                user_sandboxes[user_id].terminate()
            except Exception:
                pass
            del user_sandboxes[user_id]


async def init_sandbox(user_id: str) -> None:
    """Initialize a fresh sandbox for a user (terminate existing one first)."""
    loop = asyncio.get_running_loop()

    def _init():
        with _sandbox_lock:
            if user_id in user_sandboxes:
                try:
                    user_sandboxes[user_id].terminate()
                except Exception:
                    pass
                del user_sandboxes[user_id]
            user_sandboxes[user_id] = ModalSandbox(init_script=INIT_SCRIPT)

    await loop.run_in_executor(None, _init)


# ============ Tool Factory ============


def make_run_code_tool(user_id: str) -> Tool:
    """Create a run_code Tool that executes in this user's Modal sandbox."""

    async def execute(tool_call_id, params, signal=None, on_update=None):
        loop = asyncio.get_running_loop()
        sandbox = get_sandbox(user_id)
        result = await loop.run_in_executor(None, sandbox.run_code, params["code"])

        # Build text content from stdout/stderr
        text_parts = []
        if result.get("stdout"):
            text_parts.append(f"stdout:\n{result['stdout']}")
        if result.get("stderr"):
            text_parts.append(f"stderr:\n{result['stderr']}")
        text_content = "\n\n".join(text_parts) if text_parts else "(no output)"

        content = [{"type": "text", "text": text_content}]
        for img_base64 in result.get("images", []):
            mime_type = "image/png" if img_base64.startswith("iVBOR") else "image/jpeg"
            content.append({"type": "image_url", "image_url": f"data:{mime_type};base64,{img_base64}"})

        # Plotly HTML in details (UI-only, not sent to LLM)
        details = {}
        plotly_htmls = result.get("plotly_htmls", [])
        if plotly_htmls:
            details["plotly_htmls"] = plotly_htmls

        return ToolResult(content=content, details=details if details else None)

    return Tool(
        name="run_code",
        description="Run any arbitrary python code in a secure and isolated sandbox environment",
        parameters={
            "type": "object",
            "properties": {"code": {"type": "string", "description": "Python code to run"}},
            "required": ["code"],
        },
        execute=execute,
    )


# ============ Per-User Agent Management ============


def get_agent(user_id: str) -> Agent:
    """Get or create the Agent for a user."""
    if user_id not in user_agents:
        agent = Agent(
            model=DEFAULT_MODEL,
            tools=[make_run_code_tool(user_id)],
            system_prompt=build_system_prompt(),
        )
        agent.set_thinking_level("high")
        user_agents[user_id] = agent
    return user_agents[user_id]


def reset_agent(user_id: str) -> None:
    """Reset and remove the Agent for a user."""
    if user_id in user_agents:
        agent = user_agents[user_id]
        agent.reset()
        del user_agents[user_id]
    user_token_totals.pop(user_id, None)
