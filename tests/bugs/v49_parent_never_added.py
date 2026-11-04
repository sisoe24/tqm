"""V49: a child whose parent was never added blocks forever."""
from _common import finish, is_done, noop, spin

from tqm import TQManager, TaskBuilder
from tqm.exceptions import TqmError

manager = TQManager('a')
parent = TaskBuilder('never').with_event(noop).build()
child = TaskBuilder('c').with_event(noop).with_wait_for(parent).build()
try:
    manager.add_tasks(child)
except TqmError:
    finish(True)
manager.start_workers()
finish(spin(2, lambda: is_done(child)), f'child is {child.state.current}')
