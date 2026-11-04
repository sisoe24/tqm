"""V33: a member removed while GroupRunner iterates kills the worker and leaves the group running."""
import threading

from _common import finish, is_done, noop, spin

from tqm import TQManager, TaskBuilder, TaskGroupBuilder
from tqm._core.task_state import TaskState

manager = TQManager('a')
members = [TaskBuilder(f't{i}').with_event(noop).build() for i in range(3)]
group = TaskGroupBuilder('g').with_tasks(*members).build()


class RemovedDuringPoll(TaskState):
    """Stand in for the main thread: the race window is too small to hit on demand."""

    @property
    def is_completed(self):
        done = super().is_completed
        if done and threading.current_thread() is not threading.main_thread():
            group.tasks.discard(members[1])
        return done


members[0].state.__class__ = RemovedDuringPoll
manager.add_tasks(group)
manager.start_workers()
finish(spin(2, lambda: is_done(group)), f'group is {group.state.current}')
