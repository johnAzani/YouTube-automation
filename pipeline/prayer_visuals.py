"""Widescreen prayer rendering from the approved Psalm 91 Shorts graphics.

The live queue remains locked until real Charon audio and word alignment have
been verified end to end. No estimated timestamps are accepted here.
"""
from __future__ import annotations

import math
import re
import subprocess
import tempfile
from pathlib import Path

from PIL import Image
from .assemble import ffmpeg_bin


MAX_LINES_PER_CARD = 3   # DOCOGA REELS v2 bold 2-3 line display cards (never 6-line walls)
LONGFORM_MUSIC_VOLUME = 0.58  # exact Shorts background music mix level (tools/shorts.py)


def build_prayer_music_score(duration: float, scenes, words, out_dir: Path) -> Path:
    """Synthesize the exact Shorts background music score (`tools/score.py`) for long-form."""
    from tools.score import generate_score

    cuts = [0.0]
    acc = 0.0
    for _path, sec in scenes[:-1]:
        acc += float(sec)
        if 0.0 < acc < duration:
            cuts.append(acc)

    hushes = []
    for word, start, end in words:
        cleaned = re.sub(r"[^a-z]", "", word.lower())
        if cleaned in {"amen", "selah"} and start > 1.0:
            hushes.append(
                {
                    "t": float(start),
                    "dur": min(1.2, max(0.35, float(end) - float(start))),
                    "depth": 0.55,
                    "lead": 0.45,
                }
            )

    key = "prayer-longform"
    generate_score(key, float(duration), cuts, [], [], hushes, out_dir=str(out_dir))
    return Path(out_dir) / f"music-{key}.wav"


def sentence_stream(words, *, timing_source):
    if timing_source != 'measured' or not words:
        raise ValueError('Measured speech alignment is required')
    sentences, buf = [], []
    previous = 0.0
    for word, start, end in words:
        if (not word.strip() or not math.isfinite(start) or not math.isfinite(end)
                or start < previous or end < start):
            raise ValueError('Invalid or overlapping word boundaries')
        buf.append((word, start, end))
        previous = end
        if re.search(r'[.!?][\"\'”’)]*$', word):
            sentences.append(buf)
            buf = []
    if buf:
        sentences.append(buf)
    cards = []
    for sentence in sentences:
        # Wrap into display lines, then paginate those lines onto cards.
        #
        # This used to raise 'Sentence is too long for the widescreen layout' once a
        # sentence needed more than six lines. That was survivable while scripts were
        # 250 words of short sentences. The moment the script reached full length the
        # expansion started writing real prayer sentences — "Father, when the day has
        # left us feeling small, remind us that the hills are not higher than Your
        # compassion..." — and the renderer refused to draw the video at all. A long
        # sentence is not an error; it is two cards.
        lines: list[tuple[str, list[tuple[float, float]]]] = []
        line_text, line_timings = "", []
        for word, start, end in sentence:
            token = word.upper()
            candidate = f'{line_text} {token}'.strip()
            if line_text and len(candidate) > 30:
                lines.append((line_text, line_timings))
                line_text, line_timings = token, [(start, end)]
            else:
                line_text, line_timings = candidate, line_timings + [(start, end)]
        if line_text:
            lines.append((line_text, line_timings))

        for offset in range(0, len(lines), MAX_LINES_PER_CARD):
            chunk = lines[offset:offset + MAX_LINES_PER_CARD]
            timings = [timing for _, these in chunk for timing in these]
            start, end = timings[0][0], timings[-1][1]
            cards.append(dict(t0=start, t1=end,
                              disp_t0=cards[-1]['t1'] if cards else 0.0,
                              disp_t1=end, lines=[text for text, _ in chunk],
                              accent_words=[], kicker='', word_timings=timings))
    return cards


