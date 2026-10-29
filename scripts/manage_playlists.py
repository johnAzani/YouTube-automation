#!/usr/bin/env python3
"""Manage and synchronize Official Series Playlists on YouTube.

Maximizes Session Watch Time by grouping biblical prayers and sleep suites
into autoplay series, directly advancing the 4,000 Watch Hours YPP milestone.

Usage:
    python scripts/manage_playlists.py --dry-run      # Simulate playlist audit and sync
    python scripts/manage_playlists.py                # Perform live sync if credentials set
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.config import CONFIG
from pipeline.playlists import sync_all_series_playlists


def main() -> None:
    parser = argparse.ArgumentParser(description="YouTube Series Playlist Management Engine")
    parser.add_argument("--dry-run", action="store_true", help="Simulate playlist updates without API calls")
    args = parser.parse_args()

    youtube = None
    dry_run = args.dry_run

    # Check credentials
    if not dry_run:
        if not (CONFIG.youtube_client_id and CONFIG.youtube_client_secret and CONFIG.youtube_refresh_token):
            print("[playlist] Missing YouTube credentials. Defaulting to dry-run simulation mode.")
            dry_run = True
        else:
            try:
                from googleapiclient.discovery import build
                from pipeline.upload import _credentials
                creds = _credentials()
                youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
            except Exception as exc:
                print(f"[playlist] Warning: could not initialize authenticated YouTube client: {exc}")
                print("[playlist] Defaulting to dry-run simulation mode.")
                dry_run = True

    sync_all_series_playlists(youtube=youtube, dry_run=dry_run)


if __name__ == "__main__":
    main()
