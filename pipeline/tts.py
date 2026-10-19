"""Narration synthesis.

Primary:  edge-tts (Microsoft Edge neural voices — free, no API key).
Fallback: offline placeholder narration (silence-paced per word count) so the
pipeline always completes in dry-run / CI environments with no outbound net.

Also produces word-timed SRT captions (edge-tts emits WordBoundary events;
the fallback estimates timing from words-per-second).
"""
from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from pathlib import Path

from .config import CONFIG


@dataclass
class NarrationResult:
    audio_path: Path
    srt_path: Path
    duration_seconds: float
    word_times: list[tuple[str, float, float]]  # (word, start, end)
    engine: str  # "edge-tts" | "placeholder"


def _srt_timestamp(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _estimate_word_times(text: str, wps: float) -> list[tuple[str, float, float]]:
    words = [w for w in re.findall(r"\S+", text) if re.search(r"\w", w)]
    times: list[tuple[str, float, float]] = []
    t = 0.0
    for w in words:
        dur = max(0.12, len(w) / (wps * 5.0))
        times.append((w, t, t + dur))
        t += dur + 0.06  # inter-word gap
    return times


def _write_srt(word_times: list[tuple[str, float, float]], srt_path: Path, chunk: int = 6) -> None:
    """Group words into caption chunks of ~6 words (or by punctuation)."""
    lines: list[str] = []
    buf: list[tuple[str, float, float]] = []
    idx = 1

    def flush() -> None:
        nonlocal idx, buf
        if not buf:
            return
        text = " ".join(w for w, _, _ in buf)
        lines.append(f"{idx}\n{_srt_timestamp(buf[0][1])} --> {_srt_timestamp(buf[-1][2] + 0.15)}\n{text}\n")
        idx += 1
        buf = []

    for wt in word_times:
        buf.append(wt)
        if len(buf) >= chunk or re.search(r"[.!?,;:]$", wt[0]):
            flush()
    flush()
    srt_path.write_text("\n".join(lines), encoding="utf-8")


async def _edge_tts(text: str, voice: str, rate: str, out_path: Path) -> list[tuple[str, float, float]]:
    import edge_tts  # imported lazily so dry-run works without the package

    communicate = edge_tts.Communicate(text, voice=voice, rate=rate)
    word_times: list[tuple[str, float, float]] = []
    with open(out_path, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"] / 1e7
                dur = chunk["duration"] / 1e7
                word_times.append((chunk["text"], start, start + dur))
    return word_times


def _placeholder_audio(text: str, out_path: Path) -> list[tuple[str, float, float]]:
    """Offline stand-in narration: a soft tone bed paced to the word count.

    Keeps the assembly path fully testable with zero network and zero keys.
    """
    import subprocess

    word_times = _estimate_word_times(text, CONFIG.words_per_second)
    duration = (word_times[-1][2] if word_times else 5.0) + 0.5

    from .assemble import ffmpeg_bin

    # Quiet speech-shaped placeholder: very low sine + fades, so it's obvious
    # in QC that this is a dry-run render and not a publishable voiceover.
    cmd = [
        ffmpeg_bin(), "-y",
        "-f", "lavfi", "-i", "sine=frequency=220:duration=%.2f" % duration,
        "-af", "volume=0.03,tremolo=f=4:d=0.7,afade=t=in:st=0:d=0.4,afade=t=out:st=%.2f:d=0.4" % max(0.0, duration - 0.4),
        str(out_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return word_times


def synthesize(text: str, out_dir: Path, voice: str = "", srt_name: str = "captions") -> NarrationResult:
    out_dir.mkdir(parents=True, exist_ok=True)
    audio_path = out_dir / "narration.mp3"
    srt_path = out_dir / f"{srt_name}.srt"
    voice = voice or CONFIG.voice

    word_times: list[tuple[str, float, float]] = []
    engine = "edge-tts"
    try:
        word_times = asyncio.run(_edge_tts(text, voice, CONFIG.tts_rate, audio_path))
        if not audio_path.exists() or audio_path.stat().st_size < 512:
            raise RuntimeError("edge-tts produced no audio")
        if not word_times:  # some edge-tts versions don't emit boundaries
            word_times = _estimate_word_times(text, CONFIG.words_per_second)
    except Exception as exc:  # noqa: BLE001 - fallback is the point
        print(f"[tts] edge-tts unavailable ({exc!r}); using offline placeholder narration")
        word_times = _placeholder_audio(text, audio_path)
        engine = "placeholder"

    duration = word_times[-1][2] + 0.3 if word_times else 0.0
    # Prefer real audio duration when ffprobe is available
    duration = _probe_duration(audio_path) or duration
    _write_srt(word_times, srt_path)

    meta = {
        "engine": engine,
        "voice": voice,
        "duration_seconds": duration,
        "word_count": len(word_times),
    }
    (out_dir / "tts_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return NarrationResult(audio_path, srt_path, duration, word_times, engine)


def _probe_duration(path: Path) -> float | None:
    import os
    import re
    import shutil
    import subprocess

    from .assemble import ffmpeg_bin

    candidates: list[str] = []
    if os.environ.get("FFPROBE_BINARY"):
        candidates.append(os.environ["FFPROBE_BINARY"])
    found = shutil.which("ffprobe")
    if found:
        candidates.append(found)
    guess = ffmpeg_bin().replace("ffmpeg", "ffprobe")  # works for system installs
    candidates.append(guess)

    for ffprobe in candidates:
        try:
            out = subprocess.run(
                [ffprobe, "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
                check=True, capture_output=True, text=True,
            )
            return float(out.stdout.strip())
        except Exception:  # noqa: BLE001
            continue

    # Last resort: parse `ffmpeg -i` banner (always available)
    try:
        proc = subprocess.run([ffmpeg_bin(), "-i", str(path)],
                              capture_output=True, text=True)
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", proc.stderr)
        if m:
            h, mnt, s = m.groups()
            return int(h) * 3600 + int(mnt) * 60 + float(s)
    except Exception:  # noqa: BLE001
        pass
    return None
