"""
Tool definitions and implementations for the agent.
"""

# Define tools the agent can use
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a city",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "The city name"}
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_code",
            "description": "Evaluate a math expression",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Math expression to evaluate",
                    }
                },
                "required": ["expression"],
            },
        },
    },
]


# Tool implementations
def get_weather(city: str) -> str:
    # Fake implementation
    return f"The weather in {city} is 72°F and sunny."


def run_code(expression: str) -> str:
    try:
        result = eval(expression)  # Don't do this in production!
        return str(result)
    except Exception as e:
        return f"Error: {e}"


# Map tool names to functions
TOOL_FUNCTIONS = {
    "get_weather": get_weather,
    "run_code": run_code,
}
