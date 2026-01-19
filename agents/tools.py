"""
Tool definitions and implementations for the agent.
"""

import asyncio

import modal

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


def _terminate_all_sandboxes() -> None:
    """Terminate all existing sandboxes for the python-sandbox app."""
    try:
        app = modal.App.lookup("python-sandbox", create_if_missing=False)
        if app is None:
            return
        for sb in modal.Sandbox.list(app_id=app.app_id):
            if sb.poll() is None:  # Still running
                try:
                    sb.terminate()
                except Exception:
                    pass
    except modal.exception.NotFoundError:
        pass  # App doesn't exist yet
    except Exception:
        pass  # Ignore other errors during cleanup


async def init_sandbox() -> None:
    """Initialize a fresh sandbox (terminate all existing ones first).

    Uses a lock to ensure only one sandbox exists at a time.
    Terminates all sandboxes from previous app sessions, not just the current one.
    """
    global _sandbox
    async with _sandbox_lock:
        loop = asyncio.get_running_loop()
        # Terminate ALL existing sandboxes for this app (including from previous sessions)
        await loop.run_in_executor(None, _terminate_all_sandboxes)
        _sandbox = None
        # Create new sandbox in executor to not block event loop
        _sandbox = await loop.run_in_executor(None, lambda: ModalSandbox(init_script=INIT_SCRIPT))


# Define tools the agent can use
TOOLS = [
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
    "run_code": run_code,
}

# Tool instructions for the system prompt (used by prompts.py)
TOOL_INSTRUCTIONS = {
    "run_code": """\
Execute Python code in a secure Modal sandbox environment.

**Key capabilities:**
- **State persists between calls** — Variables, imports, and definitions carry over:
  ```
  # Call 1
  x = 2

  # Call 2
  y = 6
  print(x + y)  # Works! Prints 8
  ```
- **Install any package** — Use `os.system("pip install <package>")` or `subprocess`.
- **Fully isolated sandbox** — Run anything safely: shell commands, downloads, scripts. Nothing escapes.
- **Use `print()` for output** — stdout is captured and returned. Always print results you want to see.
- **Plots are auto-captured** — Just create matplotlib/seaborn figures normally. Don't call `plt.show()` or try to display/encode images manually. All open figures are automatically captured and returned as images after your code runs. For multi-part analyses, prefer multiple `plt.figure()` calls over dense subplots—each figure becomes a separate image.
""",
}
