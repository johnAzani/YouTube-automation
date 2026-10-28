"""Google Gemini AI Voice Synthesis.

Uses Google GenAI API (Gemini 2.0 Flash / Gemini 2.5 Flash) with multimodal audio output
to synthesize cinematic, human-grade voiceover for The Secret Place.

Supported Prebuilt Voices:
- 'Charon': Deep, calm, reverent male voice (ideal for prayer & meditation)
- 'Puck': Warm, thoughtful male voice
- 'Fenrir': Resonant, authoritative male voice
- 'Kore': Gentle, soothing female voice
- 'Aoede': Warm, expressive female voice

Requires GEMINI_API_KEY (or GOOGLE_API_KEY) in environment / GitHub Secrets.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

GEMINI_VOICES = {
    "charon": "Charon",
    "puck": "Puck",
    "fenrir": "Fenrir",
    "kore": "Kore",
    "aoede": "Aoede",
    "Charon": "Charon",
    "Puck": "Puck",
    "Fenrir": "Fenrir",
    "Kore": "Kore",
    "Aoede": "Aoede",
}

DEFAULT_MODEL = "gemini-2.5-flash"
DEFAULT_VOICE = "Charon"
FALLBACK_EDGE_VOICE = "en-US-DavisNeural"


def get_gemini_api_key() -> Optional[str]:
    """Look for Gemini API key across common environment variables and .env file."""
    for key in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        val = os.environ.get(key)
        if val and val.strip():
            return val.strip()

    # Check local .env
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() in ("GEMINI_API_KEY", "GOOGLE_API_KEY") and v.strip():
                return v.strip().strip('"').strip("'")
    return None


def _chunk_text(text: str, max_chars: int = 500) -> list[str]:
    """Split long narrative text at paragraph boundaries into <= max_chars chunks."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [text.strip()]
    chunks: list[str] = []
    curr: list[str] = []
    curr_len = 0
    for p in paragraphs:
        if curr_len + len(p) > max_chars and curr:
            chunks.append("\n\n".join(curr))
            curr = [p]
            curr_len = len(p)
        else:
            curr.append(p)
            curr_len += len(p)
    if curr:
        chunks.append("\n\n".join(curr))
    return chunks or [text]


def _synthesize_single_chunk(
    client,
    text: str,
    voice_name: str,
    system_instruction: str,
    model: str,
    temp_raw: Path,
) -> str:
    """Call Gemini generate_content for a single text chunk and write raw audio bytes."""
    import time
    from google.genai import types

    candidate_models = [model]
    for alt in ("gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash-exp"):
        if alt not in candidate_models:
            candidate_models.append(alt)

    response = None
    last_exc = None
    for cur_model in candidate_models:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model=cur_model,
                    contents=f"{system_instruction}\n\nText to read:\n{text}",
                    config=types.GenerateContentConfig(
                        response_modalities=["AUDIO"],
                        speech_config=types.SpeechConfig(
                            voice_config=types.VoiceConfig(
                                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                    voice_name=voice_name
                                )
                            )
                        ),
                    ),
                )
                break
            except Exception as exc:
                last_exc = exc
                err_msg = str(exc).lower()
                if "404" in err_msg or "not_found" in err_msg:
                    # Model not available; switch to next candidate model immediately
                    print(f"[gemini-tts] Model {cur_model} not available ({exc!r}), trying alternate model...")
                    break
                if "429" in err_msg or "resource_exhausted" in err_msg or "quota" in err_msg:
                    if attempt < max_retries - 1:
                        backoff = (attempt + 1) * 12
                        print(f"[gemini-tts] Rate limit reached (429/ResourceExhausted). Pausing {backoff}s for burst limit to reset...")
                        time.sleep(backoff)
                        continue
                    else:
                        print(f"[gemini-tts] Daily request limit reached on free Gemini tier ({exc!r}).")
                        raise
                raise
        if response:
            break

    if not response and last_exc:
        raise last_exc

    audio_bytes: bytes | None = None
    mime_type: str = "audio/wav"

    if response and response.candidates and response.candidates[0].content:
        for part in response.candidates[0].content.parts:
            if getattr(part, "inline_data", None) and part.inline_data.data:
                data_val = part.inline_data.data
                if isinstance(data_val, str):
                    import base64
                    audio_bytes = base64.b64decode(data_val)
                else:
                    audio_bytes = data_val
                mime_type = part.inline_data.mime_type or "audio/wav"
                break

    if not audio_bytes:
        raise RuntimeError("Gemini API returned no audio content in response.")

    temp_raw.write_bytes(audio_bytes)
    return mime_type


