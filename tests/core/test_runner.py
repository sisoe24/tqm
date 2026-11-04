from __future__ import annotations

from pytestqt.qtbot import QtBot

from tqm import TQManager, TaskBuilder, TaskExecutable, TaskGroupBuilder
from tqm._core.task_runner import TaskRunner

from ..utils import (SafeList, raise_error, assert_task_failed,
                     assert_task_completed)


class TestTaskRunner:
    def test_task_runner_signals(self, qtbot: QtBot):
        """Test that the TaskRunner emits the right signals in the right order."""
        signals_received = SafeList[str]()

        task = TaskBuilder('SignalTest').with_event(lambda t: None).build()
        runner = TaskRunner(task)

        # Connect to signals
        runner.signals.runner_started.connect(lambda _: signals_received.append('started'))
        runner.signals.runner_completed.connect(lambda _: signals_received.append('completed'))

        # Run the task
        runner.run()

        # Check signal order
        assert signals_received[0] == 'started'
        assert signals_received[1] == 'completed'

    def test_task_runner_exception(self, qtbot: QtBot):
        """Test that the TaskRunner properly handles exceptions."""
        signals_received = SafeList[str]()
        exceptions_caught = SafeList[str]()

        def failing_task(t: TaskExecutable):
            raise ValueError('Task failed intentionally')

        task = TaskBuilder('FailingTest').with_event(failing_task).build()
        runner = TaskRunner(task)

        # Connect to signals
        runner.signals.runner_started.connect(lambda _: signals_received.append('started'))
        runner.signals.runner_failed.connect(
            lambda t, e: (signals_received.append('failed'), exceptions_caught.append(str(e)))
        )

        # Run the task
        runner.run()

        # Check signal order
        assert signals_received[0] == 'started'
        assert signals_received[1] == 'failed'
        assert 'Task failed intentionally' in exceptions_caught[0]

    def test_callback_execution(self, qtbot: QtBot, app: TQManager):
        """Test that task callbacks are executed in the correct order."""
        callbacks_called = SafeList[str]()

        task = (
            TaskBuilder('CallbackTest')
            .with_event(lambda t: None)
            .with_on_start(lambda t: callbacks_called.append('on_start'))
            .with_on_completed(lambda t: callbacks_called.append('on_completed'))
            .with_on_finish(lambda t: callbacks_called.append('on_finish'))
            .build()
        )

        app.add_tasks(task)

        app.start_workers()
        qtbot.wait_until(lambda: task.state.is_completed)

        assert callbacks_called[0] == 'on_start'
        assert callbacks_called[1] == 'on_completed'
        assert callbacks_called[2] == 'on_finish'
        assert_task_completed(task)

    def test_task_failure_callbacks(self, qtbot: QtBot, app: TQManager):
        """Test that failure callbacks are executed correctly."""
        callbacks_called = SafeList[str]()

        def failing_task(t: TaskExecutable):
            raise ValueError('Task failed intentionally')

        task = (
            TaskBuilder('FailCallbackTest')
            .with_event(failing_task)
            .with_on_start(lambda t: callbacks_called.append('on_start'))
            .with_on_failed(lambda t: callbacks_called.append('on_failed'))
            .with_on_finish(lambda t: callbacks_called.append('on_finish'))
            .build()
        )

        app.add_tasks(task)

        app.start_workers()
        qtbot.wait_until(lambda: task.state.is_failed)

        assert callbacks_called.to_list() == ['on_start', 'on_failed', 'on_finish']
        assert str(task.exception) == 'Task failed intentionally'
        assert_task_failed(task)

    def test_group_runner(self, qtbot: QtBot, app: TQManager):
        """Test that simple GroupRunner properly manages its tasks."""
        with app.create_group('TestGroup') as group:
            task1 = group.add_event(lambda t: t.log('Task 1 executed'), label='Task1')
            task2 = group.add_event(lambda t: t.log('Task 2 executed'), label='Task2')

        # Start the group execution
        app.start_workers()
        qtbot.wait_until(lambda: group.state.is_completed)

        # All tasks should complete successfully
        assert_task_completed(task1)
        assert_task_completed(task2)
        assert_task_completed(group)

    def test_group_runner_with_failure(self, qtbot: QtBot, app: TQManager):
        """Test that simple GroupRunner properly handles task failures."""
        with app.create_group('FailGroup') as group:
            task1 = group.add_event(lambda t: t.log('Task 1 executed'), label='Task1')
            task2 = group.add_event(lambda t: raise_error(t), label='Task2')
            task3 = group.add_event(lambda t: t.log('Task 3 executed'), label='Task3')

        # Start the group execution
        app.start_workers()
        qtbot.wait_until(lambda: group.state.is_failed)

        # Task1 and Task3 should complete, Task2 should fail, and the group should fail
        assert_task_completed(task1)
        assert_task_failed(task2)
        assert_task_completed(task3)
        assert_task_failed(group)


