"""V1: cyclic GC on a worker thread destroys main-thread QObjects after a manager is replaced."""
import os
import time

from _common import finish, is_done, spin

from tqm import TQManager, TaskBuilder

os.environ['TQM_IDLE_TIMEOUT'] = '200'


def alloc(task):
    [{} for _ in range(300)]
    time.sleep(0.005)


def throw(error):
    # A plain raise does not crash here. Raising through a generator crashes every run.
    return (_ for _ in ()).throw(error)


def fail_once(task):
    alloc(task)
    task.data['runs'] = task.data.get('runs', 0) + 1
    return throw(ValueError('x')) if task.data['runs'] < 2 else None


for _ in range(5):
    manager = TQManager('a')
    tasks = [TaskBuilder().with_event(fail_once).with_retry(2, 0).build() for _ in range(10)]
    manager.add_tasks(*tasks)
    manager.start_workers()
    spin(5, lambda: all(is_done(t) for t in tasks))
    del tasks

keep = manager
for _ in range(10):
    tasks = [TaskBuilder().with_event(alloc).build() for _ in range(20)]
    keep.add_tasks(*tasks)
    keep.start_workers()
    spin(5, lambda: all(is_done(t) for t in tasks))

finish(True)
