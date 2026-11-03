from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from tqm import TQManager, TaskBuilder, TaskGroupBuilder
from tqm.exceptions import TaskGroupError

from ...utils import must_raise


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V62')
def test_empty_group_raises_at_the_caller(qtbot: QtBot, app: TQManager):
    with qtbot.capture_exceptions() as errors:
        with must_raise(TaskGroupError):
            with app.create_group('Empty'):
                pass

    assert not errors


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='audit section 6')
def test_group_built_later_does_not_sort_ahead_of_earlier_tasks():
    tasks = [TaskBuilder().build() for _ in range(3)]
    group = TaskGroupBuilder('G').with_tasks(TaskBuilder().build()).build()

    assert all(task.index < group.index for task in tasks)
