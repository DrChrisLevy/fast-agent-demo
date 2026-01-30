import time
from io import StringIO
from textwrap import dedent
from unittest.mock import MagicMock, patch
from uuid import uuid4

import modal
import pytest

from agents.coding_sandbox import ModalSandbox as Sandbox


@pytest.mark.slow
class TestRealModalSandbox:
    """
    This class contains integration tests for the ModalSandbox class,
    which launch real Modal sandboxes to verify end-to-end functionality. The
    tests are too slow to run in CI, but can be run locally to verify code changes.

    For unit tests that can run in the CI, see TestMockedModalSandbox below, which
    mocks the Modal sandbox to avoid launching real sandboxes.
    """

    def test_code_sandbox_test1(self):
        sb = Sandbox()
        resp = sb.run_code('print("Hello, World!")')
        assert resp == {
            "stdout": "Hello, World!\n",
            "stderr": "",
            "images": [],
            "plotly_htmls": [],
        }
        resp = sb.run_code("x=1")
        assert resp == {"stdout": "", "stderr": "", "images": [], "plotly_htmls": []}
        resp = sb.run_code("y=x+1\nprint(y)")
        assert resp == {"stdout": "2\n", "stderr": "", "images": [], "plotly_htmls": []}
        resp = sb.run_code("z = y ** 2\nprint(z)")
        assert resp == {"stdout": "4\n", "stderr": "", "images": [], "plotly_htmls": []}
        sb.terminate()

    def test_code_sandbox_test2(self):
        sb = Sandbox(init_script="print('INIT1')\nprint('INIT2')\nprint('INIT3')\nz=3.14")
        resp = sb.run_code("print(z)\nprint(z + 10)")
        assert resp == {
            "stdout": "3.14\n13.14\n",
            "stderr": "",
            "images": [],
            "plotly_htmls": [],
        }
        sb.terminate()

    def test_code_sandbox_test3(self):
        sb = Sandbox(init_script="x=1\ny=2\nz=3")
        resp = sb.run_code("print(x, y, z)")
        assert resp == {
            "stdout": "1 2 3\n",
            "stderr": "",
            "images": [],
            "plotly_htmls": [],
        }
        sb.terminate()

    def test_code_sandbox_test4(self):
        sb = Sandbox(init_script="x=1\ny=2\nz=3")
        resp = sb.run_code("print(x, y, z)")
        assert resp == {
            "stdout": "1 2 3\n",
            "stderr": "",
            "images": [],
            "plotly_htmls": [],
        }
        sb.terminate()

    def test_code_sandbox_test5(self):
        # Create a sandbox with initialization code that defines helper functions and variables
        init_script = dedent(
            """
        import math
        import numpy as np
        def calculate_statistics(numbers):
            return {
                'mean': np.mean(numbers),
                'median': np.median(numbers),
                'std_dev': np.std(numbers),
                'sum': sum(numbers),
                'count': len(numbers)
            }
        data = [10, 15, 20, 25, 30]
        """
        )
        sb = Sandbox(init_script=init_script)

        # Test 1: Execute a multiline code that creates a function and calls it
        code1 = dedent(
            """
        def fibonacci(n):
            a, b = 0, 1
            sequence = []
            for _ in range(n):
                sequence.append(a)
                a, b = b, a + b
            return sequence

        fib_sequence = fibonacci(10)
        print(f"Fibonacci sequence: {fib_sequence}")
        """
        )
        resp1 = sb.run_code(code1)
        assert "Fibonacci sequence: [0, 1, 1, 2, 3, 5, 8, 13, 21, 34]" in resp1["stdout"]

        # Test 2: Use previously defined functions and variables
        code2 = dedent(
            """
        # Calculate statistics on the predefined data
        stats = calculate_statistics(data)
        print(f"Statistics for {data}:")
        for key, value in stats.items():
            print(f"  {key}: {value}")

        # Calculate additional metrics
        geometric_mean = math.exp(np.mean(np.log(data)))
        print(f"Geometric mean: {geometric_mean:.2f}")
        """
        )
        resp2 = sb.run_code(code2)
        assert "Statistics for [10, 15, 20, 25, 30]:" in resp2["stdout"]
        assert resp2 == {
            "stdout": "Statistics for [10, 15, 20, 25, 30]:\n  mean: 20.0\n  median: 20.0\n  "
            "std_dev: 7.0710678118654755\n  sum: 100\n  count: 5\nGeometric mean: 18.64\n",
            "stderr": "",
            "images": [],
            "plotly_htmls": [],
        }

        # Test 3: Handle errors gracefully
        code3 = dedent(
            """
        try:
            # This will cause a ZeroDivisionError
            result = 1 / 0
        except Exception as e:
            print(f"Caught error: {type(e).__name__}: {e}")

        # The execution should continue past the error
        print("Execution continues")
        """
        )
        resp3 = sb.run_code(code3)
        assert resp3 == {
            "stdout": "Caught error: ZeroDivisionError: division by zero\nExecution continues\n",
            "stderr": "",
            "images": [],
            "plotly_htmls": [],
        }

        sb.terminate()

    def test_get_running_sandbox_from_id(self):
        assert Sandbox._get_running_sandbox_from_id(uuid4()) is None
        sb = Sandbox()
        sb.run_code("x=2")
        sb.run_code("y=4")
        sb = Sandbox(sandbox_id=sb.sandbox_id)
        resp = sb.run_code("print(x+y)")
        assert resp == {
            "stdout": "6\n",
            "stderr": "",
            "images": [],
            "plotly_htmls": [],
        }
        sb.terminate()

    def test_slow_command(self):
        sb = Sandbox()
        slow_command = dedent(
            """
        import time
        time.sleep(1)
        print("Hello, world!")
        """
        )
        res = sb.run_code(slow_command)
        assert res["stdout"] == "Hello, world!\n"
        sb.terminate()

    def test_matplotlib_plot_returns_image(self):
        """Test that matplotlib plots are captured and returned as base64 images."""
        sb = Sandbox()
        plot_code = dedent(
            """
        import matplotlib
        matplotlib.use('Agg')  # Non-interactive backend
        import matplotlib.pyplot as plt
        import matplotlib.patches as patches

        fig, ax = plt.subplots(figsize=(4, 4))
        rect = patches.Rectangle((0.2, 0.2), 0.6, 0.6, facecolor='blue')
        ax.add_patch(rect)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_title('Blue Rectangle')
        print("Plot created")
        """
        )
        res = sb.run_code(plot_code)
        assert res["stdout"] == "Plot created\n"
        assert res["stderr"] == ""
        assert len(res["images"]) == 1
        # Verify it's valid base64 (should be decodable)
        import base64

        decoded = base64.b64decode(res["images"][0])
        # PNG files start with these magic bytes
        assert decoded[:8] == b"\x89PNG\r\n\x1a\n"
        sb.terminate()

    def test_multiple_matplotlib_plots_returns_multiple_images(self):
        """Test that multiple matplotlib figures are all captured."""
        sb = Sandbox()
        plot_code = dedent(
            """
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        # Create first figure
        fig1, ax1 = plt.subplots()
        ax1.plot([1, 2, 3], [1, 2, 3])
        ax1.set_title('Figure 1')

        # Create second figure
        fig2, ax2 = plt.subplots()
        ax2.bar(['a', 'b', 'c'], [3, 2, 1])
        ax2.set_title('Figure 2')

        print("Two plots created")
        """
        )
        res = sb.run_code(plot_code)
        assert res["stdout"] == "Two plots created\n"
        assert len(res["images"]) == 2
        sb.terminate()

    def test_timeout_kills_sandbox_despite_activity(self):
        """Test that overall timeout expires even when run_code is called regularly."""
        sb = Sandbox(timeout=10, idle_timeout=30)

        with pytest.raises(Exception):
            # try to keep sandbox alive with regular activity
            for i in range(5):  # 5 iterations * 3s = 15s > 10s timeout
                sb.run_code(f"print('iteration {i}')")
                time.sleep(3)

    def test_idle_timeout_kills_sandbox_without_activity(self):
        """Test that idle_timeout kills sandbox when no activity between calls."""
        sb = Sandbox(timeout=30, idle_timeout=3)

        sb.run_code("print('first command')")
        time.sleep(5)  # wait longer than idle_timeout

        with pytest.raises(Exception):
            sb.run_code("print('should fail')")

    def test_run_code_resets_idle_timeout(self):
        """Test that run_code calls reset the idle_timeout."""
        sb = Sandbox(timeout=30, idle_timeout=4)

        # make 3 calls with 2s intervals (< 4s idle_timeout)
        # sandbox should stay alive
        for i in range(3):
            resp = sb.run_code(f"print('iteration {i}')")
            assert f"iteration {i}" in resp["stdout"]
            time.sleep(2)

        sb.terminate()

    # def test_open_sandbox_file_retries_on_exceptions(self):
    #     """
    #     This test exposes an intermittent issue seen when rapidly creating new sandboxes and
    #     executing code in quick succession. After several iterations, attempts to open the STDIN
    #     file may raise a "FilesystemExecutionError". Running this code locally can reproduce
    #     the problem.
    #     """
    #     exception: Exception | None = None

    #     try:
    #         for i in range(50):
    #             sb = Sandbox(timeout=10, idle_timeout=10)
    #             sb.run_code("x=1")
    #             print(f"Successfully ran code {i}")
    #             sb.terminate()
    #     except Exception as e:
    #         exception = e

    #     assert exception is None, f"Expected no exception, but got {exception}"


