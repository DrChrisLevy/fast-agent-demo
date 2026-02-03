"""
Tool definitions and implementations for the agent.
"""

import asyncio
import contextvars
import threading

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
        # Detect format from base64 magic bytes: PNG starts with iVBOR, JPEG with /9j/
        mime_type = "image/png" if img_base64.startswith("iVBOR") else "image/jpeg"
        content.append(
            {
                "type": "image_url",
                "image_url": f"data:{mime_type};base64,{img_base64}",
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
- **Image generation with Gemini** — Use Google's Gemini API for AI image generation. Convert the result to a PIL Image and assign to a variable—it will be auto-captured.
```python
from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO

client = genai.Client()

# Basic generation
response = client.models.generate_content(
    model="gemini-2.5-flash-image",
    contents="A cute robot painting a sunset",
    config=types.GenerateContentConfig(
        response_modalities=["TEXT", "IMAGE"],
        image_config=types.ImageConfig(aspect_ratio="16:9"),
    ),
)
for part in response.parts:
    if part.text:
        print(part.text)
    elif part.inline_data:
        generated_image = Image.open(BytesIO(part.inline_data.data))

# Edit an existing image (pass image + text prompt)
input_image = Image.open("photo.jpg")
response = client.models.generate_content(
    model="gemini-2.5-flash-image",
    contents=["Add a small wizard hat to this cat", input_image],
)
for part in response.parts:
    if part.inline_data:
        edited_image = Image.open(BytesIO(part.inline_data.data))

# Combine multiple images (Pro supports up to 14)
dress = Image.open("dress.jpg")
model_photo = Image.open("model.jpg")
response = client.models.generate_content(
    model="gemini-3-pro-image-preview",
    contents=["Put this dress on this person", dress, model_photo],
)
for part in response.parts:
    if part.inline_data:
        composite = Image.open(BytesIO(part.inline_data.data))

# High-resolution output (Pro model generates up to 4K)
# Resolution: "1K" (default), "2K", "4K" - MUST use uppercase 'K'
# Aspect ratios: "1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"
response = client.models.generate_content(
    model="gemini-3-pro-image-preview",
    contents="A stunning landscape photograph",
    config=types.GenerateContentConfig(
        response_modalities=["TEXT", "IMAGE"],
        image_config=types.ImageConfig(aspect_ratio="16:9", image_size="4K"),
    ),
)

# Pro model with grounded web search (creates images using real-time info)
chat = client.chats.create(
    model="gemini-3-pro-image-preview",
    config=types.GenerateContentConfig(
        response_modalities=["TEXT", "IMAGE"],
        image_config=types.ImageConfig(aspect_ratio="1:1", image_size="2K"),
        tools=[{"google_search": {}}],  # Enable grounded search
    ),
)
response = chat.send_message("Create an infographic about today's weather in NYC")
for part in response.parts:
    if part.inline_data:
        weather_image = Image.open(BytesIO(part.inline_data.data))

# Continue editing in same chat (multi-turn)
response = chat.send_message("Now translate it to Spanish")
for part in response.parts:
    if part.inline_data:
        spanish_image = Image.open(BytesIO(part.inline_data.data))
```
""",
}
