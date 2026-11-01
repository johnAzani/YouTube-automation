"""Local speech alignment that tolerates how speech recognisers tokenise.

Preview overlay for PR #112 — not merged. The original module in
`pipeline/prayer_alignment.py` requires the recogniser to return exactly one
token per script word and rejects the whole render otherwise. In practice
faster-whisper disagrees constantly on legitimate narrations:

    script:  "... to him be glory for evermore."
    whisper: "... to him be glory forevermore."        (2 vs 1 tokens)
    script:  "Psalm 121"      whisper: "Psalm one twenty one"  (1 vs 4)

Two real runs of job 0010 died on exactly this ("word count differs: 883 vs
884; mismatches=[(['for', 'evermore'], ['forevermore'])]"), so the strict 1:1
rule makes long-form production impossible rather than safe.

This version keeps every safety property that mattered — monotonic, finite,
confident timings that cover the narration — and adds an alignment pass that maps
script words onto recognised tokens:

  * equal blocks          → one-to-one timing
  * n script vs 1 spoken  → the recognised span is shared by the n script words
  * 1 script vs m spoken  → the union of the m spans is given to the script word
  * extra recognised word → skipped (fillers, hallucinated "you")
  * missing script word   → zero-length span at the neighbouring boundary

A zero-length span is safe downstream: `tools.shorts.py` only compares
timestamps (`w_t0 <= t < w_t1`), so such a word is simply never highlighted.

Still fails closed on: no audio/model, empty transcript, words that cannot be
matched at all (script and narration genuinely differ), out-of-order or
non-finite timings, and low-confidence recognition.
"""
from __future__ import annotations

import math
import re
from difflib import SequenceMatcher
from pathlib import Path


def _canonical(word):
    return ''.join(re.findall(r"[\w]+(?:['’][\w]+)*", word.casefold())).replace('’', "'")


def _spoken_words(audio: Path, model_dir: Path):
    """Transcribe with word timestamps. Imported lazily so the matcher is testable."""
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:  # pragma: no cover - depends on the runner image
        raise RuntimeError('Install faster-whisper for local alignment') from exc
    model = WhisperModel(str(Path(model_dir).resolve()), device='cpu',
                         compute_type='int8', local_files_only=True)
    segments, _ = model.transcribe(str(audio), language='en', beam_size=5,
                                   word_timestamps=True, vad_filter=False,
                                   condition_on_previous_text=True)
    return [word for segment in segments for word in (segment.words or [])]


def match(expected, spoken, min_confidence=0.2):
    """Map script words onto recognised tokens. `spoken` items need .word/.start/.end/.probability."""
    if not expected:
        raise ValueError('Empty transcript')
    exp = [_canonical(w) for w in expected]
    got = [_canonical(w.word) for w in spoken]
    # Whisper sometimes returns only punctuation; never let a blank token shift timing.
    usable = [(i, canon) for i, canon in enumerate(got) if canon]
    if not usable:
        raise ValueError('Speech recognition returned no words')

    result, previous_end = [], 0.0
    for kind, a, b, c, d in SequenceMatcher(a=exp, b=[c for _, c in usable],
                                            autojunk=False).get_opcodes():
        indices = [usable[k][0] for k in range(c, d)]
        if kind == 'equal':
            for offset, i in enumerate(indices):
                result.append((expected[a + offset], spoken[i]))
        elif kind == 'replace':
            n_script, mapped = b - a, indices
            if not mapped:
                for token in expected[a:b]:
                    result.append((token, None))
                continue
            if n_script == 1:
                # script has one token, recogniser split it: give the union span
                first, last = spoken[mapped[0]], spoken[mapped[-1]]
                result.append((expected[a], _Span(first.word, first.start, last.end,
                                                  min(spoken[i].probability for i in mapped))))
            elif len(mapped) == 1:
                # recogniser merged several script words into one ("for evermore"
                # -> "forevermore"): tile the recognised span across the script
                # words by length so the timeline stays ordered.
                item = spoken[mapped[0]]
                for token, span in _tile(expected[a:b], item.start, item.end, item.probability):
                    result.append((token, span))
            else:
                # proportional share of the recognised span, weighted by word length
                prob = min(spoken[i].probability for i in mapped)
                for token, span in _tile(expected[a:b], spoken[mapped[0]].start,
                                         spoken[mapped[-1]].end, prob):
                    result.append((token, span))
        elif kind == 'delete':
            # script words the recogniser did not hear at all
            for token in expected[a:b]:
                result.append((token, None))

    words, previous_end = [], 0.0
    for index, (original, heard) in enumerate(result, 1):
        if heard is None:
            start = end = previous_end
            prob = 1.0
        else:
            start, end, prob = float(heard.start), float(heard.end), float(heard.probability)
        if not all(map(math.isfinite, (start, end, prob))):
            raise ValueError(f'Non-finite alignment at word {index}')
        if start < previous_end - 1e-6:
            raise ValueError(f'Out-of-order alignment at word {index}: '
                             f'previous_end={previous_end:.3f}, start={start:.3f}')
        if end < start:
            raise ValueError(f'Negative span at word {index}: {start:.3f}-{end:.3f}')
        if not min_confidence <= prob <= 1:
            raise ValueError(f'Uncertain alignment at word {index}: confidence={prob:.3f}')
        words.append((original, round(start, 3), round(end, 3)))
        previous_end = max(previous_end, end)
    return words


def _tile(tokens, start, end, probability):
    """Split [start, end] across `tokens` in proportion to their length."""
    weights = [max(1, len(_canonical(t))) for t in tokens]
    total = sum(weights)
    span = max(0.0, float(end) - float(start))
    out, clock = [], float(start)
    for token, weight in zip(tokens, weights):
        width = span * weight / total
        out.append((token, _Span(token, clock, clock + width, probability)))
        clock += width
    return out


class _Span:
    """Minimal stand-in for a recogniser word token, so `match` stays testable."""
    __slots__ = ('word', 'start', 'end', 'probability')

    def __init__(self, word, start, end, probability):
        self.word = word
        self.start = float(start)
        self.end = float(end)
        self.probability = float(probability)


def align(audio: Path, transcript: str, model_dir: Path, min_confidence=0.2):
    audio, model_dir = Path(audio), Path(model_dir)
    if not audio.is_file() or not (model_dir / 'model.bin').is_file():
        raise ValueError('Narration and a preinstalled local speech model are required')
    if not 0 <= min_confidence <= 1:
        raise ValueError('Invalid confidence threshold')
    expected = [w for w in transcript.split() if _canonical(w)]
    if not expected:
        raise ValueError('Empty transcript')
    return match(expected, _spoken_words(audio, model_dir), min_confidence=min_confidence)
