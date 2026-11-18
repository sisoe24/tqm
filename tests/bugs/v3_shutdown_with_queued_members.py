"""V3: shutdown hangs when a running group still has queued members."""
from _common import finish, pause, spin

from tqm import TQManager, TaskBuilder, TaskGroupBuilder

manager = TQManager('a')
manager.set_max_workers(2)
members = [TaskBuilder(f't{i}').with_event(pause(0.2)).build() for i in range(8)]
manager.add_tasks(TaskGroupBuilder('g').with_tasks(*members).build())
manager.start_workers()
spin(0.15)
manager.executor.shutdown()
finish(True)
