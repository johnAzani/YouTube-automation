"""Through the night: the bedtime prayer, then hours of quiet music.

Why this exists (docs/MONETISATION_RESEARCH_2026-11-14.md). The Secret Place is
the only channel past 1,000 subscribers, so what stands between it and the
Partner Program is watch time: 4,000 public watch hours in a year, 8,000 for a
channel still outside on 1 February 2027. Its long-forms are six to eight
minutes and are watched a few times each. Fourteen of them had 55 views between
them on 13 November 2026: at best about seven hours.

The watch-time format in this niche is a video made for the night: a prayer or
a reading, then hours of gentle sound, played while the listener sleeps. One
listener is then worth hours, not minutes.

What is built here: after the prayer video is rendered exactly as before, a
ten-minute "rest" unit is made from the same video's own pictures (dimmed and
slowed) and the studio's own synthesised score, and repeated behind the prayer
until the whole runs for the configured time. The prayer itself is not touched,
re-encoded or re-spoken: no speech request, no second upload, no second video
of the same prayer.

Guards:

* Only channels listed in ``TAIL_MINUTES`` (the bedtime channel). A prayer for
  sunrise or noon is not a sleep video.
* Only when YouTube says the channel may upload long videos
  (``channels.status.longUploadsStatus == "allowed"``). A channel that is not
  phone-verified is limited to fifteen minutes and a longer upload is rejected.
* Any failure here leaves the prayer video as it was. A release is never lost
  to its tail.
* ``NIGHT_TAIL_MINUTES=0`` switches it off; another number sets the length.

What is not known: whether anybody will play it through the night. The first
week of watch time, which only YouTube Studio shows, is the test.
"""
from __future__ import annotations

import math
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Sequence

from .assemble import ffmpeg_bin

#: Whole-video length in minutes, by channel. Three hours: long enough to cover
#: falling asleep and the first sleep cycles, small enough (about a gigabyte) to
#: upload from a runner in minutes.
TAIL_MINUTES: dict[str, int] = {"secret-place": 180}
UNIT_SECONDS = 600
MAX_TOTAL_MINUTES = 600
MIN_TOTAL_MINUTES = 20
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
#: Quieter than the score under the narration (0.58): this is heard for hours.
TAIL_MUSIC_VOLUME = 0.42
EDGE_FADE_SECONDS = 3.0
MAX_UNIT_PICTURES = 8
#: The words stay for the first moments of each unit, then leave the screen dark.
PLATE_SECONDS = 40

REST_LINE = "Rest now. He that keepeth thee will not slumber."
REST_NOTE = "The prayer has ended. Quiet music plays on while you sleep."


def configured_minutes(channel_id: str | None, environ: dict | None = None) -> int:
    """Whole-video minutes for this channel; 0 means no tail."""
    from .channels import normalize_channel_id

    env = os.environ if environ is None else environ
    base = TAIL_MINUTES.get(normalize_channel_id(channel_id), 0)
    raw = str(env.get("NIGHT_TAIL_MINUTES") or "").strip()
    if raw:
        try:
            wanted = int(raw)
        except ValueError:
            return base
        if wanted <= 0 or not base:
            return 0  # the switch turns it off; it never turns it on for a daytime channel
        return max(MIN_TOTAL_MINUTES, min(MAX_TOTAL_MINUTES, wanted))
    return base


def long_uploads_allowed(youtube: Any) -> tuple[bool, str]:
    """Does YouTube let this channel upload videos longer than fifteen minutes?"""
    try:
        items = youtube.channels().list(part="status", mine=True).execute().get("items") or []
        status = str((items[0].get("status") or {}).get("longUploadsStatus") or "") if items else ""
    except Exception as exc:  # noqa: BLE001
        return False, f"could not ask YouTube ({str(exc)[:120]})"
    if status == "allowed":
        return True, "allowed"
    return False, (f"longUploadsStatus is '{status or 'unknown'}': verify the channel by phone at "
                   "youtube.com/verify to upload videos longer than 15 minutes")


def units_needed(prayer_seconds: float, total_minutes: int, unit_seconds: float = UNIT_SECONDS) -> int:
    """How many rest units follow the prayer so the whole is at least ``total_minutes``."""
    remaining = total_minutes * 60 - prayer_seconds
    return max(1, math.ceil(remaining / unit_seconds))


def _run(cmd: list[str], what: str, timeout: int) -> None:
    done = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=timeout)
    if done.returncode:
        raise RuntimeError(f"{what} failed: {done.stderr.decode(errors='replace')[-600:]}")


