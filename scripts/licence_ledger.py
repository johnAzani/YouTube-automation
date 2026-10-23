#!/usr/bin/env python3
"""Licence ledger for the authored stills in `image-search/`.

Why this exists
---------------
`image-search/` holds the story stills that `tools/deep_dive.py` and `tools/shorts.py` fall
back to when a stock provider returns nothing. Nothing in the repo recorded where they came
from or whether they may be published. The renderers papered over that with a fixed string —
*"pre-existing image-search still; source/license metadata unavailable in current ledger —
verify before monetized reuse"* — which is honest but useless: it says the same thing about
a public-domain 1889 Library of Congress photograph and about a rights-managed Getty frame.

This script replaces the guess with evidence. It reads each file's **own** embedded
metadata (EXIF Copyright/Artist/ImageDescription, XMP packets, and raw byte markers such as
`gettyimages`, `xmpRights:WebStatement`, `plus:Licensor`, `All Rights Reserved`) and records
what it found in `image-search/LICENSES.yml`, keyed by SHA-256 so a swapped file cannot
inherit its predecessor's clearance.

Statuses
--------
``rights-encumbered``  An embedded rights claim was found (e.g. "© 2002 Getty Images",
                       "Copyright 2014 Steven L. Markos", "All Rights Reserved"). Must not
                       appear in a monetized upload. Replace the file.
``unverified``         No claim found, but absence of a claim is not a licence. Provenance
                       unknown — resolve by locating the source page, or replace the file.
``cleared``            A human verified the licence and recorded it in ``license`` plus
                       ``source_url``. Only these may be used in monetized output.
``corrupt``            The file will not decode. Dead weight; referenced by no scene.

Commands
--------
``check``  (default)  Verify the ledger matches the directory. Non-zero exit on drift.
``scan``              Print what the scanner sees per file, without writing anything.
``write``             Regenerate LICENSES.yml, preserving human-edited fields for any file
                      whose SHA-256 has not changed.

Usage
-----
    python scripts/licence_ledger.py            # check (what CI runs)
    python scripts/licence_ledger.py scan
    python scripts/licence_ledger.py write
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMG_DIR = ROOT / "image-search"
LEDGER = IMG_DIR / "LICENSES.yml"
LEDGER_NAME = "LICENSES.yml"

# Byte-level markers. Deliberately literal: these are the strings rights holders actually
# embed, and a false negative here is the expensive direction.
MARKERS = (
    (rb"gettyimages", "gettyimages.com XMP namespace"),
    (rb"Getty Images", '"Getty Images" in metadata'),
    (rb"xmpRights:WebStatement", "xmpRights:WebStatement (rights web statement)"),
    (rb"plus:Licensor", "PLUS licensor record"),
    (rb"Shutterstock", "Shutterstock marker"),
    (rb"Alamy", "Alamy marker"),
    (rb"AP Images", "AP Images marker"),
    (rb"Reuters", "Reuters marker"),
    (rb"All Rights Reserved", '"All Rights Reserved"'),
    (rb"All rights reserved", '"All rights reserved"'),
    (rb"creativecommons.org/licenses/", "Creative Commons licence URL"),
    (rb"creativecommons.org/publicdomain/", "Creative Commons public-domain URL"),
    (rb"Library of Congress", '"Library of Congress"'),
    (rb"loc.gov", "loc.gov reference"),
    (rb"National Archives", '"National Archives"'),
    (rb"Public Domain", '"Public Domain"'),
    (rb"Pexels", "Pexels marker"),
    (rb"Pixabay", "Pixabay marker"),
    (rb"flickr", "Flickr reference"),
)

# EXIF tags worth transcribing, by decimal tag id.
EXIF_TAGS = {0x013B: "Artist", 0x8298: "Copyright", 0x010E: "ImageDescription",
             0x0131: "Software", 0x0132: "DateTime", 0x010F: "Make", 0x0110: "Model"}

STATUS_ORDER = ("rights-encumbered", "corrupt", "unverified", "cleared")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _clean(value) -> str:
    return re.sub(r"\s+", " ", str(value)).strip()


def scan_file(path: Path) -> dict:
    """Return what the file itself can tell us about its provenance."""
    out: dict = {"sha256": sha256(path), "bytes": path.stat().st_size}
    raw = path.read_bytes()
    out["markers"] = [label for pat, label in MARKERS if pat in raw]

    try:
        from PIL import Image
    except ImportError:  # pragma: no cover - Pillow is in requirements.txt
        out["decodes"] = None
        return out

    try:
        with Image.open(path) as im:
            im.load()
            out["decodes"] = True
            out["dimensions"] = f"{im.size[0]}x{im.size[1]}"
            out["format"] = im.format
            exif = im.getexif()
            for tag_id, name in EXIF_TAGS.items():
                if tag_id in exif:
                    out[name] = _clean(exif[tag_id])[:200]
            comment = im.info.get("comment") if isinstance(im.info, dict) else None
            if comment:
                out["Comment"] = _clean(comment if isinstance(comment, str)
                                       else comment.decode("utf-8", "replace"))[:200]
    except Exception as exc:  # noqa: BLE001 - a broken file is a finding, not a crash
        out["decodes"] = False
        out["error"] = f"{type(exc).__name__}: {exc}"
    return out


def classify(info: dict) -> tuple[str, str]:
    """Return (status, reason) from the scan evidence alone. Never returns `cleared` —
    only a human may clear a file."""
    if info.get("decodes") is False:
        return "corrupt", f"does not decode: {info.get('error', 'unknown error')}"

    claims = []
    if info.get("Copyright"):
        claims.append(f'EXIF Copyright: "{info["Copyright"]}"')
    joined = " ".join(info.get("markers", []))
    for marker, label in MARKERS:
        name = label
        if marker in (b"gettyimages", b"Getty Images") and "Getty" in joined:
            claims.append("Getty Images rights metadata embedded in the file")
            break
        if marker == b"plus:Licensor" and "PLUS" in joined:
            claims.append("PLUS licensor record embedded in the file")
        if marker == b"xmpRights:WebStatement" and "xmpRights" in joined:
            claims.append("xmpRights web statement present")
        if marker in (b"All Rights Reserved", b"All rights reserved") \
                and "All Rights Reserved" in joined:
            claims.append('"All Rights Reserved" present')
    # de-duplicate while preserving order
    claims = list(dict.fromkeys(claims))

    if claims:
        return "rights-encumbered", "; ".join(dict.fromkeys(claims))

    hints = []
    if info.get("Artist"):
        hints.append(f'EXIF Artist: "{info["Artist"]}"')
    if info.get("Comment"):
        hints.append(f'file comment: "{info["Comment"]}"')
    if "Library of Congress" in joined or "loc.gov" in joined:
        hints.append("Library of Congress reference in metadata")
    if "Creative Commons licence URL" in joined or "Creative Commons public-domain URL" in joined:
        hints.append("a Creative Commons URL appears in the file")
    reason = "; ".join(dict.fromkeys(hints)) if hints else \
        "no embedded rights claim and no provenance metadata"
    return "unverified", reason


def load_ledger() -> dict:
    if not LEDGER.is_file():
        return {}
    try:
        import yaml
    except ImportError:  # pragma: no cover
        raise SystemExit("PyYAML is required: pip install -r requirements.txt")
    return yaml.safe_load(LEDGER.read_text(encoding="utf-8")) or {}


def ledger_files(ledger: dict) -> dict:
    return {str(e.get("file")): e for e in (ledger.get("files") or []) if isinstance(e, dict)}


def build_entries(previous: dict) -> tuple[list[dict], list[dict]]:
    """Return (entries, findings). `findings` lists drift between ledger and directory."""
    prev_by_sha = {str(e.get("sha256")): e for e in previous.values()}
    entries, findings = [], []
    on_disk = sorted(p for p in IMG_DIR.iterdir()
                     if p.is_file() and p.name != LEDGER_NAME and not p.name.startswith("."))
    for path in on_disk:
        info = scan_file(path)
        status, reason = classify(info)
        entry: dict = {
            "file": path.name,
            "sha256": info["sha256"],
            "bytes": info["bytes"],
            "status": status,
            "evidence": reason,
        }
        if info.get("dimensions"):
            entry["dimensions"] = info["dimensions"]
        if info.get("Copyright"):
            entry["rights_claim"] = info["Copyright"]
        if info.get("Artist"):
            entry["embedded_artist"] = info["Artist"]
        if info.get("Comment"):
            entry["embedded_comment"] = info["Comment"]
        # Preserve human edits, but only if the bytes are unchanged — a cleared entry must
        # never silently transfer to different content.
        kept = prev_by_sha.get(info["sha256"])
        if kept:
            for field in ("license", "source_url", "attribution", "verified_on",
                          "verified_by", "notes"):
                if kept.get(field) is not None:
                    entry[field] = kept[field]
            if kept.get("status") == "cleared" and status != "cleared":
                # human said cleared and the scanner found nothing contradicting it
                entry["status"] = "cleared"
                entry["evidence"] = kept.get("evidence") or reason
        entries.append(entry)
        if kept and kept.get("status") == "cleared" and status == "rights-encumbered":
            findings.append(f"{path.name}: marked cleared in the ledger but the file carries "
                            f"an embedded rights claim ({reason})")

    on_disk_names = {p.name for p in on_disk}
    for name in sorted(set(previous) - on_disk_names):
        findings.append(f"{name}: recorded in the ledger but absent from image-search/")
    return entries, findings


def render(entries: list[dict], findings: list[dict]) -> str:
    counts = {s: sum(1 for e in entries if e["status"] == s) for s in STATUS_ORDER}
    lines = [
        "# Licence ledger for image-search/ — GENERATED BY scripts/licence_ledger.py",
        "#",
        "# Do not hand-edit `file`, `sha256`, `bytes`, `dimensions`, `evidence`,",
        "# `rights_claim`, `embedded_*`: `write` regenerates them from the files.",
        "# You MAY edit `status`, `license`, `source_url`, `attribution`, `verified_on`,",
        "# `verified_by` and `notes` — those are preserved for any file whose sha256 is",
        "# unchanged, so a clearance can never silently transfer to different bytes.",
        "#",
        "# status:",
        "#   rights-encumbered  embedded rights claim found — MUST NOT be monetized",
        "#   unverified         no claim found; absence of a claim is not a licence",
        "#   cleared            a human verified the licence and recorded it below",
        "#   corrupt            will not decode; dead weight",
        "#",
        "# Only `cleared` files may appear in monetized output. See docs/ASSET_SOURCING.md.",
        f"generated_by: scripts/licence_ledger.py",
        f"counts: {{rights-encumbered: {counts['rights-encumbered']}, "
        f"corrupt: {counts['corrupt']}, unverified: {counts['unverified']}, "
        f"cleared: {counts['cleared']}, total: {len(entries)}}}",
        "files:",
    ]
    for e in entries:
        lines.append(f"  - file: {_yaml_str(e['file'])}")
        for key in ("sha256", "bytes", "dimensions", "status", "rights_claim",
                    "embedded_artist", "embedded_comment", "license", "source_url",
                    "attribution", "verified_on", "verified_by"):
            if e.get(key) is not None:
                lines.append(f"    {key}: {_yaml_str(e[key])}")
        lines.append(f"    evidence: {_yaml_str(e['evidence'])}")
        if e.get("notes"):
            lines.append(f"    notes: {_yaml_str(e['notes'])}")
    return "\n".join(lines) + "\n"


def _yaml_str(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    text = str(value).replace('"', '\\"')
    return f'"{text}"'


def cmd_scan() -> int:
    entries, findings = build_entries(load_ledger())
    for e in entries:
        print(f"{e['file']}\n    [{e['status']}] {e['evidence']}")
    if findings:
        print("\n-- findings --")
        for f in findings:
            print(f"  ! {f}")
    return 0


def cmd_write() -> int:
    previous = ledger_files(load_ledger())
    entries, findings = build_entries(previous)
    LEDGER.write_text(render(entries, findings), encoding="utf-8")
    counts = {s: sum(1 for e in entries if e["status"] == s) for s in STATUS_ORDER}
    print(f"wrote {LEDGER.relative_to(ROOT)} — {len(entries)} files: "
          + ", ".join(f"{k}={v}" for k, v in counts.items() if v))
    for f in findings:
        print(f"  ! {f}")
    return 0


def cmd_check() -> int:
    """Fail on drift: a file with no entry, a stale entry, or a sha mismatch."""
    if not LEDGER.is_file():
        print(f"FAIL: {LEDGER.relative_to(ROOT)} does not exist — run "
              f"`python scripts/licence_ledger.py write`")
        return 1
    previous = ledger_files(load_ledger())
    entries, findings = build_entries(previous)
    problems = list(findings)

    by_name = {e["file"]: e for e in entries}
    for name, entry in by_name.items():
        recorded = previous.get(name)
        if recorded is None:
            problems.append(f"{name}: present in image-search/ but missing from the ledger")
        elif str(recorded.get("sha256")) != entry["sha256"]:
            problems.append(f"{name}: file contents changed since the ledger was written "
                            f"(sha256 {str(recorded.get('sha256'))[:12]}… → {entry['sha256'][:12]}…) "
                            "— re-verify the licence, it is not the same asset")
    for name in sorted(set(previous) - set(by_name)):
        if not any(name in f for f in problems):
            problems.append(f"{name}: in the ledger but not on disk")

    for name, entry in by_name.items():
        recorded = previous.get(name) or {}
        if recorded.get("status") == "cleared":
            if not str(recorded.get("license") or "").strip():
                problems.append(f"{name}: status=cleared but no `license` recorded")
            if not str(recorded.get("source_url") or "").strip():
                problems.append(f"{name}: status=cleared but no `source_url` recorded")

    if problems:
        print(f"licence ledger: {len(problems)} problem(s)")
        for p in problems:
            print(f"  ✗ {p}")
        print("  → regenerate with `python scripts/licence_ledger.py write`, then resolve "
              "each rights-encumbered file before any monetized upload")
        return 1

    counts = {s: sum(1 for e in entries if e["status"] == s) for s in STATUS_ORDER}
    print("licence ledger: in sync — "
          + ", ".join(f"{k}={v}" for k, v in counts.items() if v))
    if counts["rights-encumbered"]:
        print(f"  ⚠ {counts['rights-encumbered']} file(s) carry an embedded rights claim and "
              "must not be used in monetized output")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("command", nargs="?", default="check",
                        choices=("check", "scan", "write"))
    args = parser.parse_args(argv)
    return {"check": cmd_check, "scan": cmd_scan, "write": cmd_write}[args.command]()


if __name__ == "__main__":
    sys.exit(main())
