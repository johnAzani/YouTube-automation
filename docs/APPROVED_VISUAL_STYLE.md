# Locked visual style — The Secret Place

On 31 October 2026, the channel owner explicitly approved the nine-second
widescreen preview on the GitHub Pages dashboard as the reference for future
videos. This is a **visual reference**, not a finished long-form master or a
manual review gate.

- Approved reference: `docs/media/approved-style-preview.mp4`
- SHA-256: `69c55e855ed3a9a8ec1ffa79663489d7370eaaf636158c1ae853fe2c11d9f156`
- Approved renderer reference: `tools/shorts.py`, `short-psalm91`.
- Full-bleed, 16:9 long-form prayer imagery; 9:16 for Shorts.
- Sapphire sanctuary grading, frosted-glass HUD, Inter typography and
  directional shadows, with large sentence-level kinetic display text.
- Illuminate the spoken word in radiant gold, synchronized to measured speech
  without accumulated drift. Preserve natural pauses and transition when a
  sentence finishes; do not use a subtitle ribbon, micro-word cards, or scale
  bounce pulses.
- Narration remains Gemini `gemini-3.8-flash-tts`, voice `Charon`, under the
  existing fail-closed $0.00 quota policy. Never substitute another voice.
- Long-form must be genuinely full-length (at least five minutes), not a
  repeated or stretched short. Do not render or publish the rejected legacy
  montage/subtitle style as a fallback.

The approved preview uses existing Psalm 91 audio and is nine seconds long.
**It is not the full-length implementation.** The production queue renderer
remains blocked until an equivalent widescreen renderer, real speech alignment,
licensed assets, and a full-length end-to-end render have been verified. Keep
publishing automatic once those technical requirements are met; this document
is not a request for a manual website approval step.

## Verified long-form frames — 1 November 2026

The full `0010` Psalm 121 script (884 words, 5.7 minutes) was rendered end to end
through `pipeline/prayer_visuals.py` at the shipped long-form settings
(1280×720, 24 fps, H.264 + AAC) to confirm the style holds at real length, not
just in the nine-second preview. Narration was a synthetic pad and the plates
were generated stand-ins, so these images prove **layout, typography, HUD and
illumination only**; production runs use licensed stills and real Charon audio.

- `docs/media/approved-style-frame-01-chapter1.png` — chapter 1, sentence newly
  entered, gold illumination on the current word.
- `docs/media/approved-style-frame-02-chapter3.png` — chapter 3, five-line
  sentence, HUD progress pill at 42%.

Measured cost: **199 ms/frame** on a 2-core Xeon 2.60 GHz (4.9× realtime), i.e.
27 minutes for a 5.7-minute master here and roughly 12–15 minutes on a 4-core
GitHub runner. Scene chapters advanced on measured word boundaries
(01→06) with no drift.

Known cosmetic gaps to consider before the first public master:

- Long sentences wrap to five or six uppercase lines. It is legible but dense;
  consider tightening the per-line character budget (~30 → ~34) so most
  sentences settle at three or four lines.
- The scene progress bar at the very bottom edge is partially cut by the frame
  because the bar is drawn at `height - 6`. Nudge it up a few pixels.
