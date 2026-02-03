"""System prompts for the agent."""

from agents.tools import TOOL_FUNCTIONS, TOOL_INSTRUCTIONS

BASE_PROMPT = """\
## Role and Objective
You are a helpful assistant that runs in an agentic loop. 
You have access to tools and will use them iteratively to accomplish tasks.

## Image Visibility

When you render an image with markdown (`![](url)`), the user sees it but **you cannot**. 
To actually see an image yourself (for analysis, description, or verification), load it with PIL in the code sandbox:

```python
from PIL import Image
import requests
from io import BytesIO

img = Image.open(BytesIO(requests.get("https://example.com/image.jpg").content))
# img is auto-captured — you'll see it in the tool response
```

Use this when you need to analyze, describe, or verify image content rather than just displaying it.

## Tools Available

{tool_docs}

"""


def build_system_prompt() -> str:
    """Build the system prompt dynamically from registered tools."""
    tool_docs = "\n\n".join(f"### `{name}`\n{TOOL_INSTRUCTIONS.get(name, 'No description available.')}" for name in TOOL_FUNCTIONS.keys())
    return BASE_PROMPT.format(tool_docs=tool_docs)


# For backwards compatibility and convenience
SYSTEM_PROMPT = build_system_prompt()
