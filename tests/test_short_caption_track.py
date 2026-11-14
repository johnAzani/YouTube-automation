"""A published Short gets a caption track built from the words it was rendered with."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from pipeline import short_release as sr

NARRATION = ("Before you sleep tonight, hear this. The LORD is my shepherd; I shall not want. "
             "He maketh me to lie down in green pastures. Rest now, and let him keep you.")


def _timings(directory: Path, key: str, *, aligned: bool = True) -> None:
    rows, clock = [], 0.4
    for word in NARRATION.split():
        token = sr._clean_word_token(word)
        if token:
            rows.append([round(clock, 2), round(clock + 0.3, 2), token])
            clock += 0.42
    (directory / f"words-{key}.json").write_text(json.dumps(rows), encoding="utf-8")
    if aligned:
        (directory / f"words-{key}.alignment.json").write_text("{}", encoding="utf-8")


@pytest.fixture()
def youtube():
    client = MagicMock()
    client.captions.return_value.insert.return_value.execute.return_value = {"id": "cap-1"}
    return client


def _upload(tmp_path, youtube, key="short-psalm23v1"):
    return sr.upload_short_captions("VIDEO000001", key, youtube=youtube,
                                    audio_dir=tmp_path, out_dir=tmp_path / "out")


def test_the_track_carries_the_spoken_words_with_their_timings(tmp_path, youtube, monkeypatch):
    monkeypatch.delenv("SHORT_CAPTIONS", raising=False)
    _timings(tmp_path, "short-psalm23v1")
    assert _upload(tmp_path, youtube) == "ok"

    body = youtube.captions.return_value.insert.call_args.kwargs["body"]["snippet"]
    assert body == {"videoId": "VIDEO000001", "language": "en", "name": "", "isDraft": False}

    srt = (tmp_path / "out" / "captions.en.srt").read_text(encoding="utf-8")
    spoken = " ".join(line for line in srt.splitlines()
                      if line and not line.isdigit() and "-->" not in line)
    assert [sr._clean_word_token(w) for w in spoken.split()] == \
        [sr._clean_word_token(w) for w in NARRATION.split()], "every word, in order, once"
    assert srt.startswith("1\n00:00:00,400 --> "), "the first cue starts where the first word is spoken"
    stamps = [line.split(" --> ") for line in srt.splitlines() if "-->" in line]
    assert all(start < end for start, end in stamps)
    assert [s for s, _ in stamps] == sorted(s for s, _ in stamps)


def test_estimated_timings_are_never_published_as_captions(tmp_path, youtube, monkeypatch):
    monkeypatch.delenv("SHORT_CAPTIONS", raising=False)
    _timings(tmp_path, "short-psalm23v1", aligned=False)
    assert _upload(tmp_path, youtube) == "skipped: no verified word timings"
    youtube.captions.return_value.insert.assert_not_called()


def test_a_refusal_from_youtube_does_not_raise(tmp_path, youtube, monkeypatch):
    monkeypatch.delenv("SHORT_CAPTIONS", raising=False)
    _timings(tmp_path, "short-psalm23v1")
    youtube.captions.return_value.insert.return_value.execute.side_effect = RuntimeError("quotaExceeded")
    assert _upload(tmp_path, youtube).startswith("skipped")


def test_a_broken_timings_file_does_not_raise(tmp_path, youtube, monkeypatch):
    monkeypatch.delenv("SHORT_CAPTIONS", raising=False)
    (tmp_path / "words-short-psalm23v1.json").write_text("{not json", encoding="utf-8")
    (tmp_path / "words-short-psalm23v1.alignment.json").write_text("{}", encoding="utf-8")
    assert _upload(tmp_path, youtube).startswith("skipped")
    youtube.captions.return_value.insert.assert_not_called()


def test_it_can_be_switched_off(tmp_path, youtube, monkeypatch):
    monkeypatch.setenv("SHORT_CAPTIONS", "0")
    _timings(tmp_path, "short-psalm23v1")
    assert _upload(tmp_path, youtube) == "skipped: switched off"
    youtube.captions.return_value.insert.assert_not_called()


def test_the_release_uploads_the_track_last_and_records_it():
    source = Path(sr.__file__).read_text(encoding="utf-8")
    release = source[source.index("def run_short_release("):]
    assert release.index("apply_shorts_thumbnail(up.video_id") < release.index("upload_short_captions(up.video_id")
    assert release.index("audit_channel_videos(") < release.index("upload_short_captions(up.video_id")
    assert "captions=caption_status" in release
    assert "caption_track:" in source
