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

DEFAULT_MODEL = "gemini-3.8-flash-tts"
DEFAULT_VOICE = "Charon"
FALLBACK_EDGE_VOICE = "en-US-DavisNeural"


def gemini_key_names(channel_id: str | None = None) -> list[str]:
    """Env names checked for a channel's Gemini key, in priority order.

    Each channel owns a separate Gemini project/quota pool (see
    pipeline/channels.py): `prayer2` reads PRAYER2_GEMINI_API_KEY first.
    The canonical GEMINI_API_KEY / GOOGLE_API_KEY remain fallbacks because
    workflows map the selected channel's secret onto GEMINI_API_KEY, and
    channel 1 (secret-place) is unprefixed by design.
    """
    names: list[str] = []
    if channel_id:
        try:
            from .channels import get_channel
            prefixed = get_channel(channel_id).secret_name("GEMINI_API_KEY")
            if prefixed not in names:
                names.append(prefixed)
        except Exception:
            pass
    for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        if name not in names:
            names.append(name)
    return names


def get_gemini_api_key(channel_id: str | None = None) -> Optional[str]:
    """Look for Gemini API key across common environment variables and .env file."""
    names = gemini_key_names(channel_id)
    for key in names:
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
            if k.strip() in names and v.strip():
                return v.strip().strip('"').strip("'")
    return None


#: Characters per TTS request. This is a *quota* setting, not a technical one.
#:
#: The free tier allows **10 generateContent requests per day** for
#: `gemini-3.8-flash-tts` — Google's own refusal on 3 November named the metric and
#: the limit. An 888-word prayer is ~5,200 characters, so the old 450-character
#: chunking asked for **thirteen** requests to narrate one video: more than the
#: entire daily budget, which is why releases burned all ten requests on a single
#: video and then paused themselves until the next reset.
#:
#: At 4,000 characters a six-minute prayer is two requests, a Short is one, and a
#: day can carry a long-form and a Short with room for a retry. Override with
#: `TTS_CHUNK_CHARS` if the model needs smaller input.
DEFAULT_CHUNK_CHARS = 4000


def chunk_chars() -> int:
    raw = os.environ.get("TTS_CHUNK_CHARS", "").strip()
    if raw:
        try:
            value = int(raw)
            if 500 <= value <= 20000:
                return value
        except ValueError:
            pass
    return DEFAULT_CHUNK_CHARS


def _chunk_cache_key(voice_name: str, model: str, chunk: str) -> str:
    """Cache identity of one synthesized chunk.

    Includes the delivery recipe — v1/v2/v3 chunks are worthless no
    matter how well the script text matches, because the recipe (what
    else reached the model, and how) is what made them defective.
    """
    import hashlib

    return hashlib.sha256(
        f"{DELIVERY_RECIPE}:{voice_name}:{model}:{chunk}".encode("utf-8")
    ).hexdigest()


def build_tts_part(text: str, prompt_style: str):
    """One generate_content part: verbatim transcript + style metadata.

    `text` is the script chunk and nothing else — no instruction, no
    fence, no marker. Delivery lives in speech_metadata.style, the
    channel Google documents for Gemini 3.8 TTS style direction.
    """
    from google.genai import types

    return types.Part(
        text=text,
        speech_metadata=types.SpeechMetadata(style=style_text(prompt_style)),
    )


def build_interactions_content(text: str, prompt_style: str) -> list[dict]:
    """One interactions content block: verbatim transcript + annotation.

    The interactions schema's equivalent of speech_metadata is a
    `speech_metadata` annotation on the text content (style instruction
    for the speech synthesis). The text itself stays byte-for-byte the
    script chunk.
    """
    return [
        {
            "type": "text",
            "text": text,
            "annotations": [
                {
                    "type": "speech_metadata",
                    "start_index": 0,
                    "end_index": len(text.encode("utf-8")),
                    "style": style_text(prompt_style),
                }
            ],
        }
    ]


