#!/usr/bin/env python3
"""Setup doctor — pre-flight check before the first production run.

    python scripts/doctor.py

Checks everything in docs/SETUP.md's order and prints a pass/fail table with
fix hints. Exit code 0 = ready to produce.
"""
from __future__ import annotations

import importlib
import os
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, hint: str = "") -> None:
    results.append((name, ok, hint))


def main() -> int:
    check("Python ≥ 3.10", sys.version_info >= (3, 10), "pyenv/apt install python3.12")

    for mod in ("yaml", "requests", "PIL", "edge_tts"):
        try:
            importlib.import_module(mod)
            check(f"dep: {mod}", True)
        except ImportError:
            check(f"dep: {mod}", False, "pip install -r requirements.txt")

    google_ok = True
    for mod in ("googleapiclient", "google.auth", "google_auth_oauthlib"):
        try:
            importlib.import_module(mod)
        except ImportError:
            google_ok = False
    check("dep: google api client (upload only)", google_ok, "pip install -r requirements.txt")

    try:
        from pipeline.assemble import ffmpeg_bin

        bin_ = ffmpeg_bin()
        check("ffmpeg", True, f"using {Path(bin_).name}")
    except Exception as exc:  # noqa: BLE001
        check("ffmpeg", False, f"{exc} — apt install ffmpeg or pip install imageio-ffmpeg")

    from pipeline.textplates import find_font

    check("font for text plates", find_font() is not None, "apt install fonts-dejavu-core")

    # Secrets (names only — never print values)
    for secret in ("GEMINI_API_KEY", "PEXELS_API_KEY", "PIXABAY_API_KEY", "YOUTUBE_CLIENT_ID",
                   "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"):
        present = bool(os.environ.get(secret)) or (REPO / ".env").exists()
        check(f"secret/env: {secret}", present, "docs/SETUP.md §2–4 (or .env locally)")

    check("AUTO_PUBLISH off until API audit passes",
          os.environ.get("AUTO_PUBLISH", "false").lower() in {"", "0", "false", "no"},
          "set AUTO_PUBLISH=true only after the YouTube API compliance audit")

    queue = list((REPO / "content" / "queue").glob("*.md"))
    approved = 0
    for q in queue:
        try:
            from pipeline.script_doc import parse_script

            if parse_script(q).status == "approved":
                approved += 1
        except Exception:  # noqa: BLE001
            check(f"script parses: {q.name}", False, "check YAML frontmatter")
    check("approved jobs in queue", approved > 0, "set status: approved in content/queue/*.md")

    for wf in ("produce.yml", "dry-run.yml", "keepalive.yml", "metrics.yml"):
        check(f"workflow: {wf}", (REPO / ".github" / "workflows" / wf).exists())

    # Authored stills in image-search/ are the fallback visual for every deep-dive and
    # Shorts scene. 10 of the 49 carry embedded Getty rights metadata and 3 more an
    # "All Rights Reserved" photographer copyright, so the ledger is a monetization gate,
    # not bookkeeping. See docs/ASSET_SOURCING.md.
    try:
        from pipeline.licences import load_ledger, LEDGER_PATH
        ledger = load_ledger(use_cache=False)
        stills = [p.name for p in (REPO / "image-search").iterdir()
                  if p.is_file() and p.name != "LICENSES.yml" and not p.name.startswith(".")]
        recorded = set(ledger)
        missing = sorted(set(stills) - recorded)
        encumbered = sorted(n for n, e in ledger.items() if e.get("status") == "rights-encumbered")
        check("image-search licence ledger covers every still", not missing and bool(ledger),
              f"unrecorded: {', '.join(missing[:3])}… — python scripts/licence_ledger.py write"
              if missing else "python scripts/licence_ledger.py write")
        # Re-derive each status from the file's own metadata and compare. A human may
        # promote an entry to `cleared`, but must never demote an encumbered file, and a
        # swapped file must not inherit its predecessor's clearance.
        from scripts.licence_ledger import scan_file, classify, sha256
        drifted = []
        for p in (REPO / "image-search").iterdir():
            if not p.is_file() or p.name == "LICENSES.yml" or p.name.startswith("."):
                continue
            entry = ledger.get(p.name) or {}
            derived, _ = classify(scan_file(p))
            if str(entry.get("sha256")) != sha256(p):
                drifted.append(f"{p.name} (bytes changed)")
            elif derived == "rights-encumbered" and entry.get("status") == "cleared":
                drifted.append(f"{p.name} (cleared but rights-encumbered)")
        check("licence ledger agrees with the files", not drifted,
              "; ".join(drifted[:3]) + (" …" if len(drifted) > 3 else ""))
        check("authored stills free of embedded rights claims", not encumbered,
              f"{len(encumbered)} of {len(stills)} stills carry a Getty / \"All Rights Reserved\" "
              "claim — replace before any monetized upload; image-search/LICENSES.yml names each")
    except Exception as exc:  # noqa: BLE001 - a bookkeeping gap must not crash the doctor
        check("image-search licence ledger readable", False, f"{exc!r}")

    # Report
    width = max(len(n) for n, _, _ in results)
    print("\n🩺 YouTube Automation — setup doctor\n")
    fails = 0
    for name, ok, hint in results:
        mark = "✅" if ok else "❌"
        line = f"  {mark} {name.ljust(width)}"
        if not ok and hint:
            line += f"   → {hint}"
        print(line)
        fails += 0 if ok else 1
    print(f"\n{len(results) - fails}/{len(results)} checks passed.", end="")
    if fails:
        print(" Fix ❌ items before the first production run.\n")
        return 1
    print(" Ready to produce. 🚀\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
