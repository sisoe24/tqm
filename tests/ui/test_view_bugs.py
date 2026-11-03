from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Callable, Optional
from pathlib import Path
from functools import partial
from threading import Event
from unittest import mock

import pytest
from PySide2.QtGui import QContextMenuEvent
from PySide2.QtCore import Qt, QEvent
from PySide2.QtTest import QTest
from pytestqt.qtbot import QtBot
from PySide2.QtWidgets import (QMenu, QAction, QLineEdit, QApplication,
                               QTableWidget, QPlainTextEdit,
                               QStyleOptionProgressBar)

from tqm import TQManager, TaskBuilder, TaskGroupBuilder
from tqm._core.logger import LOGGER
from tqm._core.settings import Settings
from tqm._ui.toolbar import TableOptions, TasksViewToolbar
from tqm._ui.debug_widget import TasksList, DebugWidget, StateHistoryWidget
from tqm._ui.ui_view_model import TaskTreeView
from tqm._ui.progress_bar_delegate import ProgressBarRenderer

from ..utils import run_events, must_not_raise
from .test_ui_controller import find_row, cell_data


def noop_task(name: str = '') -> TaskBuilder:
    return TaskBuilder(name).with_event(lambda t: None)


@pytest.fixture
def view(app: TQManager) -> TaskTreeView:
    app.resize(1200, 700)
    app.show()
    QApplication.processEvents()
    return app.findChild(TaskTreeView)


@pytest.fixture
def search_bar(app: TQManager) -> QLineEdit:
    return app.findChild(QLineEdit, 'TqmSearchBar')


def add_rows(app: TQManager, *names: str) -> None:
    app.add_tasks(*[noop_task(name).build() for name in names])
    QApplication.processEvents()


def top_rows(view: TaskTreeView) -> List[str]:
    model = view.model()
    return [model.index(i, 0).data() for i in range(model.rowCount())]


def selected(view: TaskTreeView) -> List[str]:
    return sorted(item.text() for item in view.get_selected_items())


def click(view: TaskTreeView, name: str, button: Qt.MouseButton = Qt.LeftButton, modifier: Any = Qt.NoModifier) -> None:
    position = view.visualRect(find_row(view, name)).center()
    QTest.mouseClick(view.viewport(), button, modifier, position)


