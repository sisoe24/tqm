"""V2: each group holds a pool thread while polling, so max_workers + 1 groups deadlock."""
from _common import finish, is_done, noop, spin

from tqm import TQManager, TaskBuilder, TaskGroupBuilder

manager = TQManager('a')
groups = [
    TaskGroupBuilder(f'g{i}').with_tasks(TaskBuilder(f't{i}').with_event(noop).build()).build()
    for i in range(manager.executor.max_workers + 1)
]
manager.add_tasks(*groups)
manager.start_workers()
finish(spin(5, lambda: all(is_done(g) for g in groups)), 'groups never finished')
