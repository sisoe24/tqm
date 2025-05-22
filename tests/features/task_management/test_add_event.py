from __future__ import annotations

from pytestqt.qtbot import QtBot

from tqm import TQManager, TaskExecutable

from ...utils import (SafeList, raise_error, assert_task_failed,
                      assert_task_completed)


def test_add_event(qtbot: QtBot, app: TQManager):
    """Test that an event executes successfully."""

    execution_order = SafeList[str]()

    def record_execution(t: TaskExecutable):
        execution_order.append(t.name)

    task = app.add_event(record_execution, label='TestTask1')

    with qtbot.wait_signal(app.executor.callbacks.system_idle):
        app.start_workers()

    assert 'TestTask1' in execution_order

    assert_task_completed(task)


def test_add_two_events(qtbot: QtBot, app: TQManager):
    """Test that adding two events executes successfully."""

    execution_order = SafeList[str]()

    def record_execution(t: TaskExecutable):
        execution_order.append(t.name)

    task1 = app.add_event(record_execution, label='TestTask1')
    task2 = app.add_event(record_execution, label='TestTask2')

    with qtbot.wait_signal(app.executor.callbacks.system_idle):
        app.start_workers()

    assert 'TestTask1' in execution_order
    assert 'TestTask2' in execution_order

    assert_task_completed(task1)
    assert_task_completed(task2)


def test_add_events_with_failure(qtbot: QtBot, app: TQManager):
    """Test that adding events works even when one of them fails."""

    execution_order = SafeList[str]()

    def record_execution(task: TaskExecutable):
        execution_order.append(task.name)

    task1 = app.add_event(record_execution, label='TestTask1')
    # task raises error before running func
    task2 = app.add_event(
        lambda t: (raise_error(t), record_execution(t)),
        label='TestTask2'
    )
    task3 = app.add_event(record_execution, label='TestTask3')

    with qtbot.wait_signal(app.executor.callbacks.system_idle):
        app.start_workers()

    assert 'TestTask1' in execution_order
    assert 'TestTask2' not in execution_order
    assert 'TestTask3' in execution_order

    assert_task_completed(task1)
    assert_task_completed(task3)

    assert_task_failed(task2)
    assert task2.exception is not None
    assert isinstance(task2.exception, RuntimeError)
    assert str(task2.exception) == 'TestTask2'


def test_add_event_without_label(qtbot: QtBot, app: TQManager):
    """Test that an event without a label gets a default name."""

    execution_order = SafeList[str]()

    def record_execution(t: TaskExecutable):
        execution_order.append(t.name)

    task = app.add_event(record_execution)

    with qtbot.wait_signal(app.executor.callbacks.system_idle):
        app.start_workers()

    # Check that a default name was assigned (Task-XXXXX)
    assert task.name.startswith('Task-')
    assert task.name in execution_order
    assert_task_completed(task)


def test_add_event_with_progress(qtbot: QtBot, app: TQManager):
    """Test that an event with progress tracking works."""

    progress_values = SafeList[float]()

    def track_progress(task: TaskExecutable):
        for i in range(5):
            task.emit_progress(i * 25)
            progress_values.append(i * 25)

    task = app.add_event(track_progress, show_progress=True, label='ProgressTask')

    with qtbot.wait_signal(app.executor.callbacks.system_idle):
        app.start_workers()

    assert len(progress_values) == 5
    assert progress_values[0] == 0
    assert progress_values[-1] == 100
    assert_task_completed(task)
