from __future__ import annotations

from typing import List
from unittest import mock

from tqm import TaskBuilder
from tqm._core.task_executor import TaskExecutor

from ..utils import raise_error
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


def test_shutdown_when_nothing_runs_keeps_the_queue(executor: TaskExecutor, step_pool: StepPool):
    task = TaskBuilder().build()
    executor.add_task(task)

    executor.shutdown()
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
