# ruff: noqa: F403, F405

import json
from dotenv import load_dotenv
from fasthtml.common import *
from agents.agent import run_agent
from components import render_md

load_dotenv()

# Global in-memory message history (reset on refresh/clear)
MESSAGES = []

beforeware = Beforeware(
    lambda req, sess: None,
    skip=[],
)

hdrs = (
    # DaisyUI + Tailwind
    Link(href="https://cdn.jsdelivr.net/npm/daisyui@5/daisyui.css", rel="stylesheet"),
    Link(href="https://cdn.jsdelivr.net/npm/daisyui@5/themes.css", rel="stylesheet"),
    Script(src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"),
    # HTMX SSE extension
    Script(src="https://unpkg.com/htmx-ext-sse@2.2.1/sse.js"),
)
app, rt = fast_app(
    before=beforeware,
    pico=False,
    hdrs=hdrs,
    htmlkw={"data-theme": "corporate"},
    secret_key=os.getenv("FAST_APP_SECRET"),
    max_age=365 * 24 * 3600,
)


# ============ UI Components ============


def ChatMessage(role: str, content: str):
    """Render a chat message bubble."""
    is_user = role == "user"
    # Render markdown for assistant responses, plain text for user
    rendered = content if is_user else render_md(content)
    return Div(
        Div(
            Div(role.capitalize(), cls="chat-header opacity-70 text-xs"),
            Div(rendered, cls=f"chat-bubble {'chat-bubble-primary' if is_user else ''}"),
            cls=f"chat {'chat-end' if is_user else 'chat-start'}",
        ),
        id=f"msg-{hash(content) % 10000}",
    )


def ToolCall(name: str, args: dict):
    """Render a tool call indicator."""
    return Div(
        Div(
            Span("🔧", cls="mr-2"),
            Span("Calling ", cls="opacity-70"),
            Code(name, cls="font-bold text-primary"),
            Span("(", cls="opacity-70"),
            Code(json.dumps(args), cls="text-xs"),
            Span(")", cls="opacity-70"),
            cls="flex items-center",
        ),
        cls="alert alert-info py-2 my-1 text-sm",
    )


def ToolResult(name: str, result: str):
    """Render a tool result."""
    return Div(
        Div(
            Span("✓", cls="mr-2 text-success"),
            Code(name, cls="font-bold"),
            Span(" → ", cls="opacity-70"),
            Span(result, cls="font-mono text-xs"),
            cls="flex items-center flex-wrap",
        ),
        cls="alert py-2 my-1 text-sm bg-base-200",
    )


def ChatInput():
    """The chat input form."""
    return Form(
        Div(
            Input(
                type="text",
                name="message",
                placeholder="Ask something...",
                cls="input input-bordered flex-1",
                autofocus=True,
            ),
            Button("Send", cls="btn btn-primary", type="submit"),
            cls="flex gap-2",
        ),
        hx_post="/chat",
        hx_swap="none",  # We use OOB swaps instead
        hx_on__after_request="this.reset();",
        cls="w-full",
    )


def ThinkingIndicator():
    """Loading indicator shown while agent is thinking."""
    return Div(
        Span(cls="loading loading-dots loading-sm"),
        Span("Agent is thinking...", cls="ml-2 text-sm opacity-70"),
        cls="flex items-center py-2",
        id="thinking",
    )


# ============ Routes ============


@rt("/")
def index():
    global MESSAGES
    # Clear messages on page load (refresh = clear)
    MESSAGES = []

    # No history to render on fresh load
    chat_history = []

    return Div(
        # Header
        Div(
            H1("Agent Chat", cls="text-2xl font-bold"),
            Button(
                "Clear",
                hx_post="/clear",
                hx_target="#chat-container",
                hx_swap="innerHTML",
                cls="btn btn-ghost btn-sm",
            ),
            cls="navbar bg-base-100 border-b border-base-300",
        ),
        # Chat container
        Div(
            Div(
                *chat_history,
                id="chat-container",
                cls="flex flex-col gap-2 p-4 overflow-y-auto flex-1",
            ),
            # Response streaming area
            Div(id="response-area", cls="px-4"),
            # Input area
            Div(
                ChatInput(),
                cls="p-4 border-t border-base-300",
            ),
            cls="flex flex-col h-[calc(100vh-64px)]",
        ),
        cls="min-h-screen bg-base-200",
    )


@rt("/clear")
def post():
    global MESSAGES
    MESSAGES = []
    return ""


@rt("/chat")
def post(message: str):
    global MESSAGES
    if not message.strip():
        return ""

    # Add user message to history
    MESSAGES.append({"role": "user", "content": message})

    # Return user message to chat + SSE container to response-area
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
    )


@rt("/agent-stream")
async def get():
    """SSE endpoint that streams agent events."""
    from asyncio import sleep

    async def event_stream():
        tool_events_html = ""

        # Pass MESSAGES directly - run_agent will mutate it with tool calls/results
        for event in run_agent(MESSAGES):
            if event["type"] == "tool_call":
                tc = ToolCall(event["data"]["name"], event["data"]["args"])
                tool_events_html += to_xml(tc)
                content = Div(
                    NotStr(tool_events_html),
                    Div(
                        Span(cls="loading loading-dots loading-sm"),
                        Span(f"Running {event['data']['name']}...", cls="ml-2 text-sm opacity-70"),
                        cls="flex items-center py-2",
                    ),
                )
                yield sse_message(content, event="AgentEvent")
                await sleep(0.01)

            elif event["type"] == "tool_result":
                tr = ToolResult(event["data"]["name"], event["data"]["result"])
                tool_events_html += to_xml(tr)
                content = Div(
                    NotStr(tool_events_html),
                    Div(
                        Span(cls="loading loading-dots loading-sm"),
                        Span("Agent is thinking...", cls="ml-2 text-sm opacity-70"),
                        cls="flex items-center py-2",
                    ),
                )
                yield sse_message(content, event="AgentEvent")
                await sleep(0.01)

            elif event["type"] == "response":
                assistant_content = event["data"]["content"]
                # Note: run_agent already appended the assistant message to MESSAGES
                # Build the full trace: tool events + final response
                trace = Div(
                    NotStr(tool_events_html) if tool_events_html else "",
                    ChatMessage("assistant", assistant_content),
                    cls="border-l-2 border-primary pl-4 ml-2 my-2" if tool_events_html else "",
                )
                # Use OOB to append trace to chat-container and clear response-area
                final = Div(
                    Div(trace, id="chat-container", hx_swap_oob="beforeend"),
                    Div(id="response-area", hx_swap_oob="true"),
                )
                yield sse_message(final, event="AgentEvent")
                await sleep(0.01)
                yield sse_message(Div(), event="close")

    return EventStream(event_stream())


serve()
