# The Secret Place — prayer-channel automation

This repository automates production and publishing for **The Secret Place**: scripture-centred prayer, devotional reflection, and companion YouTube Shorts. It is not a general-purpose or multi-niche video factory.

## Cost and reliability contract

- **Target operating cost: $0.** The pipeline has no paid-provider fallback. Provider quotas, GitHub policy, and account billing settings are external dependencies; the repository cannot verify Google billing is disabled. See [`docs/ZERO_DOLLAR_LOCK.md`](docs/ZERO_DOLLAR_LOCK.md) before enabling production secrets.
- Production uses Gemini TTS (`gemini-3.8-flash-tts`, Charon). The latest reported free-tier cap was 10 TTS requests/day for that model/project. Limits vary; quota exhaustion pauses work and may mean **no upload** in that slot.
- Do not assume a scheduled run means a video will publish. An eligible reviewed script, available quota, successful render, valid YouTube credentials, and a successful upload are all required.
- Avoid paid APIs, paid Actions runners, paid stock, or paid hosting. When blocked, wait or repair the free path; never buy a fallback.

## Production flow

```text
approved prayer queue → niche/script checks → Gemini TTS → licensed visuals
    → local alignment + FFmpeg render → YouTube upload → published receipt
```

- `content/queue/` — reviewed long-form prayer scripts.
- `content/shorts-queue/` and `content/shorts-scripts/` — approved Short manifests and narration specs.
- `pipeline/` — release orchestration, TTS, alignment, licensing, rendering coordination, and upload.
- `tools/deep_dive.py`, `tools/shorts.py` — local long-form and vertical renderers.
- `image-search/LICENSES.yml` — provenance/licence ledger for bundled media.
- `.github/workflows/produce.yml` — live release workflow; scheduled at 06:14, 14:14, and 19:14 UTC, with manual dispatch.
- `.github/workflows/gemini_brain.yml` — daily prayer queue-replenishment workflow.
- `.github/workflows/scheduler-supervisor.yml` and monitoring workflows — best-effort detection/dispatch of missed automation; GitHub's scheduler itself cannot be guaranteed by another workflow on the same platform.

The production workflow is configured for public YouTube uploads when all gates pass. Do not treat cron slots, green workflow status, or a quota reset as proof of publication: check the run's explicit publish result and the `content/published/` receipt.

## Local development

Install the Python dependencies from `requirements.txt`, and ensure FFmpeg is available. Run the offline checks before changing release code:

```bash
python -m pytest -q
python -m pipeline.run --dry-run --next
```

A real upload requires the relevant GitHub Secrets and must only be tested after reviewing the account-side $0 prerequisites. Never put API keys, OAuth credentials, or refresh tokens in source files or logs.

## Key operational references

- [`docs/ZERO_DOLLAR_LOCK.md`](docs/ZERO_DOLLAR_LOCK.md) — what the code enforces versus account-side requirements.
- [`docs/PRAYER_AUTOMATION_AUDIT.md`](docs/PRAYER_AUTOMATION_AUDIT.md) — reliability/capacity gaps and current constraints.
- [`docs/SETUP.md`](docs/SETUP.md) — repository and credential setup.
- [`MAINTENANCE.md`](MAINTENANCE.md) — routine checks and troubleshooting.
