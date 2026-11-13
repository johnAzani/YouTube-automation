#!/usr/bin/env python3
"""Find and undo receipts that a production leg overwrote from a stale checkout.

Until the produce legs started from current main, a leg could run on a tree
older than its own channel's last publish (docs/STALE_CHECKOUT_RECEIPTS_2026-11-13.md).
Its ``chore(content): publish job`` commit then did one of two things to a
receipt that already existed, for a video that was already live:

* **restamp** - wrote a later ``published_at`` over the true one;
* **stub** - replaced a full Short receipt with the short "recovered from
  YouTube" record, losing its script, metadata revision and render facts.

Both leave the original in git history, so both are reversible. This reads the
publish commits, finds those two shapes (same ``youtube_video_id`` before and
after, so a genuinely new upload is never touched), and restores:

* restamp -> ``published_at`` / ``published_on`` only; everything else in the
  file is newer, legitimate state and is kept;
* stub -> the original receipt, carrying over the current ``thumbnail_*``
  fields because the monitor has kept those up to date since.

    python scripts/repair_clobbered_receipts.py            # report only
    python scripts/repair_clobbered_receipts.py --apply    # restore in the tree
    python scripts/repair_clobbered_receipts.py --check    # exit 1 if any remain

It needs history: in a depth-1 checkout there is nothing to compare and it says so.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLISHED = "content/published"
PUBLISH_SUBJECT = "publish job"
_FIELD = re.compile(r"^([A-Za-z0-9_]+):[ \t]*(.*)$")
_TIME_FIELDS = ("published_at", "published_on")


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False)
    if proc.returncode:
        raise RuntimeError(f"git {' '.join(args[:2])} failed: {proc.stderr.strip()[:200]}")
    return proc.stdout


def _show(repo: Path, rev: str, path: str) -> str | None:
    proc = subprocess.run(["git", "show", f"{rev}:{path}"], cwd=repo,
                          capture_output=True, text=True, check=False)
    return proc.stdout if proc.returncode == 0 else None


def split_front_matter(text: str) -> tuple[list[str], str] | None:
    """``(front-matter lines, everything from the closing '---' on)`` or None."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            return lines[1:idx], "\n".join(lines[idx:])
    return None


def fields(text: str) -> dict[str, str]:
    """Top-level front-matter scalars, unquoted. Enough to compare receipts."""
    parts = split_front_matter(text)
    out: dict[str, str] = {}
    if parts is None:
        return out
    for line in parts[0]:
        match = _FIELD.match(line)
        if match:
            out[match.group(1)] = match.group(2).strip().strip("'\"")
    return out


def _is_stub(meta: dict[str, str]) -> bool:
    return meta.get("receipt_recovered_from_youtube", "").lower() == "true"


def set_fields(text: str, wanted: dict[str, str]) -> str:
    """Replace (or append) raw front-matter lines; ``wanted`` maps key -> full line."""
    parts = split_front_matter(text)
    if parts is None:
        return text
    front, rest = parts
    seen: set[str] = set()
    for idx, line in enumerate(front):
        match = _FIELD.match(line)
        if match and match.group(1) in wanted:
            front[idx] = wanted[match.group(1)]
            seen.add(match.group(1))
    front.extend(line for key, line in wanted.items() if key not in seen)
    return "\n".join(["---", *front]) + "\n" + rest


def raw_lines(text: str, keys=None, prefix: str | None = None) -> dict[str, str]:
    parts = split_front_matter(text)
    out: dict[str, str] = {}
    if parts is None:
        return out
    for line in parts[0]:
        match = _FIELD.match(line)
        if not match:
            continue
        key = match.group(1)
        if (keys and key in keys) or (prefix and key.startswith(prefix)):
            out[key] = line
    return out


@dataclass
class Damage:
    path: str
    kind: str            # "restamp" | "stub"
    commit: str          # the publish commit that overwrote the receipt
    video_id: str
    original: str        # file content before that commit
    was: str             # original published_at
    became: str          # published_at the commit wrote

    def describe(self) -> str:
        what = ("full receipt replaced by a recovery stub" if self.kind == "stub"
                else f"published_at {self.was} -> {self.became}")
        return f"{self.path}  [{self.kind}] by {self.commit[:7]}: {what}"


def find_damage(repo: Path = ROOT) -> list[Damage]:
    """Every receipt a publish commit overwrote and that is still wrong in the tree."""
    log = _git(repo, "log", "--reverse", f"--grep={PUBLISH_SUBJECT}", "--diff-filter=M",
               "--format=@%H", "--name-only", "--", PUBLISHED)
    first: dict[str, Damage] = {}
    commit = ""
    for line in log.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("@"):
            commit = line[1:]
            continue
        if not line.endswith(".md"):
            continue
        before, after = _show(repo, f"{commit}^", line), _show(repo, commit, line)
        if before is None or after is None:
            continue
        old, new = fields(before), fields(after)
        video = old.get("youtube_video_id", "")
        if not video or video != new.get("youtube_video_id", ""):
            continue                      # a different or first upload: not this fault
        if _is_stub(old):
            continue                      # already a stub before this commit
        if _is_stub(new):
            kind = "stub"
        elif old.get("published_at") and old.get("published_at") != new.get("published_at"):
            kind = "restamp"
        else:
            continue
        # The oldest overwrite holds the true original; a later one only saw damage.
        first.setdefault(line, Damage(line, kind, commit, video, before,
                                      old.get("published_at", ""), new.get("published_at", "")))

    outstanding: list[Damage] = []
    for item in first.values():
        current_path = repo / item.path
        if not current_path.is_file():
            continue
        now = fields(current_path.read_text(encoding="utf-8"))
        if now.get("youtube_video_id", "") != item.video_id:
            continue
        if item.kind == "stub" and _is_stub(now):
            outstanding.append(item)
        elif item.kind == "restamp" and now.get("published_at") != item.was:
            outstanding.append(item)
    return outstanding


def repaired_text(item: Damage, current: str) -> str:
    if item.kind == "restamp":
        return set_fields(current, raw_lines(item.original, keys=_TIME_FIELDS))
    return set_fields(item.original, raw_lines(current, prefix="thumbnail_"))


def apply(items: list[Damage], repo: Path = ROOT) -> list[str]:
    changed = []
    for item in items:
        path = repo / item.path
        current = path.read_text(encoding="utf-8")
        fixed = repaired_text(item, current)
        if fixed != current:
            path.write_text(fixed, encoding="utf-8")
            changed.append(item.path)
    return changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--apply", action="store_true", help="restore the receipts in the working tree")
    parser.add_argument("--check", action="store_true", help="exit 1 if any overwritten receipt remains")
    parser.add_argument("--repo", default=str(ROOT))
    args = parser.parse_args(argv)
    repo = Path(args.repo)

    if _git(repo, "rev-parse", "--is-shallow-repository").strip() == "true":
        print("[repair] this checkout is shallow, so older publish commits cannot be "
              "compared; run `git fetch --unshallow` (or a deeper fetch) first.")
    items = find_damage(repo)
    if not items:
        print("[repair] no overwritten receipts found.")
        return 0
    print(f"[repair] {len(items)} overwritten receipt(s):")
    for item in items:
        print("  - " + item.describe())
    if args.apply:
        changed = apply(items, repo)
        print(f"[repair] restored {len(changed)} file(s). Review with `git diff`, then commit.")
        return 0
    return 1 if args.check else 0


if __name__ == "__main__":
    sys.exit(main())
