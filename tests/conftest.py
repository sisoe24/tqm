from __future__ import annotations

import gc
import os
import threading
import faulthandler
from typing import Any, List, Callable, Generator
from pathlib import Path
from unittest import mock

import pytest
from PySide2.QtCore import QEvent
from pytestqt.qtbot import QtBot
from PySide2.QtWidgets import QWidget, QApplication

from tqm import TQManager
from tqm._core.logger import LOGGER
from tqm._core.settings import Settings
from tqm._core.task_executor import TaskExecutor

from .utils.harness import StepPool

ROOT = Path(__file__).parent.parent
WATCHDOG_SECONDS = int(os.getenv('TQM_TEST_WATCHDOG', '60'))
WATCHDOG_LOG = Path(os.getenv('TQM_TEST_WATCHDOG_LOG', ROOT / 'tmp' / 'test-watchdog.log'))

_open_gates: List[threading.Event] = []


def pytest_configure(config: pytest.Config) -> None:
    # The dump must go to a file: stderr is lost under fd capture.
    WATCHDOG_LOG.parent.mkdir(parents=True, exist_ok=True)
    config.watchdog_log = WATCHDOG_LOG.open('w')


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item: pytest.Item) -> Generator[None, Any, None]:
    """Kill the session if a test hangs, and log which test it was."""
    log = item.config.watchdog_log
    log.write(f'{item.nodeid}\n')
    log.flush()
    faulthandler.dump_traceback_later(WATCHDOG_SECONDS, exit=True, file=log)
    yield
    faulthandler.cancel_dump_traceback_later()


def pytest_unconfigure(config: pytest.Config) -> None:
    # A stuck worker also blocks process exit, after the summary has printed.
    faulthandler.dump_traceback_later(WATCHDOG_SECONDS, exit=True, file=config.watchdog_log)


def _release_gates() -> None:
    while _open_gates:
        _open_gates.pop().set()


def _delete_now(widget: QWidget) -> None:
    # A pending settings-save timer must not fire in a later test.
    widget.close()
    widget.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.DeferredDelete)


@pytest.fixture(autouse=True)
def isolate_global_state(tmp_path: Path) -> Generator[None, Any, None]:
    """Keep each test away from the real config dir and from the state of other tests.

    The patch restores env vars that the code writes directly. Delete the Settings
    part at R9, the LOGGER part at R10 and the gc part at R5, or they will mask regressions.
    """
    # V1: GC on a worker thread segfaults once dropped managers pile up. Its script covers it.
    gc.disable()
    handlers = list(LOGGER.handlers)
    widget_handler = LOGGER.widget
    Settings._instance = None

    with mock.patch.dict(os.environ, {'XDG_CONFIG_HOME': tmp_path.as_posix()}):
        os.environ.pop('TQM_CONFIG_PATH', None)
        os.environ.pop('TQM_SETTINGS_PATH', None)
        yield

    _release_gates()
    Settings._instance = None
    LOGGER.widget = widget_handler
    for handler in set(LOGGER.handlers) - set(handlers):
        LOGGER.removeHandler(handler)
        handler.close()
    LOGGER.handlers[:] = handlers
    gc.collect()
    gc.enable()


@pytest.fixture
def gate() -> Callable[[], threading.Event]:
    """Create events for blocking a task. Teardown always releases them."""
    def make_gate() -> threading.Event:
        event = threading.Event()
        _open_gates.append(event)
        return event

    return make_gate


@pytest.fixture
def step_pool(qapp: Any) -> StepPool:
    return StepPool()


@pytest.fixture
def executor(step_pool: StepPool) -> TaskExecutor:
    """Create a headless executor where the test decides when each task runs."""
    return TaskExecutor(threadpool=step_pool)


@pytest.fixture
def app(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch
) -> Generator[TQManager, Any, None]:
    """Create a tqm widget for testing."""
    monkeypatch.setenv('TQM_IDLE_TIMEOUT', '200')

    # Create widget with temporary app name
    widget = TQManager(app_name='tmp_test')

    yield widget

    widget.executor.registry.clear()
    _release_gates()
    # waitForDone would block the main-thread slots that a running group needs.
    qtbot.wait_until(lambda: widget.executor._threadpool.activeThreadCount() == 0, timeout=5000)

    _delete_now(widget)


@pytest.fixture
def make_manager() -> Generator[Callable[[str], TQManager], Any, None]:
    """Create extra managers, for tests that need their own settings or several windows."""
    widgets: List[TQManager] = []

    def make(app_name: str) -> TQManager:
        widgets.append(TQManager(app_name))
        return widgets[-1]

    yield make

    for widget in widgets:
        _delete_now(widget)
