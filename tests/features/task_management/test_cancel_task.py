from __future__ import annotations

import sys
import subprocess
from typing import List

from tqm import TQManager, TaskBuilder, TaskGroupBuilder
from tqm._core.task_executor import TaskExecutor

from ...utils import raise_error
from ...utils.harness import StepPool


def start(executor: TaskExecutor, *tasks) -> None:
    for task in tasks:
        executor.add_task(task)
    executor.start_workers()


def test_running_task_sees_the_flag_and_ends_cancelled(executor: TaskExecutor, step_pool: StepPool):
    seen: List[bool] = []
    completed: List[str] = []
    finished: List[str] = []
    task = (
        TaskBuilder('Render')
        .with_event(lambda t: seen.append(t.cancel_requested))
        .with_on_completed(lambda t: completed.append(t.name))
        .with_on_finish(lambda t: finished.append(t.name))
        .build()
    )
    start(executor, task)
    assert task.state.is_running

    executor.cancel_task(task)
    assert task.state.is_running  # the thread still has to stop
    step_pool.step()

    assert seen == [True]
    assert task.state.is_cancelled
    assert completed == []
    assert finished == ['Render']


def test_cancelled_task_that_raises_is_not_retried(executor: TaskExecutor, step_pool: StepPool):
    task = TaskBuilder().with_event(raise_error).with_retry(max_attempts=3).build()
    start(executor, task)

    executor.cancel_task(task)
    step_pool.step()

    # A retry would have moved it to RETRYING.
    assert task.state.is_cancelled


def test_hooks_run_once_and_a_failing_hook_does_not_stop_the_rest(executor: TaskExecutor, step_pool: StepPool):
    calls: List[str] = []

    def bad_hook() -> None:
        raise RuntimeError('hook broke')

    task = TaskBuilder().build()
    start(executor, task)
    # Registered here, as the callable would while it runs.
    task.on_cancel(bad_hook)
    task.on_cancel(lambda: calls.append('kill'))

    executor.cancel_task(task)
    executor.cancel_task(task)

    assert calls == ['kill']
    step_pool.drain()


def test_hook_added_after_cancel_runs_at_once(executor: TaskExecutor, step_pool: StepPool):
    calls: List[str] = []
    task = TaskBuilder().with_event(lambda t: t.on_cancel(lambda: calls.append('late'))).build()
    start(executor, task)

    executor.cancel_task(task)
    step_pool.step()

    assert calls == ['late']


def test_waiting_task_is_cancelled_without_running(executor: TaskExecutor, step_pool: StepPool):
    runs: List[str] = []
    executor.set_max_workers(2)
    busy = [TaskBuilder().build() for _ in range(2)]
    waiting = TaskBuilder('Waiting').with_event(lambda t: runs.append(t.name)).build()
    start(executor, *busy, waiting)
    assert waiting.state.is_waiting

    executor.cancel_task(waiting)
    step_pool.drain()

    assert waiting.state.is_cancelled
    assert runs == []


def test_children_of_a_cancelled_task_are_cancelled(executor: TaskExecutor, step_pool: StepPool):
    parent = TaskBuilder('Parent').build()
    child = TaskBuilder('Child').with_wait_for(parent).build()
    start(executor, parent, child)
    assert child.state.is_blocked

    executor.cancel_task(parent)
    step_pool.drain()

    assert parent.state.is_cancelled
    assert child.state.is_cancelled


def test_cancel_on_a_group_cancels_every_member(executor: TaskExecutor, step_pool: StepPool):
    executor.set_max_workers(2)
    members = [TaskBuilder(f'M{i}').build() for i in range(4)]
    group = TaskGroupBuilder('G').with_tasks(*members).build()
    start(executor, group)
    assert group.state.is_running

    executor.cancel_task(group)
    step_pool.drain()

    assert all(member.state.is_cancelled for member in members)
    assert group.state.is_cancelled


def test_cancelling_one_member_cancels_the_group_once_it_settles(executor: TaskExecutor, step_pool: StepPool):
    ok = TaskBuilder('Ok').build()
    stopped = TaskBuilder('Stopped').build()
    group = TaskGroupBuilder('G').with_tasks(ok, stopped).build()
    start(executor, group)

    executor.cancel_task(stopped)
    step_pool.drain()

    assert ok.state.is_completed
    assert stopped.state.is_cancelled
    assert group.state.is_cancelled


def test_cancelled_task_can_be_retried_and_runs_clean(executor: TaskExecutor, step_pool: StepPool):
    seen: List[bool] = []
    task = TaskBuilder().with_event(lambda t: seen.append(t.cancel_requested)).build()
    start(executor, task)
    executor.cancel_task(task)
    step_pool.step()

    executor.retry_task(task)
    step_pool.step()

    assert seen == [True, False]
    assert task.state.is_completed


def test_cancelled_task_can_be_removed(executor: TaskExecutor, step_pool: StepPool):
    task = TaskBuilder().build()
    start(executor, task)
    executor.cancel_task(task)
    step_pool.step()

    executor.remove_task(task)

    assert task.state.is_deleted


def test_cancel_on_a_finished_task_does_nothing(executor: TaskExecutor, step_pool: StepPool):
    task = TaskBuilder().build()
    start(executor, task)
    step_pool.step()

    executor.cancel_task(task)

    assert task.state.is_completed
    assert not task.cancel_requested


def test_manager_cancel_tasks(make_manager):
    manager: TQManager = make_manager('cancel')
    task = TaskBuilder().with_predicate(lambda: False, max_attempts=5, delay_ms=60000).build()
    manager.add_tasks(task)
    manager.start_workers()
    assert task.state.is_blocked

    manager.cancel_tasks(task)

    assert task.state.is_cancelled


def test_hook_stops_a_real_subprocess(qtbot, app: TQManager):
    procs: List[subprocess.Popen] = []

    def render(task) -> None:
        proc = subprocess.Popen([sys.executable, '-c', 'import threading; threading.Event().wait(30)'])
        procs.append(proc)
        task.on_cancel(proc.terminate)
        proc.wait()

    task = TaskBuilder('Render').with_event(render).build()
    app.add_tasks(task)
    app.start_workers()
    qtbot.wait_until(lambda: bool(procs), timeout=5000)

    app.cancel_tasks(task)

    qtbot.wait_until(lambda: task.state.is_cancelled, timeout=5000)
    assert procs[0].poll() is not None


def test_child_added_after_its_parent_was_cancelled_is_cancelled(executor: TaskExecutor, step_pool: StepPool):
    parent = TaskBuilder('Parent').build()
    start(executor, parent)
    executor.cancel_task(parent)
    step_pool.drain()

    child = TaskBuilder('Child').with_wait_for(parent).build()
    start(executor, child)

    assert child.state.is_cancelled


def test_retry_on_a_group_reruns_its_cancelled_member(executor: TaskExecutor, step_pool: StepPool):
    ok = TaskBuilder('Ok').build()
    stopped = TaskBuilder('Stopped').build()
    group = TaskGroupBuilder('G').with_tasks(ok, stopped).build()
    start(executor, group)
    executor.cancel_task(stopped)
    step_pool.drain()
    assert group.state.is_cancelled

    executor.retry_task(group)
    step_pool.drain()

    assert stopped.state.is_completed
    assert group.state.is_completed
