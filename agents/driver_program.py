import json
import os
import sys
import time
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
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
IO_DATA_DIR = os.environ['IO_DATA_DIR']
STDIN_FILE = os.environ['STDIN_FILE']


def tail_f(filename: str) -> Generator[str, None, None]:
    """
    Continuously yields new lines from the file.
    """
    with open(filename, 'r') as f:
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.1)
                continue
            yield line


globals: dict[str, Any] = {}
for line in tail_f(STDIN_FILE):
    line = line.strip()
    print(f'Received line: {line} len: {len(line)}')
    if not line:
        continue

    command = json.loads(line)
    if (code := command.get('code')) is None:
        print(json.dumps({'error': 'No code to execute'}))
        continue

    if (command_id := command.get('command_id')) is None:
        print(json.dumps({'error': 'No command_id'}))
        continue

    stdout_io, stderr_io = StringIO(), StringIO()
    with redirect_stdout(stdout_io), redirect_stderr(stderr_io):
        try:
            exec(code, globals)
        except Exception as e:
            print(f'{type(e).__name__}: {e}', file=sys.stderr)

    with open(os.path.join(IO_DATA_DIR, f'{command_id}.txt'), 'w') as f:
        f.write(
            json.dumps(
                {
                    'stdout': stdout_io.getvalue(),
                    'stderr': stderr_io.getvalue(),
                }
            )
        )
