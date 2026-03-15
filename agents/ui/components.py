# ruff: noqa: F405, F403
"""
UI components for single-stream agent chat interface.

Everything renders in one scrolling view — user messages, streaming text,
tool executions, tool results, and finalized assistant messages.
"""

import json

from fasthtml.common import *
from agents.ui.markdown import render_md
from agents.ui.tool_renderers import render_tool_call


# ============ Chat Components ============


def ChatMessage(role: str, content: str):
    """Render a chat message in the stream."""
    is_user = role == "user"
    if is_user:
        return Div(
            Div(
                Div("You", cls="text-xs font-semibold opacity-60 mb-1"),
                Div(content, cls="text-base"),
                cls="py-3",
            ),
            cls="border-b border-base-300",
        )
    else:
        rendered = render_md(content)
        return Div(
            Div(
                Div("Assistant", cls="text-xs font-semibold opacity-60 mb-1"),
                Div(rendered, cls="text-base prose max-w-none"),
                cls="py-3",
            ),
            cls="border-b border-base-300",
        )


def ChatInput():
    """The chat input form. Cmd+Enter to send."""
    return Form(
        Textarea(
            name="message",
            placeholder="Ask something... (Cmd+Enter to send)",
            rows=3,
            cls="textarea textarea-bordered flex-1 resize-none text-base leading-relaxed",
            id="message-input",
            autofocus=True,
        ),
        Button(
            "Send",
            type="submit",
            cls="btn btn-primary self-end",
            id="send-btn",
        ),
        Div(id="chat-target"),
        hx_post="/chat",
        hx_target="#chat-target",
        hx_swap="none",
        hx_trigger="submit, keydown[metaKey&&key=='Enter'] from:#message-input, keydown[ctrlKey&&key=='Enter'] from:#message-input",
        hx_disabled_elt="#send-btn, #message-input",
        **{"hx-on::after-request": "document.getElementById('message-input').value = ''"},
        cls="flex gap-3 items-end w-full",
    )


def ThinkingIndicator():
    """Inline loading indicator while agent is thinking."""
    return Div(
        Span(cls="loading loading-dots loading-sm"),
        Span("Thinking...", cls="ml-2 text-sm opacity-70"),
        cls="flex items-center py-2",
        id="thinking-indicator",
    )


def TokenCountUpdate(total_tokens):
    """OOB update for the token count display."""
    return Span(
        f"{total_tokens:,} tokens",
        id="token-count",
        cls="text-sm opacity-70 mr-4",
        hx_swap_oob="true",
    )


# ============ Tool Execution Components (inline in stream) ============


def ToolExecutionBlock(event):
    """Render a tool call starting — shows tool name + args inline."""
    name = event.get("tool_name", "unknown")
    args = event.get("args", {})
    args_str = json.dumps(args) if isinstance(args, dict) else str(args)
    tool_call_id = event.get("tool_call_id", "")

    return Div(
        render_tool_call(name, args_str, tool_call_id),
        Div(
            Span(cls="loading loading-spinner loading-xs"),
            Span("Running...", cls="ml-1 text-xs opacity-60"),
            cls="flex items-center mt-1",
            id=f"tool-status-{tool_call_id}",
        ),
        cls="py-2 px-3 my-2 bg-base-200 rounded-lg border border-base-300",
        id=f"tool-block-{tool_call_id}",
    )


def ToolResultBlock(event):
    """Render a tool result — text, images, plotly inline."""
    tool_call_id = event.get("tool_call_id", "")
    result = event.get("result", {})
    is_error = event.get("is_error", False)
    content = result.get("content", []) if isinstance(result, dict) else []
    details = result.get("details") if isinstance(result, dict) else None

    parts = []

    # Text content
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            text = block.get("text", "")
            if text and text != "(no output)":
                parts.append(
                    Pre(
                        text,
                        cls=f"text-sm whitespace-pre-wrap bg-base-300 p-2 rounded max-h-48 overflow-y-auto {'text-error' if is_error else ''}",
                    )
                )

    # Images
    for block in content:
        if isinstance(block, dict) and block.get("type") == "image_url":
            img_url = block.get("image_url", "")
            modal_id = f"img-modal-{hash(img_url) % 100000}"
            parts.append(
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
                    cls="my-2",
                )
            )

    # Plotly charts from details
    if details and details.get("plotly_htmls"):
        for html in details["plotly_htmls"]:
            parts.append(
                Iframe(
                    srcdoc=f"<!DOCTYPE html><html><head><style>body{{margin:0}}</style></head><body>{html}</body></html>",
                    cls="w-full h-80 border-0 rounded bg-base-100 my-2",
                )
            )

    if not parts:
        parts.append(Span("(no output)", cls="text-xs opacity-50"))

    # Remove the running spinner for this tool
    return Div(
        Div(*parts),
        # Clear the spinner
        Div(id=f"tool-status-{tool_call_id}", hx_swap_oob="innerHTML"),
    )


# ============ Event Renderer ============

# Auto-scroll JS — keeps view pinned to bottom during streaming
SCROLL_JS = "let c = document.getElementById('scroll-container'); if(c) c.scrollTop = c.scrollHeight;"


_turn_counter = 0


def make_render_state(initial_tokens=0):
    """Create mutable state for render_event across a streaming session."""
    return {"total_tokens": initial_tokens, "turn": _turn_counter}


