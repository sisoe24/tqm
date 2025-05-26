
from __future__ import annotations

import pytest
from PySide2.QtGui import QColor
from PySide2.QtCore import Qt

from tqm import TaskGroup, TaskBuilder, TaskExecutable, TaskGroupBuilder
from tqm.typings import TASK_COLOR
from tqm._core.task_actions import TaskAction, TaskActionVisibility
from tqm._core.retry_policy.retry_policy import NoRetryPolicy


def test_task_builder():
    parent = TaskExecutable(execute=lambda: None, name='parent')
    t = (
        TaskBuilder('abc')
        .with_event(lambda t: t)
        .with_label('def')
        .with_comment('ghi')
        .with_wait_for(parent)
        .with_action('action', lambda t: t, visibility=TaskActionVisibility.ON_FAILED)
        .with_on_start(lambda t: t)
        .with_on_failed(lambda t: t)
        .with_on_completed(lambda t: t)
        .with_on_finish(lambda t: t)
        .with_color('blue')
        .with_min_max(1, 2)
        .with_predicate(lambda: True, max_attempts=10, delay_ms=1000)
        .with_data(data={'a': 1})
        .build()
    )

    assert t.name == 'def'
    assert t.comment == 'ghi'
    assert t.color == 'blue'
    assert t.data == {'data': {'a': 1}}

    assert isinstance(t.retry_policy, NoRetryPolicy)

    assert isinstance(t.parent, TaskExecutable)
    assert t.parent.name == 'parent'

    # options
    assert t.progress_bar.working_text == 'Working...'
    assert t.progress_bar.minimum == 1
    assert t.progress_bar.maximum == 2

    # events
    assert callable(t.execute)
    assert t.callbacks.on_start
    assert t.callbacks.on_start.cleanup == True
    assert callable(t.callbacks.on_start.callback)

    assert t.callbacks.on_failed
    assert t.callbacks.on_failed.cleanup == False
    assert callable(t.callbacks.on_failed.callback)

    assert t.callbacks.on_completed
    assert t.callbacks.on_completed.cleanup == True
    assert callable(t.callbacks.on_completed.callback)

    assert t.callbacks.on_finish
    assert t.callbacks.on_finish.cleanup == False
    assert callable(t.callbacks.on_finish.callback)

    # predicate
    assert t.predicate
    assert t.predicate.condition
    assert t.predicate.max_retries == 10
    assert t.predicate.retry_interval == 1000

    # actions
    assert len(t.actions) == 1

    assert isinstance(t.actions[0], TaskAction)
    assert t.actions[0].name == 'action'
    assert t.actions[0].visibility == TaskActionVisibility.ON_FAILED
    assert callable(t.actions[0].action)


@pytest.mark.parametrize('color_type', [
    'blue',
    '#0000ff',
    'rgb(0, 0, 255)',
    None,
    (255, 0, 0, 1),
    Qt.red,
    QColor(255, 0, 0, 1),
])
def test_task_builder_color(color_type: TASK_COLOR):
    t = TaskBuilder('abc').with_color(color_type).build()
    assert isinstance(t.color, QColor)
    assert t.color.isValid()


def test_task_group_builder():
    parent = TaskGroup('parent')
    t = (
        TaskGroupBuilder('abc')
        .with_wait_for(parent)
        .with_comment('def')
        .with_color('blue')
        .with_action('action', lambda g: g, visibility=TaskActionVisibility.ON_FAILED)
        .with_on_start(lambda g: g, cleanup=False)
        .with_on_failed(lambda g: g, cleanup=False)
        .with_on_completed(lambda g: g, cleanup=False)
        .with_on_finish(lambda g: g, cleanup=False)
        .build()
    )

    assert t.name == 'abc'

    assert t.comment == 'def'
    assert t.color == 'blue'

    assert len(t.actions) == 1
    assert isinstance(t.actions[0], TaskAction)
    assert t.actions[0].name == 'action'
    assert t.actions[0].visibility == TaskActionVisibility.ON_FAILED
    assert callable(t.actions[0].action)

    assert isinstance(t.parent, TaskGroup)
    assert t.parent.name == 'parent'

    assert t.callbacks.on_start
    assert t.callbacks.on_start.cleanup == False
    assert callable(t.callbacks.on_start.callback)

    assert t.callbacks.on_failed
    assert t.callbacks.on_failed.cleanup == False
    assert callable(t.callbacks.on_failed.callback)

    assert t.callbacks.on_completed
    assert t.callbacks.on_completed.cleanup == False
    assert callable(t.callbacks.on_completed.callback)

    assert t.callbacks.on_finish
    assert t.callbacks.on_finish.cleanup == False
    assert callable(t.callbacks.on_finish.callback)
