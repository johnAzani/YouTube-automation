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

DEFAULT_MODEL = "gemini-2.0-flash"
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
    from google.genai import types

    client = genai.Client(api_key=api_key)
    voice_name = GEMINI_VOICES.get(voice.lower(), voice)

    system_instruction = (
        f"You are a professional voiceover narrator. Read the provided text aloud in a {prompt_style}. "
        "Do not add any conversational commentary, introductory remarks, or concluding remarks. "
        "Only speak the exact provided words naturally with reverent pacing and appropriate pauses."
    )

    import time

    max_retries = 3
    response = None
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model,
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
            err_msg = str(exc).lower()
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

    audio_bytes: bytes | None = None
    mime_type: str = "audio/wav"

    if response.candidates and response.candidates[0].content:
        for part in response.candidates[0].content.parts:
            if getattr(part, "inline_data", None) and part.inline_data.data:
                audio_bytes = part.inline_data.data
                mime_type = part.inline_data.mime_type or "audio/wav"
                break

    if not audio_bytes:
        raise RuntimeError("Gemini API returned no audio content in response.")

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # If raw PCM or WAV, convert via ffmpeg to ensure compatibility with out_path extension
    from .assemble import ffmpeg_bin
    temp_raw = out_path.with_suffix(".raw_audio")
    temp_raw.write_bytes(audio_bytes)

    try:
        # Check if raw PCM or standard audio container
        if "pcm" in mime_type.lower() or "raw" in mime_type.lower():
            # Standard Gemini raw audio is 24kHz 16-bit mono little-endian PCM
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
