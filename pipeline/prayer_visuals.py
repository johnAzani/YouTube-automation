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


def sentence_stream(words, *, timing_source):
    if timing_source != 'measured' or not words:
        raise ValueError('Measured speech alignment is required')
    sentences, buf = [], []
    previous = 0.0
    for word, start, end in words:
        if (not word.strip() or not math.isfinite(start) or not math.isfinite(end)
                or start < previous or end <= start):
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
        tokens = [w.upper() for w, _, _ in sentence]
        lines, line = [], ''
        for word in tokens:
            candidate = f'{line} {word}'.strip()
            if line and len(candidate) > 30:
                lines.append(line)
                line = word
            else:
                line = candidate
        if line:
            lines.append(line)
        if len(lines) > 6:
            raise ValueError('Sentence is too long for the widescreen layout')
        start, end = sentence[0][1], sentence[-1][2]
        cards.append(dict(t0=start, t1=end,
                          disp_t0=cards[-1]['t1'] if cards else 0.0,
                          disp_t1=end, lines=lines, accent_words=[], kicker='',
                          word_timings=[(a, b) for _, a, b in sentence]))
    return cards


def render(narration: Path, scenes, words, duration: float, output: Path, *,
           timing_source: str, width=1280, height=720, fps=24):
    """Render local scene paths and measured audio. Caller validates licences.

    This draft renderer does not generate narration, upload, or modify queue state.
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
    with tempfile.TemporaryFile() as errors:
        try:
            encoder = subprocess.Popen([ffmpeg_bin(), '-y', '-loglevel', 'error',
                '-f', 'rawvideo', '-pixel_format', 'rgb24', '-video_size', f'{width}x{height}',
                '-framerate', str(fps), '-i', 'pipe:0', '-i', str(narration),
                '-map', '0:v:0', '-map', '1:a:0', '-t', str(duration), '-c:v', 'libx264',
                '-preset', 'fast', '-crf', '21', '-pix_fmt', 'yuv420p', '-c:a', 'aac',
                '-b:a', '160k', '-movflags', '+faststart', str(temp)],
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
