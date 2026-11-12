#!/usr/bin/env python3
"""Read-only staged OAuth preflight for the proposed tenth channel.

Reads only PRAYER10_* variables. This script is not wired into a workflow and
cannot activate the channel or make any YouTube writes.
"""
from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import praise_garden_preflight as shared


def check(env: Mapping[str, str], request_json: Callable = shared._request_json) -> dict:
    missing = [f'PRAYER10_{name}' for name in shared.REQUIRED
               if not str(env.get(f'PRAYER10_{name}', '')).strip()]
    if missing:
        raise shared.PreflightError('Missing required fields: ' + ', '.join(missing))
    # Translate only the target's own values into the shared checker's interface;
    # never consult another channel's secrets or default credentials.
    isolated = {f'PRAYER9_{name}': env[f'PRAYER10_{name}'] for name in shared.REQUIRED}
    shared.check(isolated, request_json)
    return {'identity': 'matched', 'upload_scope': 'present', 'channel': 'prayer10'}


def main() -> int:
    try:
        check(os.environ)
    except shared.PreflightError as exc:
        print(f'Preflight failed: {exc}')
        return 1
    except Exception:
        print('Preflight failed unexpectedly; details withheld.')
        return 1
    print('prayer10: authorized identity matched and an upload-capable scope was returned.')
    print('No upload, TTS, generation, quota, billing, or thumbnail permission was tested; the channel remains disabled.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
