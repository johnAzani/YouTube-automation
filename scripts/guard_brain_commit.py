#!/usr/bin/env python3
"""Refuse to commit brain output over newer content or a reused job ID.

The brain authors against a snapshot but commits onto the latest main. Compare
that snapshot with HEAD *after* the workflow fetch/reset, on every push retry.
A conflict must abort the whole commit, rather than silently overwrite work or
publish two different scripts with the same ID.
"""
from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

_JOB_FILE = re.compile(r"^content/queue/(\d{4})-[^/]+\.md$")
_EXISTING_JOB = re.compile(r"^content/(?:queue|published)/(\d{4})-[^/]+\.md$")


def git(repo: Path, *args: str, check: bool = True) -> str | None:
    result = subprocess.run(
        ["git", *args], cwd=repo, text=True, capture_output=True, check=False
    )
    if result.returncode:
        if check:
            raise RuntimeError(f"git {args[0]} failed")
        return None
    return result.stdout.strip()


def check_conflicts(repo: Path, base: str, touched: list[str], deleted: list[str]) -> list[str]:
    # Reject an invalid base explicitly; absence of a path is otherwise represented
    # by None, and two failures must not accidentally look like equal snapshots.
    git(repo, "rev-parse", "--verify", f"{base}^{{commit}}")
    git(repo, "rev-parse", "--verify", "HEAD^{commit}")
    conflicts: list[str] = []
    for path in sorted(set(touched + deleted)):
        before = git(repo, "rev-parse", "--verify", f"{base}:{path}", check=False)
        current = git(repo, "rev-parse", "--verify", f"HEAD:{path}", check=False)
        if before != current:
            conflicts.append(f"changed since authoring began: {path}")

    current_paths = (git(repo, "ls-tree", "-r", "--name-only", "HEAD", "--",
                         "content/queue/", "content/published/") or "").splitlines()
    occupied: dict[str, list[str]] = {}
    for path in current_paths:
        match = _EXISTING_JOB.fullmatch(path)
        if match:
            occupied.setdefault(match.group(1), []).append(path)
    for path in sorted(set(touched)):
        match = _JOB_FILE.fullmatch(path)
        if not match:
            continue
        # Existing queue files can be updated, but a new filename cannot reuse
        # an ID even if its slug differs from the file already on main.
        before = git(repo, "rev-parse", "--verify", f"{base}:{path}", check=False)
        if before is not None:
            continue
        job_id = match.group(1)
        others = [p for p in occupied.get(job_id, []) if p != path]
        if others:
            conflicts.append(f"job ID {job_id} already used: {path}; {', '.join(others)}")
        occupied.setdefault(job_id, []).append(path)
    return conflicts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--touched", required=True, type=Path)
    parser.add_argument("--deleted", required=True, type=Path)
    args = parser.parse_args()
    touched = args.touched.read_text(encoding="utf-8").splitlines()
    deleted = args.deleted.read_text(encoding="utf-8").splitlines()
    conflicts = check_conflicts(Path.cwd(), args.base, touched, deleted)
    if conflicts:
        for conflict in conflicts:
            print(f"::error title=Brain content race::{conflict}")
        print("Refusing to commit stale brain output; a fresh run can regenerate from latest main.")
        return 1
    print("Brain content race check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
