"""
Minimal Agentic Loop

The simplest possible implementation of an agent loop.
No abstractions. No bells and whistles. Just the core loop.
"""

import json
from dotenv import load_dotenv
from agents.tools import TOOLS, TOOL_FUNCTIONS
import litellm
import warnings

warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")
load_dotenv()


def run_agent(messages):
    """
    The agent loop as a generator - yields events for streaming.

    Yields dicts with 'type' and 'data':
      - {"type": "tool_call", "data": {"name": ..., "args": ...}}
      - {"type": "tool_result", "data": {"name": ..., "result": ...}}
      - {"type": "response", "data": {"content": ...}}
    """
    if not messages or messages[0].get("role") != "system":
        messages.insert(0, {"role": "system", "content": "You are a helpful assistant."})

    while True:
        # Call the LLM
        response = litellm.completion(
            model="gpt-5.2", # "gemini/gemini-3-flash-preview", #claude-opus-4-5-20251101, gpt-5.2
            messages=messages,
            tools=TOOLS,
            reasoning_effort="low"
        )

        # Append assistant message (thought signatures automatically preserved)
        message = response.choices[0].message

        # If no tool calls, we're done - append to history and yield final response
        if not message.tool_calls:
            messages.append({"role": "assistant", "content": message.content})
            yield {"type": "response", "data": {"content": message.content}}
            return

        # Otherwise, process tool calls
        messages.append(message)  # Add assistant message with tool calls

        # Execute tool and append result
        for tool_call in message.tool_calls:
            name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)

            # Yield tool call event
            yield {"type": "tool_call", "data": {"name": name, "args": args}}

            # Execute the tool
            result = TOOL_FUNCTIONS[name](**args)

            # Yield tool result event
            yield {"type": "tool_result", "data": {"name": name, "result": result}}

            # Add tool result to messages
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
            )