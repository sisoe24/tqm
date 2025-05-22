# tqm: Task Queue Manager

A simple PySide2 no-dependency framework for managing and executing tasks in parallel with a nice UI. Helps you create, queue, and track multiple tasks with dependencies and progress reporting.

![demo](resources/images/tqm-demo.gif)

## What is this?

TQM lets you run multiple tasks in the background while showing their progress in a UI. It's built with only PySide2 and handles all the complex stuff like threading, dependencies between tasks and UI.

Basically, a Task Queue Manager.

## Features

- **Task Management**
  - Run multiple tasks in parallel (multi-threaded)
  - Create task groups with parent-child relationships
  - Set dependencies so tasks wait for others to finish
  - Retry tasks automatically if they fail

- **UI Features**
  - Progress bars (both determinate and indeterminate)
  - Task filtering and search
  - Context menus for task actions
  - Detailed debug view showing task properties

- **Developer Features**
  - Simple API for creating and queuing tasks
  - Callbacks for task lifecycle events (start, finish, fail, complete)
  - Predicates to control when tasks should run
  - Customizable task colors and more
  - Comprehensive typing annotations

## Installation

Currently, TQM is distributed as a package. Install using pip:

```bash
pip install path/to/tqm-0.1.0.tar.gz
```

Or with Poetry:

```bash
poetry add path/to/tqm-0.1.0.tar.gz
```

Dependencies:
- PySide2

## Quick Start

```python
import time
from PySide2.QtWidgets import QApplication
from tqm import TasksManager

def some_task(task):
    # This will run in a separate thread
    time.sleep(2)
    task.log("Task completed!")

# Create the application
app = QApplication([])

# Create the task manager window
task_manager = TasksManager(app_name="my_app")
task_manager.show()

# Add a simple task
task_manager.add_event(
    execute=some_task,
    label="My First Task",
    comment="This is a sample task"
)

# Start executing tasks
task_manager.start_workers()

# Run the application
app.exec_()
```

## Examples

### Creating a simple task

```python
# Add a single task that does something
task_manager.add_event(
    execute=lambda task: print("Hello, world!"),
    label="Simple Task",
    comment="Prints a greeting"
)
```

### Creating a task group

```python
# Create a group of related tasks
with task_manager.create_group("Download Files") as group:
    group.add_event(lambda t: t.log("Downloading file 1"), label="File 1")
    group.add_event(lambda t: t.log("Downloading file 2"), label="File 2")
    group.add_event(lambda t: t.log("Downloading file 3"), label="File 3")
```

### Using the TaskBuilder for more control

```python
from tqm import TaskBuilder

# Create a task with the builder pattern
task = (
    TaskBuilder("Complex Task")
    .with_event(lambda t: t.log("Task running..."))
    .with_comment("A task with callbacks")
    .with_on_start(lambda t: print("Starting task"))
    .with_on_completed(lambda t: print("Task completed"))
    .with_on_failed(lambda t: print("Task failed"))
    .with_color("blue")
    .with_retry_failed(max_retries=3)  # Retry up to 3 times if it fails
    .build()
)

# Add it to the task manager
task_manager.add(task)
```

### Tasks with dependencies

```python
# Create tasks with dependencies
task1 = TaskBuilder("Task 1").with_event(lambda t: t.log("Task 1 done")).build()
task2 = (
    TaskBuilder("Task 2")
    .with_event(lambda t: t.log("Task 2 done"))
    .with_wait_for(task1)  # This will wait for task1 to complete
    .build()
)

task_manager.add(task1, task2)
```

## Configuration

tqm stores its settings in:
- Windows: `%LOCALAPPDATA%\tqm\[app_name]\`
- Linux/Mac: `~/.config/tqm/[app_name]/`

You can customize various settings like the maximum number of worker threads:

```python
from tqm._core.settings import open_settings

with open_settings(mode='w') as s:
    s.max_workers = 10
    s.enable_debug = True
```

## Current Status

tqm is still under development but stable enough for most use cases. Some features and documentation might be improved in future updates.

See the GitHub project for more information.

## License

This project is licensed under MIT.
