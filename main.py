# ruff: noqa: F403, F405
"""
Agent Chat Web App — powered by liteagent.

Single-stream interface with real-time token streaming, inline tool execution,
and steering/abort controls.
"""

import asyncio
import uuid

from dotenv import load_dotenv
from fasthtml.common import *
from agents.tools import get_agent, reset_agent, reset_sandbox, init_sandbox, user_token_totals
from agents.ui.components import ChatMessage, ChatInput, TokenCountUpdate, render_event, make_render_state, render_history

load_dotenv(dotenv_path="plash.env")


# ============ App Setup ============

# Pending prompts: POST /chat stores the message, GET /agent-stream picks it up
pending_prompts: dict[str, str] = {}


def before(req, sess):
    """Assign or retrieve user_id from session, attach to request state."""
    if "user_id" not in sess:
        sess["user_id"] = str(uuid.uuid4())
    req.state.user_id = sess["user_id"]


beforeware = Beforeware(before, skip=[])

hdrs = (
    Link(rel="icon", type="image/x-icon", href="/static/favicon.ico"),
    Link(href="https://cdn.jsdelivr.net/npm/daisyui@5/daisyui.css", rel="stylesheet"),
    Link(href="https://cdn.jsdelivr.net/npm/daisyui@5/themes.css", rel="stylesheet"),
    Script(src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"),
    Script(src="https://unpkg.com/htmx-ext-sse@2.2.1/sse.js"),
    Style("html, body { height: 100%; overflow: hidden; margin: 0; }"),
    Script("""
    (function() {
        var pinned = true;
        var sc;
        document.addEventListener('DOMContentLoaded', () => {
            sc = document.getElementById('scroll-container');
            if (!sc) return;
            sc.addEventListener('scroll', () => {
                pinned = sc.scrollHeight - sc.scrollTop - sc.clientHeight < 150;
            });
        });
        document.addEventListener('htmx:oobAfterSwap', () => {
            if (!pinned || !sc) return;
            requestAnimationFrame(() => { sc.scrollTop = sc.scrollHeight; });
        });
    })();
    """),
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
    agent = get_agent(user_id)
    total_tokens = user_token_totals.get(user_id, 0)
    history = render_history(agent.state.messages)

    return Title("Agent Chat"), Div(
        # Header
        Nav(
            Div(H1("Agent Chat", cls="text-xl font-bold"), cls="navbar-start"),
            Div(cls="navbar-center"),
            Div(
                Span(f"{total_tokens:,} tokens", id="token-count", cls="text-sm opacity-70 mr-4"),
                Button(
                    "Stop",
                    id="stop-btn",
                    hx_post="/stop",
                    cls="btn btn-ghost btn-sm hidden",
                ),
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
        # Single stream view
        Div(
            Div(*history, id="chat-container", cls="flex flex-col gap-2 max-w-3xl mx-auto w-full"),
            Div(
                Pre(id="streaming-text", cls="whitespace-pre-wrap font-sans text-base leading-relaxed m-0 px-0"),
                id="streaming-area",
                cls="max-w-3xl mx-auto w-full",
            ),
            cls="flex-1 overflow-y-auto p-4",
            id="scroll-container",
        ),
        # Input area (pinned to bottom)
        Div(
            Div(ChatInput(), cls="max-w-3xl mx-auto w-full"),
            cls="p-4 border-t border-base-300 bg-base-200",
        ),
        cls="h-screen flex flex-col overflow-hidden bg-base-200",
    )


@rt("/chat", methods=["POST"])
def send_message(req, message: str):
    user_id = req.state.user_id
    if not message.strip():
        return ""

    agent = get_agent(user_id)

    if agent.state.is_streaming:
        # Agent is running — steer it
        agent.steer(message)
        return Div(
            ChatMessage("user", f"[steer] {message}"),
            id="chat-container",
            hx_swap_oob="beforeend",
        )

    # Normal prompt — store and trigger SSE
    pending_prompts[user_id] = message
    return (
        # Append user message to chat
        Div(ChatMessage("user", message), id="chat-container", hx_swap_oob="beforeend"),
        # SSE streaming container — outerHTML so SSE attributes land in DOM
        Div(
            Pre(id="streaming-text", cls="whitespace-pre-wrap font-sans text-base leading-relaxed m-0 px-0"),
            hx_ext="sse",
            sse_connect="/agent-stream",
            sse_swap="AgentEvent",
            sse_close="close",
            hx_swap="none",
            id="streaming-area",
            hx_swap_oob="outerHTML",
            cls="max-w-3xl mx-auto w-full",
        ),
        # Show stop button
        Button("Stop", id="stop-btn", hx_post="/stop", cls="btn btn-error btn-sm", hx_swap_oob="true"),
    )


@rt("/agent-stream", methods=["GET"])
async def agent_stream(req):
    """SSE endpoint — bridges liteagent events to HTMX."""
    user_id = req.state.user_id
    message = pending_prompts.pop(user_id, None)
    if not message:
        return ""

    agent = get_agent(user_id)
    queue = asyncio.Queue()
    unsub = agent.subscribe(lambda e: queue.put_nowait(e))

    # Start agent in background
    asyncio.create_task(agent.prompt(message))

    async def event_stream():
        state = make_render_state(initial_tokens=user_token_totals.get(user_id, 0))
        try:
            while True:
                event = await asyncio.wait_for(queue.get(), timeout=300)
                etype = event.get("type", "?")
                delta_type = event.get("delta_type", "")
                extra = ""
                if etype == "message_end":
                    msg = event.get("message", {})
                    extra = f" role={msg.get('role')} stop={msg.get('stop_reason')} content={str(msg.get('content', ''))[:60]}"
                elif etype == "message_start":
                    extra = f" role={event.get('message', {}).get('role')}"
                elif etype == "tool_execution_start":
                    extra = f" tool={event.get('tool_name')}"
                elif etype == "tool_execution_end":
                    extra = f" tool={event.get('tool_name')} error={event.get('is_error')}"
                elif delta_type == "text_delta":
                    extra = f" delta={repr(event.get('delta', {}).get('content', '')[:40])}"
                elif delta_type == "thinking_delta":
                    extra = f" delta={repr(event.get('delta', {}).get('reasoning_content', '')[:40])}"
                print(f"[SSE] {etype}{f' ({delta_type})' if delta_type else ''}{extra} [turn={state['turn']}]")

                html = render_event(event, state)
                if html is not None:
                    yield sse_message(html, event="AgentEvent")
                    await asyncio.sleep(0.01)
                else:
                    print("[SSE]   -> no HTML rendered")
                if event.get("type") == "agent_end":
                    # Persist cumulative token total for this user
                    user_token_totals[user_id] = state["total_tokens"]
                    yield sse_message(Div(), event="close")
                    break
        except asyncio.TimeoutError:
            print("[SSE] TIMEOUT")
            user_token_totals[user_id] = state["total_tokens"]
            yield sse_message(Div(), event="close")
        except Exception as e:
            print(f"[SSE] ERROR: {e}")
            user_token_totals[user_id] = state["total_tokens"]
            import traceback

            traceback.print_exc()
            yield sse_message(Div(), event="close")
        finally:
            unsub()
            print("[SSE] stream ended")

    return EventStream(event_stream())


@rt("/stop", methods=["POST"])
def stop_agent(req):
    user_id = req.state.user_id
    agent = get_agent(user_id)
    agent.abort()
    return Button("Stop", id="stop-btn", hx_swap_oob="true", cls="btn btn-ghost btn-sm hidden", hx_post="/stop")


@rt("/clear", methods=["POST"])
async def clear_chat(req):
    user_id = req.state.user_id
    agent = get_agent(user_id)
    if agent.state.is_streaming:
        agent.abort()
        await agent.wait_for_idle()
    reset_agent(user_id)
    reset_sandbox(user_id)
    asyncio.create_task(init_sandbox(user_id))

    return (
        "",  # Clear chat container
        Div(
            Pre(id="streaming-text", cls="whitespace-pre-wrap font-sans text-base leading-relaxed m-0 px-0"),
            id="streaming-area",
            hx_swap_oob="outerHTML",
            cls="max-w-3xl mx-auto w-full",
        ),
        TokenCountUpdate(0),
    )


serve()
