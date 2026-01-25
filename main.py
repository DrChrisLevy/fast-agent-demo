# ruff: noqa: F403, F405
"""
Agent Chat Web App

A hackable interface for working with agents - see chat, tool calls, and traces.
"""

import asyncio
import uuid

from dotenv import load_dotenv
from fasthtml.common import *
from agents.agent import run_agent
from agents.tools import init_sandbox, get_messages, clear_messages, reset_sandbox
from agents.ui import (
    ChatMessage,
    ChatInput,
    TraceMessage,
    TraceView,
    TraceUpdate,
    ThinkingIndicator,
)
from agents.prompts import SYSTEM_PROMPT

load_dotenv(dotenv_path="plash.env")


# ============ App Setup ============


def before(req, sess):
    """Assign or retrieve user_id from session, attach to request state."""
    if "user_id" not in sess:
        sess["user_id"] = str(uuid.uuid4())
    req.state.user_id = sess["user_id"]


beforeware = Beforeware(before, skip=[])

hdrs = (
    # Favicon
    Link(rel="icon", type="image/x-icon", href="/static/favicon.ico"),
    # DaisyUI + Tailwind
    Link(href="https://cdn.jsdelivr.net/npm/daisyui@5/daisyui.css", rel="stylesheet"),
    Link(href="https://cdn.jsdelivr.net/npm/daisyui@5/themes.css", rel="stylesheet"),
    Script(src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"),
    # HTMX SSE extension
    Script(src="https://unpkg.com/htmx-ext-sse@2.2.1/sse.js"),
    # Lock viewport
    Style("html, body { height: 100%; overflow: hidden; margin: 0; }"),
)
app, rt = fast_app(
    before=beforeware,
    pico=False,
    hdrs=hdrs,
    htmlkw={"data-theme": "cupcake"},
    secret_key=os.getenv("FAST_APP_SECRET"),
    max_age=365 * 24 * 3600,
)


# ============ Routes ============


@rt("/", methods=["GET"])
async def index(req):
    user_id = req.state.user_id
    # Clear messages on page load (refresh = clear)
    clear_messages(user_id)
    messages = get_messages(user_id)
    # Initialize sandbox in background (terminate old, create new)
    asyncio.create_task(init_sandbox(user_id))

    return Title("FastAgent"), Div(
        # Header - DaisyUI navbar
        Nav(
            Div(H1("Agent Chat", cls="text-xl font-bold"), cls="navbar-start"),
            Div(cls="navbar-center"),
            Div(
                Span("0 tokens", id="token-count", cls="text-sm opacity-70 mr-4"),
                Button(
                    "Clear",
                    hx_post="/clear",
                    hx_target="#chat-container",
                    hx_swap="innerHTML",
                    cls="btn btn-ghost btn-sm",
                ),
                cls="navbar-end items-center",
            ),
            cls="navbar bg-base-100 border-b border-base-300",
        ),
        # Main split layout
        Div(
            # LEFT SIDE - Chat interface
            Div(
                Div(
                    id="chat-container",
                    cls="flex flex-col gap-2 p-4 overflow-y-auto flex-1 min-h-0",
                ),
                # Response streaming area
                Div(id="response-area", cls="px-4"),
                # Input area
                Div(
                    ChatInput(),
                    cls="p-4 border-t border-base-300",
                ),
                cls="flex flex-col min-h-0 border-r border-base-300 bg-base-200",
            ),
            # RIGHT SIDE - Message trace view
            Div(
                Div(
                    Span(
                        "MESSAGE TRACE",
                        cls="font-bold text-xs tracking-wider opacity-70",
                    ),
                    cls="p-3 border-b border-base-300 bg-base-100 sticky top-0",
                ),
                Div(
                    TraceView(messages),
                    id="trace-container",
                    cls="overflow-y-auto flex-1 min-h-0",
                ),
                cls="flex flex-col min-h-0 bg-base-100",
            ),
            cls="grid grid-cols-2 flex-1 min-h-0",
        ),
        cls="h-screen flex flex-col overflow-hidden bg-base-200",
    )


@rt("/clear", methods=["POST"])
async def clear_chat(req):
    user_id = req.state.user_id
    clear_messages(user_id)
    reset_sandbox(user_id)
    # Initialize sandbox in background (terminate old, create new)
    asyncio.create_task(init_sandbox(user_id))
    return (
        "",  # Clear chat container
        Div(
            TraceView([]),
            id="trace-container",
            hx_swap_oob="true",
            cls="overflow-y-auto flex-1 min-h-0",
        ),  # Clear trace
        TokenCountUpdate(0),  # Reset token counter
    )


@rt("/chat", methods=["POST"])
def send_message(req, message: str):
    user_id = req.state.user_id
    messages = get_messages(user_id)
    if not message.strip():
        return ""

    # Ensure system prompt exists (so trace shows it before agent runs)
    if not messages or messages[0].get("role") != "system":
        messages.insert(0, {"role": "system", "content": SYSTEM_PROMPT})

    # Add user message to history
    messages.append({"role": "user", "content": message})

    # Return user message + SSE container + trace update (shows system + user)
    return (
        Div(ChatMessage("user", message), id="chat-container", hx_swap_oob="beforeend"),
        Div(
            ThinkingIndicator(),
            Div(id="agent-events"),
            hx_ext="sse",
            sse_connect="/agent-stream",
            sse_swap="AgentEvent",
            sse_close="close",
            hx_target="#agent-events",
            hx_swap="innerHTML",
            id="response-area",
            hx_swap_oob="true",
        ),
        TraceUpdate(messages),
    )


def is_usage_update(msg):
    """Check if message is a usage update."""
    return isinstance(msg, dict) and msg.get("type") == "usage"


def is_final_response(msg):
    """Check if message is the final assistant response (no tool calls)."""
    role = msg.get("role") if isinstance(msg, dict) else getattr(msg, "role", None)
    tool_calls = msg.get("tool_calls") if isinstance(msg, dict) else getattr(msg, "tool_calls", None)
    return role == "assistant" and not tool_calls


def is_tool_result(msg):
    """Check if message is a tool result."""
    return isinstance(msg, dict) and msg.get("role") == "tool"


def get_images_from_tool_result(msg):
    """Extract image URLs from a tool result message."""
    content = msg.get("content", "")
    if not isinstance(content, list):
        return []
    return [block.get("image_url") for block in content if block.get("type") == "image_url"]


def ChatImages(images):
    """Render images in the chat area with DaisyUI modal for expansion."""
    if not images:
        return None

    image_elements = []
    for img_url in images:
        modal_id = f"chat-img-modal-{hash(img_url) % 100000}"
        image_elements.append(
            Div(
                Img(
                    src=img_url,
                    cls="max-w-md rounded-lg shadow-md cursor-pointer hover:opacity-90",
                    onclick=f"document.getElementById('{modal_id}').showModal()",
                ),
                Dialog(
                    Div(
                        Img(src=img_url, cls="max-h-[80vh] max-w-full object-contain"),
                        cls="modal-box w-fit max-w-[90vw] p-4 bg-base-300",
                    ),
                    Form(Button("", cls="cursor-default"), method="dialog", cls="modal-backdrop bg-neutral/80"),
                    id=modal_id,
                    cls="modal modal-middle",
                ),
            )
        )

    return Div(
        Div(*image_elements, cls="flex flex-wrap gap-3"),
        cls="chat chat-start",
    )


def TokenCountUpdate(total_tokens):
    """OOB update for the token count display."""
    return Span(
        f"{total_tokens:,} tokens",
        id="token-count",
        cls="text-sm opacity-70 mr-4",
        hx_swap_oob="true",
    )


def TraceAppend(msg):
    """Append a message to trace with auto-scroll to bottom."""
    scroll_js = "let c = document.getElementById('trace-container'); c.scrollTop = c.scrollHeight;"
    return Div(
        Div(TraceMessage(msg), **{"hx-on::load": scroll_js}),
        id="trace-container",
        hx_swap_oob="beforeend",
    )


@rt("/agent-stream", methods=["GET"])
async def agent_stream(req):
    """SSE endpoint that streams agent messages."""
    user_id = req.state.user_id
    messages = get_messages(user_id)

    async def event_stream():
        for msg in run_agent(messages, user_id):
            if is_usage_update(msg):
                # Usage update: update token count
                yield sse_message(TokenCountUpdate(msg["total"]), event="AgentEvent")
                await asyncio.sleep(0.01)
            elif is_final_response(msg):
                # Final response: append to chat, clear thinking indicator, append to trace
                content = msg.get("content") if isinstance(msg, dict) else msg.content
                yield sse_message(
                    Div(
                        Div(
                            ChatMessage("assistant", content),
                            id="chat-container",
                            hx_swap_oob="beforeend",
                        ),
                        Div(id="response-area", hx_swap_oob="true"),
                        TraceAppend(msg),
                    ),
                    event="AgentEvent",
                )
                await asyncio.sleep(0.01)
                yield sse_message(Div(), event="close")
            else:
                # Intermediate (tool calls or tool results): append to trace
                # Also show images in chat if this is a tool result with images
                if is_tool_result(msg):
                    images = get_images_from_tool_result(msg)
                    if images:
                        yield sse_message(
                            Div(
                                Div(
                                    ChatImages(images),
                                    id="chat-container",
                                    hx_swap_oob="beforeend",
                                ),
                                TraceAppend(msg),
                            ),
                            event="AgentEvent",
                        )
                        await asyncio.sleep(0.01)
                        continue
                yield sse_message(TraceAppend(msg), event="AgentEvent")
                await asyncio.sleep(0.01)

    return EventStream(event_stream())


serve()
