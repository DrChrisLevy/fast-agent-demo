# ruff: noqa: F405, F403
"""
Reusable UI components for the agent chat interface.
"""

import json
from fasthtml.common import *
from agents.ui.markdown import render_md
from agents.ui.tool_renderers import render_tool_call


def ChatMessage(role: str, content: str):
    """Render a chat message bubble."""
    is_user = role == "user"
    rendered = render_md(content)
    return Div(
        Div(
            Div(role.capitalize(), cls="chat-header opacity-70 text-xs"),
            Div(rendered, cls=f"chat-bubble {'chat-bubble-primary' if is_user else ''}"),
            cls=f"chat {'chat-end' if is_user else 'chat-start'}",
        ),
        id=f"msg-{hash(content) % 10000}",
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
            cls="text-xs whitespace-pre-wrap bg-base-300 p-2 rounded overflow-x-auto max-h-40 overflow-y-auto",
        )
    elif role == "user":
        content = Pre(
            msg.get("content", ""),
            cls="text-xs whitespace-pre-wrap bg-base-300 p-2 rounded",
        )
    elif role == "assistant":
        # Check if it has tool_calls (could be a ChatCompletionMessage object or dict)
        tool_calls = getattr(msg, "tool_calls", None) or msg.get("tool_calls")
        if tool_calls:
            # Assistant message with tool calls
            parts = []

            # Show assistant content if present (some models include text alongside tool calls)
            msg_content = getattr(msg, "content", None) or msg.get("content")
            if msg_content:
                parts.append(
                    Pre(
                        msg_content,
                        cls="text-xs whitespace-pre-wrap bg-base-300 p-2 rounded mb-2",
                    )
                )

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
                parts.append(
                    Div(
                        Span("⚡ parallel", cls="text-xs opacity-50 mb-1 block"),
                        Div(*calls_display, cls="grid grid-cols-2 gap-2"),
                    )
                )
            else:
                parts.extend(calls_display)

            content = Div(*parts)
        else:
            # Regular assistant response
            content = Pre(
                msg.get("content", ""),
                cls="text-xs whitespace-pre-wrap bg-base-300 p-2 rounded",
            )
    elif role == "tool":
        tool_call_id = msg.get("tool_call_id", "?")
        content = Div(
            Span(f"tool_call_id: {tool_call_id}", cls="text-xs opacity-50 block mb-1"),
            Pre(
                msg.get("content", ""),
                cls="text-xs whitespace-pre-wrap bg-base-300 p-2 rounded max-h-32 overflow-y-auto",
            ),
        )
    else:
        content = Pre(
            json.dumps(msg, indent=2, default=str),
            cls="text-xs bg-base-300 p-2 rounded",
        )

    return Div(
        Div(Span(role.upper(), cls=f"badge {badge_cls} badge-sm"), cls="mb-1"),
        content,
        cls="border-l-2 border-base-300 pl-3 py-2 mb-2",
    )


def TraceView(messages):
    """Render the full message trace."""
    if not messages:
        return Div(Span("No messages yet", cls="text-sm opacity-50"), cls="p-4")

    return Div(*[TraceMessage(m) for m in messages], cls="p-4")


def ChatInput():
    """The chat input form with multiline support. Cmd+Enter to send."""
    return Div(
        Textarea(
            name="message",
            placeholder="Ask something... (Cmd+Enter to send)",
            rows=3,
            cls="textarea textarea-bordered flex-1 resize-none text-base leading-relaxed",
            autofocus=True,
            hx_post="/chat",
            hx_target="#chat-target",
            hx_swap="none",
            hx_trigger="keydown[metaKey&&key=='Enter'], keydown[ctrlKey&&key=='Enter']",
            **{"hx-on::after-request": "this.value = ''"},
        ),
        Button(
            "Send",
            cls="btn btn-primary self-end",
            hx_post="/chat",
            hx_target="#chat-target",
            hx_swap="none",
            hx_include="[name='message']",
            **{"hx-on::after-request": "document.querySelector('[name=message]').value = ''"},
        ),
        Div(id="chat-target"),
        cls="flex gap-3 items-end w-full",
    )


def ThinkingIndicator():
    """Loading indicator shown while agent is thinking."""
    return Div(
        Span(cls="loading loading-dots loading-sm"),
        Span("Agent is thinking...", cls="ml-2 text-sm opacity-70"),
        cls="flex items-center py-2",
    )


def TraceUpdate(messages):
    """OOB swap to update trace panel."""
    return Div(
        TraceView(messages),
        id="trace-container",
        hx_swap_oob="true",
        cls="overflow-y-auto flex-1 min-h-0",
    )
