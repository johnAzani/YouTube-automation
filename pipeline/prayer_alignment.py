"""Local speech alignment. Missing models and uncertain transcripts fail closed."""
from __future__ import annotations
import math
import re
from pathlib import Path


def _canonical(word):
    return ''.join(re.findall(r"[\w]+(?:['’][\w]+)*", word.casefold())).replace('’', "'")


def align(audio: Path, transcript: str, model_dir: Path, min_confidence=0.6):
    audio, model_dir = Path(audio), Path(model_dir)
    if not audio.is_file() or not (model_dir / 'model.bin').is_file():
        raise ValueError('Narration and a preinstalled local speech model are required')
    if not 0 <= min_confidence <= 1:
        raise ValueError('Invalid confidence threshold')
    expected = [w for w in transcript.split() if _canonical(w)]
    if not expected:
        raise ValueError('Empty transcript')
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError('Install faster-whisper for local alignment') from exc
    model = WhisperModel(str(model_dir.resolve()), device='cpu', compute_type='int8', local_files_only=True)
    segments, _ = model.transcribe(str(audio), language='en', beam_size=5,
        word_timestamps=True, vad_filter=False, condition_on_previous_text=True)
    spoken = [word for segment in segments for word in (segment.words or [])]
    if len(spoken) != len(expected):
        from difflib import SequenceMatcher
        exp = [_canonical(w) for w in expected]
        got = [_canonical(w.word) for w in spoken]
        differences = [(exp[a:b], got[c:d]) for kind, a, b, c, d in SequenceMatcher(a=exp, b=got, autojunk=False).get_opcodes() if kind != 'equal']
        raise ValueError(f'Speech alignment word count differs: {len(spoken)} vs {len(expected)}; mismatches={differences[:4]}')
    result, last_end = [], 0.0
    for i, (original, actual) in enumerate(zip(expected, spoken), 1):
        if _canonical(original) != _canonical(actual.word):
            raise ValueError(f'Speech alignment transcript mismatch at word {i}')
        start, end, prob = float(actual.start), float(actual.end), float(actual.probability)
        if not all(map(math.isfinite, (start, end, prob))) or start < last_end or end <= start or not min_confidence <= prob <= 1:
            raise ValueError(f'Invalid or uncertain speech alignment at word {i}')
        result.append((original, start, end))
        last_end = end
    return result
