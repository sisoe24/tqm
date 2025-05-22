"""Shutdown tasks for the task runner.

This module contains the shutdown tasks for the task runner. The shutdown tasks
will wait (blocking the main thread) for all tasks to complete before shutting down
the workers.

"""
from __future__ import annotations

from typing import Optional

from PySide2.QtCore import Signal, QObject, QThread, QEventLoop
from PySide2.QtWidgets import QProgressDialog

from .threadpool_interface import ThreadPoolInterface


class ShutdownWorker(QObject):
    finished = Signal()

    def __init__(self, threadpool: ThreadPoolInterface) -> None:
        super().__init__()
        self.threadPool = threadpool

    def run(self) -> None:
        self.threadPool.waitForDone()
        self.finished.emit()


class ShutdownThread(QObject):
    def __init__(self, threadpool: ThreadPoolInterface) -> None:
        super().__init__()

        self.threadPool = threadpool
        self.progressDialog: Optional[QProgressDialog] = None

    def run(self) -> None:
        self.shutdownThread = QThread()
        self.shutdownWorker = ShutdownWorker(self.threadPool)

        self.shutdownWorker.moveToThread(self.shutdownThread)
        self.shutdownWorker.finished.connect(self.onShutdownComplete)

        self.shutdownThread.started.connect(self.shutdownWorker.run)

        self.progressDialog = QProgressDialog('Shutting down, please wait...', '', 0, 0)
        self.progressDialog.setCancelButton(None)
        self.progressDialog.setModal(True)
        self.progressDialog.show()

        self.shutdownThread.start()
        event_loop = QEventLoop()
        self.shutdownThread.finished.connect(event_loop.quit)
        event_loop.exec_()

    def onShutdownComplete(self) -> None:
        self.shutdownThread.quit()
        self.shutdownThread.wait()
        if self.progressDialog:
            self.progressDialog.accept()
