import base64
import json
import os
import sys
import time
from contextlib import redirect_stderr, redirect_stdout
from io import BytesIO, StringIO
from typing import Any, Generator

"""
Note: this could change in the future as modal improves.
    But at the time of writing this, the stdout channel does not work well
    with from_id at the moment. That is why we make use of the file system.
    This module implements a file-based code execution driver in a Modal sandbox.
    This module was specifically designed to support detached execution. This means
    that you can pass around the Sandbox's object ID and control the same process
    from a different process later.
    It reads commands from '/modal/io/stdin.txt'; each JSON command must include
    a "code" field and a user-supplied "command_id". The execution output (stdout and stderr)
    is written to '/modal/io/<command_id>.txt'.
    Based off this GIST from Peyton (Modal Developer)
    https://gist.github.com/pawalt/7cd4dc56de29e9cddba4d97decaab1ad
"""

# These are injected when defining the image in modal_sandbox.py
IO_DATA_DIR = os.environ["IO_DATA_DIR"]
STDIN_FILE = os.environ["STDIN_FILE"]


def tail_f(filename: str) -> Generator[str, None, None]:
    """
    Continuously yields new lines from the file.
    """
    with open(filename, "r") as f:
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.1)
                continue
            yield line


# Track captured objects by id() to avoid duplicate captures across code executions
_captured_ids: set[int] = set()

globals: dict[str, Any] = {}
for line in tail_f(STDIN_FILE):
    line = line.strip()
    print(f"Received line: {line} len: {len(line)}")
    if not line:
        continue

    command = json.loads(line)
    if (code := command.get("code")) is None:
        print(json.dumps({"error": "No code to execute"}))
        continue

    if (command_id := command.get("command_id")) is None:
        print(json.dumps({"error": "No command_id"}))
        continue

    stdout_io, stderr_io = StringIO(), StringIO()
    with redirect_stdout(stdout_io), redirect_stderr(stderr_io):
        try:
            exec(code, globals)
        except Exception as e:
            print(f"{type(e).__name__}: {e}", file=sys.stderr)

    # Capture any matplotlib figures as base64 images
    images = []
    try:
        import matplotlib.pyplot as plt

        for fig_num in plt.get_fignums():
            fig = plt.figure(fig_num)
            buf = BytesIO()
            fig.savefig(buf, format="png", bbox_inches="tight", dpi=150)
            buf.seek(0)
            images.append(base64.b64encode(buf.read()).decode("utf-8"))
            buf.close()
        plt.close("all")  # Clean up figures after capturing
    except ImportError:
        pass  # matplotlib not available

    # Capture any Plotly figures as interactive HTML + static PNG for LLM
    plotly_htmls = []
    try:
        import plotly.graph_objects as go

        for name, obj in list(globals.items()):
            if isinstance(obj, go.Figure):
                obj_id = id(obj)
                if obj_id in _captured_ids:
                    continue  # Already captured, skip
                _captured_ids.add(obj_id)
                plotly_htmls.append(obj.to_html(full_html=False, include_plotlyjs="cdn"))
                # TODO: Add static PNG export so LLM can see charts (needs kaleido)
    except ImportError:
        pass  # plotly not available

    # Capture PIL Images from globals (e.g., from Gemini image generation)
    try:
        from PIL import Image as PILImage

        def resize_for_api(img: PILImage.Image, max_size_bytes: int = 4_000_000, max_dim: int = 4096) -> bytes:
            """Resize and compress image to fit within API limits."""
            original_size = (img.width, img.height)

            # Resize if dimensions are too large
            if img.width > max_dim or img.height > max_dim:
                img.thumbnail((max_dim, max_dim), PILImage.Resampling.LANCZOS)
                print(f"Image resized: {original_size} -> {img.size} (max_dim={max_dim})")

            # Convert RGBA to RGB for JPEG (smaller file size)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            # Try JPEG with decreasing quality until under size limit
            for quality in [85, 70, 50, 30]:
                buf = BytesIO()
                img.save(buf, format="JPEG", quality=quality, optimize=True)
                if buf.tell() <= max_size_bytes:
                    if quality < 85:
                        print(f"Image compressed: quality={quality}, size={buf.tell() / 1024:.0f}KB")
                    buf.seek(0)
                    return buf.read()

            # If still too large, resize further
            while img.width > 512 or img.height > 512:
                prev_size = img.size
                img.thumbnail((img.width // 2, img.height // 2), PILImage.Resampling.LANCZOS)
                buf = BytesIO()
                img.save(buf, format="JPEG", quality=50, optimize=True)
                print(f"Image resized further: {prev_size} -> {img.size}, size={buf.tell() / 1024:.0f}KB")
                if buf.tell() <= max_size_bytes:
                    buf.seek(0)
                    return buf.read()

            buf.seek(0)
            return buf.read()

        for name, obj in list(globals.items()):
            if isinstance(obj, PILImage.Image):
                obj_id = id(obj)
                if obj_id in _captured_ids:
                    continue  # Already captured, skip
                _captured_ids.add(obj_id)
                img_bytes = resize_for_api(obj)
                images.append(base64.b64encode(img_bytes).decode("utf-8"))
    except ImportError:
        pass  # Pillow not available

    with open(os.path.join(IO_DATA_DIR, f"{command_id}.txt"), "w") as f:
        f.write(
            json.dumps(
                {
                    "stdout": stdout_io.getvalue(),
                    "stderr": stderr_io.getvalue(),
                    "images": images,
                    "plotly_htmls": plotly_htmls,
                }
            )
        )
