from __future__ import annotations

from typing import List
from unittest import mock

from tqm import TaskBuilder, TaskGroupBuilder
from tqm.exceptions import TaskError
from tqm._core.task_executor import TaskExecutor

from ..utils import must_raise, raise_error, failure_controller
from ..utils.harness import StepPool


def drain(step_pool: StepPool) -> None:
    while step_pool.activeThreadCount():
        step_pool.step()


def test_failed_task_keeps_the_error_message(executor: TaskExecutor, step_pool: StepPool):
    task = TaskBuilder('Boom').with_event(raise_error).build()
    executor.add_task(task)
    executor.start_workers()
    step_pool.step()

    assert task.state.is_failed
    assert task.state.get_last().comment == 'Boom'


def test_start_workers_respects_the_worker_limit(executor: TaskExecutor, step_pool: StepPool):
    executor.set_max_workers(2)
    tasks = [TaskBuilder().build() for _ in range(8)]
    for task in tasks:
        executor.add_task(task)

    executor.start_workers()
    assert 2 <= step_pool.activeThreadCount() < 8

    drain(step_pool)
    assert all(task.state.is_completed for task in tasks)


def test_set_max_workers_resizes_the_pool(executor: TaskExecutor, step_pool: StepPool):
    with mock.patch.object(step_pool, 'setMaxThreadCount') as resize:
        executor.set_max_workers(30)

    assert resize.call_args[0][0] >= 30


def test_max_workers_has_a_floor(executor: TaskExecutor):
    executor.set_max_workers(1)
    assert executor.max_workers == 2


def test_remove_twice_is_harmless(executor: TaskExecutor):
    task = TaskBuilder().build()
    executor.add_task(task)

    executor.remove_task(task)
    executor.remove_task(task)

    assert task.state.is_deleted


def test_status_counts_each_state(executor: TaskExecutor, step_pool: StepPool):
    seen: List[dict] = []
    executor.callbacks.status_updated.connect(seen.append)

    executor.add_task(TaskBuilder().build())
    executor.add_task(TaskBuilder().build())
    executor.add_task(TaskBuilder().with_event(raise_error).build())
    executor.start_workers()
    drain(step_pool)

    assert seen[-1] == {'Running': 0, 'Completed': 2, 'Failed': 1}


def test_shutdown_when_nothing_runs_ends_at_once(executor: TaskExecutor, step_pool: StepPool):
    executor.add_task(TaskBuilder().build())

    executor.shutdown()
    task = TaskBuilder().build()
    executor.add_task(task)
    executor.start_workers()

    assert step_pool.activeThreadCount() == 1
    step_pool.step()
    assert task.state.is_completed


def test_callback_cleanup_decides_if_it_fires_again(executor: TaskExecutor, step_pool: StepPool):
    every_time: List[str] = []
    once: List[str] = []
    task = (
        TaskBuilder('Boom')
        .with_event(raise_error)
        .with_on_failed(lambda t: every_time.append(t.name), cleanup=False)
        .with_on_finish(lambda t: once.append(t.name), cleanup=True)
        .build()
    )
    executor.add_task(task)
    executor.start_workers()
    step_pool.step()

    executor.retry_task(task)
    step_pool.step()

    assert every_time == ['Boom', 'Boom']
    assert once == ['Boom']


def test_group_retry_does_not_rerun_completed_members(executor: TaskExecutor, step_pool: StepPool):
    runs: List[str] = []
    ok = TaskBuilder('Ok').with_event(lambda t: runs.append(t.name)).build()
    flaky = TaskBuilder('Flaky').with_event(lambda t: failure_controller(t, fail_count=1)).build()
    group = TaskGroupBuilder('G').with_tasks(ok, flaky).build()
    executor.add_task(group)
    executor.start_workers()
    drain(step_pool)
    assert group.state.is_failed

    executor.retry_task(group)
    drain(step_pool)

    assert group.state.is_completed
    assert runs == ['Ok']


def test_task_blocked_by_its_predicate_is_not_idle(executor: TaskExecutor):
    task = TaskBuilder().with_predicate(lambda: False, max_attempts=5, delay_ms=60000).build()
    executor.add_task(task)
    executor.start_workers()

    assert task.state.is_blocked
    assert not executor.status_tracker.is_idle()

    executor.remove_task(task)  # stops the predicate timer


def test_completed_parent_with_a_running_child_is_not_removable(executor: TaskExecutor, step_pool: StepPool):
    parent = TaskBuilder('P').build()
    child = TaskBuilder('C').with_wait_for(parent).build()
    executor.add_task(parent)
    executor.add_task(child)
    executor.start_workers()
    step_pool.step()
    assert parent.state.is_completed and child.state.is_running

    with must_raise(TaskError):
        executor.remove_task(parent)

    assert parent in executor.registry
    step_pool.step()
    assert child.state.is_completed


def test_completed_group_with_a_running_member_is_not_removable(executor: TaskExecutor, step_pool: StepPool):
    member = TaskBuilder('M').build()
    group = TaskGroupBuilder('G').with_tasks(member).build()
    executor.add_task(group)
    executor.start_workers()
    drain(step_pool)
    assert group.state.is_completed

    executor.retry_task(member)
    assert member.state.is_running

    with must_raise(TaskError):
        executor.remove_task(group)

    assert group in executor.registry
    step_pool.step()
    assert member.state.is_completed


def test_shutdown_removes_a_task_waiting_to_retry(executor: TaskExecutor, step_pool: StepPool):
    task = TaskBuilder().with_event(raise_error).with_retry(1, 0).build()

    with mock.patch('tqm._core.task_retry.QTimer.singleShot'):
        executor.add_task(task)
        executor.start_workers()
        step_pool.step()
        assert task.state.is_retrying

        executor.shutdown()

    assert task.state.is_deleted
    assert task not in executor.registry


def test_policy_retry_counts_the_attempt_and_skips_on_start(executor: TaskExecutor, step_pool: StepPool):
    started: List[str] = []
    task = (
        TaskBuilder('T')
        .with_event(lambda t: failure_controller(t, fail_count=1))
        .with_retry(1, 0)
        .with_on_start(lambda t: started.append(t.name), cleanup=False)
        .build()
    )

    with mock.patch('tqm._core.task_retry.QTimer.singleShot') as later:
        executor.add_task(task)
        executor.start_workers()
        step_pool.step()

    assert task.state.is_retrying
    assert task.retry_policy.attempt == 1

    later.call_args[0][1]()
    step_pool.step()

    assert task.state.is_completed
    assert started == ['T']
