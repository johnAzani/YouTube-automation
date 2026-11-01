"""Offline approved-style draft from existing Charon narration, never uploads."""
from __future__ import annotations
import argparse
from pathlib import Path
from .prayer_alignment import align
from .prayer_visuals import render
from .script_doc import parse_script
from .tts import _probe_duration


def build(script: Path, narration: Path, model: Path, assets: list[Path], output: Path):
    doc = parse_script(script)
    if doc.format != 'longform' or not any(x in str(doc.meta.get('niche', '')).lower() for x in ('faith', 'prayer', 'scripture', 'devotional')):
        raise ValueError('Expected a long-form prayer')
    if doc.voice != 'Charon':
        raise ValueError('Only Charon narration is permitted')
    if not doc.scenes or len(assets) != len(doc.scenes):
        raise ValueError('Provide one verified source asset per scene')
    duration = _probe_duration(narration)
    if duration is None or duration < 300:
        raise ValueError('Narration must last at least five minutes')
    words = align(narration, doc.full_narration, model)
    boundaries = [0.0]
    count = 0
    for scene in doc.scenes[:-1]:
        count += len(scene.narration.split())
        if count <= 0 or count >= len(words):
            raise ValueError('Could not align scene boundaries')
        boundaries.append(words[count - 1][2])
    boundaries.append(duration)
    durations = [b - a for a, b in zip(boundaries, boundaries[1:])]
    if any(d <= 0 for d in durations):
        raise ValueError('Invalid scene durations')
    return render(narration, list(zip(assets, durations)), words, duration,
                  output, timing_source='measured')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script', type=Path, required=True)
    parser.add_argument('--narration', type=Path, required=True, help='Existing Gemini Charon audio')
    parser.add_argument('--model', type=Path, required=True, help='Locally installed faster-whisper model')
    parser.add_argument('--scene', type=Path, action='append', required=True, help='Licensed asset, one per scene')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(build(args.script, args.narration, args.model, args.scene, args.output))


if __name__ == '__main__':
    main()
