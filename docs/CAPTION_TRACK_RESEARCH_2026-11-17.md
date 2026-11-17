# The track nobody kept

17 November 2026. Times are UTC unless marked otherwise.

Tenth reading of the day, and the direct sequel to the ninth: the last one found
that **caption tracks are 85% of everything this network spends in YouTube's
quota** — 59,600 of ~70,000 units over seven days. This one asks what the 400
units a track buys, whether the track is any good, and what is left of it
afterwards.

## The short answer

- **149 Short caption tracks exist, and not one of them is recorded anywhere
  before today.** Every Short released since the field appeared (14–17 November)
  got a track — **149 of 149**, on all ten channels, 13–16 each — and all 106
  earlier Shorts carry no field at all. 149 × 400 = **59,600 units**.
- **The same call runs on every long-form, and no long-form receipt has ever said
  whether it worked.** `pipeline/prayer_pipeline.py` writes `out/captions.en.srt`
  and passes it to `upload()` as `caption_path` on every render; **0 of 139
  long-form receipts** carry `caption_track`. At 400 units a track that is
  **~55,600 units** of spend the receipts cannot confirm.
- **Nothing is kept.** The SRT is written into `output/` (gitignored) and uploaded
  on the same run; the alignment sidecar that makes it possible is gitignored
  too (`assets/deepdive/words-short-*.alignment.json`). The six word files that
  survive belong to the finance era (`enron`, `johnstown`, `psalm91`) and none of
  them is one of the 149. **A Short's whole track is 884–1,131 bytes** — all 149
  together would be about 150 KB; what the pipeline keeps instead is one word in
  a receipt.
- **The generator's own line-width guarantee was false in 28% of cues.** Its
  docstring promises "≤ 40 chars/line". Measured over the six real alignment
  files: **23 of 82 cues carried a line of 41–44 characters**, because a cue is
  packed to 80 characters (2 × 40) and the packer can only split on words — the
  best split lands at 43. Fixed: at a 72-character cue budget, **0 of 174 lines
  exceed 40** and the widest is exactly 40, for seven more cues (82 → 89).
- **What a track should contain is now a figure**: a Short says 90–154 words
  (median 105 across 353 specs), which at the measured 13.2 words a cue is
  **8–12 cues**. The receipt says so from tomorrow.

## 1. What the 400 units send

Measured on the six per-word alignment files the repository still holds — real
renderer input, not synthetic — with the production call
(`build_srt_from_aligned_words(words, duration=last word end)`):

