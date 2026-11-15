"""V14: retrying a task that is still waiting segfaults. It must raise TaskError instead."""
from _common import finish, noop, spin

from tqm import TQManager, TaskBuilder
from tqm.exceptions import TaskError

manager = TQManager('a')
task = TaskBuilder('t').with_event(noop).build()
manager.add_tasks(task)
try:
    manager.executor.retry_task(task)
except TaskError:
    pass
manager.start_workers()
spin(1)
finish(True)
