from __future__ import annotations

import os
import json
from typing import Dict, Callable
from pathlib import Path

import pytest

from tqm import TQManager
from tqm._core.settings import get_config_path
from tqm._ui.font_loader import get_monospace_font

from ..utils import must_not_raise


def write_settings(app_name: str, settings: Dict[str, object]) -> Path:
    folder = Path(os.environ['XDG_CONFIG_HOME']) / 'tqm' / app_name
    folder.mkdir(parents=True)
    path = folder / 'settings.json'
    path.write_text(json.dumps(settings))
    return path


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V26')
def test_each_manager_reads_its_own_settings(make_manager: Callable[[str], TQManager]):
    write_settings('a', {'max_workers': 3})
    write_settings('b', {'max_workers': 9})

    first, second = make_manager('a'), make_manager('b')

    assert first.executor.max_workers == 3
    assert second.executor.max_workers == 9


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V26')
def test_each_manager_writes_its_own_settings(make_manager: Callable[[str], TQManager]):
    path_a = write_settings('a', {'max_workers': 3})
    path_b = write_settings('b', {'max_workers': 9})
    first, _ = make_manager('a'), make_manager('b')

    first.operations.set_max_workers(7)

    assert json.loads(path_a.read_text())['max_workers'] == 7
    assert json.loads(path_b.read_text())['max_workers'] == 9


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V28')
def test_null_view_setting_does_not_break_the_constructor(make_manager: Callable[[str], TQManager]):
    write_settings('a', {'view': None})

    with must_not_raise(TypeError):
        make_manager('a')


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V57')
@pytest.mark.parametrize('name', ['TQM_CONFIG_PATH', 'TQM_SETTINGS_PATH'])
def test_preset_path_variable_is_not_overwritten(name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    preset = str(tmp_path / 'preset')
    monkeypatch.setenv(name, preset)

    get_config_path('a')

    assert os.environ[name] == preset


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V58')
def test_mono_font_variable_wins_over_the_bundled_font(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv('TQM_MONO_FONT', 'Courier New')
    get_monospace_font.cache_clear()

    family = get_monospace_font().family()
    get_monospace_font.cache_clear()

    assert family == 'Courier New'


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V59')
def test_bad_qss_path_does_not_break_the_constructor(make_manager: Callable[[str], TQManager], monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv('TQM_QSS_PATH', '/nonexistent/x.qss')

    with must_not_raise(FileNotFoundError):
        make_manager('a')


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V59')
def test_bad_idle_timeout_does_not_break_the_constructor(make_manager: Callable[[str], TQManager], monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv('TQM_IDLE_TIMEOUT', 'abc')

    with must_not_raise(ValueError):
        make_manager('a')
