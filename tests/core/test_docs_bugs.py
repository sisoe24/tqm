"""Claims that the README, the docstrings and the package metadata make."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

import tqm
from tqm import TaskBuilder
from tqm._core import task_builder

ROOT = Path(__file__).parent.parent.parent
PYPROJECT = (ROOT / 'pyproject.toml').read_text()


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V20')
@pytest.mark.parametrize('method', [TaskBuilder.with_on_failed, TaskBuilder.with_on_finish])
def test_docstrings_say_callbacks_fire_on_the_final_outcome(method: object):
    assert 'each' not in method.__doc__


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V29')
def test_readme_uses_existing_builder_methods():
    readme = (ROOT / 'README.md').read_text()

    for name in re.findall(r'\.(with_\w+)\(', readme):
        assert hasattr(TaskBuilder, name), name


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V54')
@pytest.mark.parametrize('stale', [
    'from tqm.retry_policy import',
    'LinearOffset',
    'lambda _: os.path.exists',
    'retry_interval_ms',
    '`with_file`',
    'task.update_progress',
])
def test_docstrings_show_working_examples(stale: str):
    assert stale not in Path(task_builder.__file__).read_text()


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V63')
def test_python_floor_is_3_9():
    assert re.search(r'^python = ">=3\.9', PYPROJECT, re.M)


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V64')
def test_package_version_matches_the_metadata():
    assert f'version = "{tqm.__version__}"' in PYPROJECT


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V64')
def test_pytest_is_not_a_runtime_dependency():
    runtime = PYPROJECT.split('[tool.poetry.dependencies]')[1].split('[')[0]

    assert 'pytest' not in runtime


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V64')
def test_no_script_points_at_the_ignored_sandbox():
    assert 'sandbox.' not in PYPROJECT
