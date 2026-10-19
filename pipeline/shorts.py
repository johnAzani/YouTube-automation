"""Auto-Shorts: cut vertical 9:16 clips from a finished long-form render.

Strategy (docs/GROWTH.md §7): pick the scenes with the most substance (word
count), cut ≤45 s windows from their start, crop to 1080x1920, burn the
matching caption slice, and emit per-short metadata drafts. The description of
every Short links the parent long-form.

    python -m pipeline.shorts --job content/queue/0001-....md --count 2
(uses output/<slug>/<slug>.mp4 + captions.srt produced by pipeline.run)
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from .assemble import ffmpeg_bin, _run
from .config import CONFIG, OUTPUT_DIR
from .script_doc import ScriptDoc, parse_script


def _crop_vertical() -> str:
    return (
        f"scale=1080:1920:force_original_aspect_ratio=increase,"
        f"crop=1080:1920,setsar=1,format=yuv420p"
    )


def _slice_srt(srt_path: Path, start: float, end: float, out_path: Path) -> None:
    """Copy captions in [start,end), rebased to 0."""
    try:
        import re

        text = srt_path.read_text(encoding="utf-8")
        blocks = re.split(r"\n\s*\n", text.strip())
        out_blocks = []
        idx = 1

        def ts_to_s(ts: str) -> float:
            h, m, rest = ts.split(":")
            s, ms = rest.split(",")
            return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000

        def s_to_ts(t: float) -> str:
            ms = int(round(t * 1000))
            h, ms = divmod(ms, 3_600_000)
            m, ms = divmod(ms, 60_000)
            s, ms = divmod(ms, 1000)
            return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

        for b in blocks:
            lines = b.strip().splitlines()
            if len(lines) < 3:
                continue
            m = re.match(r"(\d\d:\d\d:\d\d,\d\d\d) --> (\d\d:\d\d:\d\d,\d\d\d)", lines[1])
            if not m:
                continue
            a, z = ts_to_s(m.group(1)), ts_to_s(m.group(2))
            if a >= start - 0.05 and z <= end + 0.05:
                out_blocks.append(
                    f"{idx}\n{s_to_ts(max(0.0, a - start))} --> {s_to_ts(max(0.1, z - start))}\n"
                    + "\n".join(lines[2:]) + "\n"
                )
                idx += 1
        out_path.write_text("\n".join(out_blocks), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        print(f"[shorts] srt slice skipped: {exc!r}")


def cut_shorts(doc: ScriptDoc, video: Path, srt: Path, scene_durations: list[float],
               out_dir: Path, count: int = 2, target_seconds: float = 35.0) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    boundaries: list[tuple[float, float]] = []
    t = 0.0
    for dur in scene_durations:
        boundaries.append((t, t + dur))
        t += dur

    # rank scenes by narration substance
    ranked = sorted(
        range(len(doc.scenes)),
        key=lambda i: len(doc.scenes[i].narration.split()),
        reverse=True,
    )[:count]

    outputs: list[Path] = []
    for n, si in enumerate(sorted(ranked), start=1):
        start, end = boundaries[si]
        start = min(start + 0.15, max(0.0, end - 5.0))
        stop = min(end - 0.1, start + target_seconds)
        if stop - start < 8.0:
            continue

        clip = out_dir / f"{doc.slug}_short{n}.mp4"
        srt_slice = out_dir / f"{doc.slug}_short{n}.srt"
        _slice_srt(srt, start, stop, srt_slice)

        vf = _crop_vertical()
        if CONFIG.burn_captions and srt_slice.exists() and srt_slice.stat().st_size > 0:
            esc = str(srt_slice.resolve()).replace(":", r"\:").replace("'", r"'\''")
            vf += f",subtitles='{esc}':force_style='FontSize=22,Outline=2,MarginV=60'"

        cmd = [
            ffmpeg_bin(), "-y", "-ss", f"{start:.2f}", "-to", f"{stop:.2f}",
            "-i", str(video), "-vf", vf,
            "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k",
            "-r", "30", str(clip),
        ]
        try:
            _run(cmd)
        except RuntimeError as exc:
            # caption burn may fail without libass — retry clean
            print(f"[shorts] render with captions failed ({exc}); retrying without burn")
            cmd[cmd.index("-vf") + 1] = _crop_vertical()
            _run(cmd)
        outputs.append(clip)

        meta = {
            "parent": doc.slug,
            "scene": si + 1,
            "heading": doc.scenes[si].heading,
            "file": clip.name,
            "duration_seconds": round(stop - start, 1),
            "title_draft": doc.scenes[si].heading[:80],
            "description_draft": (
                f"{doc.scenes[si].heading[:100]} — from our full documentary. "
                f"Watch the full story: (link to {doc.slug}). #Shorts "
                + " ".join(f"#{t.replace(' ', '')}" for t in doc.tags[:2])
            ),
        }
        (out_dir / f"{doc.slug}_short{n}.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        print(f"[shorts] {clip.name}  {meta['duration_seconds']}s  «{doc.scenes[si].heading[:40]}»")

    return outputs


def main() -> int:
    ap = argparse.ArgumentParser(description="Cut vertical Shorts from a rendered long-form")
    ap.add_argument("--job", required=True, help="script markdown used for the render")
    ap.add_argument("--count", type=int, default=2)
    ap.add_argument("--seconds", type=float, default=35.0)
    args = ap.parse_args()

    doc = parse_script(Path(args.job))
    out = OUTPUT_DIR / doc.slug
    video = out / f"{doc.slug}.mp4"
    srt = out / "captions.srt"
    if not video.exists():
        print(f"render not found: {video} — run pipeline.run first")
        return 1

    from .assemble import scene_durations_from_words
    from .tts import _probe_duration

    duration = _probe_duration(video) or 0.0
    scene_durations = scene_durations_from_words(doc, duration)
    cut_shorts(doc, video, srt, scene_durations, out / "shorts", count=args.count, target_seconds=args.seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
