"""TQM Demo Module

This module provides a comprehensive demo of TQM (Task Queue Manager) features.
It can be run as a standalone application to showcase TQM capabilities.

Usage:
    Import the module and run the demo function:
    >>> from tqm.demo import run_demo
    >>> run_demo()

    Or simply run the module as a script from the application environment:
    $ tqm-demo
"""

from __future__ import annotations

import sys
import time
import random
import tempfile
from functools import partial
from itertools import count

from PySide2.QtGui import QDesktopServices
from PySide2.QtCore import QUrl
from PySide2.QtWidgets import QMainWindow, QMessageBox, QApplication

from tqm import (TQManager, TaskBuilder, TaskExecutable, TaskGroupBuilder,
                 TaskActionVisibility)


class DemoTasks:
    """Collection of demo tasks for TQM."""

    def __init__(self, manager: TQManager):
        self.manager = manager

    def add_simple_tasks(self):
        """Add simple tasks that complete quickly."""
        self.manager.add_event(
            execute=lambda t: time.sleep(2.5),
            label='Simple Task',
            comment='A basic task that completes quickly'
        )

    def add_progress_tasks(self):
        """Add tasks with progress reporting."""

        def task_with_progress(task: TaskExecutable, steps: int = 10):
            """Task that reports progress as it executes."""
            for i in range(steps):
                progress = (i + 1) / steps * 100
                task.emit_progress(progress)
                task.log(f"Progress: {int(progress)}%")
                time.sleep(0.5)

        self.manager.add_event(
            execute=partial(task_with_progress, steps=10),
            show_progress=True,
            label='Progress Task (10 steps)',
            comment='Task that reports progress'
        )

        self.manager.add_event(
            execute=partial(task_with_progress, steps=5),
            show_progress=True,
            label='Progress Task (5 steps)',
            comment='Another task with progress'
        )

    def add_task_with_action(self):
        """Add a task that creates a file and provides actions to open it."""

        def create_file_task(task: TaskExecutable):
            content = 'This file was created by TQM Demo.\n\n'
            content += 'The Queue Task Manager (TQM) is a powerful tool for managing tasks.\n'
            content += 'You can use it to run multiple tasks in parallel, track their progress,\n'
            content += 'and manage dependencies between them.'

            with tempfile.NamedTemporaryFile('w', delete=False) as f:
                f.write(content)

            # saved file in internal data
            task.data['file_path'] = f.name
            task.log(f"Created file: {f.name}")
            time.sleep(1)  # Simulate some work

        def open_file_action(task: TaskExecutable):
            """Action to open the file."""
            file_path = task.data.get('file_path', '')
            if file_path:
                QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))

        task = (
            TaskBuilder('Create File Task')
            .with_event(create_file_task)
            .with_action(
                'Open File',
                open_file_action,
                visibility=TaskActionVisibility.ON_COMPLETED
            )
            .with_comment('Creates a text file and provides actions to open it')
            .build()
        )

        self.manager.add_tasks(task)

    def add_failing_task(self):
        """Add a task that fails and can be retried."""

        def failing_task(task: TaskExecutable, should_succeed: bool):
            task.log('This task will intentionally fail')
            time.sleep(3)
            if not should_succeed:
                raise RuntimeError('Task failed intentionally. You can retry it!')

        attempts = count()

        task = (
            TaskBuilder('Failing Task')
            .with_event(lambda t: failing_task(t, next(attempts) == 1))
            .with_comment(
                'This task fails intentionally to demonstrate error handling'
            )
            .build()
        )

        self.manager.add_tasks(task)

    def add_task_group_sequence(self):
        """Add a group of related tasks."""

        def task_executor(task: TaskExecutable, delay: float = 1.0):
            task.log(f"Executing {task.name}")
            time.sleep(delay)

        with self.manager.create_group('Sequence Order Group') as group:

            # Create a chain of dependent tasks
            task1 = (
                TaskBuilder('Prerequisite Task')
                .with_event(partial(task_executor, delay=2.0))
                .with_comment('This task must complete before the next ones can start')
                .build()
            )

            task2 = (
                TaskBuilder('Dependent Task 1')
                .with_event(partial(task_executor, delay=2.8))
                .with_wait_for(task1)
                .with_comment('This task waits for Prerequisite Task to complete')
                .build()
            )

            task3 = (
                TaskBuilder('Dependent Task 2')
                .with_event(partial(task_executor, delay=2.2))
                .with_wait_for(task2)
                .with_comment('This task waits for Dependent Task 1 to complete')
                .build()
            )

            group.add_tasks(task1, task2, task3)

    def add_random_color_tasks(self):
        """Add tasks with random colors."""

        for i in range(3):
            task = (
                TaskBuilder(f"Colored Task {i+1}")
                .with_event(lambda t: time.sleep(random.uniform(0.5, 1.5)))
                .with_color()
                .build()
            )
            self.manager.add_tasks(task)

    def add_task_with_callbacks(self):
        """Add a task with various lifecycle callbacks."""

        def on_start(task: TaskExecutable):
            task.log('Task started callback triggered')

        def on_completed(task: TaskExecutable):
            task.log('Task completed callback triggered')

        def on_finish(task: TaskExecutable):
            task.log('Task finished callback triggered')

        task = (
            TaskBuilder('Callback Demo Task')
            .with_event(lambda t: (t.log('Main task execution'), time.sleep(2.0)))
            .with_on_start(on_start)
            .with_on_completed(on_completed)
            .with_on_finish(on_finish)
            .with_comment('Demonstrates task lifecycle callbacks')
            .build()
        )

        self.manager.add_tasks(task)

    def add_complex_group(self):
        """Add a complex group with nested structures and dependencies."""

        # Create main group
        main_group = (
            TaskGroupBuilder('Complex Process Group')
            .with_comment('A complex group demonstrating advanced TQM features')
            .with_color('lightskyblue')
            .build()
        )

        # First sub-task directly in group
        init_task = (
            TaskBuilder('Initialize Process')
            .with_event(lambda t: (t.log('Initializing process...'), time.sleep(1.8)))
            .with_comment('First step in the complex process')
            .build()
        )

        # Create a nested group for parallel execution
        parallel_group = (
            TaskGroupBuilder('Parallel Tasks')
            .with_comment('These tasks can run in parallel')
            .with_wait_for(init_task)
            .with_color()
            .build()
        )

        # Create tasks for parallel execution
        for i in range(3):
            task = (
                TaskBuilder(f"Parallel Task {i+1}")
                .with_event(lambda t: (t.log(f"Running {t.name}..."), time.sleep(random.uniform(0.5, 2.0))))
                .with_comment(f"Parallel execution task {i+1}")
                .build()
            )
            parallel_group.add_tasks(task)

        # Final task to finish process
        finish_task = (
            TaskBuilder('Finalize Process')
            .with_event(lambda t: (t.log('Finalizing process...'), time.sleep(1.8)))
            .with_comment('Last step in the complex process')
            .with_wait_for(parallel_group)
            .build()
        )

        # # Add all tasks to the main group
        main_group.add_tasks(init_task, finish_task)

        # Add groups to manager
        self.manager.add_tasks(main_group, parallel_group)


