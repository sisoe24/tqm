from __future__ import annotations

from typing import Any, Callable, Optional
from functools import partial


def extract_fn_name(func: Optional[Callable[..., Any]]) -> str:
    """
    Extracts the name of a function for debugging purposes.

    Args:
        func (Optional[Callable[..., Any]]): The function to extract the name from.

    Returns:
        str: The name of the function.

    """
    if not func:
        return ''

    if isinstance(func, partial):
        return func.func.__name__

    try:
        return func.__name__
    except Exception:
        return str(func)