class TestMockedModalSandbox:
    """
    This class contains tests verifying the behavior of the ModalSandbox class,
    using mocks to avoid launching real modal sandboxes or making external API calls.
    """

    @pytest.fixture(autouse=True)
    def mock_time_sleep(self):
        # mock time.sleep to avoid actual delays
        with patch("time.sleep") as mock_sleep:
            mock_sleep.return_value = None
            yield mock_sleep

    @pytest.fixture
    def mock_sandbox(self):
        """Fixture that mocks Modal sandbox creation to avoid real API calls."""
        with (
            patch("agents.coding_sandbox.modal.App.lookup") as mock_app_lookup,
            patch("agents.coding_sandbox.modal.Sandbox.create") as mock_sandbox_create,
        ):
            mock_app = MagicMock()
            mock_app_lookup.return_value = mock_app

            mock_sb = MagicMock(object_id="test-sandbox-id")
            mock_sandbox_create.return_value = mock_sb

            yield mock_sb

    def test_open_sandbox_file_retries_on_filesystem_execution_error(self, mock_sandbox):
        code_snippet = "x=1"
        mock_file = StringIO(code_snippet)

        mock_sandbox.open.side_effect = [
            modal.exception.FilesystemExecutionError(),
            modal.exception.FilesystemExecutionError(),
            modal.exception.FilesystemExecutionError(),
            mock_file,
        ]

        sb = Sandbox()

        with sb._open_sandbox_file("/test/file.txt", "r", max_attempts=10) as f:
            content = f.read()
            assert content == code_snippet

        assert mock_sandbox.open.call_count == 4

    def test_open_sandbox_file_raises_exception_on_max_attempts_reached(self, mock_sandbox):
        mock_sandbox.open.side_effect = modal.exception.FilesystemExecutionError()

        sb = Sandbox()

        with pytest.raises(modal.exception.FilesystemExecutionError):
            with sb._open_sandbox_file("/test/file.txt", "r", max_attempts=1) as _f:
                pass

        assert mock_sandbox.open.call_count == 1

    def test_open_sandbox_file_accepts_extra_exceptions(self, mock_sandbox):
        code_snippet = "x=1"
        mock_file = StringIO(code_snippet)

        mock_sandbox.open.side_effect = [
            modal.exception.FilesystemExecutionError(),
            FileNotFoundError(),
            mock_file,
        ]

        sb = Sandbox()

        with sb._open_sandbox_file("/test/file.txt", "r", max_attempts=10, extra_exceptions=(FileNotFoundError,)) as f:
            content = f.read()
            assert content == code_snippet

        assert mock_sandbox.open.call_count == 3

    def test_open_sandbox_file_raises_unexpected_exception(self, mock_sandbox):
        mock_sandbox.open.side_effect = ValueError()

        sb = Sandbox()

        with pytest.raises(ValueError):
            with sb._open_sandbox_file("/test/file.txt", "r", max_attempts=10) as _f:
                pass

        assert mock_sandbox.open.call_count == 1
