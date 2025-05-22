from __future__ import annotations

import os
import sys
import json
from typing import Any, Dict, Literal, Optional, Generator
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

    os.environ['TQM_CONFIG_PATH'] = str(path)
    os.environ['TQM_SETTINGS_PATH'] = str(path / 'settings.json')

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


class _SingletonMeta(type):
    _instance = None

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        if not cls._instance:
            instance = super().__call__(*args, **kwargs)
            cls._instance = instance
        return cls._instance


@dataclass
class Settings(metaclass=_SingletonMeta):
    max_workers: int = 20
    enable_debug: bool = False
    wrap_lines: bool = True
    view: Dict[str, Any] = field(default_factory=dict[str, Any], repr=False)


@contextmanager
def open_settings(
    mode: Literal['r', 'w'] = 'r',
    *, json_file_path: Optional[Path] = None
) -> Generator[Settings, Any, None]:
    """Open settings context manager.

    ```
    with open_settings(mode='r') as s:
        s.save_to_db = True
        s.focus_tab_on_error = False
    ```
    """
    if json_file_path is None:
        json_file_path = Path(os.environ['TQM_SETTINGS_PATH'])

    try:
        with json_file_path.open() as f:
            settings = Settings(**json.load(f))

    except FileNotFoundError:
        settings = Settings()
        with json_file_path.open('w') as f:
            json.dump(asdict(settings), f, indent=4)

    except Exception as e:
        print('[tqm error]: Invalid settings file. Resetting settings.', e)
        settings = Settings()

    yield settings

    if mode != 'w':
        return

    with json_file_path.open('w') as f:
        json.dump(asdict(settings), f, indent=4)
