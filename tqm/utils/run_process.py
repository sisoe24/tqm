from __future__ import annotations

import os
import sys
import signal
import threading
import contextlib
import subprocess
from typing import TYPE_CHECKING, Any, List, Union, Optional, Sequence
from collections import deque

from ..exceptions import TaskCancelled

if TYPE_CHECKING:
    from .._core.task import TaskExecutable

_STOP_TIMEOUT_SEC = 5
_TAIL_LINES = 20


def _stop_process_tree(proc: subprocess.Popen) -> None:
    """Stop the process and every process it started.

    `terminate` alone leaves the children running, and a child that still holds
    stdout keeps the output loop waiting.
    """
    if sys.platform == 'win32':
        subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)], capture_output=True, check=False)
        return

    # The process runs in its own session, so its pid is also its process group id.
    with contextlib.suppress(ProcessLookupError):
        os.killpg(proc.pid, signal.SIGTERM)

    with contextlib.suppress(subprocess.TimeoutExpired):
        proc.wait(timeout=_STOP_TIMEOUT_SEC)

    # Whatever is left in the group, for example a child that ignored SIGTERM.
    with contextlib.suppress(ProcessLookupError):
        os.killpg(proc.pid, signal.SIGKILL)


def _stop_in_background(proc: subprocess.Popen) -> None:
    # The cancel hook runs on the main thread, and a stop can wait up to _STOP_TIMEOUT_SEC.
    threading.Thread(target=_stop_process_tree, args=(proc,), daemon=True).start()


def run_process(
    task: TaskExecutable,
    cmd: Union[str, Sequence[str]],
    *,
    timeout: Optional[float] = None,
    **popen_kwargs: Any,
) -> None:
    """Run `cmd` in a subprocess and stop it when the user stops the task.

    stdout and stderr go to the task log line by line. A stop or a timeout kills
    the whole process tree, not only the process.

    ```
    def render(task):
        run_process(task, ['nuke', '-x', script], timeout=3600)
    ```

    Args:
        task: The running task. The first argument of the task callable.
        cmd: The command, as for `subprocess.Popen`.
        timeout: Wall time in seconds. When it runs out, the process is killed.
        popen_kwargs: Other `subprocess.Popen` arguments, for example `cwd` or `env`.
            Do not pass `stdout` or `stderr`.

    Raises:
        TaskCancelled: The user stopped the task. The task ends cancelled.
        subprocess.TimeoutExpired: The process ran longer than `timeout`.
        subprocess.CalledProcessError: The process exited with a non-zero code.
            Its `output` holds the last lines of output.
    """
    popen_kwargs.setdefault('encoding', 'utf-8')
    popen_kwargs.setdefault('errors', 'replace')
    if sys.platform == 'win32':
        popen_kwargs.setdefault('creationflags', subprocess.CREATE_NEW_PROCESS_GROUP)
    else:
        popen_kwargs.setdefault('start_new_session', True)

    tail: deque[str] = deque(maxlen=_TAIL_LINES)
    timed_out: List[bool] = []

    def on_cancel() -> None:
        # The hook outlives this call. Once the process is reaped, its pid can be reused.
        if proc.returncode is None:
            _stop_in_background(proc)

    def on_timeout() -> None:
        timed_out.append(True)
        _stop_process_tree(proc)

    with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **popen_kwargs) as proc:
        task.on_cancel(on_cancel)

        timer = threading.Timer(timeout, on_timeout) if timeout is not None else None
        if timer:
            timer.daemon = True
            timer.start()

        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                line = line.rstrip('\r\n')
                tail.append(line)
                task.log(line)
            proc.wait()
        finally:
            if timer:
                timer.cancel()

    if task.cancel_requested:
        raise TaskCancelled(f'{task.name} stopped by user')

    if timed_out:
        raise subprocess.TimeoutExpired(cmd, timeout or 0, output='\n'.join(tail))

    if proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, cmd, output='\n'.join(tail))
