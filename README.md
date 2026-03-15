# Agent Chat

A hackable ChatGPT-like code interpreter for data analysis, code execution, and image generation. Real-time token streaming, inline tool execution, and steering/abort controls.

Built with [liteagent](https://github.com/DrChrisLevy/liteagent) + [FastHTML](https://fastht.ml/) + [DaisyUI](https://daisyui.com/) + [HTMX](https://htmx.org/) + [Modal](https://modal.com).

## Features

- **Secure cloud sandboxes** — Python runs in isolated [Modal](https://modal.com) containers, fully sandboxed from the host
- **Persistent state** — Variables, imports, and definitions carry over between code executions
- **Vision-enabled tool results** — The agent sees stdout, stderr, *and* any generated images (plots, charts, etc.)
- **Auto-captured plots** — Matplotlib/seaborn figures are captured as images; Plotly figures are captured as interactive HTML for you to explore
- **Interactive Plotly charts** — Plotly figures render as fully interactive charts you can zoom, pan, and hover
- **Gemini image generation** — Generate and edit images using Google's Gemini API directly in code
- **Auto-captured PIL images** — Any PIL Image assigned to a variable is automatically captured and shown
- **Data science ready** — pandas, numpy, scipy, scikit-learn, matplotlib, seaborn, plotly, and more pre-installed; install any package with `pip`
- **Per-user isolation** — Each browser session gets its own sandbox; conversation and state persist across page refreshes and new tabs
- **Token-by-token streaming** — Response text, thinking, and tool call arguments stream in real-time via SSE
- **Steering and abort** — Send follow-up messages while the agent is running to steer it, or stop it mid-run
- **Extended thinking** — See the model's reasoning process inline (when supported)
- **Multi-provider LLM** — Uses [liteagent](https://github.com/DrChrisLevy/liteagent) + [LiteLLM](https://docs.litellm.ai/) for easy model switching

## Setup

```bash
uv sync
cp .env.example plash.env  # Then edit plash.env with your keys
```

> **Note:** This project uses `plash.env` (not `.env`) so it works seamlessly with [Plash](https://pla.sh/) deployment.

### Environment Variables

```bash
# Required for code execution (get from https://modal.com)
MODAL_TOKEN_ID=
MODAL_TOKEN_SECRET=

# Required for session encryption (generate any random string)
FAST_APP_SECRET=

# LLM API keys — only add the one you plan to use
# Model is set in agents/tools.py get_agent() — change the model= line to switch
ANTHROPIC_API_KEY=   # For Claude models
OPENAI_API_KEY=      # For GPT models (optional)
GOOGLE_API_KEY=      # For Gemini models and image generation (optional)
```

## Development

```bash
# Run the app locally
uv run python main.py

# Run tests (skips slow integration tests by default)
./dev test

# Run only slow integration tests (hits real APIs)
./dev test -m slow

# Run ALL tests (including slow)
./dev test -m ""

# Run tests with coverage
./dev test -m "" --cov=agents --cov=main --cov-report=term-missing

# Lint and format
./dev lint
```

## Project Structure

```
agents/
  tools.py           # Per-user Agent management, tool factory, sandbox lifecycle
  prompts.py         # System prompt generation
  coding_sandbox.py  # Modal sandbox wrapper for code execution
  driver_program.py  # Runs inside Modal sandbox, executes code
  ui/
    components.py    # Single-stream UI components and SSE event renderer
    markdown.py      # Markdown rendering with syntax highlighting
    tool_renderers.py # Custom tool call display
tests/               # pytest tests
main.py              # FastHTML app, routes, and SSE bridge
```

## Export requirements.txt

```bash
uv export --no-hashes --no-dev -o requirements.txt
```

## Deploy to [Plash](https://pla.sh/)

```bash
uv run plash deploy
```

## TODO

- **Persistent storage** — Currently uses in-memory TTL caches (30 min TTL); [fastlite](https://github.com/AnswerDotAI/fastlite) would be a good option for database storage if needed
- **Style/UX polish** — Collapsible thinking display, tool block styling, dark theme
- **Tool call streaming polish** — Show just the code value during streaming, not raw JSON wrapper
- **End-to-end tests** — Playwright + mocked agent for automated UI testing