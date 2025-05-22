from __future__ import annotations

from enum import Enum, auto
from typing import Any, Dict
from dataclasses import asdict, dataclass


class ProgressMode(Enum):
    DETERMINATE = auto()
    INDETERMINATE = auto()


@dataclass
class ProgressBarOptions:

    working_text: str = 'Working...'

    minimum: int = 0
    maximum: int = 100

    mode: ProgressMode = ProgressMode.DETERMINATE

    def inspect(self) -> Dict[str, Any]:
        return asdict(self)
