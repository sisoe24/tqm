from __future__ import annotations

import os
import sys
import subprocess
from typing import Any, Dict, Callable
from pathlib import Path

import pytest

from tqm import TQManager, TaskBuilder
from tqm._core.logger import LOGGER
from tqm._core.settings import Settings, open_settings, get_config_path
from tqm._core.task_executor import TaskExecutor

from .utils.harness import StepPool, assert_script_passes

CASES = Path(__file__).parent / 'utils' / 'harness_cases.py'


def run_case(name: str, tmp_path: Path, **env: str) -> subprocess.CompletedProcess[str]:
    log = tmp_path / 'watchdog.log'
    return subprocess.run(
        [sys.executable, '-m', 'pytest', f'{CASES}::{name}', '--no-cov', '-p', 'no:cacheprovider'],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env={**os.environ, 'TQM_TEST_WATCHDOG_LOG': str(log), **env}
    )


def test_watchdog_names_the_hung_test(tmp_path: Path) -> None:
    process = run_case('test_hang', tmp_path, TQM_TEST_WATCHDOG='2')

    assert process.returncode == 1
    log = (tmp_path / 'watchdog.log').read_text()
    assert 'test_hang' in log
    assert 'harness_cases.py' in log.split('Timeout', 1)[1]


def test_failure_mid_group_is_reported(tmp_path: Path) -> None:
    process = run_case('test_fails_mid_group', tmp_path)

    assert process.returncode == 1
    assert '1 failed' in process.stdout
    assert 'failure while the group is running' in process.stdout


@pytest.mark.parametrize('order', ['first', 'second'])
def test_global_state_does_not_leak(order: str, tmp_path: Path, app: TQManager) -> None:
    assert Path(os.environ['XDG_CONFIG_HOME']) == tmp_path
    assert Path(os.environ['TQM_SETTINGS_PATH']).is_relative_to(tmp_path)

    with open_settings() as settings:
        assert settings.max_workers == 20
        settings.max_workers = 3

    assert len(LOGGER.handlers) == 2


def test_env_vars_written_by_the_code_are_gone() -> None:
    assert 'TQM_CONFIG_PATH' not in os.environ
    get_config_path('leak_check')
    assert 'TQM_CONFIG_PATH' in os.environ


def test_logger_starts_without_handlers_from_other_tests() -> None:
    assert LOGGER.handlers == []
    assert Settings._instance is None


def test_step_pool_runs_tasks_only_when_asked(
    executor: TaskExecutor,
    step_pool: StepPool
) -> None:
    calls: Dict[str, int] = {'first': 0, 'second': 0}
    first = TaskBuilder('first').with_event(lambda _: calls.update(first=1)).build()
    second = TaskBuilder('second').with_event(lambda _: calls.update(second=1)).build()
    executor.add_task(first)
    executor.add_task(second)
    executor.start_workers()

    assert calls == {'first': 0, 'second': 0}
    assert step_pool.activeThreadCount() == 2

    step_pool.step()
    assert calls == {'first': 1, 'second': 0}
    assert first.state.is_completed

    step_pool.step()
    assert calls == {'first': 1, 'second': 1}
    assert second.state.is_completed
    assert step_pool.activeThreadCount() == 0


def test_gate_is_released_at_teardown(gate: Callable[[], Any]) -> None:
    assert not gate().is_set()


@pytest.mark.parametrize('source, expected', [
    ('import os; os.abort()', 'exited with'),
    ('import time; time.sleep(60)', 'hung for'),
])
def test_script_crash_and_hang_are_assertion_errors(
    source: str,
    expected: str,
    tmp_path: Path
) -> None:
    script = tmp_path / 'bug.py'
    script.write_text(source)

    with pytest.raises(AssertionError, match=expected):
        assert_script_passes(script, timeout=1)


def test_script_success_passes(tmp_path: Path) -> None:
    script = tmp_path / 'ok.py'
    script.write_text('pass')

    assert_script_passes(script, timeout=10)
