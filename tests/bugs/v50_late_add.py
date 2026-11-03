"""V50: a member added to a running group never runs and the group never ends."""
from _common import finish, is_done, noop, pause, spin

from tqm import TQManager, TaskBuilder, TaskGroupBuilder
from tqm.exceptions import TqmError

manager = TQManager('a')
group = TaskGroupBuilder('g').with_tasks(TaskBuilder('a').with_event(pause(0.3)).build()).build()
manager.add_tasks(group)
manager.start_workers()
spin(2, lambda: group.state.is_running)
try:
    group.add_event(noop, label='late')
except TqmError:
    finish(True)
finish(spin(2, lambda: is_done(group)), f'group is {group.state.current}')
