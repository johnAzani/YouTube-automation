"""ffmpeg assembly: scenes -> montage under narration -> final MP4.

Design choices for reliability on GitHub-hosted runners:
  * each scene is rendered to a normalised temp clip, then concat-demuxed;
  * caption burn is attempted and gracefully skipped if libass is missing;
  * ffmpeg is resolved via FFMPEG_BINARY env, PATH, or the imageio-ffmpeg
    static build (useful for laptops without ffmpeg installed).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from .config import CONFIG
from .script_doc import ScriptDoc


def ffmpeg_bin() -> str:
    env = os.environ.get("FFMPEG_BINARY")
    if env and Path(env).exists():
        return env
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg  # type: ignore

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "ffmpeg not found. Install ffmpeg, or `pip install imageio-ffmpeg`, "
            "or set FFMPEG_BINARY to a binary path."
        ) from exc


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed ({proc.returncode}): {' '.join(cmd[:8])}...\n"
            f"stderr tail: {proc.stderr[-1200:]}"
        )


def _cover_filter() -> str:
    return (
        f"scale={CONFIG.width}:{CONFIG.height}:force_original_aspect_ratio=increase,"
        f"crop={CONFIG.width}:{CONFIG.height},setsar=1,format=yuv420p"
    )


def render_scene_clip(asset_path: Path, duration: float, out_path: Path, is_image: bool, ken: bool = True) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    duration = max(duration, 0.8)
    ken = ken and CONFIG.ken_burns
    if is_image:
        if ken:
            # Gentle push-in. zoompan operates at OUTPUT resolution (cheap + stable).
            vf = (
                f"scale={CONFIG.width}:{CONFIG.height}:force_original_aspect_ratio=increase,"
                f"crop={CONFIG.width}:{CONFIG.height},"
                f"zoompan=z='min(1.0+0.0012*on,1.18)':"
                f"d={int(duration * CONFIG.fps)}:"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                f"s={CONFIG.width}x{CONFIG.height}:fps={CONFIG.fps},"
                f"format=yuv420p"
            )
            cmd = [
                ffmpeg_bin(), "-y", "-loop", "1", "-t", f"{duration:.2f}",
                "-i", str(asset_path), "-vf", vf,
                "-r", str(CONFIG.fps), "-c:v", "libx264", "-preset", "ultrafast",
                "-pix_fmt", "yuv420p", str(out_path),
            ]
            try:
                _run(cmd)
                return
            except RuntimeError:
                pass  # fall through to the static render
        cmd = [
            ffmpeg_bin(), "-y", "-loop", "1", "-t", f"{duration:.2f}",
            "-i", str(asset_path), "-vf", _cover_filter(),
            "-r", str(CONFIG.fps), "-c:v", "libx264", "-preset", "ultrafast",
            "-pix_fmt", "yuv420p", str(out_path),
        ]
    else:
        cmd = [
            ffmpeg_bin(), "-y", "-i", str(asset_path), "-t", f"{duration:.2f}",
            "-vf", _cover_filter() + f",fps={CONFIG.fps}",
            "-an", "-c:v", "libx264", "-preset", "ultrafast",
            "-pix_fmt", "yuv420p", "-r", str(CONFIG.fps), str(out_path),
        ]
    _run(cmd)


def assemble(
    doc: ScriptDoc,
    scene_assets: list[list[Path]],
    narration_path: Path,
    srt_path: Path,
    out_dir: Path,
    scene_durations: list[float],
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    work = out_dir / "segments"
    work.mkdir(exist_ok=True)

    # ---- 1. normalise every scene into a segment ------------------------
    segment_paths: list[Path] = []
    for i, (assets, dur) in enumerate(zip(scene_assets, scene_durations), start=1):
        if not assets:
            raise RuntimeError(f"scene {i} has no assets")
        # Distribute the scene duration across its assets
        per = dur / len(assets)
        parts: list[Path] = []
        for j, asset in enumerate(assets):
            is_image = asset.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
            seg = work / f"scene{i:02d}_part{j:02d}.mp4"
            render_scene_clip(asset, per, seg, is_image=is_image)
            parts.append(seg)
        if len(parts) == 1:
            segment_paths.append(parts[0])
        else:
            merged = work / f"scene{i:02d}.mp4"
            listfile = work / f"scene{i:02d}.txt"
            listfile.write_text(
                "\n".join(f"file '{p.resolve()}'" for p in parts), encoding="utf-8"
            )
            _run([
                ffmpeg_bin(), "-y", "-f", "concat", "-safe", "0",
                "-i", str(listfile), "-c", "copy", str(merged),
            ])
            segment_paths.append(merged)

    # ---- 2. concat scenes ---------------------------------------------
    concat_list = out_dir / "concat.txt"
    concat_list.write_text(
        "\n".join(f"file '{p.resolve()}'" for p in segment_paths), encoding="utf-8"
    )
    silent = out_dir / "video_silent.mp4"
    _run([
        ffmpeg_bin(), "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-r", str(CONFIG.fps), "-an", str(silent),
    ])

    # ---- 3. mux narration (+ optional music) --------------------------
    final_no_subs = out_dir / "final_nosubs.mp4"
    music_inputs: list[str] = []
    music_filter = ""
    if CONFIG.music_enabled and CONFIG.music_dir.exists():
        tracks = sorted(CONFIG.music_dir.glob("*.mp3")) + sorted(CONFIG.music_dir.glob("*.m4a"))
        if tracks:
            music_inputs = ["-i", str(tracks[0])]
            music_filter = (
                f"[2:a]volume={CONFIG.music_volume}[mu];"
                "[1:a][mu]amix=inputs=2:duration=first:dropout_transition=3[aout]"
            )
    audio_map = "[aout]" if music_filter else "1:a"

    cmd = [ffmpeg_bin(), "-y", "-i", str(silent), "-i", str(narration_path)]
    cmd += music_inputs
    if music_filter:
        cmd += ["-filter_complex", music_filter, "-map", "0:v", "-map", audio_map]
    else:
        cmd += ["-map", "0:v", "-map", "1:a"]
    cmd += ["-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(final_no_subs)]
    _run(cmd)

    # ---- 4. optional caption burn -------------------------------------
    final = out_dir / f"{doc.slug}.mp4"
    if CONFIG.burn_captions and srt_path.exists():
        srt_escaped = str(srt_path.resolve()).replace(":", r"\:").replace("'", r"'\''")
        cmd = [
            ffmpeg_bin(), "-y", "-i", str(final_no_subs),
            "-vf", f"subtitles='{srt_escaped}':force_style='FontSize=20,Outline=2,Shadow=0,MarginV=28'",
            "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
            "-c:a", "copy", str(final),
        ]
        try:
            _run(cmd)
        except RuntimeError as exc:
            print(f"[assemble] caption burn unavailable, shipping without burned subs: {exc}")
            shutil.copyfile(final_no_subs, final)
    else:
        shutil.copyfile(final_no_subs, final)

    # ---- 5. run manifest ----------------------------------------------
    manifest = {
        "slug": doc.slug,
        "title": doc.title,
        "scenes": len(segment_paths),
        "scene_durations": scene_durations,
        "output": str(final),
        "width": CONFIG.width,
        "height": CONFIG.height,
        "fps": CONFIG.fps,
    }
    (out_dir / "render_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return final


def scene_durations_from_words(doc: ScriptDoc, narration_duration: float) -> list[float]:
    """Split narration duration across scenes proportionally to word counts."""
    counts = [max(s.narration.split().__len__(), 1) for s in doc.scenes]
    total = float(sum(counts))
    return [narration_duration * c / total for c in counts]
