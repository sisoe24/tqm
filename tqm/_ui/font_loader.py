from __future__ import annotations

import os
import sys
from functools import cache

from PySide2.QtGui import QFont, QFontDatabase


def _load_custom_monospace_font() -> str:
    """Load bundled JetBrains Mono font from resources"""
    # Try to load from resources
    font_id = QFontDatabase.addApplicationFont(':/font/JetBrainsMonoNL-Regular.ttf')

    if font_id >= 0:
        # Successfully loaded from resources
        font_families = QFontDatabase.applicationFontFamilies(font_id)
        if font_families:
            return font_families[0]

    # Fallback to system font
    user_font = os.getenv('TQM_MONO_FONT', '')
    if user_font:
        return user_font

    if sys.platform == 'darwin':
        return 'Menlo'
    elif sys.platform == 'win32':
        return 'Consolas'
    return 'DejaVu Sans Mono'


@cache
def get_monospace_font(size: int = 12) -> QFont:
    """Get the application monospace font with specified size"""
    font_family = _load_custom_monospace_font()
    return QFont(font_family, size)
