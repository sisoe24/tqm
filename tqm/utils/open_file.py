from __future__ import annotations

import os
import shlex
import platform
import subprocess


def open_file(file_path: str, reveal: bool = False) -> None:
    """
    Opens the specified file using the default application associated with the file type.

    Args:
        file_path (str): The path of the file to be opened.
        reveal (bool, optional): If True, the file will be revealed in the file
        explorer. Defaults to False.

    Raises:
        Exception: If the operating system is not supported.

    """
    if not os.path.exists(file_path):
        return

    if platform.system() == 'Darwin':
        subprocess.run(
            shlex.split(f'open -R "{file_path}"' if reveal else f'open "{file_path}"')
        )

    elif platform.system() == 'Windows':
        if reveal:
            subprocess.run(f'explorer /select,"{file_path}"', shell=True)
        else:
            os.startfile(file_path)

    elif platform.system() == 'Linux':
        subprocess.run(
            ['xdg-open', os.path.dirname(file_path) if reveal else file_path]
        )

    else:
        raise OSError(f'{platform.system()} is not supported.')
