"""V50: a task in two groups, removed while waiting, leaves the first group running."""
from _common import finish, is_done, noop, pause, spin

from tqm import TQManager, TaskBuilder, TaskGroupBuilder

manager = TQManager('a')
manager.set_max_workers(2)
busy = [TaskBuilder(f'x{i}').with_event(pause(0.3)).build() for i in range(3)]
shared = TaskBuilder('t').with_event(noop).build()
first = TaskGroupBuilder('g1').with_tasks(*busy, shared).build()
TaskGroupBuilder('g2').with_tasks(shared).build()
manager.add_tasks(first)
manager.start_workers()
spin(1, lambda: shared.state.is_waiting)
manager.remove_tasks(shared)
finish(spin(3, lambda: is_done(first)), f'first group is {first.state.current}')
