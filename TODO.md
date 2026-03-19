# TODO & Notes

## liteagent Feature Coverage

What the app uses vs what liteagent supports:

| liteagent feature | Used? | Notes |
|---|---|---|
| `prompt(message)` | Yes | Core flow |
| `prompt(message, images=[...])` | No | No image upload UI yet |
| `continue_run()` | No | Could resume after abort |
| `steer(message)` | Yes | Input while streaming |
| `follow_up(message)` | No | Auto-chain after agent stops |
| `abort()` | Yes | Stop button |
| `wait_for_idle()` | Yes | Clear while streaming |
| `reset()` | Yes | Clear button |
| `set_model(model)` | Yes | Model selector (navbar dropdown) |
| `set_thinking_level(level)` | Yes | Hardcoded "high" for all models |
| `set_system_prompt(prompt)` | No | Could let users customize |
| `set_tools(tools)` | No | Could add/remove tools dynamically |
| `replace_messages()` | No | Could enable message editing/forking |
| `append_message()` | No | Could inject context |
| `set_steering_mode("all")` | No | Deliver all queued steers at once |
| `set_follow_up_mode("all")` | No | Deliver all follow-ups at once |
| `subscribe(callback)` | Yes | SSE bridge |
| `transform_context` hook | No | Context compaction/pruning — conversations accumulate unbounded |
| `convert_to_llm` custom | No | Using default converter |
| `on_update` in tools | No | Streaming partial tool results (e.g. stdout line-by-line) |
| `Tool(params_model=...)` | No | Pydantic validation |
| `Tool(label=...)` | No | Human-readable tool names in UI |

## Ideas

- **Image uploads** — Add file input to chat, pass to `agent.prompt(message, images=[...])`.
- **Context compaction** — Use `transform_context` to prune/summarize before hitting context window limit. Important for long conversations.
- **Streaming tool output** — Use `on_update(ToolResult(...))` so `run_code` can stream stdout line-by-line instead of waiting for completion.
- **System prompt editing** — Let users tweak the system prompt from the UI.
- **UI overhaul** — Better theme, spacing, typography. Collapsible thinking. Tool block styling.
