"""Bugs that poison the process run as scripts, so they cannot take the session down."""
from __future__ import annotations

from pathlib import Path

import pytest

from ..utils.harness import assert_script_passes

SCRIPTS = Path(__file__).parent


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
    'v35_dropped_managers',
    'shutdown_under_core_app',
])
def test_fixed_script_passes(script: str):
    assert_script_passes(SCRIPTS / f'{script}.py')


def test_add_from_worker_raises():
    # Racy crash: 5 clean attempts are what proves the fix.
    for _ in range(5):
        assert_script_passes(SCRIPTS / 'v32_add_from_worker.py')
