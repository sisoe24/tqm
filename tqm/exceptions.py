from __future__ import annotations

from typing import Type


class TqmError(Exception):
    """Base class for exceptions in the from tqm package."""


def create_exception(name: str, base: Type[TqmError] = TqmError) -> type[TqmError]:
    """Factory function to create new exception classes."""
    return type(name, (base,), {
        '__init__': lambda self, message: super(base, self).__init__(message)
    })


TaskError = create_exception('TaskError')
TaskGroupError = create_exception('TaskGroupError')
TaskManagerError = create_exception('TaskManagerError')
TaskManagerWorkerError = create_exception('TaskManagerWorkerError')
TaskManagerWorkerGroupError = create_exception('TaskManagerWorkerGroupError')
TaskManagerWorkerTaskError = create_exception('TaskManagerWorkerTaskError')
TaskPredicateError = create_exception('TaskPredicateError')
TaskParentError = create_exception('TaskParentError')
TaskEventError = create_exception('TaskEventError')
TaskAlreadyInQueue = create_exception('TaskAlreadyInQueue')