def open_context_menu(view: TaskTreeView, name: str, action: Optional[str] = None) -> Optional[List[str]]:
    """Open the row's real menu without blocking. Return its labels, or None if it stayed closed."""
    labels: Optional[List[str]] = None

    class Menu(QMenu):
        def exec_(self, *args: Any) -> None:
            nonlocal labels
            labels = [a.text() for a in self.actions() if a.text()]
            for item in self.actions():
                if item.text() == action:
                    item.trigger()

    position = view.visualRect(find_row(view, name)).center()
    event = QContextMenuEvent(QContextMenuEvent.Mouse, position, view.viewport().mapToGlobal(position))
    with mock.patch('tqm._ui.ui_view_model.QMenu', Menu):
        view.contextMenuEvent(event)
    return labels


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V15')
def test_context_retry_acts_on_the_clicked_row(
    qtbot: QtBot,
    app: TQManager,
    view: TaskTreeView,
    gate: Callable[[], Event]
):
    release = gate()
    runs: Dict[str, int] = {'Aaa': 0, 'Bbb': 0}

    def blocked(task: Any) -> None:
        runs['Aaa'] += 1
        release.wait()

    def failing(task: Any) -> None:
        runs['Bbb'] += 1
        raise RuntimeError('boom')

    running = TaskBuilder('Aaa').with_event(blocked).build()
    failed = TaskBuilder('Bbb').with_event(failing).build()
    app.add_tasks(running, failed)
    app.start_workers()
    qtbot.wait_until(lambda: failed.state.is_failed and running.state.is_running)

    click(view, 'Aaa')
    click(view, 'Bbb', Qt.RightButton)
    open_context_menu(view, 'Bbb', 'Retry')
    run_events(qtbot, 100)
    release.set()
    qtbot.wait_until(lambda: running.state.is_completed)

    assert runs == {'Aaa': 1, 'Bbb': 2}


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V16')
def test_context_remove_with_no_selection_removes_the_clicked_row(app: TQManager, view: TaskTreeView):
    add_rows(app, 'Aaa', 'Bbb')

    open_context_menu(view, 'Bbb', 'Remove selected')

    assert top_rows(view) == ['Aaa']


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V16')
def test_context_remove_ignores_another_selected_row(app: TQManager, view: TaskTreeView):
    add_rows(app, 'Aaa', 'Bbb')

    click(view, 'Aaa')
    click(view, 'Bbb', Qt.RightButton)
    open_context_menu(view, 'Bbb', 'Remove selected')

    assert top_rows(view) == ['Aaa']


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V25')
def test_progress_survives_a_retry(qtbot: QtBot, app: TQManager, gate: Callable[[], Event]):
    release = gate()

    def event(task: Any) -> None:
        if not task.data.get('retried'):
            task.data['retried'] = True
            raise RuntimeError('boom')
        task.emit_progress(90)
        release.wait()

    task = TaskBuilder('T').with_event(event, show_progress=True).with_retry(1, 0).build()
    app.add_tasks(task)
    app.start_workers()
    qtbot.wait_until(lambda: task.data.get('retried') and task.state.is_running)
    run_events(qtbot, 100)

    assert cell_data(app.findChild(TaskTreeView), 'T', 'Progress') == 90


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V25')
def test_group_member_progress_reaches_its_cell(qtbot: QtBot, app: TQManager, gate: Callable[[], Event]):
    release = gate()

    def event(task: Any) -> None:
        task.emit_progress(42)
        release.wait()

    member = TaskBuilder('M').with_event(event, show_progress=True).build()
    app.add_tasks(TaskGroupBuilder('G').with_tasks(member).build())
    app.start_workers()
    qtbot.wait_until(lambda: member.state.is_running)
    run_events(qtbot, 100)

    assert cell_data(app.findChild(TaskTreeView), 'M', 'Progress') == 42


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V35')
def test_removed_task_is_released(qtbot: QtBot, app: TQManager):
    import gc
    import weakref

    task = noop_task('T').build()
    alive = weakref.ref(task)
    app.add_tasks(task)
    app.start_workers()
    qtbot.wait_until(lambda: task.state.is_completed)
    app.remove_tasks(task)
    del task
    QApplication.processEvents()
    gc.collect()

    assert alive() is None


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V61')
def test_float_progress_is_not_truncated(qtbot: QtBot, app: TQManager, gate: Callable[[], Event]):
    release = gate()

    def event(task: Any) -> None:
        task.emit_progress(12.7)
        release.wait()

    task = TaskBuilder('T').with_event(event, show_progress=True).build()
    app.add_tasks(task)
    app.start_workers()
    qtbot.wait_until(lambda: task.state.is_running)
    run_events(qtbot, 100)

    assert cell_data(app.findChild(TaskTreeView), 'T', 'Progress') == 12.7


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V61')
def test_progress_text_scales_with_min_max():
    task = TaskBuilder().with_event(lambda t: None, show_progress=True).with_min_max(0, 10).build()
    options = QStyleOptionProgressBar()

    ProgressBarRenderer.handle_determinate_progress(options, 5, task)

    assert options.text == '50%'


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V65')
def test_log_menu_restores_saved_settings(make_manager: Callable[[str], TQManager]):
    folder = Path(os.environ['XDG_CONFIG_HOME']) / 'tqm' / 'a'
    folder.mkdir(parents=True)
    (folder / 'settings.json').write_text(json.dumps({'wrap_lines': True, 'enable_debug': True}))
    manager = make_manager('a')

    actions = {a.text(): a for a in manager.findChildren(QAction)}
    log = manager.findChild(QPlainTextEdit, 'TqmTasksLogs')

    assert log.lineWrapMode() == QPlainTextEdit.WidgetWidth
    assert actions['Wrap Lines'].isChecked()
    assert actions['Enable Debug'].isChecked()


