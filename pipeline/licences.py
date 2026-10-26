"""Read `image-search/LICENSES.yml` and tell callers whether a still may be used.

The authored Johnstown/Enron stills in `image-search/` are the fallback visual for every
scene in `tools/deep_dive.py` and `tools/shorts.py` when a stock provider returns nothing.
Until the ledger existed, both tools wrote the same fixed string into their credits file —
*"pre-existing image-search still; source/license metadata unavailable in current ledger"* —
which said the same thing about a public-domain 1889 Library of Congress photograph and
about a rights-managed Getty frame. Ten of the 49 files turn out to carry embedded Getty
Images rights metadata and three more an "All Rights Reserved" photographer copyright.

This module makes the distinction available to the renderers and to `scripts/doctor.py`.
It never blocks a render on its own: the authored deep dives are archived, out-of-niche
demonstrations, and a hard refusal would break a working tool over a bookkeeping gap. What
it does is make the credits file tell the truth and make the gap impossible to miss.

Ledger maintenance lives in `scripts/licence_ledger.py` (``write`` regenerates, ``check``
is what CI runs).
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER_PATH = ROOT / "image-search" / "LICENSES.yml"

UNSAFE_STATUSES = ("rights-encumbered", "corrupt")

_NOTE_BY_STATUS = {
    "cleared": "image-search still — licence verified and recorded in image-search/LICENSES.yml",
    "rights-encumbered": ("image-search still — RIGHTS ENCUMBERED: an embedded rights claim was "
                          "found in this file; do not use in monetized output "
                          "(see image-search/LICENSES.yml)"),
    "unverified": ("image-search still — provenance unverified; no embedded rights claim found, "
                   "but absence of a claim is not a licence (see image-search/LICENSES.yml)"),
    "corrupt": "image-search still — file does not decode; do not use (see image-search/LICENSES.yml)",
}

_cache: dict[str, dict] | None = None


def load_ledger(path: Path | str | None = None, *, use_cache: bool = True) -> dict[str, dict]:
    """Return {filename: entry}. Missing ledger or missing PyYAML → empty dict (never raises:
    a bookkeeping file must not be able to crash a render)."""
    global _cache
    if path is None and use_cache and _cache is not None:
        return _cache
    ledger_path = Path(path) if path is not None else LEDGER_PATH
    entries: dict[str, dict] = {}
    try:
        import yaml
        raw = yaml.safe_load(ledger_path.read_text(encoding="utf-8")) or {}
        for item in raw.get("files") or []:
            if isinstance(item, dict) and item.get("file"):
                entries[str(item["file"])] = item
    except Exception:  # noqa: BLE001 - absent/invalid ledger degrades to "unknown"
        entries = {}
    if path is None and use_cache:
        _cache = entries
    return entries


def clear_cache() -> None:
    global _cache
    _cache = None


def status_of(filename: str, ledger: dict[str, dict] | None = None) -> str:
    """`cleared` / `unverified` / `rights-encumbered` / `corrupt` / `unrecorded`."""
    ledger = load_ledger() if ledger is None else ledger
    fname = Path(filename).name if filename else ""
    entry = ledger.get(fname) or ledger.get(str(filename))
    if not entry:
        return "unrecorded"
    return str(entry.get("status") or "unverified")


def is_safe_for_monetized_use(filename: str, ledger: dict[str, dict] | None = None) -> bool:
    """True only for a file a human has explicitly cleared."""
    return status_of(filename, ledger) == "cleared"


def licence_note(filename: str, ledger: dict[str, dict] | None = None) -> str:
    """The string that belongs in a credits/scene-sources record for this still."""
    ledger = load_ledger() if ledger is None else ledger
    status = status_of(filename, ledger)
    note = _NOTE_BY_STATUS.get(
        status,
        "image-search still — not recorded in image-search/LICENSES.yml; run "
        "`python scripts/licence_ledger.py write`",
    )
    entry = ledger.get(str(filename)) or {}
    claim = entry.get("rights_claim")
    if claim:
        note += f' (claim: "{claim}")'
    attribution = entry.get("attribution")
    if status == "cleared" and attribution:
        note += f"; credit: {attribution}"
    return note


def licence_report(filenames, ledger: dict[str, dict] | None = None) -> list[str]:
    """Console lines naming stills that are not cleared for monetized use.

    Lives here rather than inline in the two renderers because inline versions of this
    block were exactly where a `NameError` (`_len` for `len`) shipped once already — the
    unit suite never calls a renderer's `main()`, so only CI's offline render caught it.
    Two tiers, so the warning stays readable: hard blockers are listed by name, and the
    much larger `unverified` set is summarised in one line.
    """
    ledger = load_ledger() if ledger is None else ledger
    names = [str(n) for n in filenames]
    hard = unsafe_stills(names, ledger)
    unverified = [n for n, s in uncleared_stills(names, ledger) if s == "unverified"]
    lines: list[str] = []
    if hard:
        lines.append(f"  !! {len(hard)} authored still(s) in this render MUST NOT be monetized "
                     f"(image-search/LICENSES.yml):")
        lines.extend(f"     - {name} [{status}]" for name, status in hard)
    if unverified:
        lines.append(f"  !  {len(unverified)} further still(s) have unverified provenance — "
                     f"usable for a private draft, not for a monetized upload")
    return lines


def unsafe_stills(filenames, ledger: dict[str, dict] | None = None) -> list[tuple[str, str]]:
    """Hard blockers: [(filename, status)] for files that must not be rendered at all.

    `rights-encumbered` (an actual claim is embedded in the file), `corrupt` (will not
    decode) and `unrecorded` (nobody has even scanned it). Deliberately excludes
    `unverified` — 35 of the 49 stills are in that state, and a 35-line warning gets
    ignored. `unverified` is reported by `uncleared_stills()` and by each file's own
    `licence_note()` in the credits file.
    """
    ledger = load_ledger() if ledger is None else ledger
    return [(str(name), status_of(str(name), ledger))
            for name in filenames
            if status_of(str(name), ledger) in UNSAFE_STATUSES or status_of(str(name), ledger) == "unrecorded"]


def uncleared_stills(filenames, ledger: dict[str, dict] | None = None) -> list[tuple[str, str]]:
    """Everything that is not `cleared` — the honest answer to "may I monetize this?"."""
    ledger = load_ledger() if ledger is None else ledger
    return [(str(name), status_of(str(name), ledger))
            for name in filenames
            if status_of(str(name), ledger) != "cleared"]
