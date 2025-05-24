from __future__ import annotations

from typing import List

from pytestqt.qtbot import QtBot

from tqm import TQManager, TaskBuilder, TaskExecutable, TaskGroupBuilder
from tqm._core.task_runner import TaskRunner, GroupRunner

from ..utils import (SafeList, raise_error, assert_task_failed,
                     assert_task_completed)


class estTaskRunner:
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

        with qtbot.wait_signal(app.executor.callbacks.system_idle):
            app.start_workers()

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

        with qtbot.wait_signal(app.executor.callbacks.system_idle):
            app.start_workers()

        assert callbacks_called[0] == 'on_start'
        assert callbacks_called[1] == 'on_failed'
        assert callbacks_called[2] == 'on_finish'
        assert_task_failed(task)

    def test_group_runner(self, qtbot: QtBot, app: TQManager):
        """Test that simple GroupRunner properly manages its tasks."""
        with app.create_group('TestGroup') as group:
            task1 = group.add_event(lambda t: t.log('Task 1 executed'), label='Task1')
            task2 = group.add_event(lambda t: t.log('Task 2 executed'), label='Task2')

        # Start the group execution
        with qtbot.wait_signal(app.executor.callbacks.system_idle):
            app.start_workers()

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
        with qtbot.wait_signal(app.executor.callbacks.system_idle):
            app.start_workers()

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
        with qtbot.wait_signal(app.executor.callbacks.system_idle):
            app.start_workers()

        # Verify all tasks were executed
        assert len(execution_order) == 2
        assert 'BuilderTask1' in execution_order
        assert 'BuilderTask2' in execution_order

        # Verify task and group states
        assert_task_completed(task1)
        assert_task_completed(task2)
        assert_task_completed(group)

    def test_nested_groups_with_runner(self, qtbot: QtBot, app: TQManager):
        """Test the GroupRunner with nested groups."""
        execution_order = SafeList[str]()

        # Create inner group
        inner_group = (
            TaskGroupBuilder('InnerGroup')
            .build()
        )

        # Add tasks to inner group
        inner_task1 = (
            TaskBuilder('InnerTask1')
            .with_event(lambda t: execution_order.append(t.name))
            .build()
        )

        inner_task2 = (
            TaskBuilder('InnerTask2')
            .with_event(lambda t: execution_order.append(t.name))
            .build()
        )

        inner_group.add_tasks(inner_task1, inner_task2)

        # Create outer group that depends on inner group
        outer_group = (
            TaskGroupBuilder('OuterGroup')
            .with_wait_for(inner_group)
            .build()
        )

        # Add tasks to outer group
        outer_task = (
            TaskBuilder('OuterTask')
            .with_event(lambda t: execution_order.append(t.name))
            .build()
        )

        outer_group.add_tasks(outer_task)

        # Add both groups to the task manager
        app.add_tasks(inner_group, outer_group)

        # Start execution and wait for completion
        with qtbot.wait_signal(app.executor.callbacks.system_idle):
            app.start_workers()

        # Verify execution order - inner group tasks should execute before outer group
        assert len(execution_order) == 3
        assert execution_order.index('InnerTask1') < execution_order.index('OuterTask')
        assert execution_order.index('InnerTask2') < execution_order.index('OuterTask')

        # Verify task and group states
        assert_task_completed(inner_task1)
        assert_task_completed(inner_task2)
        assert_task_completed(inner_group)
        assert_task_completed(outer_task)
        assert_task_completed(outer_group, ['inactive', 'waiting',
                              'blocked', 'waiting', 'running', 'completed'])

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
        with qtbot.wait_signal(app.executor.callbacks.system_idle):
            app.start_workers()

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
            .with_retry_failed(1)  # Allow one retry
            .build()
        )

        # Add all tasks to the group
        group.add_tasks(success_task1, fail_task1, success_task2, retry_task1)

        # Add group to task manager
        app.add_tasks(group)

        # Start execution
        with qtbot.wait_signal(app.executor.callbacks.system_idle):
            app.start_workers()

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
        assert_task_completed(retry_task1, ['inactive', 'waiting',
                              'running', 'inactive', 'waiting', 'running', 'completed'])

        # Group should fail because one task failed
        assert_task_failed(group)

    def test_direct_group_runner_execution(self, qtbot: QtBot):
        """Test direct execution of a GroupRunner without using TasksManager."""
        execution_order = SafeList[str]()

        # Create individual tasks
        task1 = (
            TaskBuilder('DirectTask1')
            .with_event(lambda t: execution_order.append(t.name))
            .build()
        )

        task2 = (
            TaskBuilder('DirectTask2')
            .with_event(lambda t: execution_order.append(t.name))
            .build()
        )

        # Create a group
        group = (
            TaskGroupBuilder('DirectGroup')
            .with_tasks(task1, task2)
            .build()
        )

        # Create a GroupRunner directly
        runner = GroupRunner(group)

        # Track signals
        signals_received = SafeList[str]()
        runner.signals.runner_started.connect(lambda _: signals_received.append('started'))
        runner.signals.runner_completed.connect(
            lambda g: (
                g.state.set_completed(), signals_received.append('completed'),
            ))

        # We need to handle the group_task_added signal to simulate what TaskExecutor would do
        def handle_task_added(tasks: List[TaskExecutable]):
            for task in tasks:
                task_runner = TaskRunner(task)
                task_runner.signals.runner_completed.connect(lambda t: t.state.set_completed())
                task_runner.run()

        runner.signals.group_task_added.connect(handle_task_added)

        # Run the group runner
        runner.run()

        # Verify execution
        assert len(execution_order) == 2
        assert 'DirectTask1' in execution_order
        assert 'DirectTask2' in execution_order

        # Verify signals
        assert signals_received[0] == 'started'
        assert signals_received[1] == 'completed'

        # Verify states
        assert task1.state.is_completed
        assert task2.state.is_completed
        assert group.state.is_completed
