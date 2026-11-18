"""V49: a group that waits for its own member never starts."""
from _common import finish, is_done, noop, spin

from tqm import TQManager, TaskBuilder, TaskGroupBuilder
from tqm.exceptions import TqmError

manager = TQManager('a')
member = TaskBuilder('t').with_event(noop).build()
group = TaskGroupBuilder('g').with_tasks(member).with_wait_for(member).build()
try:
    manager.add_tasks(group)
except TqmError:
    finish(True)
manager.start_workers()
finish(spin(2, lambda: is_done(group)), f'group is {group.state.current}')
