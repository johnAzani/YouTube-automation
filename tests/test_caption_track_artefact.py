"""The caption track: what it costs, what it looks like, and what is left of it.

A caption track is the most expensive call this pipeline makes — 400 units, eight
comments, 85% of everything the shared pool has spent — and it is the only one
whose artefact is thrown away: the SRT is written into a gitignored ``output/``
directory and uploaded on the same run. These tests hold the two things that
survive: the guarantee the generator makes about line width, and the fingerprint
the receipt now carries.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from pipeline import captions as cap
from pipeline import short_release as sr

REPO = Path(__file__).resolve().parents[1]
WORDS = sorted((REPO / "assets" / "deepdive").glob("words-*.json"))


def _cues(srt: str) -> list[list[str]]:
    blocks = [b for b in srt.strip().split("\n\n") if b.strip()]
    return [b.split("\n")[2:] for b in blocks]


@pytest.mark.parametrize("path", WORDS, ids=lambda p: p.stem)
def test_no_line_is_wider_than_forty_characters(path):
    """The docstring claims <= 40 chars/line. At the old 80-character cue budget
    23 of 82 cues broke it (worst 44) because a word boundary rarely falls at 40."""
    rows = json.loads(path.read_text(encoding="utf-8"))
    words = [(str(word), float(start), float(end)) for start, end, word in rows]
    srt = cap.build_srt_from_aligned_words(words, narration_text="", duration=words[-1][2])
    lines = [line for cue in _cues(srt) for line in cue]
    assert lines, "the generator produced no cues"
    assert max(len(line) for line in lines) <= 40, max(lines, key=len)


@pytest.mark.parametrize("path", WORDS, ids=lambda p: p.stem)
def test_a_cue_never_exceeds_two_lines_inside_the_budget(path):
    rows = json.loads(path.read_text(encoding="utf-8"))
    words = [(str(word), float(start), float(end)) for start, end, word in rows]
    srt = cap.build_srt_from_aligned_words(words, narration_text="", duration=words[-1][2])
    for cue in _cues(srt):
        assert 1 <= len(cue) <= 2
        assert len(" ".join(cue)) <= cap.MAX_CUE_CHARS


def test_the_fingerprint_names_the_track_that_was_sent(tmp_path):
    srt = tmp_path / "captions.en.srt"
    srt.write_text("1\n00:00:01,000 --> 00:00:02,000\nOne cue.\n\n"
                   "2\n00:00:03,000 --> 00:00:04,000\nAnd another.\n", encoding="utf-8")
    cues, digest = cap.caption_fingerprint(srt)
    assert cues == 2 and len(digest) == 12 and all(c in "0123456789abcdef" for c in digest)
    again = cap.caption_fingerprint(srt)
    assert again == (cues, digest), "the same bytes give the same fingerprint"
    srt.write_text(srt.read_text(encoding="utf-8").replace("another", "ANOTHER"), encoding="utf-8")
    assert cap.caption_fingerprint(srt)[1] != digest


def _timings(directory: Path, key: str) -> None:
    narration = ("Before you sleep tonight, hear this. The LORD is my shepherd; I shall not want. "
                 "He maketh me to lie down in green pastures. Rest now, and let him keep you.")
    rows, clock = [], 0.4
    for word in narration.split():
        token = sr._clean_word_token(word)
        if token:
            rows.append([round(clock, 2), round(clock + 0.3, 2), token])
            clock += 0.42
    (directory / f"words-{key}.json").write_text(json.dumps(rows), encoding="utf-8")
    (directory / f"words-{key}.alignment.json").write_text("{}", encoding="utf-8")


@pytest.fixture()
def youtube():
    client = MagicMock()
    client.captions.return_value.insert.return_value.execute.return_value = {"id": "cap-1"}
    return client


def test_a_short_records_what_its_track_contained(tmp_path, youtube, monkeypatch):
    monkeypatch.delenv("SHORT_CAPTIONS", raising=False)
    _timings(tmp_path, "short-psalm23v1")
    record: dict = {}
    status = sr.upload_short_captions("VIDEO000001", "short-psalm23v1", youtube=youtube,
                                      audio_dir=tmp_path, out_dir=tmp_path / "out",
                                      record=record)
    assert status == "ok"
    srt = tmp_path / "out" / "captions.en.srt"
    assert record["caption_cues"] == len(_cues(srt.read_text(encoding="utf-8")))
    assert record["caption_sha256"] == cap.caption_fingerprint(srt)[1]


def test_a_skipped_track_records_nothing(tmp_path, youtube, monkeypatch):
    monkeypatch.delenv("SHORT_CAPTIONS", raising=False)
    record: dict = {}
    status = sr.upload_short_captions("VIDEO000001", "short-psalm23v1", youtube=youtube,
                                      audio_dir=tmp_path, out_dir=tmp_path / "out",
                                      record=record)
    assert status.startswith("skipped")
    assert record == {}
