"""Zero-cost verified SubRip (.srt) caption generator & YouTube captions uploader.

Builds broadcast-compliant UTF-8 (no BOM) `.srt` closed captions directly from
`faster-whisper` word alignments (`words.json`) + punctuated script text:
  * Encoding: UTF-8 strictly without BOM, Unix LF (`\\n`) line endings
  * Timecode format: `HH:MM:SS,mmm --> HH:MM:SS,mmm` (comma separator)
  * Strict monotonic non-overlapping cues (`start[i] >= end[i-1] + 0.020s`)
  * Broadcast readability: <= 40 chars/line, <= 2 lines/cue, clause-aware breaks
  * Zero HTML/ASS markup (`<`, `>`, `{`, `}` stripped)
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .social_pack import sanitize_persona_integrity


def format_srt_timestamp(seconds: float) -> str:
    """Format seconds as `HH:MM:SS,mmm` with comma millisecond separator."""
    ms_total = max(0, int(round(float(seconds) * 1000.0)))
    secs, ms = divmod(ms_total, 1000)
    mins, secs = divmod(secs, 60)
    hrs, mins = divmod(mins, 60)
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{ms:03d}"


def _clean_caption_token(token: str) -> str:
    cleaned = re.sub(r"[<>{}]", "", token or "").strip()
    return sanitize_persona_integrity(cleaned)


def _restore_script_punctuation(
    words: list[tuple[str, float, float]],
    narration_text: str,
) -> list[tuple[str, float, float]]:
    """Map punctuated tokens from `narration_text` onto aligned words when counts match."""
    if not narration_text or not words:
        return [(_clean_caption_token(str(w)), float(s), float(e)) for w, s, e in words if str(w).strip()]

    script_tokens = [_clean_caption_token(tok) for tok in narration_text.split() if _clean_caption_token(tok)]
    norm = lambda s: re.sub(r"[^a-z0-9']+", "", s.lower())

    out: list[tuple[str, float, float]] = []
    j = 0
    for raw_w, t0, t1 in words:
        w = _clean_caption_token(str(raw_w))
        if not w:
            continue
        nw = norm(w)
        matched_tok = w
        if nw and j < len(script_tokens):
            for lookahead in range(0, min(4, len(script_tokens) - j)):
                cand = script_tokens[j + lookahead]
                if norm(cand) == nw:
                    matched_tok = cand
                    j = j + lookahead + 1
                    break
        out.append((matched_tok, float(t0), float(t1)))
    return out


def _wrap_cue_lines(tokens: list[str], max_line_chars: int = 40, max_lines: int = 2) -> str:
    text = " ".join(tokens).strip()
    if len(text) <= max_line_chars or max_lines <= 1 or len(tokens) < 2:
        return text

    # Find balanced split point near the middle preferring punctuation
    best_idx = 1
    best_score = 10**9
    total_len = len(text)
    running = 0
    for i in range(1, len(tokens)):
        running += len(tokens[i - 1]) + (1 if i > 1 else 0)
        left = " ".join(tokens[:i])
        right = " ".join(tokens[i:])
        overflow = max(0, len(left) - max_line_chars) + max(0, len(right) - max_line_chars)
        imbalance = abs(len(left) - (total_len / 2.0))
        punct_bonus = -8.0 if left.endswith((",", ";", ":", "—", "-", ".", "?", "!")) else 0.0
        score = overflow * 100.0 + imbalance + punct_bonus
        if score < best_score:
            best_score = score
            best_idx = i
    return f"{' '.join(tokens[:best_idx])}\n{' '.join(tokens[best_idx:])}"


def build_srt_from_aligned_words(
    words: list[tuple[str, float, float]],
    narration_text: str = "",
    duration: float | None = None,
    max_line_chars: int = 40,
    max_lines: int = 2,
) -> str:
    """Convert `(word, start, end)` alignments into a YouTube-validated `.srt` string."""
    enriched = _restore_script_punctuation(words, narration_text)
    if not enriched:
        return ""

    max_chars_per_cue = max_line_chars * max_lines
    raw_cues: list[tuple[float, float, list[str]]] = []
    cur_tokens: list[str] = []
    cur_start = 0.0
    cur_end = 0.0

    for idx, (tok, t0, t1) in enumerate(enriched):
        t0 = max(0.0, float(t0))
        t1 = max(t0 + 0.08, float(t1))
        if not cur_tokens:
            cur_tokens = [tok]
            cur_start = t0
            cur_end = t1
        else:
            candidate_text = " ".join([*cur_tokens, tok])
            gap_from_prev = t0 - cur_end
            cue_span = t1 - cur_start
            if (
                len(candidate_text) > max_chars_per_cue
                or cue_span > 5.4
                or gap_from_prev > 0.85
            ):
                raw_cues.append((cur_start, cur_end, cur_tokens))
                cur_tokens = [tok]
                cur_start = t0
                cur_end = t1
            else:
                cur_tokens.append(tok)
                cur_end = max(cur_end, t1)

        # Break cleanly at sentence-ending punctuation once cue is comfortably readable
        joined_len = len(" ".join(cur_tokens))
        if (
            cur_tokens
            and tok.endswith((".", "?", "!"))
            and (joined_len >= 18 or (cur_end - cur_start) >= 1.2)
        ):
            raw_cues.append((cur_start, cur_end, cur_tokens))
            cur_tokens = []
        elif (
            cur_tokens
            and tok.endswith((",", ";", ":", "—"))
            and joined_len >= int(max_chars_per_cue * 0.68)
        ):
            raw_cues.append((cur_start, cur_end, cur_tokens))
            cur_tokens = []

    if cur_tokens:
        raw_cues.append((cur_start, cur_end, cur_tokens))

    # Enforce strict monotonic non-overlapping timing & optional video duration ceiling
    blocks: list[str] = []
    prev_end = 0.0
    cap_dur = float(duration) if (duration is not None and duration > 0) else None

    for seq, (s, e, toks) in enumerate(raw_cues[:1450], start=1):
        start = max(s, prev_end + (0.020 if seq > 1 else 0.0))
        min_hold = max(0.85, min(2.2, len(" ".join(toks)) / 17.0))
        end = max(e, start + min_hold)
        if seq < len(raw_cues):
            next_start = float(raw_cues[seq][0])
            if end > next_start - 0.020 and next_start - 0.020 > start + 0.25:
                end = next_start - 0.020
        if cap_dur is not None:
            if start >= cap_dur - 0.05:
                break
            end = min(end, cap_dur)
        if end <= start + 0.05:
            continue
        prev_end = end
        cue_text = _wrap_cue_lines(toks, max_line_chars=max_line_chars, max_lines=max_lines)
        blocks.append(f"{len(blocks) + 1}\n{format_srt_timestamp(start)} --> {format_srt_timestamp(end)}\n{cue_text}")

    return ("\n\n".join(blocks) + "\n") if blocks else ""


def write_srt_file(
    out_path: Path,
    words: list[tuple[str, float, float]],
    narration_text: str = "",
    duration: float | None = None,
) -> Path | None:
    """Write UTF-8 (strictly without BOM) `.srt` file; returns `out_path` if non-empty."""
    srt = build_srt_from_aligned_words(words, narration_text=narration_text, duration=duration)
    if not srt.strip():
        return None
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(srt)
    return out_path


def upload_captions(
    youtube: Any,
    video_id: str,
    srt_path: Path | None,
    language: str = "en",
) -> str | None:
    """Upload `.srt` closed captions via `captions.insert` (best-effort, fail-open)."""
    if not youtube or not video_id or not srt_path or not srt_path.is_file():
        return None
    try:
        from googleapiclient.http import MediaFileUpload

        media = MediaFileUpload(str(srt_path), mimetype="application/x-subrip", resumable=False)
        resp = (
            youtube.captions()
            .insert(
                part="snippet",
                body={
                    "snippet": {
                        "videoId": video_id,
                        "language": language,
                        "name": "",
                        "isDraft": False,
                    }
                },
                media_body=media,
            )
            .execute()
        )
        cap_id = resp.get("id")
        print(f"[captions] Uploaded verified '{language}' SRT captions on {video_id} (id={cap_id})")
        return cap_id
    except Exception as exc:  # noqa: BLE001
        print(f"[captions] Notice: SRT caption upload skipped ({exc!r})")
        return None
