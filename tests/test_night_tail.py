"""The bedtime channel's prayer is followed by hours of quiet music (pipeline/night_tail.py)."""
from __future__ import annotations

import math
import struct
import subprocess
import wave
from pathlib import Path

import pytest

from pipeline import night_tail as nt


# --------------------------------------------------------------------------- #
# Which channels, and how long
# --------------------------------------------------------------------------- #
def test_only_the_bedtime_channel_gets_a_night_tail():
    assert nt.configured_minutes("secret-place", {}) == 180
    for daytime in ("prayer2", "prayer3", "prayer5", "prayer9", "prayer10"):
        assert nt.configured_minutes(daytime, {}) == 0


def test_the_switch_turns_it_off_and_sets_the_length_but_never_adds_a_channel():
    assert nt.configured_minutes("secret-place", {"NIGHT_TAIL_MINUTES": "0"}) == 0
    assert nt.configured_minutes("secret-place", {"NIGHT_TAIL_MINUTES": "60"}) == 60
    assert nt.configured_minutes("secret-place", {"NIGHT_TAIL_MINUTES": "5"}) == nt.MIN_TOTAL_MINUTES
    assert nt.configured_minutes("secret-place", {"NIGHT_TAIL_MINUTES": "9999"}) == nt.MAX_TOTAL_MINUTES
    assert nt.configured_minutes("secret-place", {"NIGHT_TAIL_MINUTES": "soon"}) == 180
    assert nt.configured_minutes("prayer2", {"NIGHT_TAIL_MINUTES": "180"}) == 0


def test_units_cover_the_asked_length():
    assert nt.units_needed(420, 180) == 18          # 7 min of prayer + 18 x 10 min >= 3 h
    assert 420 + nt.units_needed(420, 180) * 600 >= 180 * 60
    assert nt.units_needed(420, 20) == 2
    assert nt.units_needed(5000, 60) == 1


# --------------------------------------------------------------------------- #
# YouTube must allow long uploads first
# --------------------------------------------------------------------------- #
class _Channels:
    def __init__(self, answer):
        self.answer = answer

    def channels(self):
        return self

    def list(self, **kwargs):
        assert kwargs == {"part": "status", "mine": True}
        return self

    def execute(self):
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


def test_long_uploads_must_be_allowed_by_youtube():
    ok, _ = nt.long_uploads_allowed(_Channels({"items": [{"status": {"longUploadsStatus": "allowed"}}]}))
    assert ok
    ok, why = nt.long_uploads_allowed(_Channels({"items": [{"status": {"longUploadsStatus": "eligible"}}]}))
    assert not ok and "youtube.com/verify" in why
    ok, why = nt.long_uploads_allowed(_Channels({"items": []}))
    assert not ok and "unknown" in why
    ok, why = nt.long_uploads_allowed(_Channels(RuntimeError("quota")))
    assert not ok and "quota" in why


# --------------------------------------------------------------------------- #
# The description says what the video is
# --------------------------------------------------------------------------- #
def test_description_says_what_follows_the_prayer_and_marks_where():
    pack = {"description": "A prayer for the night.\n\n0:00 Opening\n2:10 Scripture\n5:40 Amen\n\nSubscribe.",
            "tags": ["night prayer", "psalm 4"]}
    out = nt.describe(pack, prayer_seconds=432.0, total_seconds=3 * 3600 + 432)
    first = out["description"].split("\n")[0]
    assert "first 7 minutes" in first and "3 hours" in first
    lines = out["description"].split("\n")
    assert lines[lines.index("5:40 Amen") + 1] == "7:12 Rest through the night (music only)"
    assert "prayer to fall asleep" in out["tags"] and out["tags"][:2] == ["night prayer", "psalm 4"]
    assert sum(len(tag) + 1 for tag in out["tags"]) <= 480
    assert pack["tags"] == ["night prayer", "psalm 4"], "the caller's pack is not changed"
    assert "Rest through the night" not in pack["description"]


def test_description_without_chapters_gets_no_orphan_chapter():
    out = nt.describe({"description": "A prayer.", "tags": []}, prayer_seconds=400, total_seconds=7200)
    assert "music only" not in out["description"] and out["description"].startswith("Pray along")


def test_tags_never_pass_the_budget():
    full = {"description": "x", "tags": ["a" * 60] * 7 + ["b" * 40]}
    out = nt.describe(full, prayer_seconds=400, total_seconds=7200)
    assert sum(len(tag) + 1 for tag in out["tags"]) <= 480


