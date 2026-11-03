"""V14: retrying a task that is still waiting segfaults."""
from _common import finish, noop, spin

from tqm import TQManager, TaskBuilder

manager = TQManager('a')
task = TaskBuilder('t').with_event(noop).build()
manager.add_tasks(task)
manager.executor.retry_task(task)
manager.start_workers()
spin(1)
finish(True)
