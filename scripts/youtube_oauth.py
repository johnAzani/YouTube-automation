#!/usr/bin/env python3
"""One-time OAuth flow to mint a YouTube refresh token.

Run LOCALLY (not in CI) with your Google account:

    python scripts/youtube_oauth.py --client-secret client_secret.json

It prints the values to put in GitHub secrets separately:
    YOUTUBE_CLIENT_ID       (the OAuth client ID)
    YOUTUBE_CLIENT_SECRET   (the raw OAuth client secret)
    YOUTUBE_REFRESH_TOKEN   (the refresh token)

Default scopes (--purpose upload): youtube.upload + youtube.readonly +
youtube.force-ssl — the exact set `pipeline/upload.py` SCOPES requests.
A token minted with fewer scopes is rejected with invalid_scope by every
pipeline script, so if you mint in OAuth Playground instead, tick all three.

--purpose full mints ONE token per channel that carries everything a creator
channel can grant (FULL_SCOPES below), so no second token is ever needed for
measurement or, later, revenue. A token with more scopes than a script asks
for still works for that script. Store it in the same YOUTUBE_REFRESH_TOKEN
secret. See docs/PERMISSIONS_2026-11-14.md.

Use --purpose analytics for a separate read-only Analytics token, or
--purpose analytics-revenue to include monetary reports. Never paste tokens in chat.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


#: Every scope a creator's own channel can grant (YouTube Data API, Analytics API
#: and Reporting API scope tables, read 14 November 2026). Left out on purpose:
#: `youtubepartner` and `youtubepartner-channel-audit`, which act only for a
#: YouTube Content Manager (a network or label), not for a channel.
FULL_SCOPES = (
    "youtube",                               # manage the account: channel page, playlists, shelves
    "youtube.force-ssl",                     # videos, comments and captions
    "youtube.upload",                        # upload, thumbnails
    "youtube.readonly",                      # read
    "yt-analytics.readonly",                 # watch time, sources, retention; bulk reports (impressions)
    "yt-analytics-monetary.readonly",        # revenue reports, once the channel earns
    "youtube.channel-memberships.creator",   # list members, once memberships exist
)


def scopes_for(purpose: str) -> list[str]:
    base = "https://www.googleapis.com/auth/"
    if purpose == "full":
        return [base + scope for scope in FULL_SCOPES]
    if purpose == "upload":
        return [base + "youtube.upload", base + "youtube.readonly", base + "youtube.force-ssl"]
    scopes = [base + "youtube.readonly", base + "yt-analytics.readonly"]
    if purpose == "analytics-revenue":
        scopes.append(base + "yt-analytics-monetary.readonly")
    return scopes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--client-secret", help="path to OAuth client secret JSON")
    ap.add_argument("--purpose", choices=("upload", "full", "analytics", "analytics-revenue"),
                    default="upload")
    ap.add_argument("--print-scopes", action="store_true",
                    help="print the scope list for --purpose (to paste into OAuth Playground) and exit")
    args = ap.parse_args()

    if args.print_scopes:
        print(" ".join(scopes_for(args.purpose)))
        return 0
    if not args.client_secret:
        ap.error("--client-secret is required")

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("pip install -r requirements.txt first", file=sys.stderr)
        return 1

    scopes = scopes_for(args.purpose)
    flow = InstalledAppFlow.from_client_secrets_file(args.client_secret, scopes)

    # Local server flow — opens the browser, listens on localhost.
    creds = flow.run_local_server(port=8765, prompt="consent", access_type="offline")

    client_config = json.loads(Path(args.client_secret).read_text(encoding="utf-8"))
    client = client_config.get("web") or client_config.get("installed")
    if not client or not client.get("client_id") or not client.get("client_secret"):
        print("OAuth client JSON must contain a web or installed client_id/client_secret", file=sys.stderr)
        return 1

    prefix = "YOUTUBE" if args.purpose in ("upload", "full") else "ANALYTICS"
    print("\n=== Sensitive values: store securely; never share in chat or public logs ===\n")
    print(f"Secret name: {prefix}_CLIENT_ID")
    print(client["client_id"])
    print(f"\nSecret name: {prefix}_CLIENT_SECRET")
    print(client["client_secret"])
    print(f"\nSecret name: {prefix}_REFRESH_TOKEN")
    print(creds.refresh_token)
    if args.purpose in ("upload", "full"):
        print("\nStore in repository Actions secrets, not source files.")
    else:
        print("\nUse ANALYTICS_* in a private local environment. Do not run private reports in public Actions.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
