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
    for secret in ("PEXELS_API_KEY", "PIXABAY_API_KEY", "YOUTUBE_CLIENT_SECRET",
                   "YOUTUBE_REFRESH_TOKEN"):
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
