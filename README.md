# YouTube Automation Lab 🎬

A **₦0 / $0** YouTube production studio that runs entirely on **GitHub Actions**.
Research plan: **[PLAN.md](PLAN.md)** · Setup: **[docs/SETUP.md](docs/SETUP.md)** ·
Fine print: **[docs/DEEP_DIVE.md](docs/DEEP_DIVE.md)** · Growth science: **[docs/GROWTH.md](docs/GROWTH.md)**

> **The honest pitch** (details & math in PLAN.md): this repo automates the *grunt work* —
> narration, b-roll, assembly, captions, upload — while a human owns the creative
> (ideas, scripts, approval, thumbnails). That split is not a compromise; it is exactly
> what YouTube's 2026 "inauthentic content" policy demands of monetized channels.
> Target: first AdSense revenue in ~4–8 months, **YPP application before 1 Feb 2027**
> (thresholds double after that), $1K–$10K/mo in 12–24 months. Not "millions next week."

## Why it costs ₦0

| Piece | Free tier |
|---|---|
| Compute | GitHub Actions — **unlimited free minutes on public repos** (4-core Linux) |
| Voice | `edge-tts` — neural voices, no API key |
| B-roll | Pexels + Pixabay (free keys) + Wikimedia + NASA (keyless) |
| Assembly | ffmpeg (preinstalled on runners) |
| Upload | YouTube Data API — free, 100 uploads/day |
| Storage | Scripts in git, videos only as 1-day artifacts → straight to YouTube |

## How it works

```
content/queue/*.md  →  [originality gate]  →  TTS  →  stock b-roll  →  ffmpeg  →  YouTube
     (human writes                  (human checklist     edge-tts    Pexels/…    render     private
      & approves)                    enforced in code)                            draft      until human
                                                                                        publishes
```

- **`content/queue/`** — one markdown file per video (frontmatter + scene-by-scene script).
  Set `status: approved` and the scheduler picks it up.
- **`.github/workflows/produce.yml`** — cron (06:14 & 14:14 UTC) + manual dispatch.
- **`.github/workflows/dry-run.yml`** — full render rehearsal on every push, zero secrets.

## Quickstart

```bash
# 1. Render the sample video with zero keys and zero network (placeholder voice + title cards)
pip install -r requirements.txt
python -m pipeline.run --dry-run --job content/queue/0001-the-canal-that-broke-a-city.md

# 2. Real render locally (needs internet for edge-tts + optional Pexels key)
export PEXELS_API_KEY=...          # https://www.pexels.com/api/
python -m pipeline.run --dry-run --job content/queue/0001-the-canal-that-broke-a-city.md

# 3. Production run (upload) — needs GitHub secrets, see docs/SETUP.md
python -m pipeline.run --next
```

Outputs land in `output/<slug>/` — video, thumbnail, SRT captions, credits.json.

## The rules we build by

1. **Human creative, machine labor.** Every script passes the originality checklist
   (`pipeline/originality.py` enforces it). No template spam, no AI "expert" personas,
   no scraped-text TTS. Reviewers judge channels by patterns — ours reads as a documentary
   studio that uses automation.
2. **Never commit media.** Git = text only. Videos = 1-day artifacts, then YouTube.
3. **Deadline discipline.** YPP thresholds double on **1 Feb 2027**. The 90-day plan in
   PLAN.md §7 is built backwards from applying *before* that date.

## Repo map

```
PLAN.md                    ← the full research + business plan (start here)
docs/SETUP.md              ← secrets, API keys, YouTube OAuth & audit walkthrough
docs/DEEP_DIVE.md          ← the traps + money fine print (OAuth 7-day, cron 60-day, RPM geography)
docs/GROWTH.md             ← algorithm 2026, packaging science, SEO spec, Test & Compare SOP
pipeline/                  ← the studio: tts, assets, assemble, upload, metadata, shorts, originality gate
scripts/doctor.py          ← pre-flight setup check
scripts/youtube_oauth.py   ← one-time refresh-token mint (run locally)
content/queue/             ← script queue (the human creative layer)
content/published/         ← done, stamped
.github/workflows/         ← produce (cron) · dry-run (CI proof) · keepalive · metrics
```

Every render produces: final MP4 + **SRT captions** + **A/B/C thumbnail drafts** (for Studio
Test & Compare) + **metadata pack** (chapters, SEO description, tags) + optional **auto-Shorts**
(vertical 9:16 cuts, `MAKE_SHORTS=1`). Run `python scripts/doctor.py` before the first
production run.