def render_rest_plate(out: Path, channel_name: str, width: int = 1280, height: int = 720) -> Path:
    """A transparent lower-third telling the listener the prayer is over and music continues."""
    from PIL import Image, ImageDraw

    from .end_screens import _get_inter_font

    plate = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(plate)
    for row in range(height // 2, height):  # a soft floor of shadow, not a box
        alpha = int(150 * ((row - height // 2) / (height // 2)) ** 1.6)
        draw.line([(0, row), (width, row)], fill=(2, 6, 14, alpha))
    line_font, note_font, mark_font = (_get_inter_font(38, "Bold"), _get_inter_font(24, "Regular"),
                                       _get_inter_font(20, "Bold"))
    def centred(text: str, y: int, font, fill) -> None:
        box = draw.textbbox((0, 0), text, font=font)
        draw.text(((width - (box[2] - box[0])) // 2, y), text, font=font, fill=fill)
    centred(REST_LINE, height - 190, line_font, (244, 232, 196, 235))
    centred(REST_NOTE, height - 132, note_font, (200, 214, 236, 215))
    centred(channel_name.upper(), height - 86, mark_font, (212, 175, 55, 190))
    out.parent.mkdir(parents=True, exist_ok=True)
    plate.save(out)
    return out


def build_unit(assets: Sequence[Path], out_dir: Path, *, channel_name: str,
               seconds: float = UNIT_SECONDS, width: int = 1280, height: int = 720,
               fps: int = 24, score: Callable[[float, Path], Path] | None = None) -> Path:
    """One loopable rest unit: the video's own pictures, dimmed, under the studio's score.

    Encoded with the settings the prayer renderer uses (pipeline/prayer_visuals.py)
    so the two join without re-encoding. Both ends fade to black and to silence,
    so the join between two units is a breath, not a cut.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    pictures = [Path(p) for p in assets if Path(p).is_file()][:MAX_UNIT_PICTURES]
    if not pictures:
        raise RuntimeError("no pictures to rest on")
    each = seconds / len(pictures)
    plate = render_rest_plate(out_dir / "rest-plate.png", channel_name, width, height)
    # The score breathes at each change of picture, as it does under the prayer.
    music = (score(seconds, out_dir) if score
             else _score(seconds, out_dir, [i * each for i in range(len(pictures))]))

    cmd = [ffmpeg_bin(), "-y", "-loglevel", "error"]
    for path in pictures:
        if path.suffix.lower() in IMAGE_SUFFIXES:
            cmd += ["-loop", "1", "-framerate", str(fps), "-t", f"{each:.3f}", "-i", str(path)]
        else:
            cmd += ["-stream_loop", "-1", "-t", f"{each * 2:.3f}", "-i", str(path)]
    cmd += ["-loop", "1", "-framerate", str(fps), "-t", f"{seconds:.3f}", "-i", str(plate),
            "-i", str(music)]
    cross = min(4.0, each / 4)
    parts = []
    for index, path in enumerate(pictures):
        slow = "" if path.suffix.lower() in IMAGE_SUFFIXES else "setpts=2*PTS,"
        parts.append(
            f"[{index}:v]{slow}scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},setsar=1,fps={fps},trim=duration={each:.3f},setpts=PTS-STARTPTS,"
            f"eq=brightness=-0.16:saturation=0.78,"
            f"fade=t=in:st=0:d={cross:.2f},fade=t=out:st={each - cross:.2f}:d={cross:.2f}[v{index}]")
    joined = "".join(f"[v{i}]" for i in range(len(pictures)))
    plate_index, music_index = len(pictures), len(pictures) + 1
    fade_out_at = max(0.0, seconds - EDGE_FADE_SECONDS)
    graph = ";".join(parts + [
        f"{joined}concat=n={len(pictures)}:v=1:a=0[bg]",
        f"[{plate_index}:v]format=rgba,fade=t=out:st={PLATE_SECONDS:.0f}:d=5:alpha=1[plate]",
        f"[bg][plate]overlay=0:0:format=auto,format=yuv420p[v]",
        f"[{music_index}:a]volume={TAIL_MUSIC_VOLUME:.2f},"
        f"afade=t=in:st=0:d={EDGE_FADE_SECONDS:.1f},"
        f"afade=t=out:st={fade_out_at:.2f}:d={EDGE_FADE_SECONDS:.1f},"
        f"aformat=sample_rates=48000:channel_layouts=stereo[a]",
    ])
    unit = out_dir / "rest-unit.mp4"
    cmd += ["-filter_complex", graph, "-map", "[v]", "-map", "[a]", "-t", f"{seconds:.3f}",
            "-c:v", "libx264", "-profile:v", "high", "-preset", "fast", "-crf", "21",
            "-pix_fmt", "yuv420p", "-r", str(fps),
            "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
            "-color_range", "tv", "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k",
            "-metadata:s:v:0", "language=eng", "-metadata:s:a:0", "language=eng", str(unit)]
    _run(cmd, "rest unit encode", timeout=max(600, int(seconds * 4)))
    return unit


def _score(seconds: float, out_dir: Path, cuts: Sequence[float] = (0.0,)) -> Path:
    """The studio's own synthesised score (tools/score.py): nothing licensed, nothing borrowed."""
    from tools.score import generate_score

    generate_score("night-rest", float(seconds), list(cuts), [], [], [], out_dir=str(out_dir))
    return Path(out_dir) / "music-night-rest.wav"


def join(prayer: Path, unit: Path, repeats: int, out: Path) -> Path:
    """The prayer, then ``repeats`` rest units, with no re-encoding of either."""
    work = out.parent / "night-tail"
    work.mkdir(parents=True, exist_ok=True)
    streams = []
    for name, source in (("prayer", prayer), ("rest", unit)):
        ts = work / f"{name}.ts"
        _run([ffmpeg_bin(), "-y", "-loglevel", "error", "-i", str(source), "-c", "copy",
              "-bsf:v", "h264_mp4toannexb", "-f", "mpegts", str(ts)], f"{name} repackage", 900)
        streams.append(ts)
    listing = work / "join.txt"
    listing.write_text("\n".join([f"file '{streams[0].resolve()}'"]
                                 + [f"file '{streams[1].resolve()}'"] * repeats), encoding="utf-8")
    partial = out.with_name(out.stem + ".night.partial.mp4")
    _run([ffmpeg_bin(), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
          "-c", "copy", "-bsf:a", "aac_adtstoasc", "-movflags", "+faststart",
          "-metadata:s:v:0", "language=eng", "-metadata:s:a:0", "language=eng", str(partial)],
         "join", 1800)
    return partial


def extend(prayer: Path, assets: Sequence[Path], *, prayer_seconds: float, total_minutes: int,
           channel_name: str, unit_seconds: float = UNIT_SECONDS,
           score: Callable[[float, Path], Path] | None = None,
           probe: Callable[[Path], float | None] | None = None) -> dict | None:
    """Lengthen ``prayer`` in place to ``total_minutes``. ``None`` (file untouched) on any failure."""
    prayer = Path(prayer)
    started = time.monotonic()
    work = prayer.parent / "night-tail"
    try:
        if total_minutes * 60 <= prayer_seconds + unit_seconds / 2:
            return None
        if probe is None:
            from .tts import _probe_duration as probe  # type: ignore[no-redef]
        unit = build_unit(assets, work, channel_name=channel_name, seconds=unit_seconds, score=score)
        repeats = units_needed(prayer_seconds, total_minutes, unit_seconds)
        partial = join(prayer, unit, repeats, prayer)
        expected = prayer_seconds + repeats * unit_seconds
        actual = probe(partial)
        if actual is None or abs(actual - expected) > max(5.0, repeats * 0.5):
            partial.unlink(missing_ok=True)
            raise RuntimeError(f"joined video is {actual}s, expected about {expected:.0f}s")
        original = prayer.with_name(prayer.stem + ".prayer-only.mp4")
        shutil.move(str(prayer), str(original))
        shutil.move(str(partial), str(prayer))
        return {"total_seconds": actual, "prayer_seconds": prayer_seconds, "units": repeats,
                "unit_seconds": unit_seconds, "megabytes": round(prayer.stat().st_size / 1e6, 1),
                "build_seconds": round(time.monotonic() - started, 1),
                "prayer_only": str(original)}
    except Exception as exc:  # noqa: BLE001 - a release is never lost to its tail
        print(f"::warning title=Night tail not added::{str(exc)[:300]}")
        return None
    finally:
        for leftover in ("prayer.ts", "rest.ts", "music-night-rest.wav"):
            (work / leftover).unlink(missing_ok=True)


def _clock(seconds: float) -> str:
    seconds = int(seconds)
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def _length_words(total_seconds: float) -> str:
    hours = total_seconds / 3600
    if hours >= 1:
        whole = int(hours + 0.01)
        return f"{whole} hour{'s' if whole != 1 else ''}"
    return f"{int(total_seconds // 60)} minutes"


NIGHT_TAGS = ("prayer to fall asleep", "sleep with god's word", "night prayer and sleep music",
              "peaceful sleep prayer", "fall asleep in god's presence")


def describe(pack: dict, *, prayer_seconds: float, total_seconds: float) -> dict:
    """Tell the viewer what the video is: say it first, mark where the music starts, add search tags."""
    import re

    pack = dict(pack)
    minutes = max(1, round(prayer_seconds / 60))
    first = (f"Pray along for the first {minutes} minutes, then rest: quiet music plays on for "
             f"{_length_words(total_seconds)} so the room stays at peace while you sleep.")
    lines = str(pack.get("description") or "").split("\n")
    stamps = [i for i, line in enumerate(lines) if re.match(r"^\d{1,2}:\d{2}(?::\d{2})?\s+\S", line)]
    if stamps:
        lines.insert(stamps[-1] + 1, f"{_clock(prayer_seconds)} Rest through the night (music only)")
    pack["description"] = first + "\n\n" + "\n".join(lines)
    tags = list(pack.get("tags") or [])
    used = sum(len(tag) + 1 for tag in tags)
    for tag in NIGHT_TAGS + (f"{_length_words(total_seconds)} sleep prayer",):
        if tag not in tags and used + len(tag) + 1 <= 480:
            tags.append(tag)
            used += len(tag) + 1
    pack["tags"] = tags
    return pack
