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

# Run only slow integration tests (hits real APIs)
./dev test -m slow

# Run ALL tests (including slow)
./dev test -m ""

# Run tests with coverage
./dev test --cov=agents --cov=main --cov-report=term-missing

# Lint and format
./dev lint
```

## Project Structure

```
agents/
  agent.py           # Agentic loop (think → act → observe → repeat)
  tools.py           # Tool definitions and implementations
  prompts.py         # System prompt generation
  coding_sandbox.py  # Modal sandbox wrapper for code execution
  driver_program.py  # Runs inside Modal sandbox, executes code
  ui/
    components.py    # Chat, trace, input components
    markdown.py      # Markdown rendering with syntax highlighting
    tool_renderers.py # Custom tool call display
tests/               # pytest tests
main.py              # FastHTML app and routes
```


## Export requirements.txt

```bash
uv export --no-hashes --no-dev -o requirements.txt
```