| | Measured |
| --- | --- |
| Words per cue | **13.2** (11.6–14.0 across the six) |
| Characters per cue | **72** (69–74) |
| Lines per cue | 1–2, never more |
| Reading speed, median cue | **15.8 characters/second** |
| Reading speed, worst cue | **21.2** (Netflix's ceiling is 20: two of 82 cues exceed it) |
| Cue length | ≤ 5.4 s by construction; none measured over it |
| Coverage | the last cue ends **0.02–0.91 s** before the audio does, on the three files whose audio is in the repository |
| SRT size | 884–1,131 bytes for a Short |

The speech is slow — this is bedtime narration — and the generator's minimum hold
(`chars / 17`, clamped to 2.2 s) never binds, so cues sit comfortably inside the
readable band. The one number outside it is the line width, and that is the story
below.

## 2. The guarantee that was not true

`pipeline/captions.py` opens with: *"Broadcast readability: <= 40 chars/line, <= 2
lines/cue, clause-aware breaks."*

The packer fills a cue until it would exceed `max_line_chars × max_lines` = 80
characters, then wraps. Wrapping can only cut at a space, and a cue filled to
exactly 80 characters almost never has a word boundary at 40 — so the two-line
split comes out 43/37, and the first line is three characters over the rule the
module advertises.

Measured over the six files, at the old 80-character budget:

| Cue budget | Cues | Cues with a line over 40 | Widest line |
| --- | --- | --- | --- |
| 80 (as shipped) | 82 | **23 (28%)** | **44** |
| 76 | 84 | 1 | 42 |
| 74 | 86 | 1 | 41 |
| **72 (now)** | **89** | **0** | **40** |
| 70 | 90 | 0 | 39 |

The fix is one constant — `MAX_CUE_CHARS = 72` — because 2 × 36 characters leaves
room for the word that will not fit. It costs **seven more cues across six
videos** (+8.5%) and shortens each cue by about 0.6 s of screen time; every
measured cue stays inside the 20 CPS ceiling. The two-line rule, the monotonic
timing, the two-decimal 0.020 s gap and the 5.4 s span are untouched, and the
"clause-aware" break rules (sentence end, comma past 68% of the budget) still run
on the smaller budget.

Nothing already uploaded changes: the 149 tracks on YouTube were made with the
80-character packer and stay as they are.

## 3. What is left afterwards

| Artefact | Kept? | Where |
| --- | --- | --- |
| The SRT that was uploaded | **no** | `output/shorts-release/<key>/captions.en.srt`, gitignored |
| The long-form SRT | **no** | `out/captions.en.srt` in the render workspace |
| The verified word alignment that made it | **no** | `assets/deepdive/words-<key>.alignment.json`, gitignored |
| The per-word timings | **no** (six legacy files only) | `assets/deepdive/words-*.json` |
| The fact that a track was sent | **yes, since today** | the receipt: `caption_track: "ok"` |

So the most expensive call the pipeline makes is the only one that leaves no
artefact: a poster is a file, a thumbnail is a file, a comment is a string in a
receipt, and the caption track is a 1 KB file that is deleted with the workspace
minutes after YouTube accepts it. If any of those 149 tracks is wrong — a dropped
word, a truncated cue list, a timestamp the renderer shifted — nothing in this
repository could show it.

Two facts per track are now kept instead of the file:

```yaml
caption_track: "ok"
caption_cues: 9
caption_sha256: "4f0b7c1d9a2e"
```

The cue count says how much of the script reached the track (a Short of 105 words
should carry 8–12 cues); the digest notices any change to the bytes, so a
re-upload can be compared to what was sent. Both are written only when the track
actually landed — a refused or skipped track claims no cues.

## 4. What changed

| Change | File |
| --- | --- |
| `MAX_CUE_CHARS = 72`, with the measurement behind it, so the "≤ 40 chars/line" claim is true | `pipeline/captions.py` |
| `caption_fingerprint()` — cue count and a 12-hex digest of the SRT | `pipeline/captions.py` |
| Shorts record the fingerprint through a `record` dict, and the writer stamps `caption_cues`/`caption_sha256` only for a landed track | `pipeline/short_release.py` |
| Long-form `UploadResult` carries the fingerprint; `run.py` stamps it beside `caption_track` | `pipeline/upload.py`, `pipeline/run.py` |

No caption policy changed: the same tracks are built from the same alignments for
the same videos at the same 400 units. The text on future tracks is
narrower by a few characters a line.

## Unproven

- **Whether anyone reads them.** `content/analytics/` holds no playback-location
  or caption data, and the Analytics scope is not granted. The 400-unit decision
  rests on what captions are for (search, translation, screen readers), not on a
  measurement this repository owns.
- **Whether YouTube's own automatic captions would be good enough.** Nothing here
  has ever compared the uploaded track against the auto-generated one; the
  receipt does not even record whether a track was uploaded, for 139 long-forms.
- **Whether 72 is the right budget** rather than 70 or 76. It is the largest
  budget at which the stated rule holds on every file measured; a designer might
  prefer shorter cues and more of them.

## Owner-only

- **Keeping the files.** ~150 KB for the 149 Shorts; roughly 90 KB an hour for the
  long-forms, so about 13 MB if every one were kept. That is a policy choice
  about repository size, not a technical limit — and it is the only way to ever
  inspect a track again.
- **Re-uploading the 149** with the narrower lines: another 59,600 units, and the
  old tracks would have to be deleted first.
- **Whether Shorts should carry an uploaded track at all**, given the same words
  are already burned into the picture as kinetic text; the long-forms, which have
  no on-screen words, are the videos that need searchable text.

## One next step

Read `caption_cues` on tomorrow's Shorts: **0 today, 8–12 expected**. A track with
three cues on a 105-word script is a caption track that lost most of its words —
and until today that failure would have been invisible, on the most expensive
call in the pipeline.
