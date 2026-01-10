"""
Minimal Agentic Loop

The simplest possible implementation of an agent loop.
No abstractions. No bells and whistles. Just the core loop.
"""

import json
from dotenv import load_dotenv
from openai import OpenAI
from pprint import pprint
from agents.tools import TOOLS, TOOL_FUNCTIONS

load_dotenv()

client = OpenAI()


def run_agent(messages) -> str:
    """
    The agent loop.

    1. Send messages to LLM
    2. If LLM returns tool calls, execute them and loop
    3. If LLM returns a regular message, return it
    """

    while True:
        pprint(messages)
        # Call the LLM
        response = client.chat.completions.create(
            model="gpt-5-mini",
            messages=messages,
            tools=TOOLS,
        )

        message = response.choices[0].message

        # If no tool calls, we're done - return the response
        if not message.tool_calls:
            return message.content

        # Otherwise, process tool calls
        messages.append(message)  # Add assistant message with tool calls

        for tool_call in message.tool_calls:
            name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)

            print(f"Calling tool: {name}({args})")

            # Execute the tool
            result = TOOL_FUNCTIONS[name](**args)

            # Add tool result to messages
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
            )