def log_text(qtbot: QtBot, app: TQManager, message: str) -> str:
    log = app.findChild(QPlainTextEdit, 'TqmTasksLogs')
    log.clear()
    LOGGER.info(message)
    qtbot.wait_until(lambda: bool(log.toPlainText()))
    return log.toPlainText().replace('\xa0', ' ')


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V67')
@pytest.mark.parametrize('message', [
    'a < b and b > c',
    '<b>bold</b>',
    'line1\nline2',
    '&amp;',
])
def test_log_view_shows_plain_text(qtbot: QtBot, app: TQManager, message: str):
    assert message in log_text(qtbot, app, message)


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V67')
def test_log_view_limits_its_blocks(app: TQManager):
    assert app.findChild(QPlainTextEdit, 'TqmTasksLogs').maximumBlockCount() > 0


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V69')
def test_add_keeps_a_collapsed_group_collapsed(app: TQManager, view: TaskTreeView):
    app.add_tasks(TaskGroupBuilder('G').with_tasks(noop_task('M').build()).build())
    view.collapseAll()

    app.add_tasks(noop_task('Other').build())

    assert not view.isExpanded(find_row(view, 'G'))


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V73')
def test_click_that_empties_the_selection_raises_nothing(qtbot: QtBot, app: TQManager, view: TaskTreeView):
    add_rows(app, 'Aaa', 'Bbb')
    click(view, 'Aaa')

    with qtbot.capture_exceptions() as errors:
        click(view, 'Aaa', Qt.LeftButton, Qt.ControlModifier)

    assert not errors


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V73')
def test_debug_panel_shows_the_clicked_task(app: TQManager, view: TaskTreeView):
    add_rows(app, 'Aaa', 'Bbb')
    view.setSelectionMode(view.MultiSelection)

    with mock.patch.object(DebugWidget, 'populate') as populate:
        click(view, 'Bbb')
        click(view, 'Aaa')

    assert populate.call_args[0][0].name == 'Aaa'


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V74')
def test_a_key_selects_all_when_a_name_starts_with_a(app: TQManager, view: TaskTreeView):
    add_rows(app, 'Aaa', 'Bbb', 'Ccc')
    view.setFocus()

    QTest.keyClick(view, Qt.Key_A)

    assert selected(view) == ['Aaa', 'Bbb', 'Ccc']


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V74')
def test_second_a_key_clears_the_selection_when_a_name_starts_with_a(app: TQManager, view: TaskTreeView):
    add_rows(app, 'Aaa', 'Bbb', 'Ccc')
    view.setFocus()

    QTest.keyClick(view, Qt.Key_A)
    QTest.keyClick(view, Qt.Key_A)

    assert selected(view) == []


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V75')
def test_click_after_select_all_selects_one_row(app: TQManager, view: TaskTreeView):
    add_rows(app, 'Xxx', 'Bbb', 'Ccc')
    view.setFocus()
    QTest.keyClick(view, Qt.Key_A)

    click(view, 'Bbb')

    assert selected(view) == ['Bbb']


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V75')
def test_shift_released_elsewhere_leaves_single_selection(app: TQManager, view: TaskTreeView, search_bar: QLineEdit):
    add_rows(app, 'Xxx', 'Bbb')
    view.setFocus()
    QTest.keyPress(view, Qt.Key_Shift, Qt.ShiftModifier)
    QTest.keyRelease(search_bar, Qt.Key_Shift)

    click(view, 'Xxx')
    click(view, 'Bbb')

    assert selected(view) == ['Bbb']


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V76')
def test_search_with_an_invalid_regex_still_matches_the_text(app: TQManager, view: TaskTreeView, search_bar: QLineEdit):
    add_rows(app, 'Aaa(1)', 'Bbb')

    search_bar.setText('Aaa(')

    assert top_rows(view) == ['Aaa(1)']


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V77')
@pytest.mark.parametrize('text', [':', 'T'])
def test_search_ignores_timestamps(app: TQManager, view: TaskTreeView, search_bar: QLineEdit, text: str):
    add_rows(app, 'Aaa', 'Bbb')

    search_bar.setText(text)

    assert top_rows(view) == []


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V78')
def test_closing_the_search_bar_clears_the_filter(app: TQManager, view: TaskTreeView, search_bar: QLineEdit):
    add_rows(app, 'Aaa', 'Bbb')
    button = app.findChild(TasksViewToolbar).search_btn
    button.setChecked(True)
    search_bar.setText('Aaa')

    button.setChecked(False)

    assert sorted(top_rows(view)) == ['Aaa', 'Bbb']


