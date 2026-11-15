"""Bugs that poison the process run as scripts, so they cannot take the session down."""
from __future__ import annotations

from pathlib import Path

import pytest

from ..utils.harness import assert_script_passes

SCRIPTS = Path(__file__).parent


def bug(reason: str, script: str, timeout: float = 30) -> pytest.param:
    mark = pytest.mark.xfail(strict=True, raises=AssertionError, reason=reason)
    return pytest.param(script, timeout, id=script, marks=mark)


@pytest.mark.parametrize('script, timeout', [
    bug('V35', 'v35_dropped_managers'),
    bug('audit section 6', 'shutdown_under_core_app'),
])
def test_script_passes(script: str, timeout: float):
    assert_script_passes(SCRIPTS / f'{script}.py', timeout=timeout)


# v1_gc_on_worker covers only the retry part of V1. The rest of V1 stays open until R5.
@pytest.mark.parametrize('script', [
    'v1_gc_on_worker',
    'v14_retry_waiting',
    'retry_right_after_failure',
    'v49_member_waits_for_group',
    'v49_group_waits_for_member',
    'v49_parent_never_added',
    'v2_group_starvation',
    'v3_shutdown_with_queued_members',
    'v4_exit_mid_group',
    'v38_retry_all_race',
    'v50_two_groups',
    'v50_late_add',
    'v50_nested_group_removed',
])
def test_fixed_script_passes(script: str):
    assert_script_passes(SCRIPTS / f'{script}.py')


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V32')
def test_add_from_worker_raises():
    # Racy crash: 5 clean attempts are what proves the fix.
    for _ in range(5):
        assert_script_passes(SCRIPTS / 'v32_add_from_worker.py')
