# Widescreen prayer pipeline — readiness review (31 October 2026)

Scope: review of `arena/564c86c7-youtube-automation` (PR #112, "Approved prayer
visual production pipeline") before it is merged into `main`. PR #112 is the only
change that can unblock long-form production: `main` currently fails closed on
every `produce.yml` run by design (five consecutive scheduled failures in the
last 24 hours, the "legacy montage renderer is forbidden" guard).

This review was performed offline. No Gemini quota was consumed, no YouTube
credential was used, and nothing was uploaded.

## What was verified

| Check | Result |
| --- | --- |
| Full test suite on the PR tip (`e7c6c42`) | **236 passed, 1,110 subtests**, 0 failures (after installing `reportlab`, `imageio-ffmpeg`, `google-genai`, `google-api-python-client`) |
| Widescreen render path executes | Yes — `pipeline/prayer_visuals.render()` produced a real 1280×720 H.264/AAC file from measured word timings |
| Visual style | Sapphire grade, frosted HUD with chapter badge and progress pill, Inter display type with directional shadow, gold illumination on the active word, gold underline sweep — matches `docs/APPROVED_VISUAL_STYLE.md` |
| Multi-scene timing maths | Scene boundaries derived from measured word ends; scenes cover the narration; decoder/encoder clean up on failure |
| Render cost | **202 ms/frame at 1280×720/24 fps** on a 2-core Xeon 2.60 GHz sandbox = **4.85× realtime**. A 6-minute master (8,640 frames) ≈ 29 min here, roughly 12–15 min on GitHub's 4-core runner — inside the 120-minute job timeout |
| Narration/scene consistency | For all 28 queue scripts, `full_narration` token-for-token equals the concatenation of scene narrations, so the word-count scene split cannot drift |
| Runway reality | **Only 1 approved job is long enough to render** (see below) |

## What is still unverified — the reasons PR #112 was left open

1. **Real Gemini Charon narration.** `gemini_tts.py` in PR #112 removes the
   alternate-model fallbacks so only `gemini-3.8-flash-tts` + `Charon` can be
   used. That is the right policy, but it means a 429/quota error now fails the
   job rather than degrading. No live synthesis has been run since the change.
2. **Local speech alignment.** `pipeline/prayer_alignment.py` needs
   `faster-whisper` plus `Systran/faster-whisper-small.en` downloaded at run
   time; `scripts/check_prayer_alignment.py` then compares alignment against the
   existing Psalm 91 reference. This sandbox has no Hugging Face access, so the
   model path and the tolerance check have never executed here.
3. **End-to-end render at real length.** Renders were verified at 9 s, 20 s and
   60 s with synthetic audio and locally generated stand-in plates. A ≥5-minute
   render with real Charon audio, real licensed stills and the upload path in
   `prayer_pipeline.produce()` has not been executed.
4. **Dispatch is blocked for this session.** `gh workflow run produce.yml`
   returns `HTTP 403: Resource not accessible by integration` — the GitHub
   integration has no `actions:write`. A dry run has to be started by the repo
   owner.

## The blocking finding: the queue is not a 30-night long-form runway

`main`'s `STATE.md` records "30-night prayer queue — COMPLETE" with 24 authored
scripts. In practice `pipeline/prayer_pipeline.py` refuses any script under 650
words because that is the floor for a ≥5-minute upload. Reproduce with:

```bash
python scripts/audit_runway.py
```

Result on the PR tip:

- 28 queue scripts, **22 below the 650-word floor**, 6 above.
- Of the 6 above the floor, 0003–0007 are `draft`; only **0010 is `approved`**.
- **Publishable approved long-form runway: 1 job / 5.7 minutes.**

The 22 short scripts are 227–408 words, i.e. 1.5–2.7 minutes of Charon speech at
the 2.6 words/second that the approved renderer is built around. If #112 merged
today, the next cron would render and publish 0010, and every subsequent
scheduled run would fail closed on the length gate — the same daily red
`produce.yml` the channel has now, only after spending a Gemini render.

## Recommendations, in order

1. **Do not merge #112 straight into `main`.** `produce.yml` runs three times a
   day and publishes public immediately; landing an unverified renderer turns the
   next scheduled run into an unreviewed public upload.
2. **Start one dry run on the PR branch** (zero cost, no upload):
   Actions → *Produce video* → *Run workflow* → branch
   `arena/564c86c7-youtube-automation`, job
   `0010-psalm-121-he-who-keeps-you-will-neither-slumber-no.md`, `dry_run: true`.
   That exercises real TTS, the alignment model, the alignment tolerance check,
   licensed asset fetch and a full-length render. Merge after it is green.
3. **Decide the long-form resolution.** The renderer defaults to 1280×720 while
   the approved Shorts reference is 1080×1920. 1080p long-form costs ~2.25× the
   pixels (~450 ms/frame here, still within the job timeout); choose before the
   first real master is produced.
4. **Close the runway gap.** Either expand the 22 short scripts to ≥650 words
   each, or re-classify them as Shorts/devotional shorts so the queue stops
   advertising runway it cannot deliver. `scripts/audit_runway.py` should be run
   whenever the queue changes.
5. **Keep the production pause until (2) is green.** `main` failing closed is the
   correct current state, not a bug to work around.

## Recovering PR #112's work

The PR branch tip is also preserved as the tag
`archive-pr112-approved-prayer-visual-pipeline` (`e7c6c42`) on `origin`, so the
commits survive even if the branch is deleted.
