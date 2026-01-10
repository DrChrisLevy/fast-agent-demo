# ruff: noqa: F403, F405

import json
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
        id="thinking",
    )


# ============ Routes ============


@rt("/")
def index():
    global MESSAGES
    # Clear messages on page load (refresh = clear)
    MESSAGES = []

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
        # Main split layout
        Div(
            # LEFT SIDE - Chat interface
            Div(
                Div(
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
                cls="flex flex-col h-full border-r border-base-300 bg-base-200",
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
                    cls="overflow-y-auto flex-1"
                ),
                cls="flex flex-col h-full bg-base-100",
            ),
            cls="grid grid-cols-2 h-[calc(100vh-64px)]",
        ),
        cls="min-h-screen bg-base-200",
    )


@rt("/clear")
def post():
    global MESSAGES
    MESSAGES = []
    return (
        "",  # Clear chat container
        Div(TraceView([]), id="trace-container", hx_swap_oob="true"),  # Clear trace
    )


@rt("/chat")
def post(message: str):
    global MESSAGES
    if not message.strip():
        return ""

    # Add user message to history
    MESSAGES.append({"role": "user", "content": message})

    # Return user message to chat + SSE container to response-area + update trace
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
        Div(TraceView(MESSAGES), id="trace-container", hx_swap_oob="true"),
    )


@rt("/agent-stream")
async def get():
    """SSE endpoint that streams agent events."""
    from asyncio import sleep

    async def event_stream():
        # Pass MESSAGES directly - run_agent will mutate it with tool calls/results
        for event in run_agent(MESSAGES):
            if event["type"] == "tool_call":
                # Left side: don't touch (initial ThinkingIndicator stays)
                # Right side: update trace with full details
                content = Div(
                    Div(TraceView(MESSAGES), id="trace-container", hx_swap_oob="true"),
                )
                yield sse_message(content, event="AgentEvent")
                await sleep(0.01)

            elif event["type"] == "tool_result":
                # Left side: don't touch
                # Right side: update trace
                content = Div(
                    Div(TraceView(MESSAGES), id="trace-container", hx_swap_oob="true"),
                )
                yield sse_message(content, event="AgentEvent")
                await sleep(0.01)

            elif event["type"] == "response":
                assistant_content = event["data"]["content"]
                # Left side: just the assistant message (clean chat UX)
                # Right side: full trace
                final = Div(
                    Div(ChatMessage("assistant", assistant_content), id="chat-container", hx_swap_oob="beforeend"),
                    Div(id="response-area", hx_swap_oob="true"),
                    Div(TraceView(MESSAGES), id="trace-container", hx_swap_oob="true"),
                )
                yield sse_message(final, event="AgentEvent")
                await sleep(0.01)
                yield sse_message(Div(), event="close")

    return EventStream(event_stream())


serve()
