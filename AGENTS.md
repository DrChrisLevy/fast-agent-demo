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


## No Custom JavaScript, use FastHTML and HTMX

Use FastHTML. See these links https://fastht.ml/docs/llms.txt and visit appropriate docs if you are unsure.
Also be sure to use only DaisyUI so that themes works. Use proper DaisyUI components everywhere.
If unsure visit https://daisyui.com/llms.txt


Embrace the power of HTMX. Do NOT write custom JavaScript for interactivity. HTMX provides declarative attributes for almost everything. Make use of `hx_trigger`, `hx_post`, `hx_get`, `hx_target`, `hx_swap`, `hx_include`, `hx_swap_oob`, etc.

If you find yourself writing inline JS event handlers or `<script>` tags for interactivity, stop and find the HTMX way. The only acceptable JS is minimal one-liners for things HTMX genuinely can't do.


## Database

This app uses https://github.com/AnswerDotAI/fastlite for the database.

## LLM
This app uses https://docs.litellm.ai/docs/ for the LLM API.


## Linting

Run `./dev lint` after finishing code changes to lint the code.

## Testing

Run `./dev test` to run the test suite. This skips slow integration tests by default.

- `./dev test` - Run tests (skips `@pytest.mark.slow`)
- `./dev test -m slow` - Run only slow integration tests (hits real APIs)
- `./dev test -m ""` - Run ALL tests (including slow)
- `./dev test --cov=agents --cov=main --cov-report=term-missing` - Run with coverage

