
from __future__ import annotations

from pprint import pformat
from typing import List, Optional

from tqm._core.task import TaskUnit


def assert_task_completed(
    task: TaskUnit,
    expected_states: Optional[list[str]] = None,
):
    """
    Asserts that a given task was completed and verifies its state, timings, and history.

    Args:
        task (TqmTaskUnit): The task object to be checked.
        expected_states (list[str] | None): A list of expected state names in the task's history.
          If None, defaults to ['inactive', 'waiting', 'running', 'completed'].

    Raises:
        AssertionError: If any of the following conditions are not met:
            - The task's state indicates completion.
            - The task's state history matches the expected states.
    """
    # Get task inspection data for clearer error messages
    task_info = task.state.inspect()
    task_name = task.name
    actual_history = [state.active_state for state in task.state.history]

    # Set default expected states if none provided
    if expected_states is None:
        expected_states = ['inactive', 'waiting', 'running', 'completed']

    # Check if task is completed
    if not task.state.is_completed:
        raise AssertionError(
            f"Task '{task_name}' failed to complete.\n"
            f"Current state: {task.state.current}\n"
            f"State history: {actual_history}\n"
            f"Detailed task info: {pformat(task_info)}"
        )

    # Check state history matches expected states
    if len(actual_history) != len(expected_states):
        raise AssertionError(
            f"Task '{task_name}' history length mismatch.\n"
            f"Expected: {len(expected_states)} states: {expected_states}\n"
            f"     Got: {len(actual_history)} states: {actual_history}"
        )

    # Check each state in history matches expected states
    for i, (actual, expected) in enumerate(zip(actual_history, expected_states)):
        if actual != expected:
            raise AssertionError(
                f"Task '{task_name}' history mismatch at position {i}.\n"
                f"Expected: {expected}\n"
                f"Actual: {actual}\n"
                f"Full expected history: {expected_states}\n"
                f"Full actual history: {actual_history}"
            )


def assert_task_failed(
    task: TaskUnit,
    expected_states: Optional[List[str]] = None
):
    """
    Asserts that a given task has failed and verifies its state, timings, and history.

    Args:
        task (TqmTaskUnit): The task object to be checked.
        expected_states (list[str]|None): A list of expected state names in the task's history.
          If None, defaults to ['inactive', 'waiting', 'running', 'failed'].

    Raises:
        AssertionError: If any of the following conditions are not met:
            - The task's state indicates failure.
            - The task's state history matches the expected states.
    """
    # Get task inspection data for clearer error messages
    task_info = task.state.inspect()
    task_name = task.name
    actual_history = [state.active_state for state in task.state.history]

    # Set default expected states if none provided
    if expected_states is None:
        expected_states = ['inactive', 'waiting', 'running', 'failed']

    # Check if task failed
    if not task.state.is_failed:
        raise AssertionError(
            f"Task '{task_name}' did not fail as expected.\n"
            f"Current state: {task.state.current}\n"
            f"State history: {actual_history}\n"
            f"Detailed task info: {pformat(task_info)}"
        )

    # Check state history matches expected states
    if len(actual_history) != len(expected_states):
        raise AssertionError(
            f"Task '{task_name}' history length mismatch.\n"
            f"Expected {len(expected_states)} states: {expected_states}\n"
            f"Got {len(actual_history)} states: {actual_history}"
        )

    # Check each state in history matches expected states
    for i, (actual, expected) in enumerate(zip(actual_history, expected_states)):
        if actual != expected:
            raise AssertionError(
                f"Task '{task_name}' history mismatch at position {i}.\n"
                f"Expected: {expected}\n"
                f"Actual: {actual}\n"
                f"Full expected history: {expected_states}\n"
                f"Full actual history: {actual_history}"
            )
