"""V4: quitting the app while a group runs hangs the process."""
import sys

from _common import app, pause

from PySide2.QtCore import QTimer

from tqm import TQManager, TaskBuilder, TaskGroupBuilder

manager = TQManager('a')
manager.set_max_workers(2)
members = [TaskBuilder(f't{i}').with_event(pause(0.2)).build() for i in range(6)]
manager.add_tasks(TaskGroupBuilder('g').with_tasks(*members).build())
manager.start_workers()
manager.show()
QTimer.singleShot(200, app.quit)
app.exec_()
sys.exit(0)