def synthesize_gemini_audio(
    text: str,
    out_path: Path,
    voice: str = DEFAULT_VOICE,
    prompt_style: str = "calm, reverent, peaceful devotional tone",
    model: str = DEFAULT_MODEL,
) -> Path:
    """Synthesize speech using Google Gemini API and write to out_path (.mp3 or .wav)."""
    api_key = get_gemini_api_key()
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Please add GEMINI_API_KEY to your environment, "
            ".env file, or GitHub Repository Secrets."
        )

    from google import genai
    from .assemble import ffmpeg_bin

    client = genai.Client(api_key=api_key)
    voice_name = GEMINI_VOICES.get(voice.lower(), voice)

    system_instruction = (
        f"You are a professional voiceover narrator. Read the provided text aloud in a {prompt_style}. "
        "Do not add any conversational commentary, introductory remarks, or concluding remarks. "
        "Only speak the exact provided words naturally with reverent pacing and appropriate pauses."
    )

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    chunks = _chunk_text(text, max_chars=450)
    if len(chunks) == 1:
        temp_raw = out_path.with_suffix(".raw_audio")
        try:
            mime_type = _synthesize_single_chunk(client, chunks[0], voice_name, system_instruction, model, temp_raw)
            if "pcm" in mime_type.lower() or "raw" in mime_type.lower():
                cmd = [
                    ffmpeg_bin(), "-y",
                    "-f", "s16le", "-ar", "24000", "-ac", "1",
                    "-i", str(temp_raw),
                    "-b:a", "192k", str(out_path)
                ]
            else:
                cmd = [
                    ffmpeg_bin(), "-y",
                    "-i", str(temp_raw),
                    "-b:a", "192k", str(out_path)
                ]
            subprocess.run(cmd, check=True, capture_output=True)
        finally:
            if temp_raw.is_file():
                temp_raw.unlink()
        return out_path

    # Multi-chunk synthesis for longform content
    chunk_wavs: list[Path] = []
    temp_dir = out_path.parent / f"_gemini_chunks_{out_path.stem}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        for idx, chunk in enumerate(chunks):
            chunk_raw = temp_dir / f"chunk_{idx:03d}.raw"
            chunk_wav = temp_dir / f"chunk_{idx:03d}.wav"
            mime_type = _synthesize_single_chunk(client, chunk, voice_name, system_instruction, model, chunk_raw)
            if "pcm" in mime_type.lower() or "raw" in mime_type.lower():
                cmd = [
                    ffmpeg_bin(), "-y",
                    "-f", "s16le", "-ar", "24000", "-ac", "1",
                    "-i", str(chunk_raw),
                    "-ar", "44100", "-ac", "2", str(chunk_wav)
                ]
            else:
                cmd = [
                    ffmpeg_bin(), "-y",
                    "-i", str(chunk_raw),
                    "-ar", "44100", "-ac", "2", str(chunk_wav)
                ]
            subprocess.run(cmd, check=True, capture_output=True)
            chunk_wavs.append(chunk_wav)

        # Concat chunks into final audio file with ffmpeg concat demuxer
        concat_txt = temp_dir / "concat.txt"
        concat_txt.write_text("\n".join(f"file '{p.resolve()}'" for p in chunk_wavs), encoding="utf-8")
        concat_cmd = [
            ffmpeg_bin(), "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_txt),
            "-c:a", "libmp3lame" if out_path.suffix.lower() == ".mp3" else "aac",
            "-b:a", "192k", str(out_path)
        ]
        subprocess.run(concat_cmd, check=True, capture_output=True)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    return out_path
