"""
Tool definitions and implementations for the agent.
"""

import asyncio
import contextvars
import threading

import modal
from cachetools import TTLCache

from agents.coding_sandbox import ModalSandbox

# TTL caches for per-user isolation (30 min TTL matches Modal's idle timeout)
# user_id -> ModalSandbox
user_sandboxes: TTLCache[str, ModalSandbox] = TTLCache(maxsize=1000, ttl=1800)
# user_id -> list of messages
user_messages: TTLCache[str, list] = TTLCache(maxsize=1000, ttl=1800)
# Lock for thread-safe sandbox operations
_sandbox_lock = threading.Lock()

# Context variable to pass user_id into tool execution
current_user_id: contextvars.ContextVar[str] = contextvars.ContextVar("current_user_id")

# Init script to download data/files or define functions etc..
INIT_SCRIPT = """"""


def get_sandbox(user_id: str | None = None) -> ModalSandbox:
    """Get or create the sandbox for a user."""
    if user_id is None:
        user_id = current_user_id.get()
    with _sandbox_lock:
        if user_id not in user_sandboxes:
            user_sandboxes[user_id] = ModalSandbox(init_script=INIT_SCRIPT)
        return user_sandboxes[user_id]


def reset_sandbox(user_id: str) -> None:
    """Terminate and clear the sandbox for a specific user (sync, no lock)."""
    with _sandbox_lock:
        if user_id in user_sandboxes:
            try:
                user_sandboxes[user_id].terminate()
            except Exception:
                pass
            del user_sandboxes[user_id]


def get_messages(user_id: str) -> list:
    """Get or create the message list for a user."""
    if user_id not in user_messages:
        user_messages[user_id] = []
    return user_messages[user_id]


def clear_messages(user_id: str) -> None:
    """Clear the message list for a user."""
    if user_id in user_messages:
        del user_messages[user_id]


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


async def init_sandbox(user_id: str) -> None:
    """Initialize a fresh sandbox for a user (terminate their existing one first)."""
    loop = asyncio.get_running_loop()

    def _init_user_sandbox():
        with _sandbox_lock:
            # Terminate user's existing sandbox if any
            if user_id in user_sandboxes:
                try:
                    user_sandboxes[user_id].terminate()
                except Exception:
                    pass
                del user_sandboxes[user_id]
            # Create new sandbox for user
            user_sandboxes[user_id] = ModalSandbox(init_script=INIT_SCRIPT)

    await loop.run_in_executor(None, _init_user_sandbox)


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
    """Run Python code in the Modal sandbox. Returns content blocks with text and optional images.

    Uses current_user_id context variable to determine which user's sandbox to use.
    """
    try:
        user_id = current_user_id.get()
        sandbox = get_sandbox(user_id)
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
    for html in result.get("plotly_htmls", []):
        content.append({"type": "plotly_html", "html": html})
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
- **Plots are auto-captured** — Just create matplotlib/seaborn/plotly figures normally. Don't call `plt.show()` or try to display/encode images manually. All open figures are automatically captured and returned after your code runs. Matplotlib figures become images; **Plotly figures become interactive HTML** (no need for kaleido or `to_image()`—just create the `fig` object and it will render interactively). For multi-part analyses, prefer multiple `plt.figure()` calls over dense subplots.
""",
}
