from __future__ import annotations

import threading
from typing import Any, List, Dict

import pytest
from pytestqt.qtbot import QtBot

from tqm import TQManager, TaskBuilder, TaskExecutor
from tqm.exceptions import TaskParentError
from tqm._ui.toolbar import ClearTasksMenu

from ...utils import raise_error, run_events, must_not_raise
from ...utils.harness import StepPool


def noop_task(name: str = '') -> TaskBuilder:
    return TaskBuilder(name).with_event(lambda t: None)


def passes_on_call(call: int) -> Any:
    calls = []

    def condition() -> bool:
        calls.append(1)
        return len(calls) >= call

    return condition


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V9')
def test_timer_stops_when_a_blocked_child_fails(
    qtbot: QtBot,
    executor: TaskExecutor,
    step_pool: StepPool
):
    failures: List[int] = []
    parent = TaskBuilder('P').with_event(raise_error).build()
    child = (
        noop_task('C')
        .with_wait_for(parent)
        .with_on_failed(lambda t: failures.append(1), cleanup=False)
        .with_predicate(lambda: False, max_attempts=2, delay_ms=100)
        .build()
    )
    executor.add_task(parent)
    executor.add_task(child)
    executor.start_workers()
    step_pool.drain()

    run_events(qtbot, 400)

    assert len(failures) == 1
    assert isinstance(child.exception, TaskParentError)


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V9')
def test_passing_predicate_does_not_revive_a_failed_child(
    qtbot: QtBot,
    executor: TaskExecutor,
    step_pool: StepPool
):
    parent = TaskBuilder('P').with_event(raise_error).build()
    child = noop_task('C').with_wait_for(parent).with_predicate(passes_on_call(2), max_attempts=5, delay_ms=50).build()
    executor.add_task(parent)
    executor.add_task(child)
    executor.start_workers()

    with qtbot.capture_exceptions() as errors:
        step_pool.drain()
        run_events(qtbot, 200)

    assert not errors
    assert child.state.is_failed


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V10')
def test_predicate_failure_with_retry_policy_reaches_idle(qtbot: QtBot, app: TQManager):
    idle: List[int] = []
    app.callbacks.on_system_idle(lambda: idle.append(1))
    task = noop_task('T').with_predicate(passes_on_call(3), max_attempts=1, delay_ms=1).with_retry(1, 0).build()
    app.add_tasks(task)

    app.start_workers()
    qtbot.wait_until(lambda: task.state.is_completed)
    run_events(qtbot, 600)

    assert idle


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V11')
def test_task_whose_predicate_passed_on_a_tick_is_removable(qtbot: QtBot, app: TQManager):
    task = noop_task('T').with_predicate(passes_on_call(2), max_attempts=5, delay_ms=1).build()
    app.add_tasks(task)
    app.start_workers()
    qtbot.wait_until(lambda: task.state.is_completed)

    with qtbot.capture_exceptions() as errors:
        app.findChild(ClearTasksMenu).clear_all_tasks_btn.trigger()

    assert not errors
    assert task not in app.executor.get_all_tasks()
    assert task.state.is_deleted


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V12')
def test_predicate_with_wrong_signature_fails_only_its_task(
    executor: TaskExecutor,
    step_pool: StepPool
):
    # The with_predicate docstring shows this signature.
    bad = noop_task('Bad').with_predicate(lambda _: True).build()
    good = noop_task('Good').build()
    executor.add_task(bad)
    executor.add_task(good)

    with must_not_raise(TypeError):
        executor.start_workers()
    step_pool.drain()

    assert bad.state.is_failed
    assert good.state.is_completed


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V12')
def test_predicate_raising_on_a_tick_fails_the_task(qtbot: QtBot, app: TQManager):
    calls: List[int] = []

    def condition() -> bool:
        calls.append(1)
        if len(calls) > 1:
            raise ValueError('condition')
        return False

    task = noop_task('T').with_predicate(condition, max_attempts=2, delay_ms=1).build()
    app.add_tasks(task)

    with qtbot.capture_exceptions():
        app.start_workers()
        run_events(qtbot, 100)
        failed, ticks = task.state.is_failed, len(calls)
        task.predicate.timer.stop()

    assert failed
    assert ticks == 2


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V34')
def test_task_built_off_main_thread_evaluates_its_predicate(qtbot: QtBot, app: TQManager):
    built: Dict[str, Any] = {}

    def build() -> None:
        built['task'] = noop_task('T').with_predicate(passes_on_call(2), max_attempts=5, delay_ms=1).build()

    thread = threading.Thread(target=build)
    thread.start()
    thread.join()

    app.add_tasks(built['task'])
    app.start_workers()
    run_events(qtbot, 300)

    assert built['task'].state.is_completed


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V47')
def test_retry_evaluates_a_predicate_that_passed_on_a_tick(
    qtbot: QtBot,
    executor: TaskExecutor,
    step_pool: StepPool
):
    calls: List[int] = []

    def condition() -> bool:
        calls.append(1)
        return len(calls) >= 2

    task = TaskBuilder('T').with_event(raise_error).with_predicate(condition, max_attempts=5, delay_ms=1).build()
    executor.add_task(task)
    executor.start_workers()
    qtbot.wait_until(lambda: step_pool.activeThreadCount() > 0)
    step_pool.drain()
    evaluated = len(calls)

    executor.retry_task(task)
    step_pool.drain()

    assert len(calls) > evaluated
