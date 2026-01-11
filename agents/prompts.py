"""System prompts for the agent."""

SYSTEM_PROMPT = """You are a helpful assistant.

Always describe what tools you are using and what you are doing
before doing them.
SO before making a tool call, send a message to the user describing what you are doing.
Then make the tool call.
"""
