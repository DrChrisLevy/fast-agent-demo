import json
import os
import time
from contextlib import contextmanager
from typing import Any, Dict, Generator, Literal, Optional
from uuid import uuid4

import modal


def get_script_as_string(filepath: str) -> str:
    with open(filepath, "r") as file:
        code_string = file.read()
        return code_string


DEFAULT_RETRY_DELAY = 0.1
# Maximum runtime allowed for code execution in the sandbox (in seconds).
# This translates to the max time we'll wait for the output file to be created.
MAXIMUM_CODE_RUNTIME = 300
MAXIMUM_OPEN_FILE_ATTEMPTS = int(MAXIMUM_CODE_RUNTIME / DEFAULT_RETRY_DELAY)

IO_DATA_DIR = "/modal/io"
STDIN_FILE = os.path.join(IO_DATA_DIR, "stdin.txt")

# Maximum lifetime of the sandbox in seconds (2 hours)
SANDBOX_TIMEOUT = 2 * 60 * 60
# Time in seconds sandbox can be idle before being terminated (30 minutes)
SANDBOX_IDLE_TIMEOUT = 30 * 60
# Default CPU cores for sandbox
SANDBOX_CPU = 4.0
# Default memory in MiB for sandbox (4 GiB)
SANDBOX_MEMORY = 4096


class ModalSandbox:
    IMAGE = (
        modal.Image.debian_slim()
        .pip_install("pandas", "tabulate")
        .env(
            {
                "IO_DATA_DIR": IO_DATA_DIR,
                "STDIN_FILE": STDIN_FILE,
            }
        )
        # Define the directory/file on the image level to ensure they exist
        # before the driver program starts. This avoids potential race conditions,
        # with reading/writing to the file (e.g file not being created yet when calling `run_code`)
        .run_commands(
            [
                f"mkdir -p {IO_DATA_DIR} && touch {STDIN_FILE}",
            ]
        )
    )

    def __init__(
        self,
        sandbox_id: Optional[str] = None,
        init_script: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        # check if running Sandbox already exists
        if sandbox_id is not None:
            existing_sb = self._get_running_sandbox_from_id(sandbox_id)
            if existing_sb is not None:
                self.sandbox = existing_sb
                return

        app = modal.App.lookup("python-sandbox", create_if_missing=True)
        driver_program = get_script_as_string("agents/driver_program.py")
        # Use provided values or fall back to defaults
        timeout = kwargs.pop("timeout", SANDBOX_TIMEOUT)
        idle_timeout = kwargs.pop("idle_timeout", SANDBOX_IDLE_TIMEOUT)
        cpu = kwargs.pop("cpu", SANDBOX_CPU)
        memory = kwargs.pop("memory", SANDBOX_MEMORY)
        self.sandbox = modal.Sandbox.create(
            "python",
            "-c",
            driver_program,
            image=self.IMAGE,
            app=app,
            timeout=timeout,
            idle_timeout=idle_timeout,
            cpu=cpu,
            memory=memory,
            **kwargs,
        )
        if init_script:
            self.run_code(init_script)

    @classmethod
    def _get_running_sandbox_from_id(cls, sb_id: str) -> Optional[modal.Sandbox]:
        # Returns None if the sandbox is not running or if the sb_id is not found
        # or some error occurs
        try:
            sb = modal.Sandbox.from_id(sb_id)
        except Exception:
            return None
        # check if the sandbox is running
        if sb.poll() is None:
            return sb

        return None

    @property
    def sandbox_id(self) -> str:
        return self.sandbox.object_id

    def terminate(self) -> None:
        self.sandbox.terminate()

    @contextmanager
    def _open_sandbox_file(
        self,
        file_path: str,
        mode: Literal["r", "w", "a"],
        max_attempts: int,
        retry_delay: float = DEFAULT_RETRY_DELAY,
        extra_exceptions: tuple[type[Exception], ...] | None = None,
    ) -> Generator[modal.file_io.FileIO, None, None]:
        """
        Context manager to open a file inside the Modal sandbox with retry logic.

        Occasionally, attempting to open a file within the Modal sandbox results in an unexpected
        FilesystemExecutionError (related to concurrent access). This context manager
        provides retry logic so we can consistently open the file.
        """

        extra_exceptions = extra_exceptions or ()
        retry_on_exceptions: tuple[type[Exception], ...] = (modal.exception.FilesystemExecutionError,) + extra_exceptions

        attempt = 0
        while True:
            try:
                with self.sandbox.open(file_path, mode) as f:
                    yield f
                    return
            except retry_on_exceptions as e:
                attempt += 1
                if attempt >= max_attempts:
                    raise e

                time.sleep(retry_delay)

    def run_code(self, code: str) -> Dict[str, str]:
        command_id = uuid4().hex

        # 1. Write code into a STDIN file on the sandbox.
        # - Opening the file occasionally fails unexpectedly
        # - We retry several times before raising the exception
        with self._open_sandbox_file(STDIN_FILE, "a", max_attempts=3) as f:
            f.write(json.dumps({"code": code, "command_id": command_id}))
            f.write("\n")

        # 2. The sandbox polls this STDIN file for changes,
        # executes the added code, then saves the output to a file.
        out_file = os.path.join(IO_DATA_DIR, f"{command_id}.txt")

        # 3. We poll the Sandbox to check if it has created the output file,
        # and if so, return the output from the file.
        # - FileNotFoundError is expected, until the driver program creates the output file.
        with self._open_sandbox_file(
            out_file,
            "r",
            max_attempts=MAXIMUM_OPEN_FILE_ATTEMPTS,
            extra_exceptions=(FileNotFoundError,),
        ) as f:
            result = json.load(f)
            return result
