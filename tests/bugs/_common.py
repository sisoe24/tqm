"""Shared setup for the scripts in this folder. They exit 0 when the bug is gone."""
from __future__ import annotations

import os
import sys
import time
from typing import Any, Callable, Optional
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))

from PySide2.QtCore import QEvent, QEventLoop, QCoreApplication
from PySide2.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


def spin(seconds: float, until: Optional[Callable[[], bool]] = None) -> bool:
    """Run the event loop for some seconds, or until the condition is true."""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents(QEventLoop.AllEvents, 20)
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        if until and until():
            return True
        time.sleep(0.002)
    return until is None


def finish(ok: bool, message: str = '') -> None:
    """Skip interpreter teardown: a stuck worker must not turn a verdict into a hang."""
    print(message, file=sys.stderr, flush=True)
    os._exit(0 if ok else 1)


def is_done(task: Any) -> bool:
    return task.state.is_completed or task.state.is_failed


def noop(task: Any = None) -> None:
    pass


def boom(task: Any = None) -> None:
    raise RuntimeError('boom')


def pause(seconds: float) -> Callable[[Any], None]:
    def event(task: Any) -> None:
        time.sleep(seconds)
    return event
