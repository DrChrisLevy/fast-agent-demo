import time
from io import StringIO
from textwrap import dedent
from unittest.mock import MagicMock, patch
from uuid import uuid4

import modal
import pytest

from vision_ai_backend.controllers.intents.coding_agent.modal_sandbox import (
    ModalSandbox as Sandbox,
)
from vision_ai_backend.controllers.intents.coding_agent.modal_sandbox import (
    get_or_create_sandbox_from_conversation_id,
)


@pytest.mark.skip(
    reason='Creates real Modal sandboxes - too slow for CI. Can still be run locally.'
)
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
            'stdout': 'Hello, World!\n',
            'stderr': '',
        }
        resp = sb.run_code('x=1')
        assert resp == {'stdout': '', 'stderr': ''}
        resp = sb.run_code('y=x+1\nprint(y)')
        assert resp == {'stdout': '2\n', 'stderr': ''}
        resp = sb.run_code('z = y ** 2\nprint(z)')
        assert resp == {'stdout': '4\n', 'stderr': ''}
        sb.terminate()

    def test_code_sandbox_test2(self):
        sb = Sandbox(init_script="print('INIT1')\nprint('INIT2')\nprint('INIT3')\nz=3.14")
        resp = sb.run_code('print(z)\nprint(z + 10)')
        assert resp == {
            'stdout': '3.14\n13.14\n',
            'stderr': '',
        }
        sb.terminate()

    def test_code_sandbox_test3(self):
        sb = Sandbox(init_script='x=1\ny=2\nz=3')
        resp = sb.run_code('print(x, y, z)')
        assert resp == {
            'stdout': '1 2 3\n',
            'stderr': '',
        }
        sb.terminate()

    def test_code_sandbox_test4(self):
        sb = Sandbox(init_script='x=1\ny=2\nz=3')
        resp = sb.run_code('print(x, y, z)')
        assert resp == {
            'stdout': '1 2 3\n',
            'stderr': '',
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
        assert 'Fibonacci sequence: [0, 1, 1, 2, 3, 5, 8, 13, 21, 34]' in resp1['stdout']

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
        assert 'Statistics for [10, 15, 20, 25, 30]:' in resp2['stdout']
        assert resp2 == {
            'stdout': 'Statistics for [10, 15, 20, 25, 30]:\n  mean: 20.0\n  median: 20.0\n  '
            'std_dev: 7.0710678118654755\n  sum: 100\n  count: 5\nGeometric mean: 18.64\n',
            'stderr': '',
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
            'stdout': 'Caught error: ZeroDivisionError: division by zero\nExecution continues\n',
            'stderr': '',
        }

        sb.terminate()

    def test_get_or_create_sandbox_from_conversation_id_with_init_script(self):
        sandboxes = modal.Dict.from_name('conversation_id_to_sandbox_id', create_if_missing=True)
        conversation_id = str(uuid4())
        assert conversation_id not in sandboxes
        init_script = "print('INIT1')\nprint('INIT2')\nprint('INIT3')\nz=3.14"
        sb = get_or_create_sandbox_from_conversation_id(conversation_id, init_script=init_script)
        sandbox_id = sb.sandbox_id
        resp = sb.run_code('print(z)\nprint(z + 10)')
        assert resp == {'stdout': '3.14\n13.14\n', 'stderr': ''}

        sb = get_or_create_sandbox_from_conversation_id(conversation_id, init_script=init_script)
        assert sb.sandbox_id == sandbox_id
        resp = sb.run_code('print(z)\nprint(z + 10)')
        assert resp == {
            'stdout': '3.14\n13.14\n',
            'stderr': '',
        }
        resp = sb.run_code('x=10\ny=8\nprint(x+y)')
        assert resp == {
            'stdout': '18\n',
            'stderr': '',
        }
        sb.terminate()
        # test that sandbox can be created again from the same conversation_id
        # even after it has been terminated
        sb = get_or_create_sandbox_from_conversation_id(conversation_id, init_script=init_script)
        resp = sb.run_code('print(z)\nprint(z + 10)')
        assert resp == {'stdout': '3.14\n13.14\n', 'stderr': ''}
        sb.terminate()

    def test_get_or_create_sandbox_from_conversation_id_without_init_script(self):
        sandboxes = modal.Dict.from_name('conversation_id_to_sandbox_id', create_if_missing=True)
        conversation_id = str(uuid4())
        assert conversation_id not in sandboxes
        sb = get_or_create_sandbox_from_conversation_id(conversation_id)
        sandbox_id = sb.sandbox_id
        sb = get_or_create_sandbox_from_conversation_id(conversation_id)
        assert sb.sandbox_id == sandbox_id
        resp = sb.run_code('z=3.14\nprint(z)\nprint(z + 10)')
        assert resp == {
            'stdout': '3.14\n13.14\n',
            'stderr': '',
        }
        sb = get_or_create_sandbox_from_conversation_id(conversation_id)
        resp = sb.run_code('print(z)\nprint(z + 10)')
        assert resp == {
            'stdout': '3.14\n13.14\n',
            'stderr': '',
        }
        resp = sb.run_code('x=10\ny=8\nprint(x+y)')
        assert resp == {
            'stdout': '18\n',
            'stderr': '',
        }
        sb.terminate()

    def test_get_running_sandbox_from_id(self):
        assert Sandbox._get_running_sandbox_from_id(uuid4()) is None
        sb = Sandbox()
        sb.run_code('x=2')
        sb.run_code('y=4')
        sb = Sandbox(sandbox_id=sb.sandbox_id)
        resp = sb.run_code('print(x+y)')
        assert resp == {
            'stdout': '6\n',
            'stderr': '',
        }
        sb.terminate()

    def test_slow_command(self):
        sb = Sandbox()
        slow_command = dedent(
            """
        import time
        time.sleep(2)
        print("Hello, world!")
        """
        )
        res = sb.run_code(slow_command)
        assert res['stdout'] == 'Hello, world!\n'
        sb.terminate()

    def test_timeout_kills_sandbox_despite_activity(self):
        """Test that overall timeout expires even when run_code is called regularly."""
        sb = Sandbox(timeout=20, idle_timeout=60)

        with pytest.raises(Exception):
            # try to keep sandbox alive with regular activity
            for i in range(5):  # 5 iterations * 5s = 25s > 20s timeout
                sb.run_code(f"print('iteration {i}')")
                time.sleep(5)

    def test_idle_timeout_kills_sandbox_without_activity(self):
        """Test that idle_timeout kills sandbox when no activity between calls."""
        sb = Sandbox(timeout=60, idle_timeout=10)

        sb.run_code("print('first command')")
        time.sleep(12)  # wait longer than idle_timeout

        with pytest.raises(Exception):
            sb.run_code("print('should fail')")

    def test_run_code_resets_idle_timeout(self):
        """Test that run_code calls reset the idle_timeout."""
        sb = Sandbox(timeout=60, idle_timeout=10)

        # make 3 calls with 7s intervals (< 10s idle_timeout)
        # sandbox should stay alive
        for i in range(3):
            resp = sb.run_code(f"print('iteration {i}')")
            assert f'iteration {i}' in resp['stdout']
            time.sleep(7)

        sb.terminate()

    def test_open_sandbox_file_retries_on_exceptions(self):
        """
        This test exposes an intermittent issue seen when rapidly creating new sandboxes and
        executing code in quick succession. After several iterations, attempts to open the STDIN
        file may raise a "FilesystemExecutionError". Running this code locally can reproduce
        the problem.
        """
        exception: Exception | None = None

        try:
            for i in range(50):
                sb = Sandbox(timeout=10, idle_timeout=10)
                sb.run_code('x=1')
                print(f'Successfully ran code {i}')
                sb.terminate()
        except Exception as e:
            exception = e

        assert exception is None, f'Expected no exception, but got {exception}'


class TestMockedModalSandbox:
    """
    This class contains tests verifying the behavior of the ModalSandbox class,
    using mocks to avoid launching real modal sandboxes or making external API calls.
    """

    @pytest.fixture(autouse=True)
    def mock_time_sleep(self):
        # mock time.sleep to avoid actual delays
        with patch('time.sleep') as mock_sleep:
            mock_sleep.return_value = None
            yield mock_sleep

    @pytest.fixture
    def mock_sandbox(self):
        """Fixture that mocks Modal sandbox creation to avoid real API calls."""
        with (
            patch(
                'vision_ai_backend.controllers.intents.coding_agent.modal_sandbox.modal.App.lookup'
            ) as mock_app_lookup,
            patch(
                'vision_ai_backend.controllers.intents.coding_agent.modal_sandbox.modal.Sandbox.create'
            ) as mock_sandbox_create,
        ):
            mock_app = MagicMock()
            mock_app_lookup.return_value = mock_app

            mock_sb = MagicMock(object_id='test-sandbox-id')
            mock_sandbox_create.return_value = mock_sb

            yield mock_sb

    def test_open_sandbox_file_retries_on_filesystem_execution_error(self, mock_sandbox):
        code_snippet = 'x=1'
        mock_file = StringIO(code_snippet)

        mock_sandbox.open.side_effect = [
            modal.exception.FilesystemExecutionError(),
            modal.exception.FilesystemExecutionError(),
            modal.exception.FilesystemExecutionError(),
            mock_file,
        ]

        sb = Sandbox()

        with sb._open_sandbox_file('/test/file.txt', 'r', max_attempts=10) as f:
            content = f.read()
            assert content == code_snippet

        assert mock_sandbox.open.call_count == 4

    def test_open_sandbox_file_raises_exception_on_max_attempts_reached(self, mock_sandbox):
        mock_sandbox.open.side_effect = modal.exception.FilesystemExecutionError()

        sb = Sandbox()

        with pytest.raises(modal.exception.FilesystemExecutionError):
            with sb._open_sandbox_file('/test/file.txt', 'r', max_attempts=1) as _f:
                pass

        assert mock_sandbox.open.call_count == 1

    def test_open_sandbox_file_accepts_extra_exceptions(self, mock_sandbox):
        code_snippet = 'x=1'
        mock_file = StringIO(code_snippet)

        mock_sandbox.open.side_effect = [
            modal.exception.FilesystemExecutionError(),
            FileNotFoundError(),
            mock_file,
        ]

        sb = Sandbox()

        with sb._open_sandbox_file(
            '/test/file.txt', 'r', max_attempts=10, extra_exceptions=(FileNotFoundError,)
        ) as f:
            content = f.read()
            assert content == code_snippet

        assert mock_sandbox.open.call_count == 3

    def test_open_sandbox_file_raises_unexpected_exception(self, mock_sandbox):
        mock_sandbox.open.side_effect = ValueError()

        sb = Sandbox()

        with pytest.raises(ValueError):
            with sb._open_sandbox_file('/test/file.txt', 'r', max_attempts=10) as _f:
                pass

        assert mock_sandbox.open.call_count == 1
