"""
Tool definitions and implementations for the agent.
"""

import asyncio

from agents.coding_sandbox import ModalSandbox

# Lazy-initialized sandbox instance
_sandbox: ModalSandbox | None = None
_sandbox_lock = asyncio.Lock()

# Init script to download data/files or define functions etc..
INIT_SCRIPT = """"""


def get_sandbox() -> ModalSandbox:
    """Get or create the shared sandbox instance."""
    global _sandbox
    if _sandbox is None:
        _sandbox = ModalSandbox(init_script=INIT_SCRIPT)
    return _sandbox


def reset_sandbox() -> None:
    """Terminate and clear the sandbox (sync, no lock)."""
    global _sandbox
    if _sandbox is not None:
        try:
            _sandbox.terminate()
        except Exception:
            pass
        _sandbox = None


async def init_sandbox() -> None:
    """Initialize a fresh sandbox (terminate existing one first).

    Uses a lock to ensure only one sandbox exists at a time.
    """
    global _sandbox
    async with _sandbox_lock:
        # Terminate existing sandbox if any
        if _sandbox is not None:
            try:
                _sandbox.terminate()
            except Exception:
                pass
            _sandbox = None
        # Create new sandbox in executor to not block event loop
        loop = asyncio.get_running_loop()
        _sandbox = await loop.run_in_executor(None, lambda: ModalSandbox(init_script=INIT_SCRIPT))


# Define tools the agent can use
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a city",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string", "description": "The city name"}},
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_code",
            "description": "Run any arbitrary python code",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python code to run",
                    }
                },
                "required": ["code"],
            },
        },
    },
]


# Tool implementations
def get_weather(city: str) -> str:
    # Fake implementation
    return f"The weather in {city} is 72°F and sunny."


def run_code(code: str) -> list:
    """Run Python code in the Modal sandbox. Returns content blocks with text and optional images."""
    try:
        sandbox = get_sandbox()
        result = sandbox.run_code(code)
    except Exception as e:
        result = {"stdout": "", "stderr": str(e), "images": []}

    # Build text content from stdout/stderr
    text_parts = []
    if result.get("stdout"):
        text_parts.append(f"stdout:\n{result['stdout']}")
    if result.get("stderr"):
        text_parts.append(f"stderr:\n{result['stderr']}")
    text_content = "\n\n".join(text_parts) if text_parts else "(no output)"

    # Always return content blocks format (litellm format)
    content = [{"type": "text", "text": text_content}]
    for img_base64 in result.get("images", []):
        content.append(
            {
                "type": "image_url",
                "image_url": f"data:image/png;base64,{img_base64}",
            }
        )
    return content


# Map tool names to functions
TOOL_FUNCTIONS = {
    "get_weather": get_weather,
    "run_code": run_code,
}
