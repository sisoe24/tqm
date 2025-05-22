
from __future__ import annotations

import os
import sys
import json
from pathlib import Path

import pytest

from tqm._core.settings import Settings, open_settings, get_config_path


def test_windows_path(monkeypatch: pytest.MonkeyPatch):
    """Test path generation on Windows platform."""
    # Setup Windows environment
    monkeypatch.setattr(sys, 'platform', 'win32')
    monkeypatch.setenv('LOCALAPPDATA', '/fake/local')

    # Test
    result = get_config_path('test_app')

    # Check result
    assert str(result) == '/fake/local/tqm/test_app'

    # Clean up
    monkeypatch.delenv('LOCALAPPDATA')


def test_unix_path(monkeypatch: pytest.MonkeyPatch):
    """Test path generation on Unix platform."""
    # Setup Unix environment
    monkeypatch.setattr(sys, 'platform', 'linux')
    monkeypatch.setenv('XDG_CONFIG_HOME', '/fake/config')

    # Test
    result = get_config_path('test_app')

    # Check result
    assert str(result) == '/fake/config/tqm/test_app'

    # Clean up
    monkeypatch.delenv('XDG_CONFIG_HOME')


def test_windows_fallback(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Test Windows fallback when LOCALAPPDATA is not set."""
    # Setup
    monkeypatch.setattr(sys, 'platform', 'win32')
    monkeypatch.delenv('LOCALAPPDATA', raising=False)
    monkeypatch.setattr(Path, 'home', lambda: Path('/fake/home'))

    # Test
    result = get_config_path('test_app')

    # Check path structure is correct (not full path as home varies)
    assert str(result).endswith('/AppData/Local/tqm/test_app')


def test_unix_fallback(monkeypatch: pytest.MonkeyPatch):
    """Test Unix fallback when XDG_CONFIG_HOME is not set."""
    # Setup
    monkeypatch.setattr(sys, 'platform', 'linux')
    monkeypatch.delenv('XDG_CONFIG_HOME', raising=False)
    monkeypatch.setattr(Path, 'home', lambda: Path('/fake/home'))

    # Test
    result = get_config_path('test_app')

    # Check result
    assert str(result) == '/fake/home/.config/tqm/test_app'


def test_environment_variables_set():
    """Test that environment variables are properly set."""
    # Setup
    app_name = 'env_var_test'

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


def test_open_settings_read_only(mock_settings: Path):
    # we only modify the current instance
    with open_settings(json_file_path=mock_settings) as s:
        assert isinstance(s, Settings)
        s.wrap_lines = False

    # opening the settings again should have the same values
    with open_settings(json_file_path=mock_settings) as s:
        assert not s.wrap_lines

    # but the file should not have been modified
    with mock_settings.open() as s:
        assert len(json.load(s)) == 1  # only the xxx attribute


def test_open_settings_read_write(mock_settings: Path):
    with open_settings(mode='w', json_file_path=mock_settings) as s:
        assert isinstance(s, Settings)
        s.wrap_lines = False

    with mock_settings.open() as s:
        data = json.load(s)
        assert data['wrap_lines'] == False
