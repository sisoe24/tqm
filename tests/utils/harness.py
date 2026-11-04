from __future__ import annotations

import sys
import subprocess
from typing import List
from pathlib import Path

from PySide2.QtCore import QRunnable
from PySide2.QtWidgets import QApplication

from tqm._core.threadpool_interface import ThreadPoolInterface


class StepPool(ThreadPoolInterface):
    """Run each started runnable on the main thread, only when the test asks.

    Groups cannot use this pool until R4, because GroupRunner.run spins inline.
    """

    def __init__(self) -> None:
        self.pending: List[QRunnable] = []

    def start(self, runnable: QRunnable, priority: int = 0) -> None:
        self.pending.append(runnable)

    def activeThreadCount(self) -> int:
        return len(self.pending)

    def waitForDone(self) -> None:
        pass

    def setMaxThreadCount(self, max_thread_count: int) -> None:
        pass

    def step(self) -> None:
        """Run the oldest runnable, then deliver the queued signals it emitted."""
        # The runnable counts as active while it runs, as it does in a real pool.
        self.pending[0].run()
        self.pending.pop(0)
        QApplication.processEvents()

    def drain(self) -> None:
        """Run every started runnable, and the ones that they start."""
        while self.pending:
            self.step()


def assert_script_passes(script: Path, timeout: float = 30) -> None:
    """Run a script that may poison the process. A crash or a hang is an AssertionError."""
    try:
        process = subprocess.run(
            [sys.executable, '-u', str(script)],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False
        )
    except subprocess.TimeoutExpired as error:
        raise AssertionError(f'{script.name} hung for {timeout}s') from error

    assert process.returncode == 0, (
        f'{script.name} exited with {process.returncode}\n{process.stderr[-2000:]}'
    )
