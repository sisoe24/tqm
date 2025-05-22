from __future__ import annotations

from typing import Any, Generator
from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from tqm import TQManager


@pytest.fixture
def app(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch
) -> Generator[TQManager, Any, None]:
    """Create a tqm widget for testing."""
    # Set environment variable to use test directory for database

    monkeypatch.setenv('TQM_IDLE_TIMEOUT', '200')
    monkeypatch.setenv('XDG_CONFIG_HOME', tmp_path.as_posix())

    # Create widget with temporary app name
    widget = TQManager(app_name='tmp_test')
    qtbot.addWidget(widget)

    yield widget

    widget.executor.registry.clear()
    widget.executor._threadpool.waitForDone()
