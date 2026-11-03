"""Retrying a task as soon as its state turns failed segfaults, without any group or retry policy."""
import time

from _common import app, finish, spin

from tqm import TQManager, TaskBuilder

manager = TQManager('a')


def event(task):
    raise RuntimeError('boom')


task = TaskBuilder('t').with_event(event).build()
manager.add_tasks(task)
manager.start_workers()

end = time.monotonic() + 5
while time.monotonic() < end:
    app.processEvents()
    if task.state.is_failed:
        manager.executor.retry_task(task)

spin(0.2)
finish(True)