def build_interactions_speech_config(voice_name: str, prompt_style: str) -> list[dict]:
    """interactions generation_config speech entries (voice + style).

    The speech_config schema carries only language/speaker/voice, so the
    style also rides here as an annotation-shaped entry when accepted;
    the authoritative carrier is the content annotation above.
    """
    return [{"voice": voice_name}]


def _chunk_text(text: str, max_chars: int = 500) -> list[str]:
    """Split long narrative text at paragraph boundaries into <= max_chars chunks."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [text.strip()]
    # A single paragraph can be longer than the limit; split it at sentence ends so
    # the cap is real rather than advisory.
    split: list[str] = []
    for p in paragraphs:
        while len(p) > max_chars:
            cut = p.rfind(". ", 0, max_chars)
            cut = cut + 1 if cut > max_chars // 2 else max_chars
            split.append(p[:cut].strip())
            p = p[cut:].strip()
        if p:
            split.append(p)
    paragraphs = split or paragraphs

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


def _convert_raw_audio(temp_raw: Path, out_path: Path, mime_type: str = "") -> None:
    """Robustly convert raw audio bytes from Gemini to target container (mp3/wav)."""
    from .assemble import ffmpeg_bin

    # 1. First try raw PCM 24kHz s16le (Gemini's native audio stream format)
    try:
        cmd = [
            ffmpeg_bin(), "-y",
            "-f", "s16le", "-ar", "24000", "-ac", "1",
            "-i", str(temp_raw),
            "-ar", "44100", "-b:a", "192k", str(out_path)
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode == 0 and out_path.exists() and out_path.stat().st_size > 512:
            return
    except Exception:
        pass

    # 2. Try container auto-detect (if Gemini returned a formatted WAV/MP3 header)
    try:
        cmd = [
            ffmpeg_bin(), "-y",
            "-i", str(temp_raw),
            "-ar", "44100", "-b:a", "192k", str(out_path)
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode == 0 and out_path.exists() and out_path.stat().st_size > 512:
            return
    except Exception:
        pass

    # 3. Fallback to 16kHz s16le
    cmd = [
        ffmpeg_bin(), "-y",
        "-f", "s16le", "-ar", "16000", "-ac", "1",
        "-i", str(temp_raw),
        "-ar", "44100", "-b:a", "192k", str(out_path)
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def _emit(message: str) -> None:
    """Progress line, best effort: narration must never fail on logging."""
    try:
        from .progress import emit
        emit(message)
    except Exception:  # noqa: BLE001
        print(f"[gemini-tts] {message}", flush=True)


#: Set once a chunk stalls on the `interactions` transport. Every later chunk in
#: this process then uses `models.generate_content`, which honours the request
#: timeout — one bad transport must not cost twelve stalls.
_INTERACTIONS_STALLED = False


#: Backoff for temporary upstream trouble. Short on purpose: a 172-second video
#: is twelve chunks, and a two-minute sleep per chunk would eat the step budget.
_BACKOFF = (5, 15, 45)


_DRIFT_REPORTED = False


def _schema_drift(exc: BaseException) -> bool:
    """Is this the service rejecting our request *shape*?

    "Unknown name X ... Cannot find field" means the payload no longer matches the
    endpoint. It is never a quota problem and never fixes itself by retrying; it is
    the SDK or the model contract moving. On 6 November 2026 this arrived as
    `google-genai 3.0.0` (published 02:29 UTC) and took narration down mid-morning:
    nothing in this repository had changed.
    """
    text = str(exc).lower()
    return "unknown name" in text or "cannot find field" in text


_MODEL_IN_TEXT = None


def suggested_model(*texts: str) -> str | None:
    """The model the service tells us to use, if it names one.

    Gemini replies in prose when a model is withdrawn — "Please update your code to
    use models/gemini-3.8-flash" — and a voice call that comes back as *text* is the
    same message in a different wrapper. Reading it and retrying once beats
    failing with "no audio content" and leaving a human to guess the new name.
    """
    import re

    global _MODEL_IN_TEXT
    if _MODEL_IN_TEXT is None:
        _MODEL_IN_TEXT = re.compile(r"models/([A-Za-z0-9][A-Za-z0-9.\-]+)")
    for text in texts:
        if not text:
            continue
        match = _MODEL_IN_TEXT.search(str(text))
        if match:
            return match.group(1)
    return None


def _response_parts(response) -> tuple[str, list[str]]:
    """(any text the model returned, per-part mime types) — evidence, not a guess."""
    text_parts: list[str] = []
    mimes: list[str] = []
    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        for part in (getattr(content, "parts", None) or []):
            inline = getattr(part, "inline_data", None)
            if inline is not None:
                mimes.append(str(getattr(inline, "mime_type", "?") or "?"))
            if getattr(part, "text", None):
                text_parts.append(str(part.text))
    return (" ".join(text_parts).strip(), mimes)


def _report_drift(exc: BaseException) -> None:
    """Say what happened, once, where a human will see it."""
    global _DRIFT_REPORTED
    if _DRIFT_REPORTED:
        return
    _DRIFT_REPORTED = True
    print(f"::error title=Gemini TTS rejected the request shape::{exc} — this is SDK or "
          f"model-contract drift, not quota and not retryable. Check the google-genai "
          f"pin in requirements.txt (>=2.34,<3 exists because 3.0.0 broke exactly this) "
          f"and the TTS model name. Retrying will not fix it; the run stops here.")


def _transient(exc: BaseException) -> bool:
    """Is this worth another attempt, or is it a real refusal?

    503 UNAVAILABLE ("This model is currently experiencing high demand") is
    temporary and extremely common on the free TTS tier at peak hours. It used to
    propagate straight out of the release, so one overloaded minute on Google's
    side cost the whole 170-minute slot — twice on 3 November.
    """
    text = f"{type(exc).__name__} {exc}".lower()
    if any(marker in text for marker in ("429", "resource_exhausted", "quota")):
        return False          # quota is handled by quota_handler, not by sleeping
    if any(marker in text for marker in ("503", "500", "502", "504", "unavailable",
                                         "overloaded", "high demand", "deadline",
                                         "timeout", "timed out", "connection reset",
                                         "remoteprotocol", "internal error")):
        return True
    return False


def _transient_label(exc: BaseException) -> str:
    text = f"{type(exc).__name__}: {exc}"
    for marker in ("503", "500", "502", "504"):
        if marker in text:
            return f"Gemini returned HTTP {marker}"
    if "timeout" in text.lower() or "timed out" in text.lower():
        return "Gemini timed out"
    return "Gemini was temporarily unavailable"


def style_text(prompt_style: str = "calm, reverent, peaceful devotional tone") -> str:
    """Delivery style for the voice — carried ONLY in speech_metadata.style.

    Gemini 3.8 TTS models read the `text` of each part as a verbatim
    transcript (Google's migration guide: "directions written into the
    text might be spoken aloud… Put sustained acting, tone, prosody, and
    pacing directions in speech_metadata.style"). Every earlier carrier
    has been owner-verified to leak into the audio:

    * "Text to read:" prefix in `contents` — Psalm 27 (7ll7w1hYf7o)
    * fenced read-aloud contract in every payload — Psalm 5 (oS7f32WDj_Y)
    * GenerateContentConfig.system_instruction — Psalm 5 replacement
      (R8mVvedhYVw). A TTS model has no conversational frame in which a
      "system instruction" stays unspoken; three defective uploads trace
      to instruction-shaped text reaching the model at all. The style
      string is therefore short delivery adjectives, never imperative
      sentences addressed to the model.

    Narration cache keys and chunk hashes are versioned by
    DELIVERY_RECIPE, so changing any of this invalidates every cached
    chunk — see _chunk_cache_key.
    """
    return prompt_style


#: Version of the full delivery recipe: model-facing style carrier +
#: style string + chunking. Bump whenever the recipe changes; it is mixed
#: into every narration fingerprint and per-chunk cache hash so no audio
#: synthesized under an older recipe can ever be reused.
DELIVERY_RECIPE = "tts-v4-speech-metadata-style"


def _guarded_chunk(client, text, voice_name, prompt_style, model, temp_raw,
                   index, total):
    """One chunk, with a deadline the transport cannot ignore.

    A stalled chunk is retried once — a dead connection is worth one more go —
    and then abandoned by name, so the release fails at "TTS chunk 7/12" instead
    of sitting silently inside chunk 7 until the step is killed.
    """
    from .gemini_client import GeminiRequestTimedOut, hard_deadline, http_timeout_seconds

    label = f"TTS chunk {index}/{total}"
    last = None
    for attempt in (1, 2, 3):
        try:
            with hard_deadline(http_timeout_seconds(), label):
                return _synthesize_single_chunk(client, text, voice_name, prompt_style,
                                                 model, temp_raw)
        except GeminiRequestTimedOut as exc:
            global _INTERACTIONS_STALLED
            last = exc
            # Demote the transport for the rest of this process: the next chunk
            # goes straight to the path that honours the request timeout instead
            # of paying another full stall to learn the same lesson.
            _INTERACTIONS_STALLED = True
            _emit(f"{label} stalled on attempt {attempt}: {exc}")
            if attempt < 3:
                continue
        except Exception as exc:  # noqa: BLE001 - classify, then decide
            from .gemini_client import GeminiRequestTimedOut as _Timeout

            if isinstance(exc, _Timeout):
                raise
            # Only temporary upstream trouble is retried here; a quota refusal and
            # a bad request must fail fast so the caller can pause the job.
            if not _transient(exc):
                raise
            last = exc
            _emit(f"{label} attempt {attempt} hit {_transient_label(exc)}")
            if attempt < 3:
                import time as _t
                wait = _BACKOFF[min(attempt - 1, len(_BACKOFF) - 1)]
                _emit(f"{label} retrying in {wait}s")
                _t.sleep(wait)
                continue
    raise last


#: Charon's pace, used only to notice a *truncated* result.
WORDS_PER_MINUTE = 145


def _is_daily_quota_error(err_lower: str) -> bool:
    """True when Gemini explicitly reports daily free-tier exhaustion vs RPM burst."""
    daily_tokens = (
        "per_day",
        "perday",
        "requests per day",
        "per day",
        "daily quota",
        "daily limit",
        "generaterequestsperday",
    )
    return any(tok in err_lower for tok in daily_tokens)


def _assert_not_truncated(audio: Path, text: str) -> None:
    """Refuse audio far shorter than the words it is meant to contain.

    One 4,000-character request is the only way to fit a six-minute prayer inside a
    ten-request day, so the risk moves: if the model truncates a long answer we must
    not publish the first three minutes of a prayer and call it the whole thing.
    This is a floor, not a fine measurement.
    """
    from .tts import _probe_duration

    words = len(text.split())
    if words < 50:
        return
    expected = words / WORDS_PER_MINUTE * 60
    actual = _probe_duration(audio)
    if actual is None:
        return
    _emit(f"narration is {actual:.0f}s for {words} words (expected ~{expected:.0f}s)")
    if actual < expected * 0.7:
        raise RuntimeError(
            f"Narration came back truncated: {actual:.0f}s of audio for {words} words, "
            f"when Charon needs ~{expected:.0f}s. Send it in smaller TTS_CHUNK_CHARS "
            f"pieces rather than publishing a partial prayer."
        )


def _synthesize_single_chunk(
    client,
    text: str,
    voice_name: str,
    prompt_style: str,
    model: str,
    temp_raw: Path,
) -> str:
    """Call Gemini generate_content or interactions for a single text chunk and write raw audio bytes."""
    import time
    from google.genai import types

    # 1. Try modern Interactions API if available (Gemini TTS standard)
    global _INTERACTIONS_STALLED
    if hasattr(client, "interactions") and not _INTERACTIONS_STALLED:
        for tts_model in (model,):
            try:
                from .gemini_client import http_timeout_seconds

                # `interactions` builds its own httpx client whose default is
                # `Timeout(timeout=None, connect=5.0)` — bounded to connect,
                # unbounded to read. Passing `timeout` here is the only thing that
                # bounds the response for this path.
                interaction = client.interactions.create(
                    timeout=http_timeout_seconds(),
                    model=tts_model,
                    input=[{
                        "type": "user_input",
                        "content": build_interactions_content(text, prompt_style),
                    }],
                    response_format={"type": "audio"},
                    generation_config={"speech_config": [{"voice": voice_name}]},
                )
                output_audio = getattr(interaction, "output_audio", None)
                if output_audio and getattr(output_audio, "data", None):
                    data_val = output_audio.data
                    if isinstance(data_val, str):
                        import base64
                        temp_raw.write_bytes(base64.b64decode(data_val))
                    else:
                        temp_raw.write_bytes(data_val)
                    mime_type = getattr(output_audio, "mime_type", "audio/pcm;rate=24000") or "audio/pcm"
                    return mime_type
            except Exception as exc:
                from .gemini_client import GeminiRequestTimedOut

                # A stall is not "this transport is unavailable": falling through
                # to the next path silently is what let a hang look like a slow
                # synthesis for 170 minutes. Report it and let the retry wrapper
                # decide.
                if isinstance(exc, GeminiRequestTimedOut):
                    raise
                error = str(exc).lower()
                if any(x in error for x in ("429", "resource_exhausted", "quota")):
                    from pipeline.quota_handler import GeminiQuotaExceededError, calculate_next_quota_reset_utc
                    if _is_daily_quota_error(error):
                        raise GeminiQuotaExceededError(str(exc), reset_utc=calculate_next_quota_reset_utc()) from exc
                    # 3-RPM burst rate limit on interactions.create: wait for the
                    # 60s rolling window before declaring the whole day exhausted.
                    last_burst = exc
                    for burst_idx, burst_wait in enumerate((12, 22, 30), start=1):
                        print(f"[gemini-tts] interactions burst rate limit (attempt {burst_idx}/3); "
                              f"pausing {burst_wait}s for RPM window...", flush=True)
                        time.sleep(burst_wait)
                        try:
                            interaction = client.interactions.create(
                                timeout=http_timeout_seconds(),
                                model=tts_model,
                                input=[{"type": "user_input",
                                        "content": build_interactions_content(text, prompt_style)}],
                                response_format={"type": "audio"},
                                generation_config={"speech_config": [{"voice": voice_name}]},
                            )
                        except Exception as burst_again:  # noqa: BLE001
                            last_burst = burst_again
                            again_low = str(burst_again).lower()
                            if _is_daily_quota_error(again_low):
                                break
                            if any(x in again_low for x in ("429", "resource_exhausted", "quota")):
                                continue
                            raise
                        output_audio = getattr(interaction, "output_audio", None)
                        if output_audio and getattr(output_audio, "data", None):
                            data_val = output_audio.data
                            if isinstance(data_val, str):
                                import base64
                                temp_raw.write_bytes(base64.b64decode(data_val))
                            else:
                                temp_raw.write_bytes(data_val)
                            return (getattr(output_audio, "mime_type",
                                            "audio/pcm;rate=24000") or "audio/pcm")
                    raise GeminiQuotaExceededError(
                        str(last_burst), reset_utc=calculate_next_quota_reset_utc()
                    ) from last_burst
                if _transient(exc):
                    # 503 UNAVAILABLE ("high demand") is the single most common TTS
                    # failure at peak and it is *temporary*. Treating it like an
                    # unsupported transport threw away a whole release slot on
                    # 3 November; wait and try again instead.
                    last = exc
                    for wait in _BACKOFF:
                        print(f"[gemini-tts] {_transient_label(exc)} — retrying "
                              f"interactions in {wait}s", flush=True)
                        time.sleep(wait)
                        try:
                            interaction = client.interactions.create(
                                timeout=http_timeout_seconds(),
                                model=tts_model,
                                input=[{"type": "user_input",
                                        "content": build_interactions_content(text, prompt_style)}],
                                response_format={"type": "audio"},
                                generation_config={"speech_config": [{"voice": voice_name}]},
                            )
                        except Exception as again:  # noqa: BLE001
                            last = again
                            if not _transient(again):
                                break
                            continue
                        output_audio = getattr(interaction, "output_audio", None)
                        if output_audio and getattr(output_audio, "data", None):
                            data_val = output_audio.data
                            if isinstance(data_val, str):
                                import base64
                                temp_raw.write_bytes(base64.b64decode(data_val))
                            else:
                                temp_raw.write_bytes(data_val)
                            return (getattr(output_audio, "mime_type",
                                            "audio/pcm;rate=24000") or "audio/pcm")
                    print(f"[gemini-tts] interactions still failing after retries: {last!r}",
                          flush=True)
                    if _schema_drift(last or exc):
                        _report_drift(last or exc)
                else:
                    print(f"[gemini-tts] interactions.create({tts_model}) unavailable: {exc!r}")
                    if _schema_drift(exc):
                        _report_drift(exc)

    # 2. Try models.generate_content with AUDIO modality across candidate audio models.
    #
    # One redirect is allowed. When a model is withdrawn the service answers with
    # prose naming its replacement ("Please update your code to use
    # models/gemini-3.8-flash"), as a 404 for text and as *text in place of audio*
    # for speech. Reading that suggestion and retrying once is the difference between
    # a self-healing pipeline and a morning spent guessing a model name.
    response = None
    last_exc = None
    cur_model = model
    for redirect in range(2):
        max_retries = 1 + len(_BACKOFF)
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model=cur_model,
                    contents=build_tts_part(text, prompt_style),
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
                if _schema_drift(exc):
                    _report_drift(exc)
                if "404" in err_msg or "not_found" in err_msg or "only supports text" in err_msg or "invalid_argument" in err_msg:
                    print(f"[gemini-tts] Model {cur_model} unavailable; no alternate model is permitted: {exc!r}")
                    break
                if _transient(exc):
                    if attempt < max_retries - 1:
                        backoff = _BACKOFF[min(attempt, len(_BACKOFF) - 1)]
                        print(f"[gemini-tts] {_transient_label(exc)}. Retrying in "
                              f"{backoff}s (attempt {attempt + 2}/{max_retries})...", flush=True)
                        time.sleep(backoff)
                        continue
                if "429" in err_msg or "resource_exhausted" in err_msg or "quota" in err_msg:
                    if not _is_daily_quota_error(err_msg) and attempt < max_retries - 1:
                        backoff = (attempt + 1) * 8
                        print(f"[gemini-tts] Rate limit reached. Pausing {backoff}s for burst limit to reset...")
                        time.sleep(backoff)
                        continue
                    else:
                        from pipeline.quota_handler import GeminiQuotaExceededError, calculate_next_quota_reset_utc
                        reset_dt = calculate_next_quota_reset_utc()
                        print(f"[gemini-tts] Google Gemini free tier daily quota exhausted ($0.00 lock active). Pausing until reset at {reset_dt.isoformat()} UTC.")
                        raise GeminiQuotaExceededError(
                            f"Google Gemini daily free tier limit reached: {exc!r}",
                            reset_utc=reset_dt,
                        ) from exc
                raise
        if not response:
            break

        audio_bytes: bytes | None = None
        mime_type: str = "audio/wav"
        candidates = getattr(response, "candidates", None) or []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            for part in (getattr(content, "parts", None) or []):
                inline = getattr(part, "inline_data", None)
                if inline is not None and getattr(inline, "data", None):
                    data_val = inline.data
                    if isinstance(data_val, str):
                        import base64
                        audio_bytes = base64.b64decode(data_val)
                    else:
                        audio_bytes = data_val
                    mime_type = getattr(inline, "mime_type", None) or "audio/wav"
                    break
            if audio_bytes:
                break
        if audio_bytes:
            break

        # No audio. Report the evidence instead of a bare sentence, then take the
        # service's own advice about which model to use, if it gave any.
        text_back, mimes = _response_parts(response)
        detail = f"model={cur_model} mime_types={mimes or 'none'}"
        if text_back:
            detail += f" text={text_back[:300]!r}"
        print(f"::error title=Gemini TTS returned no audio::{detail}")
        hint = suggested_model(text_back)
        if hint and hint != cur_model and redirect == 0:
            print(f"[gemini-tts] the service names {hint!r} as the replacement for "
                  f"{cur_model!r}; retrying once with it")
            cur_model = hint
            response = None
            continue
        raise RuntimeError(
            f"Gemini API returned no audio content for model {cur_model} "
            f"(mime_types={mimes or 'none'}"
            + (f", text={text_back[:200]!r}" if text_back else "")
            + "). Set GEMINI_TTS_MODEL or update DEFAULT_MODEL in pipeline/gemini_tts.py."
        )

    if not response and last_exc:
        raise last_exc

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

    from .assemble import ffmpeg_bin
    from .gemini_client import (Deadline, hard_deadline, http_timeout_seconds,
                                make_client, stage_budget_seconds)

    # Bounded per request AND bounded as a stage. Without the first, one stalled
    # socket can consume the whole release step and print nothing (0017, run
    # 41495990952, killed at its 90-minute cap); without the second, twelve slow
    # calls add up to the same thing.
    client = make_client(api_key)
    budget = Deadline(stage_budget_seconds(900), "speech synthesis")
    voice_name = GEMINI_VOICES.get(voice.lower(), voice)

    style = style_text(prompt_style)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    limit = chunk_chars()
    chunks = _chunk_text(text, max_chars=limit)
    # The arithmetic that matters under a 10-request-per-day quota, printed before
    # the first call, so the run page answers "does this even fit today".
    _emit(f"narration is {len(text)} characters → {len(chunks)} TTS request(s) "
          f"of up to {limit} characters")
    if len(chunks) == 1:
        budget.check("single chunk")
        temp_raw = out_path.with_suffix(".raw_audio")
        try:
            mime_type = _guarded_chunk(client, chunks[0], voice_name, style,
                                       model, temp_raw, 1, 1)
            with hard_deadline(http_timeout_seconds(), "audio conversion"):
                _convert_raw_audio(temp_raw, out_path, mime_type)
        finally:
            if temp_raw.is_file():
                temp_raw.unlink()
        _assert_not_truncated(out_path, text)
        return out_path

    # Multi-chunk synthesis for longform content
    import hashlib
    chunk_wavs: list[Path] = []
    temp_dir = out_path.parent / f"_gemini_chunks_{out_path.stem}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        for idx, chunk in enumerate(chunks):
            budget.check(f"chunk {idx + 1}/{len(chunks)}")
            _emit(f"TTS chunk {idx + 1}/{len(chunks)} "
                  f"({budget.elapsed():.0f}s elapsed)")
            chunk_raw = temp_dir / f"chunk_{idx:03d}.raw"
            chunk_wav = temp_dir / f"chunk_{idx:03d}.wav"
            chunk_sha = temp_dir / f"chunk_{idx:03d}.sha256"
            expected_sha = _chunk_cache_key(voice_name, model, chunk)
            # Resume: a run that stalls at chunk 9 must not repay chunks 1-8. Verify
            # the chunk text hash so an expanded script never reuses stale audio.
            if chunk_wav.is_file() and chunk_wav.stat().st_size > 0:
                cached_sha = chunk_sha.read_text(encoding="utf-8").strip() if chunk_sha.is_file() else expected_sha
                if cached_sha == expected_sha:
                    if not chunk_sha.is_file():
                        chunk_sha.write_text(expected_sha, encoding="utf-8")
                    chunk_wavs.append(chunk_wav)
                    _emit(f"TTS chunk {idx + 1}/{len(chunks)} reused from this attempt")
                    continue
                chunk_wav.unlink(missing_ok=True)
            mime_type = _guarded_chunk(client, chunk, voice_name, style,
                                       model, chunk_raw, idx + 1, len(chunks))
            with hard_deadline(http_timeout_seconds(), f"audio conversion, chunk {idx + 1}"):
                _convert_raw_audio(chunk_raw, chunk_wav, mime_type)
            chunk_sha.write_text(expected_sha, encoding="utf-8")
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
        # Chunks are kept on purpose: under a ten-request daily quota, a run that
        # dies at chunk 2 of 2 must not start from zero tomorrow. The workflow
        # caches this directory.
        pass

    _assert_not_truncated(out_path, text)
    return out_path
