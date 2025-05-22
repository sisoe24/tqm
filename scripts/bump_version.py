from __future__ import annotations

import sys
import pathlib
import argparse
import subprocess

ROOT = pathlib.Path(__file__).parent.parent


def bump_version(version: str) -> None:
    if not version:
        raise ValueError('A valid version string must be provided')

    # check if branch is clean
    if subprocess.run(['git', 'diff', '--quiet'], cwd=ROOT).returncode != 0:
        raise ValueError(
            'Working directory is not clean. Please commit your changes before bumping the version')

    # check if branch is up-to-date
    if subprocess.run(['git', 'pull', '--ff-only'], cwd=ROOT).returncode != 0:
        raise ValueError(
            'Branch is not up-to-date. Please pull the latest changes before bumping the version')

    # check if branch is main
    branch = subprocess.run(['git', 'branch', '--show-current'], cwd=ROOT,
                            capture_output=True).stdout.decode().strip()
    if branch != 'main':
        raise ValueError('You must be on the main branch to bump the version')

    # Bump the version
    version = subprocess.run(
        ['poetry', 'version', '-s', version], cwd=ROOT, capture_output=True
    ).stdout.decode().strip()

    print(f'Bumped version to {version}')
    with open(ROOT / 'tqm' / 'version.py', 'w') as f:
        f.write(f"__version__ = '{version}'")

    # Build the package
    subprocess.run(['poetry', 'build'], cwd=ROOT)

    if input('Do you want to create a release on GitHub? [y/N]: ').lower() == 'y':
        subprocess.run([
            'gh', 'release', 'create', f'v{version}', f'dist/*{version}*.gz',
            '--title', f'v{version}'
        ], cwd=ROOT)

    # Commit the changes
    subprocess.run(['git', 'add', '.'], cwd=ROOT)
    subprocess.run(['git', 'commit', '-m', f'Bump version to {version}'], cwd=ROOT)

    if input('Do you want to push the changes to the remote repository? [y/N]: ').lower() == 'y':
        subprocess.run(['git', 'push'], cwd=ROOT)

    print('Done!')


def main():

    parser = argparse.ArgumentParser(description='tqm - Build Manager')
    parser.add_argument(
        '--bump',
        type=str,
        metavar='VERSION',
        help='''
        Bump the version of the package. A valid version string must be provided.
        Valid versions are the same as the ones accepted by poetry version command.
        Bumping the version will also build the package and create a new release.
        '''
    )

    args = parser.parse_args()

    if args.bump:
        bump_version(args.bump)
        sys.exit(0)

    parser.print_help()
    sys.exit(1)


if __name__ == '__main__':
    main()
