# Feature TODO — Unused liteagent Capabilities

## User-Facing

- [ ] **Image uploads in prompts** — `agent.prompt(message, images=[...])`. Users can't attach images to chat messages currently.
- [ ] **Follow-up messages** — `agent.follow_up(message)`. Could be used for automated chaining (e.g. "after generating code, automatically run it").
- [ ] **System prompt editing** — `agent.set_system_prompt(prompt)`. Let users customize the agent's behavior.
- [ ] **Dynamic tools** — `agent.set_tools(tools)`. Add/remove tools mid-conversation (e.g. enable a web search tool on demand).

## Streaming / UI

- [ ] **Way cooler looking UI** — Overhaul the chat interface to look more polished and modern.
- [ ] **Streaming tool updates** — `on_update(ToolResult(...))` for streaming partial results. The `run_code` tool could stream stdout line-by-line instead of waiting for completion.
- [ ] **Tool labels** — `Tool(label="...")` for human-readable display names instead of showing `run_code`.

## Data / State

- [ ] **Context compaction** — `transform_context` hook. Called before every LLM call to prune/summarize/compress message history. Currently conversations accumulate unbounded and will hit the context window limit.
- [ ] **Message history editing** — `replace_messages()` / `append_message()`. Could enable editing/deleting messages, or forking conversations.
- [ ] **Pydantic tool validation** — `Tool(params_model=MyModel)` for automatic argument validation/coercion before execution.
- [ ] **Steering modes** — `set_steering_mode("all")` to deliver all queued steers at once instead of one-at-a-time.
