"""Stage-by-stage progress for a release, written while it runs.

Why this exists
---------------
Every failure on 2 November had the same shape: a step disappeared for an hour
and a half and left nothing behind but "exit code 1". The run page showed one
opaque *in progress*, the job log was unreachable, and the only way to tell a
slow render from a wedged one was to guess. Three renders were lost that way.

A release is a sequence of expensive stages — speech, alignment, asset fetch per
scene, encode, thumbnails, upload — and each can be the slow one for a different
reason. This module writes a timestamped line as each stage opens and closes, to
stdout *and* straight into ``$GITHUB_STEP_SUMMARY``, flushed immediately, so the
run page shows where the time actually went even when the job is killed.

It is deliberately dependency-free, cannot raise into the pipeline, and costs
nothing: no API, no file, no network. When ``GITHUB_STEP_SUMMARY`` is absent
(local runs, tests) it degrades to stdout.
"""
from __future__ import annotations

import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path


def _summary_path() -> Path | None:
    raw = os.environ.get("GITHUB_STEP_SUMMARY")
    return Path(raw) if raw else None


def emit(message: str) -> None:
    """Timestamped line to stdout and, in CI, to the step summary. Never raises."""
    stamp = time.strftime("%H:%M:%S", time.gmtime())
    line = f"[progress {stamp}Z] {message}"
    try:
        print(line, flush=True)
    except Exception:  # noqa: BLE001 - a closed stdout must never break a render
        pass
    try:
        path = _summary_path()
        if path is not None:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(f"- `{stamp}Z` {message}\n")
                fh.flush()
    except Exception:  # noqa: BLE001
        pass


#: The stage currently open, and when it opened. Read by the heartbeat thread.
_current: dict[str, object] = {"label": None, "since": 0.0}
_watchdog_started = False
#: How often to say "still inside <stage>" while the main thread is blocked.
STALL_REPORT_SECONDS = 120.0


def _watchdog() -> None:
    """Say which stage we are stuck in, while we are stuck in it.

    A per-stage ✓/✗ line only helps if the stage ever finishes. The failure this
    exists for is the opposite: the release step is killed at its cap, the log
    ends mid-sentence, and 68 unaccounted minutes look exactly like a wedged
    render. This thread prints from *outside* the blocked call, so a hung socket
    or a stalled subprocess names itself within two minutes.
    """
    while True:  # pragma: no cover - daemon loop
        time.sleep(STALL_REPORT_SECONDS)
        label = _current.get("label")
        if not label:
            continue
        since = float(_current.get("since") or 0.0)
        emit(f"… still inside {label} after {(time.monotonic() - since) / 60:.1f} min")


def _ensure_watchdog() -> None:
    global _watchdog_started
    if _watchdog_started or os.environ.get("PROGRESS_WATCHDOG", "1") == "0":
        return
    _watchdog_started = True
    thread = threading.Thread(target=_watchdog, name="progress-watchdog", daemon=True)
    thread.start()


@contextmanager
def stage(name: str, detail: str = ""):
    """Time a stage and report it opening and closing, including on failure."""
    label = f"{name}{' — ' + detail if detail else ''}"
    started = time.monotonic()
    _ensure_watchdog()
    previous = (_current.get("label"), _current.get("since"))
    _current["label"] = label
    _current["since"] = started
    emit(f"▶ {label}")
    try:
        yield
    except BaseException as exc:
        elapsed = time.monotonic() - started
        emit(f"✗ {label} failed after {elapsed:.1f}s: {type(exc).__name__}: {exc}")
        raise
    else:
        emit(f"✓ {label} in {time.monotonic() - started:.1f}s")
    finally:
        _current["label"], _current["since"] = previous


class Heartbeat:
    """Report progress inside a long loop, at most once per interval.

    The renderer calls this per frame, so the interval is checked before any
    formatting work: when it is not time yet, this costs a comparison.
    """

    def __init__(self, label: str, total: int, every_seconds: float = 120.0,
                 every_fraction: float = 0.10):
        self.label = label
        self.total = max(1, int(total))
        self.every_seconds = every_seconds
        self.every_fraction = every_fraction
        self.started = time.monotonic()
        self._last = 0.0
        self._next_fraction = every_fraction

    def tick(self, done: int) -> None:
        now = time.monotonic()
        fraction = done / self.total
        time_due = self.every_seconds > 0 and (now - self._last) >= self.every_seconds
        if fraction < self._next_fraction and not time_due:
            return
        self._last = now
        while self._next_fraction <= fraction:
            self._next_fraction += self.every_fraction
        elapsed = now - self.started
        rate = done / elapsed if elapsed > 0 else 0.0
        remaining = (self.total - done) / rate if rate > 0 else 0.0
        emit(f"{self.label}: {done}/{self.total} frames ({fraction * 100:.0f}%), "
             f"{elapsed:.0f}s elapsed, ~{remaining / 60:.0f} min left")
