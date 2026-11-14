"""A Short whose spoken take fails alignment must not block its channel.

13 November 2026: seven channels each had the Short at the head of their queue
fail "Short speech alignment unavailable or incomplete" in two production runs
five hours apart. The rejected audio was saved to the Actions cache, restored by
the next run, still looked valid (same text, same checksum) and was refused
again. Shorts release in order, so those channels released none.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest
import yaml

from pipeline import short_release as sr
from pipeline.gemini_tts import DEFAULT_MODEL

KEY = "short-test"
TEXT = "A fresh prayer"


@pytest.fixture()
def studio(tmp_path, monkeypatch):
    """A repo root with a spec, a speech model file and a counting narrator."""
    monkeypatch.setattr(sr, "REPO_ROOT", tmp_path)
    (tmp_path / "assets" / "deepdive").mkdir(parents=True)
    model = tmp_path / "output" / "alignment-model"
    model.mkdir(parents=True)
    (model / "model.bin").write_bytes(b"weights")
    spec_file = tmp_path / "spec.json"
    spec_file.write_text("{}")
    takes = []

    def narrator(text, path):
        takes.append(text)
        Path(path).write_bytes(f"charon take {len(takes)}".encode())
        return DEFAULT_MODEL

    monkeypatch.setattr(sr, "_synthesise_narration", narrator)
    spec = SimpleNamespace(narration_text=TEXT, words=3)
    with mock.patch("pipeline.short_script.spec_path", return_value=spec_file), \
         mock.patch("pipeline.short_script.load_spec", return_value=spec):
        yield SimpleNamespace(root=tmp_path, takes=takes,
                              files=sr._short_take_files(KEY), model=model)


GOOD = [("A", 0.0, 0.2), ("fresh", 0.2, 0.6), ("prayer", 0.6, 1.1)]


def _aligner(*outcomes):
    """align() that returns or raises each outcome in turn."""
    queue = list(outcomes)

    def align(audio, text, model_dir):
        outcome = queue.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome
    return align


def test_good_take_is_kept_and_reused(studio):
    with mock.patch("pipeline.prayer_alignment.align", _aligner(GOOD)):
        sr._ensure_narration(KEY)
        sr._ensure_narration(KEY)          # second call: cached audio and timings
    assert len(studio.takes) == 1
    assert all(p.is_file() for p in studio.files)


def test_saved_take_that_fails_alignment_is_replaced_in_the_same_run(studio):
    # Run 1 leaves a take behind that alignment will reject from now on.
    with mock.patch("pipeline.prayer_alignment.align", _aligner(GOOD)):
        sr._ensure_narration(KEY)
    studio.files[2].unlink()               # timings lost; the audio is "restored from cache"
    studio.files[3].unlink()
    first_audio = studio.files[0].read_bytes()

    with mock.patch("pipeline.prayer_alignment.align",
                    _aligner(ValueError("word 12 'selah' was not spoken"), GOOD)):
        sr._ensure_narration(KEY)

    assert len(studio.takes) == 2, "exactly one fresh take, no more"
    assert studio.files[0].read_bytes() != first_audio
    assert all(p.is_file() for p in studio.files)


def test_fresh_take_that_fails_is_discarded_without_a_second_request(studio):
    with mock.patch("pipeline.prayer_alignment.align", _aligner(ValueError("mismatch"))):
        with pytest.raises(sr.ShortAlignmentError, match="mismatch"):
            sr._ensure_narration(KEY)
    assert len(studio.takes) == 1
    assert not any(p.exists() for p in studio.files), "a rejected take must not reach the cache"


def test_retry_that_also_fails_leaves_nothing_behind(studio):
    with mock.patch("pipeline.prayer_alignment.align", _aligner(GOOD)):
        sr._ensure_narration(KEY)
    studio.files[2].unlink()
    studio.files[3].unlink()
    with mock.patch("pipeline.prayer_alignment.align",
                    _aligner(ValueError("bad"), ValueError("still bad"))):
        with pytest.raises(sr.ShortAlignmentError, match="still bad"):
            sr._ensure_narration(KEY)
    assert len(studio.takes) == 2
    assert not any(p.exists() for p in studio.files)


def test_missing_speech_model_never_costs_the_audio(studio):
    (studio.model / "model.bin").unlink()
    with mock.patch("pipeline.prayer_alignment.align",
                    _aligner(ValueError("Narration and a preinstalled local speech model are required"))):
        with pytest.raises(RuntimeError) as caught:
            sr._ensure_narration(KEY)
    assert not isinstance(caught.value, sr.ShortAlignmentError)
    assert studio.files[0].is_file() and studio.files[1].is_file()
    assert len(studio.takes) == 1


def test_a_crash_in_the_aligner_is_not_blamed_on_the_take(studio):
    with mock.patch("pipeline.prayer_alignment.align", _aligner(OSError("disk"))):
        with pytest.raises(RuntimeError) as caught:
            sr._ensure_narration(KEY)
    assert not isinstance(caught.value, sr.ShortAlignmentError)
    assert studio.files[0].is_file()


def test_the_error_says_why(studio):
    with mock.patch("pipeline.prayer_alignment.align",
                    _aligner(ValueError("word 12 'selah' was not spoken"))):
        with pytest.raises(RuntimeError, match=r"alignment unavailable.*selah"):
            sr._ensure_narration(KEY)


def _manifest(tmp_path, **extra) -> Path:
    path = tmp_path / "0018-short-test.yml"
    path.write_text(yaml.safe_dump({"short": KEY, "channel": "secret-place",
                                    "status": "approved", **extra}, sort_keys=False))
    return path


def test_failures_are_counted_and_the_short_is_stepped_over_at_the_limit(tmp_path):
    path = _manifest(tmp_path)
    for expected in range(1, sr.MAX_ALIGNMENT_FAILURES):
        data = sr.record_alignment_failure(path, sr.ShortAlignmentError("mismatch"))
        assert data["alignment_failures"] == expected
        assert yaml.safe_load(path.read_text())["status"] == "approved"
    sr.record_alignment_failure(path, sr.ShortAlignmentError("mismatch"))
    saved = yaml.safe_load(path.read_text())
    assert saved["status"] == "alignment_paused"
    assert saved["alignment_failures"] == sr.MAX_ALIGNMENT_FAILURES
    assert "mismatch" in saved["last_alignment_error"]
    assert saved["short"] == KEY and saved["channel"] == "secret-place"


def test_a_stepped_over_short_lets_the_next_one_through(tmp_path, monkeypatch):
    # The selector also asks the renderer whether it knows the key. That is not
    # what this test is about, and it must not depend on today's queue.
    monkeypatch.setattr(sr, "_renderer_script_keys", lambda: {"short-stuck", "short-next"})
    monkeypatch.setattr(sr, "resolve_edition",
                        lambda key, channel_id=None: SimpleNamespace(slug=key))
    queue = tmp_path / "shorts-queue"
    queue.mkdir()
    published = tmp_path / "published"
    published.mkdir()
    (queue / "0018-short-stuck.yml").write_text(yaml.safe_dump(
        {"short": "short-stuck", "channel": "secret-place", "status": "alignment_paused"}))
    (queue / "0019-short-next.yml").write_text(yaml.safe_dump(
        {"short": "short-next", "channel": "secret-place", "status": "approved"}))
    chosen = sr.select_next_queued_short(queue, published, "secret-place")
    assert chosen is not None and chosen[1] == "short-next"
    # While it is still approved, the stuck one is what the channel releases.
    (queue / "0018-short-stuck.yml").write_text(yaml.safe_dump(
        {"short": "short-stuck", "channel": "secret-place", "status": "approved"}))
    assert sr.select_next_queued_short(queue, published, "secret-place")[1] == "short-stuck"


def test_missing_manifest_is_not_an_error():
    assert sr.record_alignment_failure(None, RuntimeError("x")) == {}
    assert sr.record_alignment_failure(Path("/no/such.yml"), RuntimeError("x")) == {}


# --- A word the recogniser did not hear is not a bad take ----------------------
#
# `prayer_alignment.match` accepts a take with 85% of the script recognised and
# gives each unheard word a zero-length span. The Short's own check then refused
# any word with no length, so one unheard word refused the whole Short.

def test_one_unheard_word_no_longer_refuses_the_short(studio):
    unheard = [("A", 0.0, 0.2), ("fresh", 0.2, 0.2), ("prayer", 0.6, 1.1)]
    with mock.patch("pipeline.prayer_alignment.align", _aligner(unheard)):
        sr._ensure_narration(KEY)
    rows = json.loads(studio.files[2].read_text())
    assert [row[2] for row in rows] == ["a", "fresh", "prayer"]
    # The silence between its neighbours is the unheard word's.
    assert rows[1][:2] == [0.2, 0.6]
    assert len(studio.takes) == 1          # no second speech request


def test_an_unheard_word_with_no_silence_shares_the_word_before_it():
    rows = sr._spread_unheard_words([[0.0, 0.4, "lord"], [0.4, 0.4, "my"], [0.4, 0.9, "shield"]])
    assert rows[0][0] == 0.0 and rows[1][1] == 0.4 and rows[2] == [0.4, 0.9, "shield"]
    assert rows[0][1] == rows[1][0] and rows[0][1] > 0.0 and rows[1][1] > rows[1][0]
    # Longer words get the longer share.
    assert rows[0][1] - rows[0][0] > rows[1][1] - rows[1][0]


def test_unheard_words_at_either_end_and_in_a_row():
    first = sr._spread_unheard_words([[0.0, 0.0, "o"], [0.0, 0.5, "lord"]])
    assert first[0][1] > first[0][0] and first[1][0] == first[0][1] and first[1][1] == 0.5
    last = sr._spread_unheard_words([[0.0, 0.5, "amen"], [0.5, 0.5, "amen"]])
    assert last[0][1] == last[1][0] and last[1][1] == 0.5 and last[1][1] > last[1][0]
    several = sr._spread_unheard_words(
        [[0.0, 0.3, "be"], [0.3, 0.3, "not"], [0.3, 0.3, "afraid"], [1.2, 1.5, "today"]])
    starts = [row[0] for row in several]
    assert starts == sorted(starts) and all(row[1] > row[0] for row in several)
    assert several[1][0] == 0.3 and several[2][1] == 1.2


def test_words_that_were_heard_are_not_moved():
    rows = [[0.0, 0.2, "a"], [0.25, 0.6, "fresh"], [0.6, 1.1, "prayer"]]
    assert sr._spread_unheard_words(rows) == rows


def test_a_hair_of_overlap_from_rounding_is_closed():
    rows = sr._spread_unheard_words([[0.0, 0.201, "a"], [0.2, 0.6, "fresh"]])
    assert rows[1][0] == 0.201


def test_a_take_that_is_out_of_order_is_still_refused_and_says_where(studio):
    backwards = [("A", 0.0, 0.5), ("fresh", 0.2, 0.6), ("prayer", 0.6, 1.1)]
    with mock.patch("pipeline.prayer_alignment.align", _aligner(backwards, backwards)):
        with pytest.raises(sr.ShortAlignmentError, match=r"word 2 'fresh' starts at 0\.200s"):
            sr._ensure_narration(KEY)


def test_the_real_aligner_and_the_short_check_now_agree():
    """End to end through `match`: a script word missing from what was heard."""
    from pipeline import prayer_alignment as pa

    script = ("The Lord is my shepherd I shall not want he makes me lie down in green "
              "pastures he leads me beside still waters he restores my soul").split()
    heard, clock = [], 0.3
    for index, word in enumerate(script):
        if index != 9:                      # "makes" was swallowed
            heard.append(pa._Span(word, clock, clock + 0.3, 0.9))
        clock += 0.3
    aligned = pa.match(script, heard)
    rows = [[float(s), float(e), sr._clean_word_token(o)] for o, s, e in aligned]
    assert rows[9][0] == rows[9][1]         # the aligner's documented zero-length span
    fixed = sr._spread_unheard_words(rows)
    assert sr._why_invalid(fixed, [sr._clean_word_token(w) for w in script]) == ""
    assert fixed[9][1] - fixed[9][0] >= sr.MIN_WORD_SPAN_S
