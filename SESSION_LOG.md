# Session Log: Rebuild agents app on liteagent

**Date:** 2026-03-14
**Branch:** `liteagent-rebuild`
**Starting point:** Hand-rolled agent loop, two-panel UI, no token streaming
**End point:** Full liteagent integration, single-stream UI, all events streaming

---

## What We Did

### 1. Architecture Rebuild

Replaced the hand-rolled 95-line generator-based agent loop (`agents/agent.py`) with `liteagent` as a library dependency. This was a ground-up rewrite of the app layer while keeping the Modal sandbox infrastructure (`coding_sandbox.py`, `driver_program.py`) untouched.

**Key architectural changes:**
- `agents/agent.py` **deleted** — replaced by `liteagent.Agent`
- Per-user `Agent` instances in a TTL cache (replaces per-user message lists + contextvars)
- Tool factory pattern: `make_run_code_tool(user_id)` closes over the user ID, eliminating contextvars
- Async tool execution via `run_in_executor` (Modal sandbox API is sync)
- Plotly HTML goes in `ToolResult.details` (UI-only, never sent to LLM) instead of content-block filtering
- `TOOL_INSTRUCTIONS` moved to `prompts.py` to break a circular import

### 2. SSE Bridge Pattern

liteagent uses `subscribe(callback)` for events. FastHTML SSE needs an async generator. We bridged them:

```
agent.subscribe(callback) → asyncio.Queue → SSE async generator
```

Key details:
- `agent.prompt()` runs as `asyncio.create_task()`
- `hx_swap="none"` on the SSE container — only OOB swaps fire (prevents the primary swap from destroying streaming targets; this was a major bug we debugged)
- `outerHTML` swap for the SSE container so `hx-ext="sse"` attributes land in the DOM (another bug — `innerHTML` only replaced children, not attributes)
- `pending_prompts` dict bridges POST `/chat` (stores message) → GET `/agent-stream` (picks it up)

### 3. Single-Stream UI

Replaced the two-panel layout (chat + trace) with a single scrolling view:
- One container, `max-w-3xl mx-auto`, everything appends in chronological order
- Input pinned to bottom
- DaisyUI + Tailwind CSS + HTMX (same stack as before)

### 4. Event Streaming — All Types

Every liteagent event type now streams to the UI:

| Event | What renders |
|-------|-------------|
| `thinking_delta` | Reasoning text streams token-by-token (40% opacity, monospace) |
| `text_delta` | Response text streams into a `<pre>`, replaced with rendered markdown on `message_end` |
| `tool_call_delta` | Tool call arguments stream as raw JSON, replaced with syntax-highlighted code on `tool_execution_start` |
| `message_start` (assistant) | Creates a thinking text container with unique global ID |
| `message_end` (final) | Finalizes markdown, clears streaming areas, updates token count |
| `message_end` (tool_calls) | Clears streaming text, prepares for tool execution |
| `tool_execution_start` | Replaces raw JSON with rendered tool call + "Running..." spinner |
| `tool_execution_end` | Renders tool result (text, images, plotly charts) |
| `agent_end` | Hides stop button, clears streaming areas |

### 5. Steering and Abort

- **Stop button** — shown during streaming, calls `agent.abort()`
- **Steering from input** — if agent is streaming, new message calls `agent.steer()` instead of creating a new prompt

### 6. Extended Thinking

- Thinking level set to `"medium"` by default
- Thinking text streams and **persists** in the chat (not cleared after completion)
- Each assistant turn gets a unique thinking element ID to prevent cross-turn collisions

---

## Bugs Found and Fixed

### SSE container attributes not landing in DOM
- **Symptom:** No responses at all after sending a message
- **Cause:** `hx_swap_oob="innerHTML"` only replaced children, not the element's attributes. The SSE attributes (`hx-ext`, `sse_connect`) were on the incoming element but never made it to the DOM.
- **Fix:** Changed to `hx_swap_oob="outerHTML"`

### Primary SSE swap destroying streaming targets
- **Symptom:** Text streaming appeared to not work (but events were firing)
- **Cause:** `sse_swap="AgentEvent"` with default `innerHTML` swap replaced `#streaming-area` content on every event, destroying `#streaming-text` before OOB could append to it
- **Fix:** Added `hx_swap="none"` so only OOB swaps fire

### 196 `htmx:oobErrorNoTarget` console errors
- **Symptom:** Massive console error spam, janky UI
- **Cause:** `tool_call_delta` events tried to OOB-append to `#tool-args-{turn}` which didn't exist
- **Fix:** Changed `tool_call_delta` handler to return `None` (later replaced with proper streaming)

### Thinking text appearing in two places (first occurrence)
- **Symptom:** Second turn's thinking text showed above AND below the user message
- **Cause:** `make_render_state()` created fresh `turn: 0` per SSE connection. Second message created `thinking-1` again, colliding with first turn's element still in DOM.
- **Fix:** Global turn counter that persists across SSE sessions

