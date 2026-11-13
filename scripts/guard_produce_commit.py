#!/usr/bin/env python3
"""Prevent a producer from overwriting a newer change on the same content path.

This guard is deliberately path-level, not a channel-level lock or an upload
idempotency key. Production must remain serial until those larger problems are
solved. The caller checks the freshly fetched tip before *each* staging attempt.
"""
from __future__ import annotations

import argparse
import os
import stat
import subprocess
from pathlib import Path, PurePosixPath


def _git(repo: Path, *args: str, data: bytes | None = None) -> bytes:
    proc = subprocess.run(['git', *args], cwd=repo, input=data, capture_output=True, check=False)
    if proc.returncode:
        raise RuntimeError(f'git {args[0]} failed: {proc.stderr.decode(errors="replace").strip()}')
    return proc.stdout


def _validate_path(path: str) -> None:
    value = PurePosixPath(path)
    if (not path.startswith('content/') or value.is_absolute() or
            '..' in value.parts or '\n' in path or '\r' in path or '\x00' in path):
        raise ValueError(f'unsafe content path: {path!r}')


def _tree_entry(repo: Path, ref: str, path: str) -> tuple[str, str] | None:
    output = _git(repo, 'ls-tree', '-z', ref, '--', path)
    if not output:
        return None
    entries = output.split(b'\0')
    if len(entries) != 2 or entries[-1]:
        raise RuntimeError(f'ambiguous tree entry for {path}')
    description, raw_path = entries[0].split(b'\t', 1)
    mode, kind, oid = description.decode('ascii').split(' ')
    if raw_path.decode('utf-8') != path or kind != 'blob':
        raise RuntimeError(f'unsupported tree entry for {path}')
    return mode, oid


def _working_entry(repo: Path, path: str) -> tuple[str, str]:
    target = repo / path
    info = target.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise RuntimeError(f'cannot safely stage non-regular file: {path}')
    # Use Git's normal clean filters, as git add will; do not write the object.
    oid = _git(repo, 'hash-object', f'--path={path}', '--stdin', data=target.read_bytes()).decode('ascii').strip()
    mode = '100755' if info.st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH) else '100644'
    return mode, oid


def check_conflicts(repo: Path, base: str, target: str,
                    touched: list[str], deleted: list[str]) -> list[str]:
    """Return paths that a concurrent writer changed to a different state."""
    _git(repo, 'rev-parse', '--verify', f'{base}^{{commit}}')
    _git(repo, 'rev-parse', '--verify', f'{target}^{{commit}}')
    touched_set, deleted_set = set(touched), set(deleted)
    if touched_set & deleted_set:
        raise ValueError('a path cannot be both touched and deleted')
    conflicts = []
    for path in sorted(touched_set | deleted_set):
        _validate_path(path)
        # Reject paths through symlinked directories instead of reading outside
        # the workspace or comparing a different file than git add will stage.
        if any((repo / Path(*PurePosixPath(path).parts[:i])).is_symlink()
               for i in range(1, len(PurePosixPath(path).parts))):
            raise ValueError(f'symlinked parent in content path: {path}')
        if path in deleted_set:
            if os.path.lexists(repo / path):
                raise ValueError(f'deleted path still exists in working tree: {path}')
            desired = None
        else:
            desired = _working_entry(repo, path)
        before = _tree_entry(repo, base, path)
        current = _tree_entry(repo, target, path)
        if before == current:
            continue
        if current != desired:
            conflicts.append(path)
    return conflicts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', required=True)
    parser.add_argument('--target', required=True)
    parser.add_argument('--touched', required=True, type=Path)
    parser.add_argument('--deleted', required=True, type=Path)
    args = parser.parse_args()
    try:
        touched = args.touched.read_text(encoding='utf-8').splitlines()
        deleted = args.deleted.read_text(encoding='utf-8').splitlines()
        conflicts = check_conflicts(Path.cwd(), args.base, args.target, touched, deleted)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f'::error title=Producer state check failed::{exc}')
        return 1
    if conflicts:
        for path in conflicts:
            print(f'::error title=Producer content conflict::Newer content exists at {path}')
        print('Refusing to overwrite newer state. Reconcile any uploaded videos before retrying.')
        return 1
    print('Producer content race check passed; production remains serialized.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