class TestGroupRunner:
    """Tests for the GroupRunner class with complex groups."""

    def test_group_runner_with_task_group_builder(self, qtbot: QtBot, app: TQManager):
        """Test the GroupRunner with a group created using TaskGroupBuilder."""
        execution_order = SafeList[str]()

        # Create tasks
        task1 = (
            TaskBuilder('BuilderTask1')
            .with_event(lambda t: execution_order.append(t.name))
            .build()
        )

        task2 = (
            TaskBuilder('BuilderTask2')
            .with_event(lambda t: execution_order.append(t.name))
            .build()
        )

        # Create a group using TaskGroupBuilder
        group = (
            TaskGroupBuilder('BuilderGroup')
            .with_tasks(task1, task2)
            .with_color('blue')
            .with_comment('A group created with TaskGroupBuilder')
            .build()
        )

        # Add the group to the task manager
        app.add_tasks(group)

        # Start execution and wait for completion
        app.start_workers()
        qtbot.wait_until(lambda: group.state.is_completed)

        # Verify all tasks were executed
        assert len(execution_order) == 2
        assert 'BuilderTask1' in execution_order
        assert 'BuilderTask2' in execution_order

        # Verify task and group states
        assert_task_completed(task1)
        assert_task_completed(task2)
        assert_task_completed(group)

    def test_group_with_complex_callbacks(self, qtbot: QtBot, app: TQManager):
        """Test a group with callbacks at multiple levels."""
        callback_sequence = SafeList[str]()

        # Create a group with callbacks
        group = (
            TaskGroupBuilder('CallbackGroup')
            .with_on_start(lambda g: callback_sequence.append('group_start'))
            .with_on_completed(lambda g: callback_sequence.append('group_completed'))
            .with_on_finish(lambda g: callback_sequence.append('group_finish'))
            .build()
        )

        # Add tasks with their own callbacks
        task1 = (
            TaskBuilder('CallbackTask1')
            .with_event(lambda t: callback_sequence.append('task1_execute'))
            .with_on_start(lambda t: callback_sequence.append('task1_start'))
            .with_on_completed(lambda t: callback_sequence.append('task1_completed'))
            .with_on_finish(lambda t: callback_sequence.append('task1_finish'))
            .build()
        )

        task2 = (
            TaskBuilder('CallbackTask2')
            .with_event(lambda t: callback_sequence.append('task2_execute'))
            .with_on_start(lambda t: callback_sequence.append('task2_start'))
            .with_on_completed(lambda t: callback_sequence.append('task2_completed'))
            .with_on_finish(lambda t: callback_sequence.append('task2_finish'))
            .build()
        )

        group.add_tasks(task1, task2)

        # Add group to task manager
        app.add_tasks(group)

        # Start execution and wait for completion
        app.start_workers()
        qtbot.wait_until(lambda: group.state.is_completed)

        # Verify callback sequence
        # Group should start first
        assert callback_sequence[0] == 'group_start'

        # Tasks should execute next
        assert 'task1_start' in callback_sequence
        assert 'task1_execute' in callback_sequence
        assert 'task1_completed' in callback_sequence
        assert 'task1_finish' in callback_sequence

        assert 'task2_start' in callback_sequence
        assert 'task2_execute' in callback_sequence
        assert 'task2_completed' in callback_sequence
        assert 'task2_finish' in callback_sequence

        # Group should complete last
        assert callback_sequence[-2] == 'group_completed'
        assert callback_sequence[-1] == 'group_finish'

        # Task starts should come before task completions
        assert callback_sequence.index('task1_start') < callback_sequence.index('task1_completed')
        assert callback_sequence.index('task2_start') < callback_sequence.index('task2_completed')

    def test_complex_group_with_mixed_success_failure(self, qtbot: QtBot, app: TQManager):
        """Test a complex group with mixed success and failure states."""
        execution_order = SafeList[str]()

        # Create a group
        group = (
            TaskGroupBuilder('MixedGroup')
            .build()
        )

        # Add successful tasks
        success_task1 = (
            TaskBuilder('SuccessTask1')
            .with_event(lambda t: execution_order.append(t.name))
            .build()
        )

        success_task2 = (
            TaskBuilder('SuccessTask2')
            .with_event(lambda t: execution_order.append(t.name))
            .build()
        )

        # Add failing task
        def fail_task(t: TaskExecutable):
            execution_order.append(f"{t.name}_started")
            raise ValueError('Task failed intentionally')

        fail_task1 = (
            TaskBuilder('FailTask1')
            .with_event(fail_task)
            .build()
        )

        # Add task with retry capability
        attempt_counter = SafeList[int]()

        def retry_task(t: TaskExecutable):
            attempt_counter.append(1)
            # Fail on first attempt, succeed on retry
            if len(attempt_counter) == 1:
                raise ValueError('First attempt fails')
            execution_order.append(t.name)

        retry_task1 = (
            TaskBuilder('RetryTask1')
            .with_event(retry_task)
            .with_retry(1, delay_seconds=0)  # Allow one retry
            .build()
        )

        # Add all tasks to the group
        group.add_tasks(success_task1, fail_task1, success_task2, retry_task1)

        # Add group to task manager
        app.add_tasks(group)

        # Start execution
        app.start_workers()
        qtbot.wait_until(lambda: group.state.is_failed)

        # Verify execution occurred
        assert 'SuccessTask1' in execution_order
        assert 'SuccessTask2' in execution_order
        assert 'FailTask1_started' in execution_order

        # FailTask1 should not complete
        assert 'FailTask1' not in execution_order

        # RetryTask1 should succeed after retry
        assert 'RetryTask1' in execution_order
        assert len(attempt_counter) == 2  # Should have attempted twice

        # Verify states
        assert_task_completed(success_task1)
        assert_task_completed(success_task2)
        assert_task_failed(fail_task1)
        assert_task_completed(
            retry_task1, [
                'inactive', 'waiting', 'running', 'retrying',
                'inactive', 'waiting', 'running', 'completed'
            ]
        )

        # Group should fail because one task failed
        assert_task_failed(group)
