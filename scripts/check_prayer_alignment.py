#!/usr/bin/env python3
"""Compare offline alignment against the existing approved Psalm 91 recording.

No Gemini API or YouTube credentials are used. This diagnostic deliberately fails
if speech recognition disagrees with the script or timing drifts from the
existing word-timing reference; it does not enable publishing.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline.prayer_alignment import align


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--max-error', type=float, default=0.4)
    args = parser.parse_args()
    reference = json.loads((ROOT/'assets/deepdive/words-short-psalm91.json').read_text())
    audio = ROOT/'assets/deepdive/short-prayer-psalm91.mp3'
    words = align(audio, ' '.join(row[2] for row in reference), args.model)
    worst = max(max(abs(start - ref[0]), abs(end - ref[1])) for (_, start, end), ref in zip(words, reference))
    segment3 = words[39:52]
    worst3 = max(max(abs(start - ref[0]), abs(end - ref[1])) for (_, start, end), ref in zip(segment3, reference[39:52]))
    print(f'Aligned {len(words)} words; maximum reference difference {worst:.3f}s; segment 3 {worst3:.3f}s')
    if worst > args.max_error:
        raise SystemExit('Alignment exceeds timing tolerance; publishing must remain blocked')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
