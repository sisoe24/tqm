from __future__ import annotations

import os
import sys
import time
import threading
import subprocess
from typing import List

import pytest

from tqm import TQManager, TaskBuilder
from tqm.utils import run_process
from tqm.exceptions import TaskCancelled
from tqm._core.task import TaskExecutable


def python(code: str) -> List[str]:
    return [sys.executable, '-u', '-c', code]


@pytest.fixture()
def task() -> TaskExecutable:
    return TaskBuilder('Render').build()


@pytest.fixture()
def logs(task: TaskExecutable, monkeypatch: pytest.MonkeyPatch) -> List[str]:
    lines: List[str] = []
    monkeypatch.setattr(task, 'log', lines.append)
    return lines


def cancel_later(task: TaskExecutable, delay: float = 0.3) -> None:
    threading.Timer(delay, task._request_cancel).start()


def test_output_streams_to_the_task_log(task: TaskExecutable, logs: List[str]):
    run_process(task, python('import sys; print("out"); print("err", file=sys.stderr)'))

    assert sorted(logs) == ['err', 'out']


def test_non_zero_exit_raises_with_the_output_tail(task: TaskExecutable, logs: List[str]):
    with pytest.raises(subprocess.CalledProcessError) as error:
        run_process(task, python('print("boom"); raise SystemExit(3)'))

    assert error.value.returncode == 3
    assert error.value.output == 'boom'


def test_timeout_kills_the_process_and_raises(task: TaskExecutable, logs: List[str]):
    start = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        run_process(task, python('import time; time.sleep(30)'), timeout=0.3)

    assert time.monotonic() - start < 10


def test_stop_raises_task_cancelled(task: TaskExecutable, logs: List[str]):
    cancel_later(task)
    start = time.monotonic()
    with pytest.raises(TaskCancelled):
        run_process(task, python('import time; time.sleep(30)'))

    assert time.monotonic() - start < 10


def test_stop_before_start_raises_task_cancelled(task: TaskExecutable, logs: List[str]):
    task._request_cancel()

    with pytest.raises(TaskCancelled):
        run_process(task, python('import time; time.sleep(30)'))


@pytest.mark.skipif(sys.platform == 'win32', reason='checks the pid with os.kill')
def test_stop_kills_the_child_processes(task: TaskExecutable, logs: List[str]):
    # The command starts a child that would outlive a plain terminate.
    code = (
        'import subprocess, sys, time\n'
        'child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])\n'
        'print(child.pid)\n'
        'time.sleep(30)\n'
    )
    cancel_later(task, delay=1.0)
    with pytest.raises(TaskCancelled):
        run_process(task, python(code))

    child_pid = int(logs[0])
    for _ in range(50):
        try:
            os.kill(child_pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.1)
    pytest.fail(f'child {child_pid} is still alive')


def test_stop_from_the_manager_ends_the_task_cancelled(qtbot, app: TQManager):
    started: List[bool] = []

    def render(task: TaskExecutable) -> None:
        started.append(True)
        run_process(task, python('import time; time.sleep(30)'))

    task = TaskBuilder('Render').with_event(render).build()
    app.add_tasks(task)
    app.start_workers()
    qtbot.wait_until(lambda: bool(started), timeout=5000)

    app.cancel_tasks(task)

    qtbot.wait_until(lambda: task.state.is_cancelled, timeout=10000)
