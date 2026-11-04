# The Secret Place — prayer automation maintenance

This runbook describes the prayer-only production path. For a broader current risk/capacity audit see [`docs/PRAYER_AUTOMATION_AUDIT.md`](docs/PRAYER_AUTOMATION_AUDIT.md); for $0 account requirements see [`docs/ZERO_DOLLAR_LOCK.md`](docs/ZERO_DOLLAR_LOCK.md). Historical implementation notes are in `CHANGELOG.md`, not in the operational instructions below.

## 1. Cost and safety prerequisites

- The operating target is **$0**. Do not attach billing to the Google project used by `GEMINI_API_KEY`. The repo cannot inspect the project’s billing state.
- No paid API, TTS fallback, paid stock, paid runner, or paid hosting is allowed. On quota exhaustion, stop and wait; do not switch services.
- Never print, commit, or ask for credentials in chat. GitHub Actions secrets should contain the required Gemini and YouTube credentials.
- The active render catalogs and production queue are prayer/scripture/devotional only. Production niche validation and the licence ledger are fail-closed gates.
- Public uploads are enabled in the production workflow when its gates pass. A scheduled slot or green workflow is not proof that a video uploaded; inspect the explicit release result and durable receipt.

## 2. Current release schedule and limits

| Workflow | Schedule | Purpose |
|---|---|---|
| Produce video | 06:14, 14:14, 19:14 UTC (07:14, 15:14, 20:14 WAT) | Repair supply where needed, process a queued Short, then attempt the eligible long-form release. |
| Gemini Brain | 03:14 UTC (04:14 WAT) daily | Maintain prayer queue runway and author/review queue material. |
| Scheduler supervisor | Every 15 minutes, plus other triggers | Best-effort dispatch of workflows when a scheduled slot appears missed. It still depends on GitHub Actions being able to start jobs. |
| Community posts / monitoring / metrics | See the workflow files under `.github/workflows/` | Separate from video upload; not proof of a video release. |

The latest production error reported a **10 requests/day** Gemini TTS allowance for `gemini-3.8-flash-tts`. This is an observed limit for the configured project/model, not a permanent contract or the generic Gemini text limit. A long-form release may need multiple requests; Shorts share the TTS quota. See `docs/ZERO_DOLLAR_LOCK.md` and `docs/PRAYER_AUTOMATION_AUDIT.md`.

## 3. Local checks

Use Python 3.12 to match GitHub Actions where possible. Dependencies and FFmpeg are local/free:

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Full offline/unit suite
PYTHONPATH=. .venv/bin/pytest -q

# Rights ledger must be in sync
PYTHONPATH=. .venv/bin/python scripts/licence_ledger.py check

# Optional, no-upload sample renders
ENABLE_STOCK_BROLL=0 ENABLE_KEYLESS_SOURCES=0 .venv/bin/python tools/deep_dive.py psalm91
ENABLE_STOCK_BROLL=0 ENABLE_KEYLESS_SOURCES=0 .venv/bin/python tools/shorts.py short-psalm91
```

The test suite and sample renders prove local code/encoding behavior only. They do not prove Google billing status, available free quota, GitHub schedule delivery, live YouTube privacy, channel analytics, or a production upload.

Before a code change is merged, keep the existing CI jobs green: unit tests/doctor, offline end-to-end render, and general pipeline dry-run. Preserve protected workflow permissions and publishing concurrency; do not trigger a real production run as part of a test.

## 4. Investigating a missed or failed release

1. Open the most recent **Produce video** Actions run and read its named stage and summary. Confirm whether a video ID was returned and whether the receipt was committed.
2. If the log says Gemini TTS quota is exhausted, identify the `quota_reset_utc` in the paused queue item/Short manifest. Both formats share the TTS quota; the cross-queue breaker should send no additional TTS request while a live pause exists.
3. After the recorded reset, verify the queue item is eligible and let a scheduled or manually authorized release attempt run. Reset time only means quota may return; it does not promise an upload.
4. If an upload may have succeeded but the workflow did not record the receipt, let the remote duplicate reconciliation run before retrying. Do not force a duplicate upload.
5. If the queue is empty or under the word floor, inspect the queue-repair summary and the brain workflow. Total approved files are not the same as eligible runway.
6. If scheduled jobs did not start, inspect **Scheduler supervisor** and **Automation monitor**. They are best-effort and run on the same GitHub platform; a truly independent always-on monitor would require a separately verified zero-cost sender. The repository’s manual repository-dispatch path may be used by an authorized operator.
7. If the failure concerns a source asset, run `scripts/licence_ledger.py check`; a non-cleared or unrecorded asset must not be used in monetized output.

## 5. Queue and render contracts

- Long-form queue items require `status: approved`, the prayer niche, valid script metadata, substantive scripture references, and the configured minimum word count. Do not make a short draft appear publishable by padding it or lowering the gate silently.
- Short manifests must resolve to a prayer renderer/spec and pass the same niche and licensing boundaries. A missing renderer or audio input is not a successful release.
- TTS chunk audio is cacheable across workflow runs but GitHub cache retention is best-effort. Chunk reuse must match the exact text, voice, and model; if the cache is absent, the free quota may block synthesis.
- Render output is temporary (`output/`, `social/`) and should not be committed. Publication receipts in `content/published/` and queue status changes are repository state and must remain durable.
- Historical receipts and rights-regression fixtures may remain for audit/deduplication/testing; they are not active queue entries or render candidates.

## 6. Recovery and change discipline

- Keep production workflow concurrency and the queue/receipt commit path intact. A successful YouTube upload without a durable local receipt can lead to duplicate retries.
- Use manual workflow dispatch only for an intentional run; use `dry_run` for render-only checks. Do not test by pointing a live workflow at an unreviewed or non-prayer script.
- Never purge GitHub artifacts, caches, queue receipts, or historical published records without checking their retention/deduplication role.
- Update the runbook and quota notes when provider limits or workflow schedules change. State what is observed, what is configured, and what the repository cannot verify.
