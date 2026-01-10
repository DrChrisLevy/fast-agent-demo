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
                "properties": {"city": {"type": "string", "description": "The city name"}},
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_code",
            "description": "Run any arbitrary python code",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python code to run",
                    }
                },
                "required": ["code"],
            },
        },
    },
]


# Tool implementations
def get_weather(city: str) -> str:
    # Fake implementation
    return f"The weather in {city} is 72°F and sunny."


def run_code(code: str) -> str:
    """Run multi-line Python code. Don't do this in production!"""
    try:
        # Create a namespace to capture variables
        namespace = {}
        # Capture stdout
        import io
        import sys

        stdout_capture = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = stdout_capture

        try:
            exec(code, namespace)
        finally:
            sys.stdout = old_stdout

        output = stdout_capture.getvalue()

        # Return printed output, or the last assigned variable named 'result'
        if output:
            return output.strip()
        elif "result" in namespace:
            return str(namespace["result"])
        else:
            return "Code executed successfully (no output)"
    except Exception as e:
        return f"Error: {e}"


# Map tool names to functions
TOOL_FUNCTIONS = {
    "get_weather": get_weather,
    "run_code": run_code,
}
