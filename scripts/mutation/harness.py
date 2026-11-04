"""Mutation gate: run the test suite against one source change at a time.

    .venv/bin/python scripts/mutation/harness.py --workers 6
    .venv/bin/python scripts/mutation/harness.py --check
    .venv/bin/python scripts/mutation/harness.py --only 3,17

A mutant counts as killed only if the same named test fails in the full run and in 2 of 2
reruns. A hang, a crash, or a run stopped by the outer alarm kills nothing by itself.
Results go to tmp/mutation/.
"""
from __future__ import annotations

import os
import re
import sys
import json
import queue
import shutil
import argparse
import tempfile
import threading
import subprocess
from typing import Dict, List, Tuple, Optional, Sequence
from pathlib import Path
from collections import Counter

from mutations import MUTANTS, Mutant

REPO = Path(__file__).resolve().parents[2]
OUTPUT = REPO / 'tmp' / 'mutation'

MIN_KILLED = 150
RERUNS = 2
RERUN_LIMIT = 5
ALARM_SECONDS = 300

COPY_IGNORE = shutil.ignore_patterns('.*', 'tmp', 'sandbox', '__pycache__', 'coverage.xml')
PYTEST_ARGS = (
    '-p', 'no:cacheprovider', '-p', 'no:randomly', '-v', '--tb=no', '-rfE', '--color=no'
)

# The verbose line survives a watchdog exit. The summary, the only place naming XPASS, does not.
FAILED_LINE = re.compile(r'^(tests/\S+::.+?) (?:FAILED|ERROR)\b', re.M)
XPASS_LINE = re.compile(r'^FAILED (.+?) - \[XPASS', re.M)


def apply_mutant(source: str, mutant: Mutant) -> str:
    return source.replace(mutant.old, mutant.new, 1)


def validate(mutants: Sequence[Mutant]) -> List[str]:
    """Return one problem per mutant that no longer applies to the source."""
    problems = []
    for index, mutant in enumerate(mutants):
        source = (REPO / mutant.file).read_text()
        if mutant.old not in source:
            problems.append(f'{index} no match in {mutant.file}: {mutant.change}')
            continue
        try:
            compile(apply_mutant(source, mutant), mutant.file, 'exec')
        except SyntaxError as error:
            problems.append(f'{index} syntax error in {mutant.file}: {mutant.change}: {error}')
    return problems


def run_pytest(copy: Path, nodes: Sequence[str], log: Path) -> Tuple[object, List[str]]:
    """Run pytest in a repo copy. Return the exit code, or 'alarm', and the failed test names."""
    env = {
        **os.environ,
        'QT_QPA_PLATFORM': 'offscreen',
        'PYTHONDONTWRITEBYTECODE': '1',  # a stale .pyc could hide a same-size mutation
        'PYTHONPATH': str(copy),
        'XDG_CONFIG_HOME': str(copy / '.xdg'),
        'COLUMNS': '300',
    }
    command = [sys.executable, '-m', 'pytest', *PYTEST_ARGS, *nodes]
    with log.open('w') as output:
        try:
            returncode: object = subprocess.run(
                command,
                cwd=copy,
                env=env,
                stdout=output,
                stderr=subprocess.STDOUT,
                timeout=ALARM_SECONDS,
                check=False
            ).returncode
        except subprocess.TimeoutExpired:
            returncode = 'alarm'

    text = log.read_text(errors='replace')
    # A strict xfail that passes says nothing about the behaviour the mutant broke.
    xpassed = set(XPASS_LINE.findall(text))
    return returncode, sorted(set(FAILED_LINE.findall(text)) - xpassed)


def classify(returncode: object) -> str:
    """Name a run that no test failed in."""
    if returncode == 0:
        return 'survived'
    if returncode == 'alarm':
        return 'alarm'
    if isinstance(returncode, int) and returncode < 0:
        return 'crash'
    return 'hang'  # the watchdog exits with 1, and takes the summary with it


