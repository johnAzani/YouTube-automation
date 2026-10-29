#!/usr/bin/env python3
"""One-time OAuth flow to mint a YouTube refresh token.

Run LOCALLY (not in CI) with your Google account:

    python scripts/youtube_oauth.py --client-secret client_secret.json

It prints the values to put in GitHub secrets separately:
    YOUTUBE_CLIENT_ID       (the OAuth client ID)
    YOUTUBE_CLIENT_SECRET   (the raw OAuth client secret)
    YOUTUBE_REFRESH_TOKEN   (the refresh token)

Default scopes: youtube.upload + youtube.readonly.
Use --purpose analytics for a separate read-only Analytics token, or
--purpose analytics-revenue to include monetary reports. Never paste tokens in chat.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def scopes_for(purpose: str) -> list[str]:
    base = "https://www.googleapis.com/auth/"
    if purpose == "upload":
        return [base + "youtube.upload", base + "youtube.readonly", base + "youtube.force-ssl"]
    scopes = [base + "youtube.readonly", base + "yt-analytics.readonly"]
    if purpose == "analytics-revenue":
        scopes.append(base + "yt-analytics-monetary.readonly")
    return scopes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--client-secret", required=True, help="path to OAuth client secret JSON")
    ap.add_argument("--purpose", choices=("upload", "analytics", "analytics-revenue"), default="upload")
    args = ap.parse_args()

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

    prefix = "YOUTUBE" if args.purpose == "upload" else "ANALYTICS"
    print("\n=== Sensitive values: store securely; never share in chat or public logs ===\n")
    print(f"Secret name: {prefix}_CLIENT_ID")
    print(client["client_id"])
    print(f"\nSecret name: {prefix}_CLIENT_SECRET")
    print(client["client_secret"])
    print(f"\nSecret name: {prefix}_REFRESH_TOKEN")
    print(creds.refresh_token)
    if args.purpose == "upload":
        print("\nStore in repository Actions secrets, not source files.")
    else:
        print("\nUse ANALYTICS_* in a private local environment. Do not run private reports in public Actions.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