### Thinking text appearing in two places (second occurrence)
- **Symptom:** Same duplicate thinking, but in a multi-tool-call scenario
- **Cause:** `make_render_state()` incremented the global counter, AND `message_start` incremented `state["turn"]`. Second SSE session's first `message_start` could collide with first session's second `message_start`.
- **Fix:** Only increment the global counter in `message_start`. `make_render_state()` just reads the current value.

### Token counter resetting to 0 on each new prompt
- **Symptom:** Token count in the header reset to zero every time the user sent a new message, instead of accumulating across the conversation
- **Cause:** `make_render_state()` hardcoded `total_tokens: 0`. Each SSE session (one per prompt) started fresh. liteagent emits per-call usage in `message_end` events (not cumulative), so the counter only ever showed tokens from the current prompt.
- **Fix:** Added `user_token_totals` TTL cache in `tools.py` to persist the running total per user. `make_render_state()` now accepts `initial_tokens` param, seeded from the cache. The total is written back on `agent_end`, timeout, or error.

### Multi-tool-call rendering — raw JSON not replaced for earlier tool calls
- **Symptom:** When the model issued 3 parallel tool calls, the first two showed raw JSON args AND a rendered version below. Only the last one rendered correctly.
- **Cause:** `state["current_tc_id"]` only tracked the last streamed tool call ID. When `tool_execution_start` fired for earlier tool calls, they didn't match, so they were appended as new blocks instead of replacing the streamed ones.
- **Fix:** Changed to `state["streamed_tc_ids"]` (a set) to track all streamed tool call IDs. `tool_execution_start` checks set membership instead of equality.

### Empty thinking `<pre>` tags when model doesn't think
- **Symptom:** Empty `<pre id="thinking-N">` elements left in the DOM between user message and assistant response on turns where the model didn't use extended thinking.
- **Cause:** `message_start` eagerly created the thinking container for every assistant turn, regardless of whether thinking deltas followed.
- **Fix:** Removed eager creation from `message_start`. Thinking container is now created lazily on the first `thinking_delta` event. A `thinking_created` flag in render state prevents duplicate creation.

---

## Files Changed

| File | Action |
|------|--------|
| `agents/agent.py` | **Deleted** |
| `agents/tools.py` | **Rewritten** — `make_run_code_tool()`, `get_agent()`, `reset_agent()` |
| `agents/prompts.py` | **Rewritten** — self-contained with `TOOL_INSTRUCTIONS` |
| `agents/ui/components.py` | **Rewritten** — `render_event()`, single-stream components, tool streaming |
| `agents/ui/__init__.py` | **Updated** exports |
| `main.py` | **Rewritten** — SSE bridge, single-stream layout, steering/abort |
| `pyproject.toml` | **Updated** — liteagent path dep, dropped litellm/openai |
| `agents/coding_sandbox.py` | Unchanged |
| `agents/driver_program.py` | Unchanged |
| `agents/ui/markdown.py` | Unchanged |
| `agents/ui/tool_renderers.py` | Unchanged |

---

## Commits on `liteagent-rebuild`

1. **Rebuild app on liteagent** — the big rewrite (delete agent.py, rewrite tools/prompts/components/main)
2. **Fix duplicate thinking text across turns** — global turn counter
3. **Add tool call argument streaming** — tool_call_delta events stream into UI
4. **Fix thinking ID collisions** — only increment counter in message_start
5. **Fix token counter resetting on each prompt** — persist cumulative total in TTL cache across SSE sessions
6. **Skip empty thinking elements** — lazy container creation on first thinking_delta
7. **Rewrite test suite, add parallel tests, update docs** — 169 tests passing, pytest-xdist, opus/high thinking, README/AGENTS.md sync
8. **Restore full Gemini image generation examples** — re-added extended examples (editing, compositing, 4K, grounded search, multi-turn) that were dropped during migration
9. **Update Gemini docs with Nano Banana 2** — all 3 models documented, extended aspect ratios, 512 resolution, thinking control, text rendering, image search grounding
10. **Fix multi-tool-call rendering + pin google-genai SDK** — track streamed tool IDs in a set (not just last one), restore full SearchTypes syntax, pin google-genai>=1.67.0 in sandbox

---

## Tested and Working

- Token-by-token text streaming
- Thinking text streaming (persists in chat)
- Tool call argument streaming (raw JSON → syntax-highlighted code)
- Tool execution with Modal sandbox (matplotlib, plotly)
- Image rendering inline (with DaisyUI modal for expansion)
- Interactive Plotly charts in iframes
- Multimodal tool results (model can "see" images from tool results)
- Stop/abort mid-run
- Continue after stop
- Steering from input during streaming
- Multi-turn conversation
- Clear/reset
- Error handling (model self-corrects on tool errors)
- Cumulative token counter across prompts
- Multiple parallel tool calls render correctly (no duplicate raw JSON)
- Gemini image generation with SearchTypes/ImageSearch grounding
- 169 tests passing (parallel via pytest-xdist)
- Zero console errors

---

## What's Next

- **Style/UX polish** — thinking display (collapsible?), tool block styling, spacing, dark theme option
- **Orphan sandbox cleanup** — server restarts leak Modal sandboxes (they idle-timeout after 30min but could be cleaned up better)
- **Tool call streaming polish** — during streaming show just the code value, not raw JSON wrapper
