#!/usr/bin/env python3
"""Read-only Gemini model-list probe for the staged tenth channel."""
from __future__ import annotations

import os
import sys
import urllib.request
from collections.abc import Mapping
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import praise_garden_gemini_preflight as shared


def check(env: Mapping[str, str], opener: Callable = urllib.request.urlopen) -> None:
    key = str(env.get('PRAYER10_GEMINI_API_KEY', '')).strip()
    if not key:
        raise shared.PreflightError('PRAYER10_GEMINI_API_KEY is missing.')
    # Translate only the target key to the shared read-only implementation.
    shared.check({'PRAYER9_GEMINI_API_KEY': key}, opener)


def main() -> int:
    try:
        check(os.environ)
    except shared.PreflightError as exc:
        print(f'Gemini preflight failed: {exc}')
        return 1
    except Exception:
        print('Gemini preflight failed unexpectedly; details withheld.')
        return 1
    print('PRAYER10 Gemini key successfully listed model metadata (read-only).')
    print('Generation, TTS, quota, billing, and project ownership were not verified; the channel remains disabled.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
