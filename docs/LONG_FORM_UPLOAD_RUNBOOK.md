# Long-form upload runbook — approved style via GitHub Actions

How to publish a long-form prayer video in the locked visual style, entirely from
GitHub, and how to tell whether the result is actually correct.

**Current facts (1 November 2026, after the verified dry render)**

| Item | Status |
| --- | --- |
| `main` renderer | Fails closed on purpose. Every `Produce video` run on `main` ends at *"the legacy montage renderer is forbidden"*. |
| Working renderer | Verified end to end on run `41280103404` (dry, nothing uploaded). It now lives on PR #113 together with the alignment fixes that run exposed. |
| PR #112 CI | Green: unit tests, and the offline render job. |
| Jobs long enough to render | **1** — `0010-psalm-121-…` (884 words ≈ 5.7 min). The other 22 approved scripts are 227–408 words and fail the 650-word gate. |
| Upload credentials | Present in repo secrets (`YOUTUBE_*`, `GEMINI_API_KEY`, `PIXABAY_API_KEY`). |

**Merge PR #113 first.** It contains PR #112's renderer plus the three alignment
fixes a real run exposed, so after merging, `produce.yml` can be dispatched from
`main` — the branch the mobile app always offers. Until then, the push-triggered
`Dry render — approved style (no upload)` workflow renders on demand without any
branch selection.

---

## Recommended path: merge #113, then upload from `main`

### Step 1 — dry run (no upload, ~35 min, $0)

Already done once: run `41280103404` rendered 0010 completely. To repeat it,
either re-run that workflow, or use **Actions → Produce video → Run workflow**:

| Field | Value |
| --- | --- |
| Use workflow from | `main` (after #113 merges) |
| job | `0010-psalm-121-he-who-keeps-you-will-neither-slumber-no.md` |
| short | *(leave empty)* |
| dry_run | ✔ **ticked** |

This does everything except upload: real Gemini `gemini-3.8-flash-tts` Charon
narration, `faster-whisper` alignment against the transcript, the tolerance
check, licensed asset fetch, a full-length widescreen render, and thumbnails.

**Green run means:** the renderer works end to end on real audio. Download the
artifact `render-<run-id>` (kept 1 day) and watch it before going further. This
is the checkpoint that the earlier rejected upload never had.

### Step 2 — real upload (public, ~15 min)

Same screen, same branch, `dry_run` **unticked**. On success:

- the video is uploaded as **public** (per the script's `privacy: public`),
- the pastoral comment is posted,
- `content/queue/0010-…md` is moved to `content/published/` and committed **to
  the PR branch**, not to `main`,
- `job_result.json` and the render are in the run artifact.

### Step 3 — check the receipt

The upload moves `content/queue/0010-…md` to `content/published/`, posts the
pastoral comment and writes `job_result.json`. Confirm all three before the next
cron at 06:14 / 10:14 / 14:14 / 19:14 / 23:14 UTC.

---

## What a real run costs

Measured: narration ~5 minutes, alignment model download ~1 minute, render
~20 minutes for a 5-minute master on a 4-core runner, total ≈ 35 minutes and 0
currency. The run timeout is 120 minutes, so there is headroom for 1080p later.

## What was wrong before

Three separate guards aborted full-length renders on legitimate recogniser
output: a zero-length word, a "for evermore" → "forevermore" tokenisation, and a
correctly transcribed word with probability 0.117. `pipeline/prayer_alignment.py`
now maps script words onto recognised tokens and only gates confidence where the
text did not match; it still refuses narration that differs from the script.

---

## What "in the approved style" means — check these on the artifact

1. **16:9 widescreen**, 1280×720, H.264 + AAC, duration ≥ 5:00.
2. **Sapphire sanctuary grade** with a vignette; no stock-slide look.
3. **Frosted-glass HUD** top-left: gold chapter pill (`01/06`), "THE SECRET PLACE",
   "PRAYER AND SCRIPTURE". Top-right: progress pill with percent.
4. **Inter display type**, sentence-level (not word-by-word, no subtitle ribbon),
   uppercase, with a directional drop shadow.
5. **Gold illumination** lands on the word being spoken and moves with it; a gold
   underline sweeps in under the line.
6. **No scale-bounce pulses**, no micro-word cards. Sentences change cleanly on
   sentence boundaries.
7. Description carries both Selar links; the pastoral comment appears.

A local reference render of the same script/styles is
`preview/psalm121-approved-style-preview.mp4` in this workspace (generated
plates and a synthetic pad, real script text, real renderer). Use it to compare
typography, HUD and illumination — the production run differs only in using
licensed photographs and real Charon narration.

---

## About the red "General pipeline dry-run (needs network)" check

That job is advisory (`continue-on-error: true`) and is expected to be red:

- on `main` it hits the legacy-renderer guard, by design;
- on PR #112 it would reach the new renderer but the job does not pass
  `GEMINI_API_KEY` into its environment, so it stops at
  "Gemini API key missing; refusing voice substitution" — which is the correct
  fail-closed behaviour, not a regression.

A merge is not blocked by it. The two required checks — *Unit tests + doctor*
and *Offline end-to-end render* — are green.

## Known failure modes and what each one means

| Log line | Meaning | Action |
| --- | --- | --- |
| `Production paused: the legacy montage renderer is forbidden` | You ran from `main`. | Run from the PR #112 branch. |
| `Prayer script has only N words; expand it before full-length production` | Job under 650 words. | Use 0010; expand the others. |
| `Offline speech alignment model is not installed` | `faster-whisper` or `model.bin` missing. | Re-run; the workflow downloads `Systran/faster-whisper-small.en` itself. |
| `Speech alignment word count differs` | Whisper heard different words than the script (TTS mispronunciation, numbers, pauses). | Rewrite the affected sentence; do not lower the threshold. |
| `Actual Charon narration is shorter than five minutes` | Script too short after TTS. | Expand the script. |
| `No licensed asset for scene N` | Wikimedia/Pixabay returned nothing for that query. | Broaden that scene's `asset_query` (see `0009`'s broadened queries). |
| `status: quota_paused` | Gemini free-tier limit hit. | Automatic; the job pauses and resumes after the Pacific reset. |
| `HTTP 403: Resource not accessible by integration` on dispatch | The caller has no `actions:write`. | Dispatch from the GitHub UI as the repo owner. |

---

## Straight after 0010 publishes

The queue becomes empty of renderable work: the next approved job is `0011`
(408 words ≈ 2.6 min), which the renderer refuses. So the cron will go red again
one run later — this time for a content reason, not a code one. Fix by either:

- expanding `0011`–`0033` to ≥650 words each (`python scripts/audit_runway.py`
  reports exactly which ones and by how much), or
- moving them into the Shorts/devotional track and keeping long-form slots for
  the six full-length scripts (0003–0007 are already 1,055–3,175 words but sit
  at `status: draft`; approving them would restore ~50 minutes of runway).

Approving 0003–0007 alone gives roughly **6 more long-form uploads** without
writing anything new.
