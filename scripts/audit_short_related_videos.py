#!/usr/bin/env python3
"""Suggest same-channel Short-to-long-form matches from published receipts.

Read-only: no YouTube calls or writes. These are candidates, not verified live
visibility, links, rights, or YPP eligibility. A human must review each in Studio.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.gemini_brain import _BOOK_RE, short_key_for_doc
from pipeline.script_doc import parse_script

VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}\Z")


def _receipt(path: Path) -> dict | None:
    doc = parse_script(path)
    meta = doc.meta
    video_id = str(meta.get('youtube_video_id') or '').strip()
    # Conflicting, missing, private, deleted, or rejected receipts are not candidates.
    visibility = [str(meta[key]).strip().lower() for key in ('privacy_status', 'privacy')
                  if meta.get(key) is not None and str(meta[key]).strip()]
    if (not VIDEO_ID.fullmatch(video_id) or not visibility or any(v != 'public' for v in visibility)
            or str(meta.get('youtube_status', '')).lower() == 'deleted_or_missing'
            or str(meta.get('youtube_upload_status', '')).lower() in {'rejected', 'failed', 'deleted'}):
        return None
    # Do not match on generic title fallbacks (e.g., 'prayer') as if scripture matched.
    if not _BOOK_RE.search(doc.title or ''):
        return None
    kind = str(meta.get('format', '')).strip().lower()
    if kind and kind not in {'short', 'longform'}:
        return None
    is_short = kind == 'short' or (not kind and path.name.startswith('short-'))
    return {'channel': doc.channel, 'key': short_key_for_doc(doc), 'video_id': video_id,
            'title': doc.title, 'is_short': is_short}


def find_candidates(published_dir: Path) -> list[dict]:
    """Return exact scripture-key matches; ambiguous candidates remain explicit."""
    grouped: dict[tuple[str, str], dict[str, list[dict]]] = defaultdict(lambda: {'shorts': [], 'longforms': []})
    for path in sorted(published_dir.glob('*.md')):
        try:
            row = _receipt(path)
        except Exception as exc:
            print(f'Warning: could not parse receipt {path.name}: {type(exc).__name__}', file=sys.stderr)
            continue
        if row is None:
            continue
        key = (row['channel'], row['key'])
        group = grouped[key]['shorts' if row['is_short'] else 'longforms']
        # Duplicated receipts of the same video must not create ambiguity.
        if all(existing['video_id'] != row['video_id'] for existing in group):
            group.append(row)
    results = []
    for (channel, key), group in sorted(grouped.items()):
        if not group['shorts'] or not group['longforms']:
            continue
        for short in group['shorts']:
            candidates = [v for v in group['longforms'] if v['video_id'] != short['video_id']]
            if candidates:
                results.append({'channel': channel, 'scripture_key': key, 'short': short,
                                'longforms': candidates, 'ambiguous': len(candidates) != 1})
    return results


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--published-dir', type=Path, default=ROOT / 'content' / 'published')
    args = ap.parse_args()
    if not args.published_dir.is_dir():
        ap.error('published directory does not exist')
    print('Candidate pairs from receipts only; verify live status, relevance and any existing Related Video in Studio.')
    print('Short description/comment URLs are not clickable in the Shorts player. No changes were made.\n')
    for match in find_candidates(args.published_dir):
        s = match['short']
        print(f"{match['channel']} | {match['scripture_key']}" + (' | REVIEW MULTIPLE MATCHES' if match['ambiguous'] else ''))
        print(f"  Short: {s['title']} — https://www.youtube.com/shorts/{s['video_id']}")
        for video in match['longforms']:
            print(f"  Candidate: {video['title']} — https://youtu.be/{video['video_id']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
