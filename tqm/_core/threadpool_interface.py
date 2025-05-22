"""ThreadPoolInterface and ThreadPoolWrapper classes.

This module only exists to simplify testing by providing a
ThreadPoolInterface that can be mocked.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from PySide2.QtCore import QObject, QRunnable, QThreadPool


class ThreadPoolInterface(ABC):
    @abstractmethod
    def start(self, runnable: QRunnable, priority: int = ...) -> None: ...
    @abstractmethod
    def activeThreadCount(self) -> int: ...
    @abstractmethod
    def waitForDone(self) -> None: ...
    @abstractmethod
    def setMaxThreadCount(self, max_thread_count: int) -> None: ...


class ThreadPoolWrapper(ThreadPoolInterface):
    def __init__(self, parent: QObject):
        self._threadpool = QThreadPool(parent)

    def start(self, runnable: QRunnable, priority: int = 0) -> None:
        self._threadpool.start(runnable, priority)

    def activeThreadCount(self) -> int:
        return self._threadpool.activeThreadCount()

    def waitForDone(self) -> None:
        self._threadpool.waitForDone()

    def setMaxThreadCount(self, max_thread_count: int) -> None:
        self._threadpool.setMaxThreadCount(max_thread_count)
