from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Tuple, Callable, Optional
from datetime import datetime
from dataclasses import field, dataclass

from PySide2.QtGui import QColor


class TaskStateEnum(str, Enum):
    """Enum representing the possible states of a task."""
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'
    BLOCKED = 'blocked'
    RETRYING = 'retrying'
    DELETED = 'deleted'
    WAITING = 'waiting'
    INACTIVE = 'inactive'


class TaskStates:
    """Singleton class managing the configuration for task states."""

    COLORS = {
        TaskStateEnum.RUNNING:   QColor('#61AFEF'),  # BLUE
        TaskStateEnum.COMPLETED: QColor('#3FC13F'),  # GREEN
        TaskStateEnum.BLOCKED:   QColor('#D19A66'),  # ORANGE
        TaskStateEnum.RETRYING:  QColor('#C678DD'),  # PURPLE
        TaskStateEnum.FAILED:    QColor('#E06C75'),  # BRIGHT RED
        TaskStateEnum.DELETED:   QColor('#BE5046'),  # DARKER RED
        TaskStateEnum.WAITING:   QColor('#8A8D94'),  # LIGHT GREY
        TaskStateEnum.INACTIVE:  QColor('#5C6370'),  # MEDIUM GREY
    }

    @classmethod
    def get_color(cls, state: TaskStateEnum) -> QColor:
        """Get the color for a task state."""
        return cls.COLORS[state]


def format_duration(seconds: float) -> str:
    """Format duration in a human-readable form."""
    if seconds < 0.1:
        return f"+{int(seconds * 1000)}ms"
    elif seconds < 10:
        return f"+{seconds:.3f}s"
    elif seconds < 60:
        return f"+{int(seconds)}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        remaining_seconds = int(seconds % 60)
        return f"+{minutes}m {remaining_seconds}s"

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    return f"+{hours}h {minutes}m"


@dataclass
class StateHistory:
    active_state: str
    comment: str = ''
    timestamp: str = field(init=False)

    def __post_init__(self) -> None:
        self.timestamp = datetime.now().isoformat()


@dataclass
class TaskState:
    """TaskState.

    This class represents the state of a task. A task always starts in the inactive state.
    """
    current: TaskStateEnum = TaskStateEnum.INACTIVE
    history:  Tuple[StateHistory, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        self._on_state_changed: Optional[Callable[[str, str], None]] = None

    def __str__(self) -> str:
        return self.current.name.lower()

    @property
    def color(self) -> QColor:
        """Get the color associated with the current state."""
        return TaskStates.get_color(self.current)

    def inspect(self) -> Dict[str, Any]:
        return {
            'current': self.current.value,
            'history': self._process_history_entries()
        }

    def _process_history_entries(self) -> List[Dict[str, Any]]:
        """Process history entries to add duration and formatting."""

        result: List[Dict[str, Any]] = []
        prev_time: Optional[datetime] = None

        for entry in self.history:
            timestamp = entry.timestamp
            current_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))

            # Calculate duration since previous state
            duration = ''
            if prev_time is not None:
                diff = current_time - prev_time
                duration = format_duration(diff.total_seconds())

            result.append({
                'state': entry.active_state,
                'comment': entry.comment,
                'duration': duration,
                'timestamp': timestamp
            })

            prev_time = current_time

        return result

    def _set_state(self, state: TaskStateEnum, comment: str = '') -> None:
        previous_state = self.current
        self.current = state
        history = StateHistory(self.current.value, comment)
        self.history = self.history + (history,)

        if self._on_state_changed:
            self._on_state_changed(previous_state, state)

    def register_state_change_callback(
        self,
        on_state_changed: Callable[[str, str], Any]
    ) -> None:
        self._on_state_changed = on_state_changed

    def set_running(self, comment: str = '') -> None:
        self._set_state(TaskStateEnum.RUNNING, comment)

    def set_completed(self, comment: str = '') -> None:
        self._set_state(TaskStateEnum.COMPLETED, comment)

    def set_failed(self, comment: str = '') -> None:
        self._set_state(TaskStateEnum.FAILED, comment)

    def set_blocked(self, comment: str = '') -> None:
        self._set_state(TaskStateEnum.BLOCKED, comment)

    def set_retrying(self, comment: str = '') -> None:
        self._set_state(TaskStateEnum.RETRYING, comment)

    def set_deleted(self, comment: str = '') -> None:
        self._set_state(TaskStateEnum.DELETED, comment)

    def set_waiting(self, comment: str = '') -> None:
        self._set_state(TaskStateEnum.WAITING, comment)

    def set_inactive(self, comment: str = '') -> None:
        self._set_state(TaskStateEnum.INACTIVE, comment)

    def get_first(self) -> StateHistory:
        return self.history[0]

    def get_last(self) -> StateHistory:
        return self.history[-1]

    @property
    def is_running(self) -> bool:
        return self.current == TaskStateEnum.RUNNING

    @property
    def is_completed(self) -> bool:
        return self.current == TaskStateEnum.COMPLETED

    @property
    def is_failed(self) -> bool:
        return self.current == TaskStateEnum.FAILED

    @property
    def is_blocked(self) -> bool:
        return self.current == TaskStateEnum.BLOCKED

    @property
    def is_retrying(self) -> bool:
        return self.current == TaskStateEnum.RETRYING

    @property
    def is_deleted(self) -> bool:
        return self.current == TaskStateEnum.DELETED

    @property
    def is_waiting(self) -> bool:
        return self.current == TaskStateEnum.WAITING

    @property
    def is_inactive(self) -> bool:
        return self.current == TaskStateEnum.INACTIVE

    @property
    def is_active(self) -> bool:
        return any([
            self.is_running, self.is_retrying, self.is_blocked,
        ])

    @property
    def is_removable(self) -> bool:
        return any([
            self.is_waiting, self.is_deleted, self.is_inactive,
            self.is_completed, self.is_failed
        ])
