"""
Minimal Agentic Loop

The simplest possible implementation of an agent loop.
No abstractions. No bells and whistles. Just the core loop.
"""

import json
from dotenv import load_dotenv
from agents.tools import TOOLS, TOOL_FUNCTIONS
from agents.prompts import SYSTEM_PROMPT
import litellm
import warnings

warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")
load_dotenv()


def run_agent(messages):
    """
    The agent loop as a generator - yields messages as they're added.

    Yields messages in standard Chat Completions format:
      - {"role": "assistant", "tool_calls": [...], ...}  # Assistant requesting tool calls
      - {"role": "tool", "tool_call_id": ..., "content": ...}  # Tool result
      - {"role": "assistant", "content": ...}  # Final response (no tool_calls)

    Also yields usage updates:
      - {"type": "usage", "total": ...}  # Cumulative token count
    """
    if not messages or messages[0].get("role") != "system":
        messages.insert(0, {"role": "system", "content": SYSTEM_PROMPT})

    # Track cumulative token usage across the agentic loop
    total_tokens = 0

    while True:
        # Call the LLM
        response = litellm.completion(
            model="claude-opus-4-5-20251101",  # "gemini/gemini-3-flash-preview", #claude-opus-4-5-20251101, gpt-5.2
            messages=messages,
            tools=TOOLS,
            reasoning_effort="low",
        )

        # Update cumulative usage
        if response.usage:
            total_tokens += response.usage.total_tokens or 0
            yield {"type": "usage", "total": total_tokens}

        # Append assistant message (thought signatures automatically preserved)
        message = response.choices[0].message

        # If no tool calls, we're done - yield final response
        if not message.tool_calls:
            final_msg = {"role": "assistant", "content": message.content}
            messages.append(final_msg)
            yield final_msg
            return

        # Assistant message with tool calls - add and yield it
        messages.append(message)
        yield message

        # Execute each tool and yield results
        for tool_call in message.tool_calls:
            name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)
            result = TOOL_FUNCTIONS[name](**args)

            tool_msg = {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            }
            messages.append(tool_msg)
            yield tool_msg
