"""V32 and Q7: adding a task from a worker thread raises TaskError instead of corrupting the queue."""
import contextlib

from _common import finish, is_done, noop, spin

from tqm import TQManager, TaskBuilder
from tqm.exceptions import TaskError

manager = TQManager('a')
manager.set_max_workers(16)
rejected = []


def spawn(task):
    for i in range(40):
        try:
            manager.add_event(noop, label=f'x{i}')
        except TaskError:
            rejected.append(i)
    with contextlib.suppress(TaskError):
        manager.start_workers()


seeds = [TaskBuilder(f's{i}').with_event(spawn).build() for i in range(16)]
manager.add_tasks(*seeds)
manager.start_workers()
spin(10, lambda: all(is_done(s) for s in seeds))
finish(len(rejected) == 640, f'{len(rejected)} of 640 adds rejected')
