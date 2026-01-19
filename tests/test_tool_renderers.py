"""Tests for tool renderers."""

from fasthtml.common import to_xml
from agents.ui.tool_renderers import (
    render_tool_call,
    render_run_code,
    TOOL_RENDERERS,
)


def render(component):
    """Helper to render a FastHTML component to string."""
    return to_xml(component)


class TestRenderToolCall:
    """Tests for the render_tool_call function."""

    def test_default_rendering_shows_tool_name(self):
        html = render(render_tool_call("some_tool", '{"param": "value"}', "call_123"))
        assert "some_tool" in html

    def test_default_rendering_shows_args(self):
        args = '{"param": "value"}'
        html = render(render_tool_call("some_tool", args, "call_123"))
        assert "value" in html

    def test_default_rendering_shows_id(self):
        html = render(render_tool_call("some_tool", "{}", "call_123"))
        assert "call_123" in html

    def test_handles_dict_args(self):
        args = {"param": "value"}
        html = render(render_tool_call("some_tool", args, "call_123"))
        assert "value" in html

    def test_handles_invalid_json_args(self):
        args = "not valid json"
        html = render(render_tool_call("some_tool", args, "call_123"))
        # Should not raise, just render what it can
        assert "some_tool" in html

    def test_uses_custom_renderer_for_run_code(self):
        args = '{"code": "print(42)"}'
        html = render(render_tool_call("run_code", args, "call_123"))
        # Should use the custom renderer which shows syntax highlighting
        assert "print" in html
        assert "42" in html


class TestRenderRunCode:
    """Tests for the run_code custom renderer."""

    def test_shows_tool_name(self):
        html = render(render_run_code("run_code", {"code": "x = 1"}))
        assert "run_code" in html

    def test_shows_code_content(self):
        code = "print('hello world')"
        html = render(render_run_code("run_code", {"code": code}))
        assert "print" in html
        assert "hello" in html

    def test_handles_missing_code(self):
        html = render(render_run_code("run_code", {}))
        # Should not raise
        assert "run_code" in html

    def test_handles_multiline_code(self):
        code = "def foo():\n    return 42"
        html = render(render_run_code("run_code", {"code": code}))
        assert "def" in html
        assert "foo" in html


class TestToolRenderers:
    """Tests for the TOOL_RENDERERS registry."""

    def test_run_code_is_registered(self):
        assert "run_code" in TOOL_RENDERERS

    def test_registered_renderer_is_callable(self):
        for name, renderer in TOOL_RENDERERS.items():
            assert callable(renderer), f"{name} renderer should be callable"
