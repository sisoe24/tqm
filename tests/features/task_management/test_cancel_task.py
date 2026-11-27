from __future__ import annotations

import sys
import subprocess
from typing import List, Callable

import pytest

from tqm import TQManager, TaskBuilder, TaskGroupBuilder
from tqm._core.task import TaskExecutable
from tqm._core.task_executor import TaskExecutor

from ...utils import raise_error
from ...utils.harness import StepPool


def start(executor: TaskExecutor, *tasks) -> None:
    for task in tasks:
        executor.add_task(task)
    executor.start_workers()


def stoppable(name: str = '') -> TaskBuilder:
    return TaskBuilder(name).with_event(lambda t: None, cancellable=True)


def test_running_task_sees_the_flag_and_ends_cancelled(executor: TaskExecutor, step_pool: StepPool):
    seen: List[bool] = []
    completed: List[str] = []
    finished: List[str] = []
    task = (
        TaskBuilder('Render')
        .with_event(lambda t: seen.append(t.cancel_requested), cancellable=True)
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
    task = TaskBuilder().with_event(raise_error, cancellable=True).with_retry(max_attempts=3).build()
    start(executor, task)

    executor.cancel_task(task)
    step_pool.step()

    # A retry would have moved it to RETRYING.
    assert task.state.is_cancelled


def test_hooks_run_once_and_a_failing_hook_does_not_stop_the_rest(executor: TaskExecutor, step_pool: StepPool):
    calls: List[str] = []

    def bad_hook() -> None:
        raise RuntimeError('hook broke')

    task = stoppable().build()
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
    task = TaskBuilder().with_event(lambda t: t.on_cancel(lambda: calls.append('late')), cancellable=True).build()
    start(executor, task)

    executor.cancel_task(task)
    step_pool.step()

    assert calls == ['late']


def test_waiting_task_is_cancelled_without_running(executor: TaskExecutor, step_pool: StepPool):
    runs: List[str] = []
    executor.set_max_workers(2)
    busy = [TaskBuilder().build() for _ in range(2)]
    waiting = TaskBuilder('Waiting').with_event(lambda t: runs.append(t.name), cancellable=True).build()
    start(executor, *busy, waiting)
    assert waiting.state.is_waiting

    executor.cancel_task(waiting)
    step_pool.drain()

    assert waiting.state.is_cancelled
    assert runs == []


def test_children_of_a_cancelled_task_are_cancelled(executor: TaskExecutor, step_pool: StepPool):
    parent = stoppable('Parent').build()
    child = TaskBuilder('Child').with_wait_for(parent).build()  # not cancellable
    start(executor, parent, child)
    assert child.state.is_blocked

    executor.cancel_task(parent)
    step_pool.drain()

    assert parent.state.is_cancelled
    assert child.state.is_cancelled


def test_cancel_on_a_group_cancels_every_member(executor: TaskExecutor, step_pool: StepPool):
    executor.set_max_workers(2)
    members = [stoppable(f'M{i}').build() for i in range(4)]
    group = TaskGroupBuilder('G').with_tasks(*members).build()
    start(executor, group)
    assert group.state.is_running

    executor.cancel_task(group)
    step_pool.drain()

    assert all(member.state.is_cancelled for member in members)
    assert group.state.is_cancelled


def test_cancelling_one_member_cancels_the_group_once_it_settles(executor: TaskExecutor, step_pool: StepPool):
    ok = TaskBuilder('Ok').build()
    stopped = stoppable('Stopped').build()
    group = TaskGroupBuilder('G').with_tasks(ok, stopped).build()
    start(executor, group)

    executor.cancel_task(stopped)
    step_pool.drain()

    assert ok.state.is_completed
    assert stopped.state.is_cancelled
    assert group.state.is_cancelled


def test_cancelled_task_can_be_retried_and_runs_clean(executor: TaskExecutor, step_pool: StepPool):
    seen: List[bool] = []
    task = TaskBuilder().with_event(lambda t: seen.append(t.cancel_requested), cancellable=True).build()
    start(executor, task)
    executor.cancel_task(task)
    step_pool.step()

    executor.retry_task(task)
    step_pool.step()

    assert seen == [True, False]
    assert task.state.is_completed


def test_cancelled_task_can_be_removed(executor: TaskExecutor, step_pool: StepPool):
    task = stoppable().build()
    start(executor, task)
    executor.cancel_task(task)
    step_pool.step()

    executor.remove_task(task)

    assert task.state.is_deleted


def test_cancel_on_a_finished_task_does_nothing(executor: TaskExecutor, step_pool: StepPool):
    task = stoppable().build()
    start(executor, task)
    step_pool.step()

    executor.cancel_task(task)

    assert task.state.is_completed
    assert not task.cancel_requested


def test_manager_cancel_tasks(make_manager):
    manager: TQManager = make_manager('cancel')
    task = stoppable().with_predicate(lambda: False, max_attempts=5, delay_ms=60000).build()
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

    task = TaskBuilder('Render').with_event(render, cancellable=True).build()
    app.add_tasks(task)
    app.start_workers()
    qtbot.wait_until(lambda: bool(procs), timeout=5000)

    app.cancel_tasks(task)

    qtbot.wait_until(lambda: task.state.is_cancelled, timeout=5000)
    assert procs[0].poll() is not None


def test_child_added_after_its_parent_was_cancelled_is_cancelled(executor: TaskExecutor, step_pool: StepPool):
    parent = stoppable('Parent').build()
    start(executor, parent)
    executor.cancel_task(parent)
    step_pool.drain()

    child = TaskBuilder('Child').with_wait_for(parent).build()
    start(executor, child)

    assert child.state.is_cancelled


def test_retry_on_a_group_reruns_its_cancelled_member(executor: TaskExecutor, step_pool: StepPool):
    ok = TaskBuilder('Ok').build()
    stopped = stoppable('Stopped').build()
    group = TaskGroupBuilder('G').with_tasks(ok, stopped).build()
    start(executor, group)
    executor.cancel_task(stopped)
    step_pool.drain()
    assert group.state.is_cancelled

    executor.retry_task(group)
    step_pool.drain()

    assert stopped.state.is_completed
    assert group.state.is_completed


def running(executor: TaskExecutor, step_pool: StepPool) -> TaskExecutable:
    task = TaskBuilder('Running').build()
    start(executor, task)
    return task


def waiting(executor: TaskExecutor, step_pool: StepPool) -> TaskExecutable:
    executor.set_max_workers(1)
    task = TaskBuilder('Waiting').build()
    start(executor, TaskBuilder('Busy').build(), task)
    return task


def blocked(executor: TaskExecutor, step_pool: StepPool) -> TaskExecutable:
    task = TaskBuilder('Blocked').with_predicate(lambda: False, max_attempts=5, delay_ms=60000).build()
    start(executor, task)
    return task


def retrying(executor: TaskExecutor, step_pool: StepPool) -> TaskExecutable:
    task = TaskBuilder('Retrying').with_event(raise_error).with_retry(max_attempts=3).build()
    start(executor, task)
    step_pool.step()
    return task


@pytest.mark.parametrize('setup', [running, waiting, blocked, retrying])
def test_task_that_is_not_cancellable_is_not_stopped_in_any_state(
    executor: TaskExecutor,
    step_pool: StepPool,
    monkeypatch: pytest.MonkeyPatch,
    setup: Callable[[TaskExecutor, StepPool], TaskExecutable]
):
    # A pending retry timer would fire after the executor is gone.
    monkeypatch.setattr('tqm._core.task_retry.QTimer.singleShot', lambda *args: None)
    task = setup(executor, step_pool)
    state = task.state.current
    hooks: List[str] = []
    task.on_cancel(lambda: hooks.append('kill'))

    executor.cancel_task(task)

    assert task.state.current == state
    assert not task.cancel_requested
    assert hooks == []


def test_manager_cancel_tasks_skips_a_task_that_is_not_cancellable(make_manager):
    manager: TQManager = make_manager('cancel')
    plain = TaskBuilder().with_predicate(lambda: False, max_attempts=5, delay_ms=60000).build()
    task = stoppable().with_predicate(lambda: False, max_attempts=5, delay_ms=60000).build()
    manager.add_tasks(plain, task)
    manager.start_workers()

    manager.cancel_tasks(plain, task)

    assert plain.state.is_blocked
    assert task.state.is_cancelled


def test_group_is_cancellable_only_if_every_member_is(executor: TaskExecutor, step_pool: StepPool):
    group = TaskGroupBuilder('G').with_tasks(stoppable('A').build(), TaskBuilder('B').build()).build()
    start(executor, group)
    assert not group.cancellable

    executor.cancel_task(group)
    step_pool.drain()

    assert group.state.is_completed
    assert all(member.state.is_completed for member in group.tasks)


def test_chain_after_a_cancelled_group_ends_cancelled(executor: TaskExecutor, step_pool: StepPool):
    # Shots chained group after group: none of the later ones can run.
    shot1 = TaskGroupBuilder('Shot1').with_tasks(stoppable('Render1').build()).build()
    shot2 = TaskGroupBuilder('Shot2').with_tasks(TaskBuilder('Render2').build()).with_wait_for(shot1).build()
    shot3 = TaskGroupBuilder('Shot3').with_tasks(TaskBuilder('Render3').build()).with_wait_for(shot2).build()
    start(executor, shot1, shot2, shot3)

    executor.cancel_task(shot1)
    step_pool.drain()

    assert shot1.state.is_cancelled
    assert shot2.state.is_cancelled
    assert shot3.state.is_cancelled
    assert not shot2.cancellable  # cancelled as a dependant, never as a Stop target


def test_running_dependant_that_is_not_cancellable_is_not_stopped(executor: TaskExecutor, step_pool: StepPool):
    # A manual retry can rerun a parent while its child runs.
    parent = stoppable('Parent').build()
    child = TaskBuilder('Child').with_wait_for(parent).build()
    start(executor, parent, child)
    step_pool.step()
    assert child.state.is_running

    executor.retry_task(parent)
    executor.cancel_task(parent)
    step_pool.pending.reverse()  # the parent ends while the child still runs
    step_pool.step()

    assert parent.state.is_cancelled
    assert child.state.is_running
    assert not child.cancel_requested
    step_pool.drain()
    assert child.state.is_completed


def test_manager_add_event_takes_the_cancellable_flag(make_manager):
    manager: TQManager = make_manager('cancel')
    plain = manager.add_event(lambda t: None, label='Plain')
    task = manager.add_event(lambda t: None, label='Stoppable', cancellable=True)
    assert plain.state.is_waiting and task.state.is_waiting  # workers not started

    manager.cancel_tasks(plain, task)

    assert plain.state.is_waiting
    assert task.state.is_cancelled


def test_group_add_event_takes_the_cancellable_flag(executor: TaskExecutor, step_pool: StepPool):
    group = TaskGroupBuilder('G').build()
    plain = group.add_event(lambda t: None, label='Plain')
    task = group.add_event(lambda t: None, label='Stoppable', cancellable=True)
    assert task.cancellable and not plain.cancellable
    assert not group.cancellable  # mixed members
    start(executor, group)

    executor.cancel_task(plain)
    executor.cancel_task(task)
    step_pool.drain()

    assert plain.state.is_completed
    assert task.state.is_cancelled


def test_group_of_add_event_members_that_all_opt_in_is_cancellable(executor: TaskExecutor, step_pool: StepPool):
    group = TaskGroupBuilder('G').build()
    members = [group.add_event(lambda t: None, cancellable=True) for _ in range(2)]
    assert group.cancellable
    start(executor, group)

    executor.cancel_task(group)
    step_pool.drain()

    assert group.state.is_cancelled
    assert all(member.state.is_cancelled for member in members)
