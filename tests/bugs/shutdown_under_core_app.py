"""TaskExecutor is headless, so shutdown must not need a QApplication."""
import os
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))

from PySide2.QtCore import QTimer, QCoreApplication

from tqm import TaskBuilder, TaskExecutor

app = QCoreApplication([])
release = threading.Event()
executor = TaskExecutor()
task = TaskBuilder('t').with_event(lambda t: release.wait()).build()
executor.add_task(task)
executor.start_workers()
end = time.monotonic() + 5
while time.monotonic() < end and not task.state.is_running:
    app.processEvents()
QTimer.singleShot(0, release.set)
executor.shutdown()
sys.stderr.flush()
os._exit(0)
