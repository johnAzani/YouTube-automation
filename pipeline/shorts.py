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


def _make_hook_overlay(png_path: Path, text: str, width: int = 1000, height: int = 300) -> None:
    """Transparent lower-third PNG with wrapped hook text (Pillow — no drawtext)."""
    import textwrap

    from PIL import Image, ImageDraw

    from .textplates import find_font

    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([0, 0, width, height], radius=28, fill=(10, 12, 24, 175))
    draw.rectangle([0, 0, 14, height], fill=(255, 210, 60, 235))

    from PIL import ImageFont

    font_path = find_font()
    font = ImageFont.truetype(font_path, 52) if font_path else ImageFont.load_default()
    lines = textwrap.wrap(text.strip(), width=22)[:3]
    y = (height - len(lines) * 62) // 2
    for line in lines:
        draw.text((44, y + 2), line, font=font, fill=(0, 0, 0, 220))
        draw.text((44, y), line, font=font, fill=(255, 255, 255, 255))
        y += 62
    img.save(png_path)


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

    # Cut from the PRE-caption-burn source when available: scaling the burned
    # 720p captions to 1080x1920 makes them gigantic. Each Short burns its own
    # caption slice instead.
    source = video
    nosubs = video.parent / "final_nosubs.mp4"
    if nosubs.exists():
        source = nosubs

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
            print(f"[shorts] scene {si + 1} too short for a clip ({stop - start:.1f}s) — skipped")
            continue

        clip = out_dir / f"{doc.slug}_short{n}.mp4"
        srt_slice = out_dir / f"{doc.slug}_short{n}.srt"
        _slice_srt(srt, start, stop, srt_slice)

        # Filter chain: crop 9:16 -> burn captions -> hook overlay (bottom band)
        chain: list[str] = [f"[0:v]{_crop_vertical()}[base]"]
        cur = "[base]"
        if CONFIG.burn_captions and srt_slice.exists() and srt_slice.stat().st_size > 0:
            esc = str(srt_slice.resolve()).replace(":", r"\:").replace("'", r"'\''")
            # PlayRes makes every unit a real pixel (libass defaults to a 288px
            # reference which silently scales FontSize/Margins ~6.7x).
            chain.append(
                f"{cur}subtitles='{esc}':force_style='"
                f"PlayResX=1080,PlayResY=1920,FontSize=44,Outline=2,Shadow=0,"
                f"MarginV=400,MarginL=80,MarginR=80,Alignment=2'[sub]"
            )
            cur = "[sub]"

        overlay_png = out_dir / f"{doc.slug}_short{n}_hook.png"
        inputs_extra: list[str] = []
        try:
            _make_hook_overlay(overlay_png, doc.scenes[si].heading)
            inputs_extra = ["-i", str(overlay_png)]
            chain.append(f"{cur}[1:v]overlay=40:1500[vfin]")
            map_label = "[vfin]"
        except Exception as exc:  # noqa: BLE001
            print(f"[shorts] hook overlay skipped: {exc!r}")
            map_label = cur

        cmd = [
            ffmpeg_bin(), "-y", "-ss", f"{start:.2f}", "-to", f"{stop:.2f}",
            "-i", str(source), *inputs_extra,
            "-filter_complex", ";".join(chain),
            "-map", map_label, "-map", "0:a",
            "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-r", "30", str(clip),
        ]
        cmd_plain = [
            ffmpeg_bin(), "-y", "-ss", f"{start:.2f}", "-to", f"{stop:.2f}",
            "-i", str(source), "-vf", _crop_vertical(),
            "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-r", "30", str(clip),
        ]
        try:
            _run(cmd)
        except RuntimeError as exc:
            # captions/overlay may fail on minimal ffmpeg builds — retry plain
            print(f"[shorts] decorated render failed ({exc}); retrying plain")
            _run(cmd_plain)
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

    duration = _probe_duration(video)
    if not duration:  # fall back to the render's own TTS metadata
        meta_path = out / "tts_meta.json"
        if meta_path.exists():
            duration = float(json.loads(meta_path.read_text())["duration_seconds"])
    if not duration:
        print("could not determine video duration — was the render complete?")
        return 1
    scene_durations = scene_durations_from_words(doc, duration)
    cut_shorts(doc, video, srt, scene_durations, out / "shorts", count=args.count, target_seconds=args.seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
