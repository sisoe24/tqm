
from __future__ import annotations

import os
import sys
import json
from pathlib import Path

import pytest

from tqm._core.settings import (Settings, get_qss_path, open_settings,
                               get_config_path)


def test_windows_path(monkeypatch: pytest.MonkeyPatch):
    """Test path generation on Windows platform."""
    # Setup Windows environment
    monkeypatch.setattr(sys, 'platform', 'win32')
    monkeypatch.setenv('LOCALAPPDATA', '/fake/local')

    # Test
    result = get_config_path('test_app')

    # Check result
    assert result == Path('/fake/local/tqm/test_app')


def test_unix_path(monkeypatch: pytest.MonkeyPatch):
    """Test path generation on Unix platform."""
    # Setup Unix environment
    monkeypatch.setattr(sys, 'platform', 'linux')
    monkeypatch.setenv('XDG_CONFIG_HOME', '/fake/config')

    # Test
    result = get_config_path('test_app')

    # Check result
    assert result == Path('/fake/config/tqm/test_app')


def test_windows_fallback(monkeypatch: pytest.MonkeyPatch):
    """Test Windows fallback when LOCALAPPDATA is not set."""
    # Setup
    monkeypatch.setattr(sys, 'platform', 'win32')
    monkeypatch.delenv('LOCALAPPDATA', raising=False)
    monkeypatch.setattr(Path, 'home', lambda: Path('/fake/home'))

    # Test
    result = get_config_path('test_app')

    # Check result
    assert result == Path('/fake/home/AppData/Local/tqm/test_app')


def test_unix_fallback(monkeypatch: pytest.MonkeyPatch):
    """Test Unix fallback when XDG_CONFIG_HOME is not set."""
    # Setup
    monkeypatch.setattr(sys, 'platform', 'linux')
    monkeypatch.delenv('XDG_CONFIG_HOME', raising=False)
    monkeypatch.setattr(Path, 'home', lambda: Path('/fake/home'))

    # Test
    result = get_config_path('test_app')

    # Check result
    assert result == Path('/fake/home/.config/tqm/test_app')


def test_environment_variables_set(monkeypatch: pytest.MonkeyPatch):
    """Test that environment variables are properly set."""
    # Setup
    app_name = 'env_var_test'
    monkeypatch.setenv('TQM_CONFIG_PATH', 'stale')
    monkeypatch.setenv('TQM_SETTINGS_PATH', 'stale')

    # Test
    result = get_config_path(app_name)

    # Check environment variables
    assert os.environ['TQM_CONFIG_PATH'] == str(result)
    assert os.environ['TQM_SETTINGS_PATH'] == str(result / 'settings.json')


@pytest.fixture
def mock_settings(tmp_path: Path):
    f = tmp_path / 'settings.json'

    # this attribute is not in the settings.Settings class and should not break
    f.write_text('{"xxx": -1}')

    yield f
    f.unlink()


def test_load_from_json(tmp_path: Path):
    f = tmp_path / 'settings.json'
    f.write_text('{"max_workers": 3, "wrap_lines": false, "enable_debug": true}')

    with open_settings(json_file_path=f) as s:
        assert s.max_workers == 3
        assert s.wrap_lines is False
        assert s.enable_debug is True


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V28')
def test_load_from_json_keeps_known_keys_on_unknown_key(tmp_path: Path):
    f = tmp_path / 'settings.json'
    f.write_text('{"max_workers": 3, "xxx": -1}')

    with open_settings(json_file_path=f) as s:
        assert s.max_workers == 3


def test_open_settings_read_only(mock_settings: Path):
    # we only modify the current instance
    with open_settings(json_file_path=mock_settings) as s:
        assert isinstance(s, Settings)
        s.wrap_lines = False

    # but the file should not have been modified
    with mock_settings.open() as s:
        assert json.load(s) == {'xxx': -1}


def test_open_settings_read_write(mock_settings: Path):
    with open_settings(mode='w', json_file_path=mock_settings) as s:
        assert isinstance(s, Settings)
        s.wrap_lines = False

    with mock_settings.open() as s:
        data = json.load(s)
        assert data['wrap_lines'] == False


def test_open_settings_writes_defaults_for_a_new_file(tmp_path: Path):
    f = tmp_path / 'settings.json'

    with open_settings(json_file_path=f):
        pass

    assert json.loads(f.read_text())['max_workers'] == Settings().max_workers


def test_qss_path_uses_the_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv('TQM_QSS_PATH', '/fake/style.qss')

    assert get_qss_path(tmp_path) == Path('/fake/style.qss')


def test_qss_path_keeps_the_user_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv('TQM_QSS_PATH', raising=False)
    (tmp_path / 'style.qss').write_text('mine')

    assert get_qss_path(tmp_path).read_text() == 'mine'
