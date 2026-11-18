"""V50: removing a finished inner group from a running outer group leaves the outer group running."""
from _common import finish, is_done, noop, pause, spin

from tqm import TQManager, TaskBuilder, TaskGroupBuilder

manager = TQManager('a')
inner = TaskGroupBuilder('inner').with_tasks(TaskBuilder('c').with_event(noop).build()).build()
outer = TaskGroupBuilder('outer').build()
outer.add_tasks(inner, TaskBuilder('k').with_event(pause(0.5)).build())
manager.add_tasks(outer)
manager.start_workers()
spin(1, lambda: inner.state.is_completed)
manager.remove_tasks(inner)
finish(spin(3, lambda: is_done(outer)), f'outer group is {outer.state.current}')
