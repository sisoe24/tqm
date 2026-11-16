from __future__ import annotations

import os
import sys
import json
from typing import Any, Dict, Literal, Generator
from pathlib import Path
from contextlib import contextmanager
from dataclasses import field, asdict, dataclass


def get_config_path(app_name: str) -> Path:
    """
    Get the config directory path for the application.

    Args:
        app_name (str): The name of the application

    Returns:
        Path: The config directory path for the application.
    """
    home = Path.home()

    if sys.platform == 'win32':
        env = os.getenv('LOCALAPPDATA')
        path = (
            Path(env) / 'tqm' / app_name
            if env
            else home / 'AppData' / 'Local' / 'tqm' / app_name
        )
    else:
        env = os.environ.get('XDG_CONFIG_HOME')
        path = (
            Path(env) / 'tqm' / app_name
            if env
            else home / '.config' / 'tqm' / app_name
        )

    return path


def get_qss_path(config_path: Path) -> Path:
    """Returns the style qss path.

    Uses the environment variable `TQM_QSS_PATH` if set.

    """
    env = os.getenv('TQM_QSS_PATH')
    if env:
        return Path(env)

    user_qss = config_path / 'style.qss'
    base_qss = Path(__file__).parent.parent / 'theme' / 'style.qss'

    if not user_qss.exists():
        user_qss.write_text(base_qss.read_text())

    return user_qss


@dataclass
class Settings:
    max_workers: int = 20
    enable_debug: bool = False
    wrap_lines: bool = True
    view: Dict[str, Any] = field(default_factory=dict[str, Any], repr=False)


@contextmanager
def open_settings(
    mode: Literal['r', 'w'] = 'r',
    *, json_file_path: Path
) -> Generator[Settings, Any, None]:
    """Open settings context manager.

    ```
    with open_settings(mode='r', json_file_path=path) as s:
        s.save_to_db = True
        s.focus_tab_on_error = False
    ```
    """
    settings = Settings()
    try:
        with json_file_path.open() as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError(f'expected an object, got {data!r}')

        # Keep each known key with the default's type, so one bad key does not reset the rest.
        for name, value in data.items():
            if name in asdict(settings) and type(value) is type(getattr(settings, name)):
                setattr(settings, name, value)

    except FileNotFoundError:
        with json_file_path.open('w') as f:
            json.dump(asdict(settings), f, indent=4)

    except Exception as e:
        print('[tqm error]: Invalid settings file. Resetting settings.', e)

    yield settings

    if mode != 'w':
        return

    with json_file_path.open('w') as f:
        json.dump(asdict(settings), f, indent=4)
