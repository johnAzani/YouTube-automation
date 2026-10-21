#!/usr/bin/env python3
"""One-time OAuth flow to mint a YouTube refresh token.

Run LOCALLY (not in CI) with your Google account:

    python scripts/youtube_oauth.py --client-secret client_secret.json

It prints the values to put in GitHub secrets separately:
    YOUTUBE_CLIENT_ID       (the OAuth client ID)
    YOUTUBE_CLIENT_SECRET   (the raw OAuth client secret)
    YOUTUBE_REFRESH_TOKEN   (the refresh token)

Scopes requested: youtube.upload only (least privilege).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--client-secret", required=True, help="path to OAuth client secret JSON")
    args = ap.parse_args()

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("pip install -r requirements.txt first", file=sys.stderr)
        return 1

    scopes = [
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube.readonly",
    ]
    flow = InstalledAppFlow.from_client_secrets_file(args.client_secret, scopes)

    # Local server flow — opens the browser, listens on localhost.
    creds = flow.run_local_server(port=8765, prompt="consent", access_type="offline")

    client_config = json.loads(Path(args.client_secret).read_text(encoding="utf-8"))
    client = client_config.get("web") or client_config.get("installed")
    if not client or not client.get("client_id") or not client.get("client_secret"):
        print("OAuth client JSON must contain a web or installed client_id/client_secret", file=sys.stderr)
        return 1

    print("\n=== Paste each value into its own GitHub secret ===\n")
    print("Secret name: YOUTUBE_CLIENT_ID")
    print(client["client_id"])
    print("\nSecret name: YOUTUBE_CLIENT_SECRET")
    print(client["client_secret"])
    print("\nSecret name: YOUTUBE_REFRESH_TOKEN")
    print(creds.refresh_token)
    print("\nThen, in the repo: Settings → Secrets and variables → Actions → New repository secret")
    return 0


if __name__ == "__main__":
    sys.exit(main())