def test_the_rest_line_is_scripture_as_written():
    from pipeline import scripture_text

    verse = " ".join(v.text for v in scripture_text.passage("Psalm 121:3")).lower()
    assert "he that keepeth thee will not slumber" in verse
    assert "He that keepeth thee will not slumber" in nt.REST_LINE


# --------------------------------------------------------------------------- #
# Real encode and join, small
# --------------------------------------------------------------------------- #
def _ffmpeg() -> str | None:
    try:
        from pipeline.assemble import ffmpeg_bin

        binary = ffmpeg_bin()
        subprocess.run([binary, "-version"], capture_output=True, check=True, timeout=20)
        return binary
    except Exception:  # noqa: BLE001
        return None


def _tone(seconds: float, out_dir: Path) -> Path:
    path = Path(out_dir) / "tone.wav"
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(48000)
        frames = bytearray()
        for i in range(int(seconds * 48000)):
            sample = int(3000 * math.sin(2 * math.pi * 196 * i / 48000))
            frames += struct.pack("<hh", sample, sample)
        handle.writeframes(bytes(frames))
    return path


def _stand_in_prayer(binary: str, path: Path, seconds: int = 4) -> None:
    """Encoded with the arguments pipeline/prayer_visuals.render uses."""
    subprocess.run(
        [binary, "-y", "-loglevel", "error",
         "-f", "lavfi", "-i", f"testsrc2=size=1280x720:rate=24:duration={seconds}",
         "-f", "lavfi", "-i", f"sine=frequency=220:duration={seconds}",
         "-af", "aformat=channel_layouts=stereo",
         "-c:v", "libx264", "-profile:v", "high", "-preset", "fast", "-crf", "21", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-ar", "48000", "-b:a", "192k", "-movflags", "+faststart", str(path)],
        check=True, timeout=120)


def _probe(binary: str):
    import re

    def probe(path: Path) -> float | None:
        text = subprocess.run([binary, "-i", str(path)], capture_output=True, timeout=60).stderr.decode()
        found = re.search(r"Duration: (\d+):(\d+):([\d.]+)", text)
        return (int(found[1]) * 3600 + int(found[2]) * 60 + float(found[3])) if found else None
    return probe


@pytest.fixture()
def studio(tmp_path):
    binary = _ffmpeg()
    if not binary:
        pytest.skip("ffmpeg is not available")
    from PIL import Image

    pictures = []
    for index, colour in enumerate(((20, 40, 90), (70, 40, 20))):
        picture = tmp_path / f"scene-{index}.jpg"
        Image.new("RGB", (1600, 900), colour).save(picture)
        pictures.append(picture)
    prayer = tmp_path / "prayer.mp4"
    _stand_in_prayer(binary, prayer)
    return binary, prayer, pictures


def test_prayer_is_followed_by_rest_and_plays_through(studio):
    binary, prayer, pictures = studio
    before = prayer.read_bytes()
    info = nt.extend(prayer, pictures, prayer_seconds=4.0, total_minutes=1, channel_name="The Secret Place",
                     unit_seconds=6, score=_tone, probe=_probe(binary))
    assert info and info["units"] == 10, info
    assert abs(info["total_seconds"] - 64.0) < 3
    assert prayer.read_bytes() == before, "the prayer as rendered is never changed"
    night = Path(info["video"])
    assert night.name == "prayer.night.mp4" and night.parent == prayer.parent
    decoded = subprocess.run([binary, "-v", "error", "-i", str(night), "-f", "null", "-"],
                             capture_output=True, timeout=120)
    assert decoded.returncode == 0 and not decoded.stderr.strip(), decoded.stderr.decode()[:400]
    # Still one video stream and one stereo audio stream, the prayer's own.
    streams = subprocess.run([binary, "-i", str(night)], capture_output=True, timeout=60).stderr.decode()
    assert streams.count("Video: h264") == 1 and streams.count("Audio: aac") == 1
    assert "1280x720" in streams and "stereo" in streams


def test_a_failed_tail_leaves_the_prayer_as_it_was(studio, capsys):
    binary, prayer, _pictures = studio
    before = prayer.read_bytes()
    info = nt.extend(prayer, [], prayer_seconds=4.0, total_minutes=1, channel_name="The Secret Place",
                     unit_seconds=6, score=_tone, probe=_probe(binary))
    assert info is None
    assert prayer.read_bytes() == before
    assert "Night tail not added" in capsys.readouterr().out


def test_a_join_of_the_wrong_length_is_refused(studio):
    binary, prayer, pictures = studio
    before = prayer.read_bytes()
    info = nt.extend(prayer, pictures, prayer_seconds=4.0, total_minutes=1, channel_name="The Secret Place",
                     unit_seconds=6, score=_tone, probe=lambda _path: 12.0)
    assert info is None and prayer.read_bytes() == before
    assert not list(prayer.parent.glob("*.partial.mp4")) and not list(prayer.parent.glob("*.night.mp4"))


def test_nothing_to_add_when_the_prayer_already_fills_the_time(tmp_path):
    prayer = tmp_path / "prayer.mp4"
    prayer.write_bytes(b"as rendered")
    assert nt.extend(prayer, [], prayer_seconds=3500, total_minutes=60, channel_name="x") is None
    assert prayer.read_bytes() == b"as rendered"


# --------------------------------------------------------------------------- #
# Wiring in the long-form pipeline
# --------------------------------------------------------------------------- #
class _Doc:
    def __init__(self, channel):
        self.explicit_channel = channel


def test_pipeline_skips_daytime_channels_without_asking_youtube(monkeypatch):
    from pipeline import prayer_pipeline as pp
    from pipeline import upload

    monkeypatch.delenv("NIGHT_TAIL_MINUTES", raising=False)
    monkeypatch.setattr(upload, "_thumb_client", lambda *a, **k: pytest.fail("YouTube was asked"))
    assert pp._add_night_tail(_Doc("prayer2"), Path("x.mp4"), [], 400.0) is None


def test_pipeline_skips_when_youtube_does_not_allow_long_uploads(monkeypatch, capsys):
    from pipeline import prayer_pipeline as pp
    from pipeline import upload

    monkeypatch.delenv("NIGHT_TAIL_MINUTES", raising=False)
    monkeypatch.setattr(upload, "_thumb_client",
                        lambda *a, **k: _Channels({"items": [{"status": {"longUploadsStatus": "eligible"}}]}))
    monkeypatch.setattr(nt, "extend", lambda *a, **k: pytest.fail("built a tail YouTube would reject"))
    assert pp._add_night_tail(_Doc("secret-place"), Path("x.mp4"), [], 400.0) is None
    assert "Night tail skipped" in capsys.readouterr().out


def test_pipeline_builds_the_tail_for_the_bedtime_channel(monkeypatch, capsys):
    from pipeline import prayer_pipeline as pp
    from pipeline import upload

    monkeypatch.delenv("NIGHT_TAIL_MINUTES", raising=False)
    monkeypatch.setattr(upload, "_thumb_client",
                        lambda *a, **k: _Channels({"items": [{"status": {"longUploadsStatus": "allowed"}}]}))
    seen = {}

    def fake_extend(final, assets, **kwargs):
        seen.update(kwargs, final=final)
        return {"video": "x.night.mp4", "total_seconds": 11220.0, "units": 18, "unit_seconds": 600,
                "megabytes": 900.0, "build_seconds": 300.0}

    monkeypatch.setattr(nt, "extend", fake_extend)
    info = pp._add_night_tail(_Doc("secret-place"), Path("x.mp4"), ["a.jpg"], 420.0)
    assert info["units"] == 18
    assert seen["total_minutes"] == 180 and seen["prayer_seconds"] == 420.0
    assert seen["channel_name"] == "The Secret Place"
    assert "[night-tail] secret-place" in capsys.readouterr().out


def test_a_crash_in_the_tail_never_stops_the_release(monkeypatch):
    from pipeline import prayer_pipeline as pp
    from pipeline import upload

    monkeypatch.delenv("NIGHT_TAIL_MINUTES", raising=False)

    def boom(*a, **k):
        raise RuntimeError("no credentials")

    monkeypatch.setattr(upload, "_thumb_client", boom)
    assert pp._add_night_tail(_Doc("secret-place"), Path("x.mp4"), [], 400.0) is None


def test_release_workflow_keeps_the_joined_video_out_of_the_qc_artifact():
    workflow = (Path(__file__).resolve().parent.parent / ".github" / "workflows" / "produce.yml").read_text()
    assert f"!output/*/*{nt.NIGHT_SUFFIX}" in workflow
