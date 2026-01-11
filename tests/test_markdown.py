"""Tests for markdown rendering."""

from fasthtml.common import NotStr
from agents.ui.markdown import render_md, apply_classes, TAILWIND_CLASS_MAP


class TestRenderMd:
    """Tests for the render_md function."""

    def test_empty_content_returns_empty_string(self):
        assert render_md("") == ""
        assert render_md("   ") == ""
        assert render_md(None) == ""

    def test_returns_notstr(self):
        """Output should be NotStr so FastHTML renders it as raw HTML."""
        result = render_md("Hello")
        assert isinstance(result, NotStr)

    def test_renders_paragraph(self):
        result = render_md("Hello world")
        assert "Hello world" in str(result)
        assert "<p" in str(result)

    def test_renders_heading(self):
        result = render_md("# Title")
        assert "Title" in str(result)
        assert "<h1" in str(result)

    def test_renders_code_block(self):
        result = render_md("```python\nprint('hi')\n```")
        html = str(result)
        assert "print" in html
        assert "<pre" in html

    def test_renders_inline_code(self):
        result = render_md("Use `code` here")
        html = str(result)
        assert "<code" in html
        assert "code" in html

    def test_renders_bold(self):
        result = render_md("**bold text**")
        html = str(result)
        assert "<strong" in html or "<b" in html
        assert "bold text" in html

    def test_renders_list(self):
        result = render_md("- item 1\n- item 2")
        html = str(result)
        assert "<ul" in html
        assert "<li" in html
        assert "item 1" in html


class TestApplyClasses:
    """Tests for the apply_classes function."""

    def test_adds_classes_to_paragraph(self):
        html = "<p>Hello</p>"
        result = apply_classes(html)
        assert TAILWIND_CLASS_MAP["p"] in result

    def test_adds_classes_to_heading(self):
        html = "<h1>Title</h1>"
        result = apply_classes(html)
        assert TAILWIND_CLASS_MAP["h1"] in result

    def test_preserves_existing_classes(self):
        html = '<p class="existing">Hello</p>'
        result = apply_classes(html)
        assert "existing" in result
        assert TAILWIND_CLASS_MAP["p"] in result

    def test_handles_nested_elements(self):
        html = "<ul><li>Item</li></ul>"
        result = apply_classes(html)
        assert TAILWIND_CLASS_MAP["ul"] in result
        assert TAILWIND_CLASS_MAP["li"] in result

    def test_custom_class_map(self):
        html = "<p>Hello</p>"
        custom_map = {"p": "custom-class"}
        result = apply_classes(html, custom_map)
        assert "custom-class" in result

    def test_handles_invalid_html_gracefully(self):
        # Should return original string if parsing fails
        invalid = "not valid html <<<"
        result = apply_classes(invalid)
        assert result is not None
