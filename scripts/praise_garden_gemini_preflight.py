#!/usr/bin/env python3
"""Check the staged channel's Gemini key with a model-list request only.

The check does not generate content, establish project ownership, verify billing,
confirm quota, or enable the channel. Never print credentials or response bodies.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Mapping
from typing import Callable


class PreflightError(Exception):
    """Sanitized failure that must not contain credentials or response bodies."""


def check(env: Mapping[str, str], opener: Callable = urllib.request.urlopen) -> None:
    key = str(env.get('PRAYER9_GEMINI_API_KEY', '')).strip()
    if not key:
        raise PreflightError('PRAYER9_GEMINI_API_KEY is missing.')
    req = urllib.request.Request(
        'https://generativelanguage.googleapis.com/v1beta/models?pageSize=1',
        headers={'x-goog-api-key': key}, method='GET',
    )
    try:
        with opener(req, timeout=20) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        raise PreflightError(f'Model listing failed (HTTP {exc.code}); response withheld.') from None
    except Exception:
        raise PreflightError('Model listing failed; details withheld.') from None
    if not isinstance(data, dict) or not isinstance(data.get('models'), list) or not data['models']:
        raise PreflightError('Model listing returned no models or an unexpected response.')


def main() -> int:
    try:
        check(os.environ)
    except PreflightError as exc:
        print(f'Gemini preflight failed: {exc}')
        return 1
    except Exception:
        print('Gemini preflight failed unexpectedly; details withheld.')
        return 1
    print('PRAYER9 Gemini key successfully listed model metadata (read-only).')
    print('Generation, TTS, quota, billing, and project ownership were not verified; the channel remains disabled.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
