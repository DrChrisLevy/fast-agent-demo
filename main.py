# ruff: noqa: F403, F405
"""
Agent Chat Web App

A hackable interface for working with agents - see chat, tool calls, and traces.
"""

from asyncio import sleep
from dotenv import load_dotenv
from fasthtml.common import *
from agents.agent import run_agent
from agents.tools import reset_sandbox
from agents.ui import (
    ChatMessage,
    ChatInput,
    TraceView,
    TraceUpdate,
    ThinkingIndicator,
)

load_dotenv()

# Global in-memory message history (reset on refresh/clear)
MESSAGES = []


# ============ App Setup ============


def before(req, sess):
    print(r"running beforeware")
    print(f"Request: {req.method} {req.url.path}")


beforeware = Beforeware(before, skip=[])

hdrs = (
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
def index():
    global MESSAGES
    # Clear messages on page load (refresh = clear)
    MESSAGES = []
    reset_sandbox()

    return Div(
        # Header - DaisyUI navbar
        Nav(
            Div(H1("Agent Chat", cls="text-xl font-bold"), cls="navbar-start"),
            Div(cls="navbar-center"),
            Div(
                Button(
                    "Clear",
                    hx_post="/clear",
                    hx_target="#chat-container",
                    hx_swap="innerHTML",
                    cls="btn btn-ghost btn-sm",
                ),
                cls="navbar-end",
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
            # NOTE: OOB swaps reset scroll position and HTMX scroll modifiers don't work with OOB.
            # This after-swap handler on the parent is the workaround to keep trace scrolled to bottom.
            Div(
                Div(
                    Span(
                        "MESSAGE TRACE",
                        cls="font-bold text-xs tracking-wider opacity-70",
                    ),
                    cls="p-3 border-b border-base-300 bg-base-100 sticky top-0",
                ),
                Div(
                    TraceView(MESSAGES),
                    id="trace-container",
                    cls="overflow-y-auto flex-1 min-h-0",
                ),
                cls="flex flex-col min-h-0 bg-base-100",
                **{
                    "hx-on:htmx:after-swap": "document.getElementById('trace-container').scrollTop = document.getElementById('trace-container').scrollHeight"
                },
            ),
            cls="grid grid-cols-2 flex-1 min-h-0",
        ),
        cls="h-screen flex flex-col overflow-hidden bg-base-200",
    )


@rt("/clear", methods=["POST"])
def clear_chat():
    global MESSAGES
    MESSAGES = []
    reset_sandbox()
    return (
        "",  # Clear chat container
        Div(
            TraceView([]),
            id="trace-container",
            hx_swap_oob="true",
            cls="overflow-y-auto flex-1 min-h-0",
        ),  # Clear trace
    )


@rt("/chat", methods=["POST"])
def send_message(message: str):
    global MESSAGES
    if not message.strip():
        return ""

    # Add user message to history
    MESSAGES.append({"role": "user", "content": message})

    # Return user message + SSE container + trace update
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
        TraceUpdate(MESSAGES),
    )


@rt("/agent-stream", methods=["GET"])
async def agent_stream():
    """SSE endpoint that streams agent events."""

    async def event_stream():
        for event in run_agent(MESSAGES):
            if event["type"] in ("tool_call", "tool_result"):
                # Just update the trace panel, keep thinking indicator on left
                yield sse_message(TraceUpdate(MESSAGES), event="AgentEvent")
                await sleep(0.01)

            elif event["type"] == "response":
                # Final response: add assistant message, clear response area, update trace
                yield sse_message(
                    Div(
                        Div(
                            ChatMessage("assistant", event["data"]["content"]),
                            id="chat-container",
                            hx_swap_oob="beforeend",
                        ),
                        Div(id="response-area", hx_swap_oob="true"),
                        TraceUpdate(MESSAGES),
                    ),
                    event="AgentEvent",
                )
                await sleep(0.01)
                yield sse_message(Div(), event="close")

    return EventStream(event_stream())


serve()
