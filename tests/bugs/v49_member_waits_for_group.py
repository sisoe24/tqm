"""V49: a member that waits for its own group deadlocks it."""
from _common import finish, is_done, noop, spin

from tqm import TQManager, TaskBuilder, TaskGroupBuilder
from tqm.exceptions import TqmError

manager = TQManager('a')
group = TaskGroupBuilder('g').build()
member = TaskBuilder('t').with_event(noop).with_wait_for(group).build()
group.add_tasks(member)
try:
    manager.add_tasks(group)
except TqmError:
    finish(True)
manager.start_workers()
finish(spin(2, lambda: is_done(group)), f'group is {group.state.current}')