def add_group(app: TQManager) -> Any:
    member = noop_task('kid').build()
    app.add_tasks(TaskGroupBuilder('Gruppe').with_tasks(member).build())
    return member


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V79')
def test_filter_on_a_group_keeps_its_children(app: TQManager, view: TaskTreeView, search_bar: QLineEdit):
    add_group(app)

    search_bar.setText('Gruppe')

    model = view.model()
    assert model.rowCount(model.index(0, 0)) == 1


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V79')
def test_filter_follows_a_child_change(app: TQManager, view: TaskTreeView, search_bar: QLineEdit):
    member = add_group(app)
    search_bar.setText('zzz')
    assert top_rows(view) == []

    parent = member.item.parent()
    parent.child(member.item.row(), view.get_column_index('Comment')).setText('zzz note')

    assert top_rows(view) == ['Gruppe']


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V79')
def test_clearing_the_filter_keeps_groups_expanded(app: TQManager, view: TaskTreeView, search_bar: QLineEdit):
    add_group(app)

    search_bar.setText('zzz')
    search_bar.setText('')

    assert view.isExpanded(find_row(view, 'Gruppe'))


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V80')
def test_expand_all_menu_item_expands(app: TQManager, view: TaskTreeView):
    add_group(app)
    view.collapseAll()

    app.findChild(TableOptions).expand_all.trigger()

    assert view.isExpanded(find_row(view, 'Gruppe'))


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V81')
def test_sort_order_survives_a_restart(qtbot: QtBot, app: TQManager, view: TaskTreeView):
    # The view saves on a 2s timer that its own first layout starts.
    run_events(qtbot, 2100)
    view.sortByColumn(4, Qt.AscendingOrder)
    run_events(qtbot, 2100)

    Settings._instance = None
    restarted = TaskTreeView()
    section = restarted.header().sortIndicatorSection()
    restarted.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.DeferredDelete)

    assert section == 4


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V82')
def test_default_sort_is_natural_and_ascending(app: TQManager, view: TaskTreeView):
    add_rows(app, 'Task1', 'Task2', 'Task3', 'Task10')

    assert top_rows(view) == ['Task1', 'Task2', 'Task3', 'Task10']


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V83')
def test_group_progress_follows_a_removed_member(qtbot: QtBot, app: TQManager, view: TaskTreeView):
    members = [noop_task(f'c{i}').build() for i in range(3)]
    group = TaskGroupBuilder('G').with_tasks(*members).build()
    app.add_tasks(group)
    app.start_workers()
    qtbot.wait_until(lambda: group.state.is_completed)
    QApplication.processEvents()

    app.remove_tasks(members[0])

    assert group.progress_bar.maximum == 2
    assert cell_data(view, 'G', 'Progress') == 2


class CallableObject:
    def __call__(self, task: Any) -> None:
        pass


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V84')
@pytest.mark.parametrize('builder', [
    lambda: noop_task('IntKeys').with_data(x={1: 'a'}),
    lambda: noop_task('MixedKeys').with_data(x={1: 'a', 'b': 2}),
    lambda: TaskBuilder('Partial').with_event(partial(CallableObject())),
], ids=['int_keys', 'mixed_keys', 'partial_callable_object'])
def test_debug_panel_shows_any_task(app: TQManager, builder: Callable[[], TaskBuilder]):
    with must_not_raise(TypeError, AttributeError):
        app.findChild(DebugWidget).populate(builder().build())


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V84')
def test_debug_panel_replaces_the_previous_history(app: TQManager):
    panel = app.findChild(DebugWidget)
    panel.populate(noop_task('Ok').build())

    bad = noop_task('Bad').with_data(x={1: 'a'}).build()
    bad.state.set_waiting()
    try:
        panel.populate(bad)
    except TypeError:
        pass

    assert panel.findChild(StateHistoryWidget).topLevelItemCount() == 2


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V85')
def test_registry_tab_keeps_every_task_after_sorting(app: TQManager):
    names = {f'task{i}' for i in range(12)}
    app.add_tasks(*[noop_task(name).build() for name in names])
    registry = app.findChild(TasksList)
    table = registry.findChild(QTableWidget)

    registry._load_tasks()
    table.sortItems(0, Qt.AscendingOrder)
    registry._load_tasks()

    assert {table.item(row, 0).text() for row in range(table.rowCount())} == names


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V86')
def test_context_menus_do_not_pile_up(app: TQManager, view: TaskTreeView):
    add_rows(app, 'Aaa')

    open_context_menu(view, 'Aaa')
    before = len(view.findChildren(QMenu)), len(view.findChildren(QAction))
    for _ in range(5):
        open_context_menu(view, 'Aaa')

    assert (len(view.findChildren(QMenu)), len(view.findChildren(QAction))) == before


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V86')
def test_running_task_shows_no_empty_menu(qtbot: QtBot, app: TQManager, view: TaskTreeView, gate: Callable[[], Event]):
    release = gate()
    task = TaskBuilder('Run').with_event(lambda t: release.wait()).build()
    app.add_tasks(task)
    app.start_workers()
    qtbot.wait_until(lambda: task.state.is_running)

    assert open_context_menu(view, 'Run') != []


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V87')
def test_view_parent_is_callable(view: TaskTreeView):
    with must_not_raise(TypeError):
        view.parent()


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V53')
def test_set_max_workers_with_no_value_asks_the_user(app: TQManager):
    with mock.patch('tqm._ui.ui_controller.QInputDialog.getInt', return_value=(7, True)):
        app.operations.set_max_workers()

    assert app.executor.max_workers == 7