def run_mutant(copy: Path, index: int, mutant: Mutant) -> Dict[str, object]:
    path = copy / mutant.file
    source = path.read_text()
    path.write_text(apply_mutant(source, mutant))
    logs = OUTPUT / 'logs'
    try:
        returncode, failed = run_pytest(copy, (), logs / f'{index}.log')
        if isinstance(returncode, int) and returncode < 0 and not failed:
            # V1 can segfault an unrelated test before the suite reaches the one that matters.
            returncode, failed = run_pytest(copy, (), logs / f'{index}.again.log')
        stable = failed[:RERUN_LIMIT]  # one stable test is enough, and reruns are not free
        for attempt in range(RERUNS):
            if stable:
                log = logs / f'{index}.rerun{attempt}.log'
                _, again = run_pytest(copy, stable, log)
                stable = [node for node in stable if node in again]
    finally:
        path.write_text(source)

    status = 'killed' if stable else 'unstable' if failed else classify(returncode)
    return {
        'index': index,
        'file': mutant.file,
        'change': mutant.change,
        'status': status,
        'returncode': returncode,
        'killed_by': stable,
        'first_pass': failed,
    }


def make_copy(root: Path, worker: int) -> Path:
    copy = root / f'worker{worker}'
    shutil.copytree(REPO, copy, ignore=COPY_IGNORE)
    return copy


def check_baseline(copy: Path, problems: List[str]) -> None:
    """The unmutated suite must pass and import tqm from the copy, or no result means anything."""
    imported = subprocess.run(
        [sys.executable, '-c', 'import tqm; print(tqm.__file__)'],
        cwd=copy,
        env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen', 'PYTHONPATH': str(copy)},
        capture_output=True,
        text=True,
        check=False
    ).stdout.strip()
    if not Path(imported).resolve().is_relative_to(copy.resolve()):
        problems.append(f'{copy.name} imports tqm from {imported}')

    returncode, failed = run_pytest(copy, (), OUTPUT / 'logs' / f'baseline-{copy.name}.log')
    if returncode != 0:
        problems.append(f'{copy.name} baseline returned {returncode}, failed: {failed}')


def in_parallel(target, args_per_thread: Sequence[tuple]) -> None:
    threads = [threading.Thread(target=target, args=args) for args in args_per_thread]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()


def run_all(selected: Dict[int, Mutant], workers: int) -> List[Dict[str, object]]:
    jobs: queue.Queue = queue.Queue()
    for job in selected.items():
        jobs.put(job)

    results: List[Dict[str, object]] = []
    lock = threading.Lock()

    def work(copy: Path) -> None:
        while True:
            try:
                index, mutant = jobs.get_nowait()
            except queue.Empty:
                return
            result = run_mutant(copy, index, mutant)
            with lock:
                results.append(result)
                print(index, result['status'], mutant.change, result['killed_by'][:1], flush=True)

    with tempfile.TemporaryDirectory(prefix='tqm-mutation-') as root:
        copies = [make_copy(Path(root), worker) for worker in range(workers)]

        problems: List[str] = []
        in_parallel(check_baseline, [(copy, problems) for copy in copies])
        if problems:
            sys.exit('Baseline is not clean:\n' + '\n'.join(problems))

        in_parallel(work, [(copy,) for copy in copies])

    return sorted(results, key=lambda result: result['index'])


def report(results: List[Dict[str, object]], skipped: int) -> None:
    counts = Counter(result['status'] for result in results)
    print(f'\nkilled {counts["killed"]}/{len(results)}, equivalents: {skipped}, {dict(counts)}')
    for result in results:
        if result['status'] != 'killed':
            where = f'{result["index"]:>3} {result["file"]}'
            print(f'  {result["status"]:9} {where}: {result["change"]}')


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--workers', type=int, default=6)
    parser.add_argument('--check', action='store_true', help='only validate the mutants')
    parser.add_argument('--only', help='comma separated mutant positions')
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()

    problems = validate(MUTANTS)
    if problems:
        print('\n'.join(problems))
        return 1

    selected = {i: mutant for i, mutant in enumerate(MUTANTS) if not mutant.equivalent}
    skipped = len(MUTANTS) - len(selected)
    print(f'{len(selected)} mutants valid, {skipped} equivalent', flush=True)
    if args.check:
        return 0

    if args.only:
        selected = {int(i): MUTANTS[int(i)] for i in args.only.split(',')}

    (OUTPUT / 'logs').mkdir(parents=True, exist_ok=True)
    results = run_all(selected, args.workers)

    name = 'results-only.jsonl' if args.only else 'results.jsonl'
    with (OUTPUT / name).open('w') as output:
        output.writelines(json.dumps(result) + '\n' for result in results)
    report(results, skipped)

    if args.only:
        return 0
    killed = sum(result['status'] == 'killed' for result in results)
    alarms = sum(result['status'] == 'alarm' for result in results)
    return 0 if killed >= MIN_KILLED and not alarms else 1


if __name__ == '__main__':
    sys.exit(main())