def render_event(event, state):
    """Convert a liteagent event to HTMX HTML fragments for SSE.

    Returns html_fragment_or_None. Mutates state dict in place.
    """
    t = event.get("type")
    delta_type = event.get("delta_type")
    turn = state["turn"]

    # ---- Streaming deltas ----

    if t == "message_update" and delta_type == "text_delta":
        delta_text = event.get("delta", {}).get("content", "")
        if delta_text:
            return Pre(
                delta_text,
                id="streaming-text",
                hx_swap_oob="beforeend",
                cls="whitespace-pre-wrap font-sans text-base leading-relaxed m-0 px-0",
                **{"hx-on::load": SCROLL_JS},
            )

    elif t == "message_update" and delta_type == "thinking_delta":
        delta_text = event.get("delta", {}).get("reasoning_content", "")
        if delta_text:
            return Span(
                delta_text,
                id=f"thinking-{turn}",
                hx_swap_oob="beforeend",
                **{"hx-on::load": SCROLL_JS},
            )

    elif t == "message_update" and delta_type == "tool_call_delta":
        delta = event.get("delta", {})
        tool_calls = delta.get("tool_calls", [])
        if tool_calls:
            tc = tool_calls[0]
            tc_id = tc.get("id", "")
            name = tc.get("function", {}).get("name", "")
            args_chunk = tc.get("function", {}).get("arguments", "")

            # First delta for a new tool call has the id and name
            if tc_id:
                state["current_tc_id"] = tc_id
                return Div(
                    Div(
                        Span(f"🔧 {name}", cls="font-mono text-primary font-bold"),
                        Pre(
                            id=f"tc-args-{tc_id}",
                            cls="whitespace-pre-wrap font-mono text-sm bg-base-300 p-2 rounded mt-1 overflow-x-auto",
                        ),
                        cls="py-2 px-3 my-2 bg-base-200 rounded-lg border border-base-300",
                        id=f"tc-block-{tc_id}",
                    ),
                    id="chat-container",
                    hx_swap_oob="beforeend",
                    **{"hx-on::load": SCROLL_JS},
                )
            elif args_chunk and state.get("current_tc_id"):
                return Span(
                    args_chunk,
                    id=f"tc-args-{state['current_tc_id']}",
                    hx_swap_oob="beforeend",
                )

    # ---- Message boundaries ----

    elif t == "message_start":
        msg = event.get("message", {})
        if msg.get("role") == "assistant":
            global _turn_counter
            _turn_counter += 1
            state["turn"] = _turn_counter
            return Div(
                Pre(id=f"thinking-{_turn_counter}", cls="whitespace-pre-wrap font-mono text-sm opacity-40 m-0 px-0 py-1"),
                id="chat-container",
                hx_swap_oob="beforeend",
            )

    elif t == "message_end":
        msg = event.get("message", {})
        role = msg.get("role")

        usage = msg.get("usage")
        if usage:
            state["total_tokens"] += usage.get("total_tokens", 0)

        if role == "assistant" and msg.get("content") and msg.get("stop_reason") != "tool_calls":
            return Div(
                Div(
                    ChatMessage("assistant", msg["content"]),
                    id="chat-container",
                    hx_swap_oob="beforeend",
                    **{"hx-on::load": SCROLL_JS},
                ),
                Span(id="streaming-text", hx_swap_oob="innerHTML"),
                TokenCountUpdate(state["total_tokens"]),
            )
        elif role == "assistant" and msg.get("stop_reason") == "tool_calls":
            content = msg.get("content")
            parts = []
            if content:
                parts.append(Div(ChatMessage("assistant", content), id="chat-container", hx_swap_oob="beforeend"))
            parts.append(Span(id="streaming-text", hx_swap_oob="innerHTML"))
            if usage:
                parts.append(TokenCountUpdate(state["total_tokens"]))
            return Div(*parts)

    # ---- Tool execution ----

    elif t == "tool_execution_start":
        tool_call_id = event.get("tool_call_id", "")
        name = event.get("tool_name", "")
        args = event.get("args", {})
        args_str = json.dumps(args) if isinstance(args, dict) else str(args)

        if state.get("current_tc_id") == tool_call_id:
            # Already streamed — replace entire block with rendered version + spinner
            return Div(
                render_tool_call(name, args_str, tool_call_id),
                Div(
                    Span(cls="loading loading-spinner loading-xs"),
                    Span("Running...", cls="ml-1 text-xs opacity-60"),
                    cls="flex items-center mt-1",
                    id=f"tool-status-{tool_call_id}",
                ),
                cls="py-2 px-3 my-2 bg-base-200 rounded-lg border border-base-300",
                id=f"tc-block-{tool_call_id}",
                hx_swap_oob="outerHTML",
            )
        else:
            # No streaming happened — render full block
            return Div(
                ToolExecutionBlock(event),
                id="chat-container",
                hx_swap_oob="beforeend",
                **{"hx-on::load": SCROLL_JS},
            )

    elif t == "tool_execution_end":
        tool_call_id = event.get("tool_call_id", "")
        return Div(
            Div(ToolResultBlock(event), id="chat-container", hx_swap_oob="beforeend", **{"hx-on::load": SCROLL_JS}),
            Div(id=f"tool-status-{tool_call_id}", hx_swap_oob="innerHTML"),
        )

    # ---- Session lifecycle ----

    elif t == "agent_end":
        return Div(
            Button("Stop", id="stop-btn", hx_swap_oob="true", cls="btn btn-ghost btn-sm hidden", hx_post="/stop"),
            Span(id="streaming-text", hx_swap_oob="innerHTML"),
        )

    return None
