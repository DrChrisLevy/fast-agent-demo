# Agent Chat

A hackable web interface for working with AI agents. See chat, tool calls, and message traces in real-time.

Built with [FastHTML](https://fastht.ml/) + [DaisyUI](https://daisyui.com/) + [HTMX](https://htmx.org/).

## Setup

```bash
uv sync
cp .env.example .env  # Add your API keys
```

## Development

```bash
# Run the app
uv run python main.py

# Run tests (skips slow integration tests by default)
./dev test

# Run all tests including integration tests that hit real APIs
./dev test -m slow

# Run tests with verbose output
./dev test -v

# Run tests with coverage report
./dev cov

# Lint and format
./dev lint
```

## Project Structure

```
agents/
  agent.py           # Agent loop
  tools.py           # Tool definitions
  coding_sandbox.py  # Modal sandbox for code execution
  ui/                # UI components
    components.py    # Chat, trace, input components
    markdown.py      # Markdown rendering
    tool_renderers.py # Custom tool display
tests/               # pytest tests
main.py              # FastHTML app and routes
```
