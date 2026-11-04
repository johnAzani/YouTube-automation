# The Secret Place automation: reliability and $0 audit

**Audit date:** 2026-11-04 (UTC)
**Scope:** repository code, queue structure, GitHub Actions schedules, quota/error handling, render and publish path, and the most recent production run details recorded for this session. This audit did not inspect Google Cloud billing, YouTube Studio analytics, or private GitHub account settings.

## Executive finding

The automation has substantial safeguards (niche validation, queue gating, TTS chunk persistence, deadline-bounded API calls, licensing checks, duplicate checks, publishing receipts, retries, workflow monitoring, and a production run report). It is not yet an end-to-end guarantee of daily uploads, nor can source code alone prove an account costs $0.

The latest production run, [41743246072](https://github.com/johnAzani/YouTube-automation/actions/runs/41743246072), failed because the Gemini TTS daily free-tier quota was exhausted. The reported cap was **10 requests/day for `gemini-3.8-flash-tts`**. Psalm 27 was paused until the reset timestamp reported in the run, and **nothing uploaded**. This is the desired fail-closed behavior; it is not evidence that the next scheduled run will publish.

### $0 caveat that cannot be solved in code

`GEMINI_API_KEY` belongs to a Google project whose billing status is external to this repository. The pipeline can avoid paid fallbacks and stop on quota errors, but cannot check whether that project has billing enabled or prevent Google from charging a billable project. To keep the target truly at $0, billing must be disabled for that project. The current code/docs now state this prerequisite instead of claiming an unconditional or permanent cost guarantee.

## System map and observed capacity

- **Production schedule:** 06:14, 14:14, and 19:14 UTC daily. These are opportunities to process work, not upload promises. Production is serialized with other content-state writers.
- **Supply:** the Gemini Brain replenishes the prayer queue daily; production also attempts bounded queue repair. The inspected PR tree had 22 approved long-form scripts and 8 approved Short specs, but “approved” is not the same as eligible: word floor, citations, scene assets, audio, queue status, and publication receipts all matter.
- **Speech:** long-form and Shorts share Gemini TTS quota. A typical long-form release may take multiple text-to-audio requests, depending on script length/chunking and cache hits. The returned quota error—not an old generic Gemini request allowance—is the authoritative evidence for that project/model.
- **Caching:** completed long-form chunks and Short audio are restored/saved through GitHub Actions cache. This avoids intentionally repeating completed chunks when the cache is present, but cache retention is best-effort and is not durable storage.
- **Build:** render, word alignment, and FFmpeg are runner-local; there is no paid render/transcription service in the active release path.
- **Publish:** YouTube OAuth and Data API quotas are finite. Upload occurs only after the approved content, render, audio, license, duplicate, and upload gates pass. The receipt is essential to prevent duplicate publication on retry.
- **Monitoring:** workflow monitors and the scheduler supervisor catch many failures, but they run on GitHub Actions too. A scheduled workflow cannot guarantee that GitHub’s own scheduler will wake it; the repository-dispatch watchdog needs an external/manual sender. There is no always-on paid monitor, by design.

## Highest-priority findings and changes

| Priority | Finding | Action / status |
|---|---|---|
| P0 | Old docs stated generic Gemini `15 RPM / 1,500 RPD` as the TTS limit, despite production reporting a 10-request/day TTS cap. | Corrected the zero-cost contract, Brain documentation, system instruction, quickstart, and studio audit report. Limits are now described as project/model-specific and the observed value is identified as an observation, not a guarantee. |
| P0 | A quota-paused long-form item stopped later long-form work, but Short narration could still make another request against the same exhausted TTS quota (and the reverse path also needed protection). | Added a shared quota-state circuit breaker checked before every Gemini TTS request; it reads both long-form and Short queues and fails before sending another request. Long-form release gating now includes a paused Short. Tests cover both directions, expired pauses, and YouTube-only pauses. |
| P0 | The local “zero dollar lock” report returned `$0.00` and `active_locked` without access to provider billing settings; it also claimed unverified channel subscriber/YPP and A/B/localization facts. | Reworked the report to say billing is unverified, actual monthly spend is unknown, and analytics/A-B/localization are not queried by this local audit. Removed fabricated fixed subscriber/YPP values and “100% optimal” output. |
| P1 | The renderers retained active finance/history editions even though production was prayer-only. | Removed the Johnstown/Enron active render specs, off-channel infographic branches, procedural plate generator, and unused off-channel narration/timing files; the long-form renderer defaults to Psalm 91. Short tests now exercise prayer editions and the production niche gate directly. The historical published receipt and rights-regression fixtures remain only for audit/deduplication and licensing tests. |
| P1 | Three daily production slots can repeatedly start work that cannot succeed if a shared provider quota is exhausted. | Existing run-level cooldown plus the new per-request cross-queue breaker now stop repeat TTS probes. The daily schedule remains because cached work or quota resets can make later slots useful; no upload cadence is promised. |
| P1 | The studio health tool called itself “100% optimal” and reported live channel/financial facts it did not fetch. | Corrected its output so it differentiates local file/queue observations from external account/analytics state. |
| P1 | CI cache and scheduled automation are GitHub-hosted, so cache eviction and scheduler suppression remain outside local control. | Documented as best-effort platform dependencies. No paid external heartbeat was added; manual/externally-triggered repository dispatch remains the zero-cost recovery option. |

## Remaining gaps / recommended next work

1. **Verify the account-side $0 lock manually (release blocker if uncertain).** Confirm billing is disabled on the exact Google project behind `GEMINI_API_KEY`, and do not attach a billing account. A repository secret or `ZERO_DOLLAR_MODE` variable cannot prove this. No production API request was made as part of this audit.
2. **Capacity-aware scheduling.** The 10-request/day observation is too small to assume multiple uncached releases will fit. Use observed request counts and cache hits from successful runs to set a conservative per-day target; do not hard-code a permanent provider limit. If demand exceeds the free cap, reduce attempts/publishing volume or wait—never add paid TTS.
3. **Persist one normalized release outcome.** The pipeline already emits explicit upload/quota results and receipts. Future work should ensure every workflow, including Short-only and queue-repair cases, records a machine-readable result with `uploaded`, item ID, request/cached counts, failure class, reset time, and receipt path. Do not count a green “continued after error” step as a publication.
4. **Eligibility-based runway.** Report “ready to publish” counts separately from total approved scripts: valid niche + approved state + word floor + non-duplicate + required audio/assets. Alert when the eligible runway falls below one full long-form release, not merely when the queue has few files.
5. **Publisher postcondition checks.** After upload, verify the returned video ID, requested privacy/schedule, and channel receipt; on the next run reconcile the local receipt against the channel before retrying. Avoid aggressive polling that consumes YouTube quota.
6. **External scheduler monitor tradeoff.** A truly independent always-on watchdog requires a reliable external sender. Free third-party cron plans can change, sleep, or require payment; none was added. Until a suitable verified $0 sender exists, treat GitHub’s monitor/supervisor as best-effort and retain the documented manual dispatch procedure.
7. **Provider policy drift.** Recheck free-tier limits and GitHub Actions terms periodically. The code should classify new quota errors and stop safely; it cannot lock a provider’s free plan in perpetuity.
8. **Content rights and trust.** Keep source/license provenance checks. Scripture edition, translation copyright, factual citations, repetition, and pastoral safety require editorial scrutiny; generation volume is not a quality metric.
9. **Channel analytics and claims.** This repository-local audit does not read Studio watch time, subscriber counts, Content ID claims, restrictions, or monetization eligibility. Do not use generated “YPP target met” statuses as evidence unless they come from actual channel analytics.

## Acceptance tests for release changes

- No new paid service, billable tier, paid fallback, paid stock, or paid runner.
- TTS quota failure records an explicit pause/reset and no later queued narration sends a request while that pause is live, regardless of format or manual job selection.
- Cache hits are hash-verified against the exact text, voice, and model; cache miss degrades to a safe pause/failure.
- A release is reported as published only after an upload response and durable receipt; retries reconcile remote state first.
- Prayer-only niche and asset licensing checks remain enforced in production and render tests.
- Local health reports state what they did not inspect; never claim zero actual spend or successful upload without evidence.

## Boundaries of this audit

No external quota console was queried; no YouTube upload, production run, or manual API request was performed. The open PR branch has not been merged, so these changes do not alter `main` production behavior until review and merge. Existing production runs continue to use `main`.
