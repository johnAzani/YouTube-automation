#!/usr/bin/env python3
"""Report the real long-form runway of content/queue/ in minutes of narration.

`pipeline/prayer_pipeline.py` refuses to render any prayer script under
MIN_LONGFORM_WORDS (850), which is the first length that fills five minutes at
Charon's measured pace — the old 650-word figure was four minutes and could never
have rendered.
A queue full of 250-word scripts therefore looks like a thirty-night runway
while actually failing closed at render time. This audit makes that visible
without changing queue state.

Usage:
    python scripts/audit_runway.py            # table + summary
    python scripts/audit_runway.py --json     # machine-readable
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.script_doc import MIN_LONGFORM_WORDS, parse_script  # noqa: E402

# Must match the gate in pipeline/prayer_pipeline.py.
MIN_WORDS = MIN_LONGFORM_WORDS
# Measured Charon delivery is 2.6 words/second in the approved renderer.
WORDS_PER_SECOND = 2.6


def audit(queue: Path) -> list[dict]:
    rows = []
    for path in sorted(queue.glob('*.md')):
        try:
            doc = parse_script(path)
        except Exception as exc:  # noqa: BLE001 - reported, not raised
            rows.append({'file': path.name, 'error': f'{type(exc).__name__}: {exc}'})
            continue
        words = doc.word_count
        rows.append({
            'file': path.name,
            'id': doc.id,
            'status': doc.meta.get('status'),
            'format': doc.format,
            'words': words,
            'minutes': round(words / WORDS_PER_SECOND / 60, 1),
            'scenes': len(doc.scenes),
            'full_length_ok': words >= MIN_WORDS,
        })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--queue', type=Path, default=ROOT / 'content/queue')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()

    rows = audit(args.queue)
    if args.json:
        print(json.dumps(rows, indent=2))
        return 1 if any(r.get('error') or r.get('full_length_ok') is False
                        for r in rows) else 0

    ok = [r for r in rows if r.get('full_length_ok')]
    short = [r for r in rows if r.get('full_length_ok') is False]
    broken = [r for r in rows if r.get('error')]
    print(f"{'id':6}{'status':12}{'format':10}{'words':>6}{'min':>6}  full-length")
    for r in rows:
        if r.get('error'):
            print(f"{r['file']:<30} ERROR {r['error']}")
            continue
        flag = 'yes' if r['full_length_ok'] else 'NO'
        print(f"{r['id']:6}{str(r['status']):12}{r['format']:10}{r['words']:>6}"
              f"{r['minutes']:>6}  {flag}")
    approved_ok = [r for r in ok if str(r.get('status')).startswith('approved')]
    total = sum(r['minutes'] for r in approved_ok)
    print(f"\n{len(rows)} scripts, {len(ok)} above the {MIN_WORDS}-word "
          f"(~{MIN_WORDS / WORDS_PER_SECOND / 60:.1f} min) full-length floor, "
          f"{len(short)} below, {len(broken)} unreadable.")
    print(f"Publishable approved long-form runway: {len(approved_ok)} jobs / "
          f"{total:.1f} minutes of narration.")
    return 1 if (short or broken) else 0


if __name__ == '__main__':
    raise SystemExit(main())
