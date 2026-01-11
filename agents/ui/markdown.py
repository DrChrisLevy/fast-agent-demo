# ruff: noqa: F405, F403
"""
Markdown Rendering with Tailwind/DaisyUI Styling and Syntax Highlighting.

Pipeline: Markdown -> mistletoe + Pygments -> strip inline styles -> apply_classes() -> NotStr
"""

import re

import mistletoe
from mistletoe.contrib.pygments_renderer import PygmentsRenderer
from fasthtml.common import *
from lxml import html as lxml_html


# Tailwind/DaisyUI class mappings for HTML elements
TAILWIND_CLASS_MAP = {
    # Headings
    "h1": "text-4xl font-bold mt-8 mb-4",
    "h2": "text-3xl font-bold mt-6 mb-3",
    "h3": "text-2xl font-semibold mt-5 mb-2",
    "h4": "text-xl font-semibold mt-4 mb-2",
    "h5": "text-lg font-semibold mt-3 mb-2",
    # Text elements
    "p": "text-base leading-relaxed mb-4",
    "a": "link link-primary",
    "strong": "font-bold",
    "em": "italic",
    # Lists
    "ul": "list-disc space-y-1 mb-4 ml-6",
    "ol": "list-decimal space-y-1 mb-4 ml-6",
    "li": "leading-relaxed",
    # Code
    "code": "bg-base-200 px-1 rounded text-sm font-mono",
    "pre": "bg-base-200 p-4 rounded-lg overflow-x-auto mb-4",
    # Other
    "blockquote": "border-l-4 border-primary pl-4 italic my-4 text-base-content/60",
    "img": "max-w-full h-auto rounded-lg my-4",
    "table": "table table-zebra w-full my-4",
    "th": "text-left font-semibold p-2",
    "td": "p-2",
    "hr": "my-8 border-base-300",
}


def apply_classes(html_str, class_map=None):
    """Apply CSS classes to HTML elements based on tag name."""
    if class_map is None:
        class_map = TAILWIND_CLASS_MAP

    try:
        doc = lxml_html.fragment_fromstring(html_str, create_parent="div")

        for tag, classes in class_map.items():
            for elem in doc.xpath(f".//{tag}"):
                existing = elem.get("class", "")
                elem.set("class", f"{existing} {classes}".strip())

        result = lxml_html.tostring(doc, encoding="unicode")
        if result.startswith("<div>") and result.endswith("</div>"):
            result = result[5:-6]
        return result
    except Exception:
        return html_str


def _strip_pygments_styles(html_str):
    """Strip inline styles from Pygments output so Tailwind classes can apply."""
    html_str = re.sub(r'<div class="highlight"[^>]*>', '<div class="highlight">', html_str)
    html_str = re.sub(r"<pre[^>]*>", "<pre>", html_str)
    return html_str


def render_md(md_content, class_map=None):
    """
    Render markdown to HTML with Tailwind/DaisyUI classes and syntax highlighting.

    Code blocks are syntax-highlighted server-side by Pygments.
    Returns NotStr so FastHTML renders the HTML directly.
    """
    if not md_content or not md_content.strip():
        return ""

    with PygmentsRenderer() as renderer:
        html_str = renderer.render(mistletoe.Document(md_content))

    html_str = _strip_pygments_styles(html_str)
    html_str = apply_classes(html_str, class_map or TAILWIND_CLASS_MAP)

    return NotStr(html_str)