def render(narration: Path, scenes, words, duration: float, output: Path, *,
           timing_source: str, width=1280, height=720, fps=24, progress=None):
    """Render local scene paths and measured audio. Caller validates licences.

    This draft renderer does not generate narration, upload, or modify queue state.

    `progress`, when given, is called with the number of frames written so far.
    A render is the longest stage in a release and used to report nothing at all
    until it finished, which is how three renders were mistaken for hangs. It is
    called once per frame and the caller does the throttling, so it must stay
    cheap; passing None keeps the behaviour byte-for-byte as before.
    """
    from tools.shorts import grade_sanctuary, hud_chapter_layer, kinetic_typography_layer, camera_frame
    if width <= 0 or height <= 0 or width % 2 or height % 2 or width * 9 != height * 16:
        raise ValueError('Output must be even-sized 16:9')
    if not isinstance(fps, int) or not 1 <= fps <= 60 or not math.isfinite(duration) or duration <= 0:
        raise ValueError('Invalid duration or frame rate')
    narration, output = Path(narration), Path(output)
    scenes = [(Path(p), float(d)) for p, d in scenes]
    if not narration.is_file() or output.suffix.lower() != '.mp4':
        raise ValueError('Valid narration and MP4 output required')
    if not scenes or any(not p.is_file() or not math.isfinite(d) or d <= 0 for p, d in scenes):
        raise ValueError('Each scene needs an existing asset and positive duration')
    if sum(d for _, d in scenes) < duration - 0.001:
        raise ValueError('Scenes do not cover narration')
    if output.resolve() in {narration.resolve(), *(p.resolve() for p, _ in scenes)}:
        raise ValueError('Output cannot overwrite an input')
    cards = sentence_stream(words, timing_source=timing_source)
    if words[-1][2] > duration + .05:
        raise ValueError('Word boundaries extend past narration')
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_name(output.stem + '.partial.mp4')
    frames = math.ceil(duration * fps)
    size = width * height * 3
    decoder = encoder = None
    index = 0
    elapsed = 0.0
    fade_in = min(0.8, max(0.05, duration * 0.10))
    fade_out = min(2.4, max(0.10, duration * 0.25))
    fade_out_st = max(0.0, duration - fade_out)
    # Voice mastering and music ducking live in pipeline/voice_master.py. The
    # narration file is only measured here, never rewritten, so its checksum,
    # cached chunks and word alignment are untouched. If the measurement fails
    # the filter returned is the previous, unmastered mix.
    from .voice_master import mix_filter
    audio_filter = mix_filter(
        narration,
        f"volume={LONGFORM_MUSIC_VOLUME:.2f},"
        f"afade=t=in:st=0:d={fade_in:.2f},"
        f"afade=t=out:st={fade_out_st:.2f}:d={fade_out:.2f}",
    )
    with tempfile.TemporaryDirectory() as score_tmp, tempfile.TemporaryFile() as errors:
        try:
            music_wav = build_prayer_music_score(duration, scenes, words, Path(score_tmp))
            encoder = subprocess.Popen([ffmpeg_bin(), '-y', '-loglevel', 'error',
                '-f', 'rawvideo', '-pixel_format', 'rgb24', '-video_size', f'{width}x{height}',
                '-framerate', str(fps), '-i', 'pipe:0', '-i', str(narration), '-i', str(music_wav),
                '-filter_complex', audio_filter,
                '-map', '0:v:0', '-map', '[a]', '-t', str(duration), '-c:v', 'libx264',
                '-profile:v', 'high', '-preset', 'fast', '-crf', '21', '-pix_fmt', 'yuv420p',
                '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-color_range', 'tv',
                '-c:a', 'aac', '-ar', '48000', '-b:a', '192k',
                '-metadata:s:v:0', 'language=eng', '-metadata:s:a:0', 'language=eng',
                '-movflags', '+faststart', str(temp)],
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=errors)
            for scene_index, (path, seconds) in enumerate(scenes):
                scene_start = elapsed
                elapsed += seconds
                stop = frames if elapsed >= duration else min(frames, round(elapsed * fps))
                if stop <= index:
                    continue
                image = path.suffix.lower() in {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}
                loop = ['-loop', '1', '-framerate', str(fps)] if image else ['-stream_loop', '-1']
                decoder = subprocess.Popen([ffmpeg_bin(), '-loglevel', 'error', *loop,
                    '-i', str(path), '-an', '-vf', f'scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1,fps={fps}',
                    '-frames:v', str(stop - index), '-f', 'rawvideo', '-pix_fmt', 'rgb24', 'pipe:1'],
                    stdout=subprocess.PIPE, stderr=errors)
                while index < stop:
                    raw = bytearray()
                    while len(raw) < size:
                        chunk = decoder.stdout.read(size - len(raw))
                        if not chunk:
                            raise RuntimeError(f'Incomplete frame from {path}')
                        raw.extend(chunk)
                    frame = grade_sanctuary(Image.frombytes('RGB', (width, height), bytes(raw)))
                    t = index / fps
                    frame = camera_frame(frame, (t - scene_start) / seconds, canvas_size=(width, height))
                    overlay = hud_chapter_layer(frame, 'THE SECRET PLACE', 'PRAYER AND SCRIPTURE',
                        scene_index + 1, len(scenes), t - scene_start, seconds, t / duration,
                        is_prayer=True, canvas_size=(width, height))
                    overlay.alpha_composite(kinetic_typography_layer(frame, cards, t, is_prayer=True,
                                                                    canvas_size=(width, height)))
                    encoder.stdin.write(Image.alpha_composite(frame.convert('RGBA'), overlay).convert('RGB').tobytes())
                    index += 1
                    if progress is not None:
                        progress(index)
                decoder.stdout.close()
                if decoder.wait():
                    raise RuntimeError(f'Decoder failed for {path}')
                decoder = None
                if index >= frames:
                    break
            if index < frames:
                raise RuntimeError('Scenes ended before narration')
            encoder.stdin.close()
            if encoder.wait():
                raise RuntimeError('Encoder failed')
            encoder = None
            temp.replace(output)
            return output
        except Exception as exc:
            for proc in (decoder, encoder):
                if proc and proc.poll() is None:
                    proc.kill()
                    proc.wait()
            temp.unlink(missing_ok=True)
            errors.seek(0)
            detail = errors.read().decode(errors='replace')[-1500:]
            raise RuntimeError(f'Prayer rendering failed: {exc}\n{detail}') from exc
