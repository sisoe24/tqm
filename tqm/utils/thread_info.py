
from __future__ import annotations

import threading
from pprint import pformat
from typing import Any, Dict, Union

from PySide2.QtCore import QThread


def get_thread_info(pretty: bool = False) -> Union[str, Dict[str, Any]]:
    """Get information about the current thread."""
    current_thread = threading.current_thread()
    qt_thread = QThread.currentThread()
    info: Dict[str, Any] = {
        'name': current_thread.name,
        'id': threading.get_ident(),
        'native_id': current_thread.native_id,
        'qt_thread_id': qt_thread.currentThread()
    }
    return pformat(info) if pretty else info
