# ruff: noqa: F405, F403
"""
Custom renderers for tool calls in the trace view.

Each renderer takes (name, args_dict) and returns an FT component.
"""

import json
from fasthtml.common import *
from agents.ui.markdown import render_md


def render_run_code(name, args):
    """Custom renderer for run_code tool - shows code with syntax highlighting."""
    code = args.get("code", "")
    code_md = f"```python\n{code}\n```"
    return Div(
        Span(f"🔧 {name}", cls="font-mono text-primary font-bold"),
        Div(render_md(code_md), cls="mt-1"),
    )


# Custom renderers for specific tools (tool_name -> render function)
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
            cls="mb-2",
        )

    # Default rendering
    return Div(
        Span(f"🔧 {name}", cls="font-mono text-primary font-bold"),
        Pre(args_str, cls="text-xs bg-base-300 p-1 rounded mt-1 overflow-x-auto"),
        Span(f"id: {tc_id}", cls="text-xs opacity-50"),
        cls="mb-2",
    )
