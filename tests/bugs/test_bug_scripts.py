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
    bug('V1', 'v1_gc_on_worker'),
    bug('V2', 'v2_group_starvation'),
    bug('V3', 'v3_shutdown_with_queued_members', timeout=10),
    bug('V4', 'v4_exit_mid_group', timeout=10),
    bug('V14', 'v14_retry_waiting'),
    bug('V33', 'v33_set_mutated_during_poll'),
    bug('V35', 'v35_dropped_managers'),
    bug('V38', 'v38_retry_all_race'),
    bug('V49', 'v49_member_waits_for_group'),
    bug('V49', 'v49_group_waits_for_member'),
    bug('V49', 'v49_parent_never_added'),
    bug('V50', 'v50_two_groups'),
    bug('V50', 'v50_late_add'),
    bug('V50', 'v50_nested_group_removed'),
    bug('audit section 6', 'shutdown_under_core_app'),
    bug('found in T3', 'retry_right_after_failure'),
])
def test_script_passes(script: str, timeout: float):
    assert_script_passes(SCRIPTS / f'{script}.py', timeout=timeout)


@pytest.mark.xfail(strict=True, raises=AssertionError, reason='V32')
def test_add_from_worker_raises():
    # Racy crash: 5 clean attempts are what proves the fix.
    for _ in range(5):
        assert_script_passes(SCRIPTS / 'v32_add_from_worker.py')
