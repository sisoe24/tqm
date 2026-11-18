"""V35: partial on runner.signals keeps dropped managers and their tasks alive."""
import gc
import weakref

from _common import finish, noop, spin

from tqm import TQManager, TaskBuilder

alive = []
for _ in range(5):
    manager = TQManager('a')
    task = TaskBuilder().with_event(noop).build()
    alive.append(weakref.ref(task))
    manager.add_tasks(task)
    manager.start_workers()
    spin(2, lambda: task.state.is_completed)
    manager.remove_tasks(task)
    spin(0.05)
    del task
    manager = None

gc.collect()
spin(0.1)
gc.collect()
left = sum(1 for ref in alive if ref() is not None)
finish(left == 0, f'{left} of 5 tasks still alive')