def setup_manager() -> TQManager:
    """
    Run the TQM demo application.

    Returns:
        The QApplication instance if standalone=True, otherwise None.
    """

    # Setup task manager
    task_manager = TQManager(app_name='tqm_demo')
    task_manager.setWindowTitle('TQM Demo - Queue Task Manager')

    # Set up demo tasks
    demo_tasks = DemoTasks(task_manager)

    # Add various types of tasks
    demo_tasks.add_simple_tasks()
    demo_tasks.add_progress_tasks()
    demo_tasks.add_task_with_action()
    demo_tasks.add_failing_task()
    demo_tasks.add_task_group_sequence()
    demo_tasks.add_random_color_tasks()
    demo_tasks.add_task_with_callbacks()
    demo_tasks.add_complex_group()

    QMessageBox.information(
        task_manager,
        'TQM Demo',
        'Welcome to the TQM Demo!\n\n'
        'This demo showcases various features of the Queue Task Manager:\n'
        '• Simple tasks\n'
        '• Tasks with progress reporting\n'
        '• File-related tasks with context menu actions\n'
        '• Task failure and retry\n'
        '• Task groups\n'
        '• Task dependencies\n'
        '• Task colors\n'
        '• Complex nested groups\n'
        '• Task lifecycle callbacks\n\n'
        "Click 'Start Workers' to begin executing the tasks.\n"
        'You can interact with tasks by right-clicking on them.'
    )

    # Display the task manager
    return task_manager


def run_demo():
    """
    Main entry point when run as a script.
    """
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    window = QMainWindow()
    window.setCentralWidget(setup_manager())
    window.show()

    sys.exit(app.exec_())
