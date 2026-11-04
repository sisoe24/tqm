"""V38: Retry All can leave a group failed while every member completed."""
import time

from _common import finish, noop, spin

from tqm import TQManager, TaskBuilder, TaskGroupBuilder

manager = TQManager('a')
members = [TaskBuilder(f't{i}').with_event(lambda t: 1 / 0).build() for i in range(3)]
group = TaskGroupBuilder('g').with_tasks(*members).build()
manager.add_tasks(group)
manager.start_workers()
spin(3, lambda: group.state.is_failed)

for member in members:
    member.execute = noop

retry_task = manager.executor.retry_task


def retry_with_stalled_main(task):
    retry_task(task)
    # CPU load hit this in 2 of 240 rounds: the new runner polls before main resets the members.
    if task is group:
        time.sleep(0.05)


manager.executor.retry_task = retry_with_stalled_main
manager.operations.retry_all_failed()
spin(3, lambda: all(m.state.is_completed for m in members))
spin(0.5, lambda: group.state.is_completed)
finish(group.state.is_completed, f'group is {group.state.current}')
