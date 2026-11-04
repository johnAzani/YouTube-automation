# The Secret Place: zero-cost operating contract

This document describes what the repository can enforce and what must be locked in the provider accounts. It is not a claim that the automation can inspect Google billing settings or guarantee that a third-party free tier will remain unchanged forever.

## Non-negotiable target

**Operating target: $0.00.** Do not add paid APIs, paid SaaS, paid Actions runners, paid fallback voices, paid stock, or paid hosting. When a quota or prerequisite blocks a release, fail closed and wait; never switch to a paid service to keep the schedule.

A source-code repository cannot see whether the Google Cloud project behind `GEMINI_API_KEY` has billing enabled. Therefore, the $0 guarantee is conditional on the account-side setting below. Do not enable billing on the project used for this channel. If its free quota is exhausted, the request must fail rather than become billable. The workflow cannot independently verify that project setting.

## What the active production path uses

| Stage | Current implementation | Cost boundary / constraint |
|---|---|---|
| Long-form and Short narration | Google Gemini TTS, model `gemini-3.8-flash-tts`, voice Charon | Uses the configured API project. Its free limits are project/model/tier-specific and can change. The latest production failure reported **10 TTS requests/day** exhausted; do not treat older generic Gemini limits as TTS limits. |
| Queue writing / expansion | Gemini text API | Also quota-limited; it is a separate API workload from TTS. Queue repair is bounded and production can continue from existing approved scripts if the brain is unavailable. |
| Video rendering and alignment | FFmpeg and local CPU alignment on GitHub Actions runners | No third-party render/transcription SaaS. Public-repository runner eligibility and GitHub policy remain external dependencies. |
| Visuals | Existing licensed asset catalogue and keyless/free sources, with the source/licence ledger gate | No paid stock fallback. A missing or unverified source must fail or use an already-approved local plate. |
| Upload | YouTube Data API with the channel's OAuth credentials | YouTube API quota is free but finite and can be changed or exhausted. No paid upload fallback. |
| Workflow, source, and review pages | GitHub Actions and GitHub Pages | This repository relies on public-repository free allowances and current GitHub terms. |

The old generic figures sometimes quoted for Gemini (for example, 1,500 requests/day) are **not** evidence of the TTS allowance. The active model's quota must be read from its API error/Google project quota page. No exact daily publishing volume is guaranteed by a free-tier request count: long-form narration may consume multiple calls, Shorts consume calls when their audio is not cached, and transient failures may consume attempts.

## Required account-side lock (manual, cannot be proved by CI)

1. Keep the API key on a Google AI Studio / Generative Language API project with **billing disabled**. Do not attach a billing account or enable Vertex AI billing for this key.
2. Restrict the key to the APIs and environments actually needed. Never put it in repository content, logs, fixtures, or a commit; GitHub Actions receives it through `GEMINI_API_KEY`.
3. If the provider console shows the project is billable or its status is uncertain, remove the key from production secrets and pause publishing until the account is checked. A repository variable such as `ZERO_DOLLAR_MODE=true` cannot prove billing is disabled.
4. Keep optional Pexels/Pixabay keys absent unless their free-plan terms and limits have been reviewed. Missing optional asset keys must not trigger a paid fallback.
5. Do not add a paid fallback model, voice, rendering service, runner, storage service, or stock source in a future change.

## Fail-closed behavior in code

- Gemini TTS quota errors pause the affected long-form item or Short manifest with a reset timestamp. They do not switch production narration to Edge TTS or a different paid model.
- A shared circuit breaker now checks both queue types before every Gemini TTS request. A live TTS quota pause for either format blocks another narration request until the reset; this prevents the next Short/long-form job from repeatedly probing an exhausted allowance.
- Finished chunk audio is cached/restored between production runs, so a resumed long-form narration does not intentionally repay already-completed chunks. Cache availability is best-effort, not guaranteed storage.
- YouTube quota failures pause uploads; they do not change provider or privacy settings.
- The misleading, unused `ZERO_DOLLAR_MODE` config field was removed. No repository flag can attest that an external billing account is disabled.

## Operating expectations

- The production workflow has three scheduled slots per day at 06:14, 14:14, and 19:14 UTC, but one or more may publish nothing because of quota, missing credentials, a failed runner, or an empty eligible queue.
- A quota reset is not a promise that the next slot will upload. The queue still needs an approved eligible script, valid audio/rendering, and a successful YouTube upload.
- The latest observed production failure (run `41743246072`, 2026-11-04) exhausted the Gemini TTS daily allowance. The run paused a long-form item until the returned reset time and uploaded nothing. This is the correct $0 behavior, not a missed guaranteed upload.
- Free-tier limits and platform policies can change. Recheck the provider's own console and public terms periodically; code can prevent paid fallback but cannot freeze another company's free plan.

## Review checklist for future changes

- [ ] No paid API, paid subscription, paid Actions runner, or billable fallback is introduced.
- [ ] Every new provider call has a bounded timeout, quota/transient classification, and fail-closed path.
- [ ] Quota state is shared across formats that use the same provider/model.
- [ ] TTS chunk/audio cache survives the common retry path without stale-text reuse.
- [ ] Uploads are verified and recorded; retries cannot knowingly duplicate a live video.
- [ ] Documentation states observed/project-specific limits, not generic quota figures as guarantees.
- [ ] The account-side billing-disabled prerequisite remains true; repository code cannot attest it.
