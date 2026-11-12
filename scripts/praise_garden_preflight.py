#!/usr/bin/env python3
"""Read-only, fail-closed identity preflight for the *staged* ninth channel.

This tool does not register a channel or enable any workflow. Supply the four
PRAYER9 YouTube values through a secure local environment; never paste them into chat.
Successful identity/scope checks do not prove upload, generation, or thumbnail
permissions. No YouTube write endpoints are used.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from typing import Callable

PREFIX = 'PRAYER9_'
REQUIRED = ('YOUTUBE_CLIENT_ID', 'YOUTUBE_CLIENT_SECRET', 'YOUTUBE_REFRESH_TOKEN', 'YOUTUBE_CHANNEL_ID')
UPLOAD_SCOPES = frozenset({
    'https://www.googleapis.com/auth/youtube',
    'https://www.googleapis.com/auth/youtube.upload',
    'https://www.googleapis.com/auth/youtubepartner',
})
CHANNEL_ID = re.compile(r'UC[A-Za-z0-9_-]{22}\Z')


class PreflightError(Exception):
    """A safe, non-secret-bearing failure message."""


def _request_json(request: urllib.request.Request) -> dict:
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            value = json.load(response)
    except urllib.error.HTTPError as exc:
        raise PreflightError(f'Read-only OAuth or channel lookup failed (HTTP {exc.code}).') from None
    except Exception:
        raise PreflightError('Read-only OAuth or channel lookup failed; details withheld.') from None
    if not isinstance(value, dict):
        raise PreflightError('Unexpected API response.')
    return value


def check(env: Mapping[str, str], request_json: Callable = _request_json) -> dict:
    """Check target identity and returned OAuth scopes; perform no writes."""
    values = {key: str(env.get(PREFIX + key, '')).strip() for key in REQUIRED}
    missing = [PREFIX + key for key, value in values.items() if not value]
    if missing:
        raise PreflightError('Missing required fields: ' + ', '.join(missing))
    expected = values['YOUTUBE_CHANNEL_ID']
    if not CHANNEL_ID.fullmatch(expected):
        raise PreflightError('Configured channel ID has an invalid format.')
    token_request = urllib.request.Request(
        'https://oauth2.googleapis.com/token',
        data=urllib.parse.urlencode({
            'client_id': values['YOUTUBE_CLIENT_ID'],
            'client_secret': values['YOUTUBE_CLIENT_SECRET'],
            'refresh_token': values['YOUTUBE_REFRESH_TOKEN'],
            'grant_type': 'refresh_token',
        }).encode(),
        method='POST',
    )
    token_response = request_json(token_request)
    token = token_response.get('access_token')
    scopes = set(str(token_response.get('scope') or '').split())
    if not isinstance(token, str) or not token:
        raise PreflightError('OAuth response omitted an access token.')
    if not scopes:
        raise PreflightError('OAuth response did not disclose scopes; upload capability is unverified.')
    if not scopes.intersection(UPLOAD_SCOPES):
        raise PreflightError('OAuth response did not include an upload-capable scope.')
    channel_request = urllib.request.Request(
        'https://www.googleapis.com/youtube/v3/channels?part=id&mine=true',
        headers={'Authorization': 'Bearer ' + token}, method='GET',
    )
    channel_response = request_json(channel_request)
    channels = channel_response.get('items')
    if not isinstance(channels, list) or len(channels) != 1 or not isinstance(channels[0], dict):
        raise PreflightError('Authorized channel lookup was missing or ambiguous.')
    if channels[0].get('id') != expected:
        raise PreflightError('Authorized channel does not match the configured expected channel.')
    return {'identity': 'matched', 'upload_scope': 'present', 'channel': 'prayer9'}


def main() -> int:
    try:
        result = check(os.environ)
    except PreflightError as exc:
        print(f'Preflight failed: {exc}')
        return 1
    except Exception:
        # Never serialize request, response, token, or exception details.
        print('Preflight failed unexpectedly; details withheld.')
        return 1
    print(f"{result['channel']}: authorized identity matched and an upload-capable scope was returned.")
    print('No upload, TTS, generation, quota, billing, or thumbnail permission was tested; the channel remains disabled.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
