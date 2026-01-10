# ruff: noqa: F403, F405

import json
from asyncio import sleep
from dotenv import load_dotenv
from fasthtml.common import *
from agents.agent import run_agent
from components import render_md

load_dotenv()

# Global in-memory message history (reset on refresh/clear)
MESSAGES = []

def before(req, sess):
    print(r'running beforeware')
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


# Custom renderers for specific tools (tool_name -> render function)
# Render function takes (name, args_dict) and returns an FT component
def render_run_code(name, args):
    """Custom renderer for run_code tool - shows code with syntax highlighting."""
    code = args.get("code", "")
    code_md = f"```python\n{code}\n```"
    return Div(
        Span(f"🔧 {name}", cls="font-mono text-primary font-bold"),
        Div(render_md(code_md), cls="mt-1"),
    )


TOOL_RENDERERS = {
    "run_code": render_run_code,
}


def render_tool_call(name, args_str, tc_id):
    """Render a tool call, using custom renderer if available."""
    try:
        args_dict = json.loads(args_str) if isinstance(args_str, str) else args_str
    except json.JSONDecodeError:
        args_dict = {}

    # Check for custom renderer
    if name in TOOL_RENDERERS:
        return Div(
            TOOL_RENDERERS[name](name, args_dict),
            Span(f"id: {tc_id}", cls="text-xs opacity-50"),
            cls="mb-2"
        )

    # Default rendering
    return Div(
        Span(f"🔧 {name}", cls="font-mono text-primary font-bold"),
        Pre(args_str, cls="text-xs bg-base-300 p-1 rounded mt-1 overflow-x-auto"),
        Span(f"id: {tc_id}", cls="text-xs opacity-50"),
        cls="mb-2"
    )


def TraceMessage(msg):
    """Render a single message in the trace view with full detail."""
    role = msg.get("role", "unknown")

    # Color coding by role
    role_colors = {
        "system": "badge-warning",
        "user": "badge-primary",
        "assistant": "badge-secondary",
        "tool": "badge-accent",
    }
    badge_cls = role_colors.get(role, "badge-ghost")

    # Handle different message types
    if role == "system":
        content = Pre(
            msg.get("content", ""),
            cls="text-xs whitespace-pre-wrap bg-base-300 p-2 rounded overflow-x-auto max-h-40 overflow-y-auto"
        )
    elif role == "user":
        content = Pre(
            msg.get("content", ""),
            cls="text-xs whitespace-pre-wrap bg-base-300 p-2 rounded"
        )
    elif role == "assistant":
        # Check if it has tool_calls (could be a ChatCompletionMessage object or dict)
        tool_calls = getattr(msg, "tool_calls", None) or msg.get("tool_calls")
        if tool_calls:
            # Assistant message with tool calls
            calls_display = []
            for tc in tool_calls:
                # Handle both object and dict formats
                if hasattr(tc, "function"):
                    name = tc.function.name
                    args = tc.function.arguments
                    tc_id = tc.id
                else:
                    name = tc.get("function", {}).get("name", "?")
                    args = tc.get("function", {}).get("arguments", "{}")
                    tc_id = tc.get("id", "?")

                calls_display.append(render_tool_call(name, args, tc_id))

            # Parallel calls: display side-by-side in a grid
            if len(calls_display) > 1:
                content = Div(
                    Span("⚡ parallel", cls="text-xs opacity-50 mb-1 block"),
                    Div(*calls_display, cls="grid grid-cols-2 gap-2"),
                )
            else:
                content = Div(*calls_display)
        else:
            # Regular assistant response
            content = Pre(
                msg.get("content", ""),
                cls="text-xs whitespace-pre-wrap bg-base-300 p-2 rounded"
            )
    elif role == "tool":
        tool_call_id = msg.get("tool_call_id", "?")
        content = Div(
            Span(f"tool_call_id: {tool_call_id}", cls="text-xs opacity-50 block mb-1"),
            Pre(
                msg.get("content", ""),
                cls="text-xs whitespace-pre-wrap bg-base-300 p-2 rounded max-h-32 overflow-y-auto"
            )
        )
    else:
        content = Pre(json.dumps(msg, indent=2, default=str), cls="text-xs bg-base-300 p-2 rounded")

    return Div(
        Div(
            Span(role.upper(), cls=f"badge {badge_cls} badge-sm"),
            cls="mb-1"
        ),
        content,
        cls="border-l-2 border-base-300 pl-3 py-2 mb-2"
    )


def TraceView(messages):
    """Render the full message trace."""
    if not messages:
        return Div(
            Span("No messages yet", cls="text-sm opacity-50"),
            cls="p-4"
        )

    return Div(
        *[TraceMessage(m) for m in messages],
        cls="p-4"
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
    )


def TraceUpdate():
    """OOB swap to update trace panel."""
    return Div(TraceView(MESSAGES), id="trace-container", hx_swap_oob="true", cls="overflow-y-auto flex-1 min-h-0")


# ============ Routes ============


@rt("/", methods=["GET"])
def index():
    global MESSAGES
    # Clear messages on page load (refresh = clear)
    MESSAGES = []

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
            Div(
                Div(
                    Span("MESSAGE TRACE", cls="font-bold text-xs tracking-wider opacity-70"),
                    cls="p-3 border-b border-base-300 bg-base-100 sticky top-0"
                ),
                Div(
                    TraceView(MESSAGES),
                    id="trace-container",
                    cls="overflow-y-auto flex-1 min-h-0"
                ),
                cls="flex flex-col min-h-0 bg-base-100",
            ),
            cls="grid grid-cols-2 flex-1 min-h-0",
        ),
        cls="h-screen flex flex-col overflow-hidden bg-base-200",
    )


@rt("/clear", methods=["POST"])
def clear_chat():
    global MESSAGES
    MESSAGES = []
    return (
        "",  # Clear chat container
        Div(TraceView([]), id="trace-container", hx_swap_oob="true", cls="overflow-y-auto flex-1 min-h-0"),  # Clear trace
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
        TraceUpdate(),
    )


@rt("/agent-stream", methods=["GET"])
async def agent_stream():
    """SSE endpoint that streams agent events."""

    async def event_stream():
        for event in run_agent(MESSAGES):
            if event["type"] in ("tool_call", "tool_result"):
                # Just update the trace panel, keep thinking indicator on left
                yield sse_message(TraceUpdate(), event="AgentEvent")
                await sleep(0.01)

            elif event["type"] == "response":
                # Final response: add assistant message, clear response area, update trace
                yield sse_message(
                    Div(
                        Div(ChatMessage("assistant", event["data"]["content"]), id="chat-container", hx_swap_oob="beforeend"),
                        Div(id="response-area", hx_swap_oob="true"),
                        TraceUpdate(),
                    ),
                    event="AgentEvent",
                )
                await sleep(0.01)
                yield sse_message(Div(), event="close")

    return EventStream(event_stream())


serve()
