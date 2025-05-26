"""
Queue Task Manager: PySide2 parallel task queuing and execution framework.
"""

from __future__ import annotations

from .version import __version__

from ._core import logger
from ._core.logger import write_log
try:
    from . import _resources_rc
except ImportError:
    import warnings
    warnings.warn(
        "Resource file '_resources_rc.py' not found. "
        'Some UI resources may not be available. '
        'If you are developing, ensure resources are compiled and available in the package.',
    )


from . import exceptions
from ._core import retry_policy
from ._main import TQManager
from ._core.task import TaskExecutable, TaskGroup, TaskUnit
from ._core.task_builder import TaskBuilder, TaskGroupBuilder
from ._core.task_executor import TaskExecutor
from ._core.task_actions import TaskActionVisibility
from .widgets.help_widget import about


__all__ = [
    'exceptions',
    'write_log',
    'retry_policy',
    'TaskExecutable',
    'TaskUnit',
    'TaskGroup',
    'TaskBuilder',
    'TaskGroupBuilder',
    'TaskActionVisibility',
    'TQManager',
    'TaskExecutor',
    'about',
    '__version__',
]
