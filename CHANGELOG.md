# Changelog

Notable changes to the studio. Newest first. Reconstructed from `git log` on 2026-10-20 —
there was no changelog before this file.

---

## 2026-11-14 — Shorts refused over one unheard word

- First run of the new mix (5:27am Nigeria time): of the first seven channels, three published their Short and four were refused with `alignment does not cover the narration in order`. The speech aligner (`pipeline/prayer_alignment.py`) accepts a take when 85% of the script is recognised and gives a word it did not hear a zero-length span; the check after it in `pipeline/short_release.py` refused any word with no length. One unheard word refused the Short, and longer Shorts were refused more often (93 and 96 words went out; 99, 114, 120 and 133 were refused; the token lists were identical in all six). This is the failure that stopped Shorts on seven channels on 13 November.
- `_spread_unheard_words` gives such a word the silence between its neighbours, or a share of the previous word's span by length. Words that were heard are not moved. A take that is out of order is still refused, and the error now names the word and the times.
- Not proven on the failing audio itself: the recordings are on the runners. The reasoning is the error's origin (one line), identical token lists, and a reproduction through the real aligner with one word removed. If a Short is refused again the message says which word and why.

## 2026-11-14 — one long-form and five Shorts a day; Shorts that stand on their own

- The owner handed the mix decision over. Each channel still makes six uploads a day, now one long-form and five Shorts instead of three and three (91 Shorts drew 7,513 views, 95 long-forms 261). Full note: `docs/SHORTS_FIRST_MIX_2026-11-14.md`.
- `.github/workflows/produce.yml`: two more slots, 10:14 and 23:14 UTC (11:14am and 12:14am Nigeria time). Every slot owes each channel a Short; one slot a day owes it a long-form (`LONGFORM_SLOT_UTC` in `scripts/produce_plan.py`, two channels to a slot). A new step asks `scripts.produce_plan --longform-due` and the long-form step is skipped only on an explicit "no". A channel whose newest long-form is over 26 hours old is owed one at any slot. A Shorts-only slot whose Short did not publish gets a long-form instead of nothing, not within 7 hours of the last one. New `longform` input forces one by hand.
- `scripts/scheduler_supervisor.py`: a slot is served by what it owes the channel, a long-form at the channel's long-form slot and a Short at the others, so the supervisor recovers a missing Short and does not chase a long-form the slot never makes.
- New `pipeline/evergreen_shorts.py` and `GeminiBrain.generate_standalone_short`: a Short no longer needs a long-form. 150 well-known passages (15 per channel, none shared), then the channel's roadmap ahead of its long-forms; never a second Short on a passage the channel has. Standalone manifests are named `0000-<key>.yml` and go out first. The daily brain run keeps ten Shorts ready per channel.
- `scripts/automation_monitor.py`: "produce published nothing" is judged against the slot the run belonged to, not the calendar date. A late run that correctly did nothing after midnight UTC kept the monitor red for six hours on 14 November.
- Passage lists last about eight to eleven days at this pace; a run says so when a channel has fewer than eight left.
- Tests: `tests/test_shorts_first_mix.py` (36); slot expectations updated in `tests/test_scheduled_publishing.py`, `tests/test_parallel_production.py`, `tests/test_supply.py`.

## 2026-11-14 — acting on the view counts: Shorts openings, 41 queued titles

- Read the ten analytics snapshot issues of 13 November: 95 long videos drew 261 views (median 1, 35 with none); 91 Shorts drew 7,513 (median 65). 97% of all views come from Shorts. Table and reasoning: `docs/GROWTH_EVIDENCE_2026-11-14.md`.
- `pipeline/short_script.py`: the Short prompt no longer hands the model the channel's stock invitation as its first line (every channel's Shorts opened with one skeleton; the view counts do not prove that costs views, but it is templated content). The first sentence is now written for that Short, at most 16 words, about the listener's moment; the channel's used openings are listed for the model to avoid (`recent_openings`). Target length 105 words (was 120); validator limits unchanged. New Shorts only.
- 41 queued long-form jobs retitled need-first with the scripture reference kept; 13 thumbnail lines replaced with whole phrases. Fact-check worksheets regenerated. Short keys, slugs and scripture references unchanged.
- Tests: `tests/test_short_hook_standard.py` (17).

## 2026-11-14 — background music 3 dB louder (voice unchanged)

- Owner feedback on the first mastered videos: "the voice is perfect, the background music volume is a little low". `pipeline/voice_master.py` now lifts the music bed by 3 dB in the mastered mix (`MUSIC_LIFT_DB`, recipe `voice-master-v2`), long-form and Shorts. Voice over music goes from 14.6 / 17.4 LU (pauses / speech) to 11.6 / 14.4 LU; the voice stays at -15 LUFS and the finished mix at -14.9 LUFS, peak -1.5 dBFS. Applies to new renders only. Notes: `docs/VOICE_AND_VIEWER_FIRST_2026-11-13.md`, "Music balance".

## 2026-11-13 — Shorts no longer stuck behind a rejected take; scheduled-publish trial result

- Seven channels failed the same Short in two production runs ("Short speech alignment unavailable or incomplete"). The rejected narration was saved to the Actions cache, restored next run, still looked valid and was refused again; Shorts release in order, so those channels released none. `pipeline/short_release.py` now deletes a rejected take, synthesises one fresh take in the same run when the rejected one came from the cache, puts the aligner's reason in the error, and after three rejected takes marks the manifest `alignment_paused` so the channel's next Short releases. A missing speech model is not treated as a bad take. Notes: `docs/SHORT_ALIGNMENT_RECOVERY_2026-11-13.md`.
- `pipeline/voice_master.py` writes its outcome to the run page (`Voice master (<file>)` notice, or a warning when a render falls back to the unmastered mix).
- Scheduled-publish trial (job `0406`, The Healing Balm): the upload was accepted as private with a publish time, YouTube made it public without the monitor's help, and the owed pinned comment was posted at the next monitor pass, 39 minutes after the slot. Recorded in `docs/SCHEDULED_PUBLISHING_2026-11-13.md`.

## 2026-11-13 — louder, clearer voice on every video; titles and openings written for the viewer

- New `pipeline/voice_master.py`. Finished videos measured about -19 LUFS against YouTube's -14 reference (YouTube never turns a quiet video up) with the music only 10 LU under the voice. The final encode of long-form (`pipeline/prayer_visuals.py`) and Shorts (`tools/shorts.py`) now measures the narration, shapes tone, compresses gently, applies one fixed gain to -15 LUFS / -1.5 dBTP, ducks the music about 2.5 dB under speech and limits the mix at -1 dBFS. Measured before/after on the committed Psalm 91 narration: -19.1 → -14.9 LUFS, same duration. The narration file, its cache and word timings are untouched; no speech is re-synthesised. A failed measurement falls back to the previous mix.
- New `pipeline/brain_equipment/viewer_first_standard.md`, appended to every channel's authoring prompt. Titles lead with the listener's need, then the scripture (still 35-70 characters, still ending with the channel name); no greeting or channel name in the first three sentences; scripture within 45 seconds; no promised outcomes. The front-matter skeleton no longer shows `<reference> <daypart> Prayer`.
- `strip_channel_greeting` (`pipeline/gemini_brain.py`) removes a first sentence that only says "…welcome to <channel>." at authoring time; ten of the twelve most recent scripts opened that way. Skipped when it would take a script under the 850-word floor.
- Thumbnail line: `_clamp_thumb_text_for_ctr` replaced any line whose first three words were too wide with the fixed phrase `PERFECT PEACE`; two Family Altar jobs authored in one pass (`0309`, `0310`) got the same unrelated line and `tests/test_supply_never_stalls.py` was failing on `main`. The line is now kept whole when it fits (up to four words) or cut to a contiguous part of its own words. The two jobs read `A HEDGE AROUND US` and `A BLESSED HOME`; worksheets rebuilt.
- `tests/test_workflow_channel_selection.py` read the live slot ledger through the produce plan, so it failed on every branch for the hours after The Secret Place had been served in a slot. It no longer depends on what has been published.
- Applies to newly authored scripts and newly rendered videos. Other queued jobs and published videos are unchanged.
- Notes, measurements and limits: `docs/VOICE_AND_VIEWER_FIRST_2026-11-13.md`.

## 2026-11-13 — scheduled publishing: four faults found before the first live upload, and the trial

- `scripts/sync_published_thumbnails.py` made any private, processed, full-length long-form public when its receipt wanted public. A scheduled upload is private on purpose, so the monitor would have published it early whenever its thumbnail was still pending (32 of 76 long-form receipts on 13 November). It now skips a video with a `publishAt` on YouTube or `scheduled_publish: true` on its receipt.
- `scripts/confirm_scheduled_publish.py` asks YouTube whether the channel's comment is already under the video before posting an owed one (a lost receipt edit used to mean a second copy), retries a refused comment on later passes, and stops after three refusals (`pinned_comment_failed: true`).
- `publish_at:` in a job's front matter now goes through the same checks as a dispatch time: at least 15 minutes ahead, no later than the next production slot, otherwise public at once. An unquoted value (a YAML date) is sent as text, and a time YouTube refuses falls back to public at once.
- A publish time may be the word `next-slot`. `produce.yml` also reads it from the `publish-now` repository_dispatch payload (`client_payload[publish_at]`).
- Trial: `content/queue/0406-philippians-4-6-7-peace-that-passeth-understanding-prayer.md` (The Healing Balm) carries `publish_at: next-slot`. It is the first video ever uploaded with a publish time.
- Receipts overwritten by the last serial run (`086bc51`, `a2204a6`, `6ab1229`) restored: `0601-genesis-15-1-protection-prayer.md`, `0700-psalm-100-4-thanksgiving-prayer.md`, `short-gardenpsalm100v4-thanksgiving-prayer.md`, `0800-proverbs-3-5-6-guidance-prayer.md`, `short-guidedproverbs3v5-guidance-prayer.md`. That run ended at 3:42pm WAT; it was the last one created before legs started from current `main`.
- The same serial leg (`a2204a6`, working from a checkout made at 1:17am WAT) authored a second job numbered `0702` for The Praise Garden on the scripture the queue already held, and overwrote that job's companion Short script. Two jobs with one ID are both skipped by production, so the channel had nothing publishable. The later copy and its worksheet are removed and the Short manifest and script are back to the earlier version.
- Details: `docs/SCHEDULED_PUBLISHING_2026-11-13.md`, "Second read".
- Observed at 3:42pm WAT: the scheduled production run waiting on `content-state` (created 3:34pm, with `queue: max`) was cancelled the second the lock was handed to a brain run created at 11:57am, before `queue: max` was merged. The supervisor dispatched the nine unserved channels three minutes later. See `MAINTENANCE.md`.

## 2026-11-13 — scheduled publishing, built and switched off

- A long-form can be uploaded private with a publish time so YouTube makes it public on the slot minute. `pipeline/publish_schedule.py` decides: an explicit `publish_at` on a manual dispatch of `produce.yml`, otherwise the production slot plus `PUBLISH_LEAD_MINUTES` (`scripts/produce_plan.py`, **0 = off**, overridable by the repository variable `PRODUCE_PUBLISH_LEAD_MINUTES`). Less than 15 minutes to go, a past time, an unreadable value or any error publishes at once. A lead that reaches the next slot is refused.
- Receipts for a scheduled upload are dated with the public time and carry `scheduled_publish: true`, `privacy_status: private` and `uploaded_at`. With the switch off, receipts and the upload request are unchanged.
- New `scripts/confirm_scheduled_publish.py`, run by the monitor: after the public time it confirms the video is public, posts a pinned comment YouTube refused on the private video, publishes a video still private 20 minutes late, and marks a rejected or missing video `scheduled_publish_failed` so the supervisor produces the channel again. No API call before the public time.
- `upload()` retries public at once when YouTube answers `invalidPublishAt`, and never gives a publish time to an upload that is meant to stay private.
- Not on yet: the first scheduled upload is a one-channel trial; turning it on for the schedule is one change (crons 4 h 30 min earlier, lead 270). Shorts and per-channel times are not built. Steps and sources: `docs/SCHEDULED_PUBLISHING_2026-11-13.md`.

## 2026-11-13 — waiting runs keep their place, comment ledger cannot be dropped

- `produce.yml` and `gemini_brain.yml` set `queue: max` on the shared `content-state` lock. GitHub then keeps every waiting run in arrival order (up to 100) instead of one; before, a newer waiting run cancelled the older one. Checked on this repository with two throwaway workflows sharing one group: six runs, one at a time, alternating in arrival order, none cancelled.
- `comments.yml`: each channel leg checks out the branch tip (`ref: ${{ github.ref }}`) instead of the commit the run was created at. The reply ledger is one JSON object for all channels, so a leg on the old commit conflicted with the entries the previous leg had pushed, on every retry, and the step still ended green with the entries dropped. The commit step now aborts a failed rebase, tries five times, and fails with `Reply ledger not recorded` if the entries are not on the branch. Nobody was answered twice by this: the engine also looks for the channel's reply on YouTube. Whether production ever dropped an entry this way is not established (it needs two channels to post replies in the same run, and the run logs cannot be read from here); the fault is reproduced in `tests/test_comments_ledger_rehearsal.py`.
- Three more receipts overwritten by the last serial run (`99c3716`, `e45a240`, 13 November) restored with `scripts/repair_clobbered_receipts.py`: `0404-exodus-15-26-jehovah-rapha-healing-prayer.md` (publish time back to 03:44:08 UTC), `0504-psalm-90-17-morning-prayer-the-provision-table.md` (back to 04:52:46 UTC) and `short-healingexodus15v26-restoration-prayer.md` (full receipt back).

## 2026-11-13 — channels are produced side by side

- Production legs now run in lanes instead of one after another. The plan job sets `max-parallel` from the repository variable `PRODUCE_MAX_PARALLEL` (default 5, clamped to 1–10; `1` restores the serial matrix with no code change). Measured 8–13 November: ten legs in a row took 537 minutes, production held `content-state` for 1,412 minutes of 12 November, and that day published 17 long-forms of the 30 scheduled with three channels getting none. Replaying the recorded leg times with five lanes gives 118 minutes. Not yet run in production; the lane expression was checked on GitHub with a throwaway workflow.
- A scheduled run no longer publishes a slot twice: it drops every channel that already has a long-form receipt dated at or after the current slot (`scripts/produce_plan.py`). If that check fails the run produces every channel.
- `produce.yml` accepts `channels` (comma-separated) on manual and `repository_dispatch` triggers. The supervisor sends every channel that owes the slot in one dispatch, tries a channel at most twice per slot, and steps in 30 minutes after a production slot instead of 90. Other workflows keep 90.
- Fixed `prev_occurrence()`: with several cron lines it returned yesterday's first slot from 00:00 UTC until the first slot of the day, so the 19:14 UTC production slot stopped being recoverable at midnight UTC instead of after six hours. `comments.yml` was affected the same way.
- Commit step: twelve attempts instead of six (ten lanes can need ten), a random extra delay between attempts, and its path lists in a private `mktemp -d` directory instead of fixed names in `/tmp`.
- Added `scripts/repair_clobbered_receipts.py` and used it: ten receipts overwritten by stale legs between 7 and 13 November are restored (six `published_at` values, four full Short receipts). Nothing on YouTube was changed.
- Still open: upload idempotency when a leg dies between the YouTube upload and the receipt commit (unchanged by lanes; a channel never has two legs at once), `queue: max` on the lock (verified available, not applied), and scheduled publishing, which is what would put a video on the slot minute. Research, evidence and plan: `docs/PARALLEL_PRODUCTION_2026-11-13.md`.

## 2026-11-13 — production legs start from current main

- Each production leg now fast-forwards to `origin/main` before it reads queue or receipt state, and stops with a `Stale checkout` error if it cannot. `actions/checkout` had pinned every leg to the commit its run was created at; with runs waiting up to 401 minutes for the `content-state` lock and a ten-channel matrix holding it for 537, a leg routinely started on a tree older than its own channel's previous publish. Runs on a ref other than `main` keep the commit they asked for. `START_SHA` is written after the fast-forward.
- Measured effect of the stale tree, 8–13 November: four publish commits (`e19ed94`, `c34235b`, `56983d3`, `1e4286c`) re-stamped an existing long-form receipt with a later `published_at` and reset its thumbnail state, and three of them replaced a real Short receipt with a recovered stub after rendering that Short a second time. Video IDs are unchanged; there was no duplicate upload. The seven receipts are not repaired by this change.
- With the commit guard from the previous entry, the same stale leg would be refused instead — together with the receipt for the video it had just uploaded. A test reproduces that; no production run has used the guard yet.
- Added `tests/test_produce_leg_rehearsal.py`, which runs the refresh and commit steps taken from `produce.yml` against a local bare repository: stale, current, off-`main`, unreachable and diverged checkouts, and two channels whose pushes race. `max-parallel` remains 1.
- Details, timeline and what is left for the owner: `docs/STALE_CHECKOUT_RECEIPTS_2026-11-13.md`.

## 2026-11-13 — future Short narration and footage

- Prayer Short cards use the complete narrated text and audio-bound word alignment, rather than condensed authored phrases. Production requires complete local alignment; estimates are limited to preview.
- Rotate stock candidates by edition and scene, exclude selected and recently recorded channel footage, and require at least two distinct licensed video clips in production. Missing alignment or varied footage stops the Short and preserves its queue entry. Older receipts lack source fingerprints and cannot establish historical reuse.

## 2026-11-13 — all-channel automation safety

- Supervisor inspects production matrix jobs and cancels only when every active job exceeds the 240-minute job cap plus grace; queued workflow status, missing data, fresh legs and failed job lookups cannot justify a cancellation. Other workflows are left alone pending workflow-specific policies.
- Long-form and authored Shorts now fail closed instead of substituting Edge speech for Gemini Charon. Narration caches are tied to the model, voice, text and audio hash; old unverified Shorts caches are re-synthesized, while legacy prayer Shorts without provenance and pre-rendered production prayer Shorts are refused. This may consume free quota on the first retry and may delay releases when Charon is unavailable.
- New confirmed receipts can record the narration model and voice, long-form receipts receive the actual thumbnail outcome, and Short thumbnail success must match the receipt's video ID. Long-form and Short recovery verify remote ownership, title, privacy, timestamp and status before recording a match; recovered receipts do not claim a voice, thumbnail or metadata revision that was not verified. Short replacement no longer automatically deletes legacy videos; rejected replacements retain their queue state for review.
- Before every producer state-commit attempt, compare touched and deleted paths with the run's starting commit and the latest main. Refuse conflicting overwrites, preserve pending content in the run report and require reconciliation before retries. This path-level guard does not make parallel uploads safe.
- The dashboard labels receipts and reports receipt-based thumbnail pending counts and the monitor snapshot time, rather than claiming zero missed slots. Missing monitoring state is not healthy. Feedback commits require both successful metrics collection and successful computation, so an old checkout cannot replace a newer report after a failed step. Aggregate diagnostics describe receipt matches and signal thresholds; only mature, measured videos influence theme scores and guidance. Metrics collection checks the authenticated channel against the configured expected ID without extra API calls, warning if none is configured. Guided Path's YAML time strings are quoted and validated.
- Added three planned Morning Altar roadmap entries, restoring the branch's unqueued headroom from 14 to 17; these are plans, not approved scripts or published videos.
- Resumed quota-paused jobs now pass the same published-receipt and minimum-length checks as other approved jobs. Existing published job IDs block re-use even with a different slug or unreadable receipt. `--all` processes every selected job instead of stopping after the first; errors and quota pauses still stop the run. `--next` remains limited to one new release and continues past a verified duplicate recovery. Remote duplicate checks scan up to 20 playlist pages and fail closed on invalid, incomplete or ambiguous results, including before long-form narration, unless the explicit duplicate override is set. Title lookup still does not guarantee exactly-once delivery.
- Production remains sequential: channel-level parallelism needs isolated state writes and upload/receipt recovery before it is safe. Nothing here deploys to the live schedule.

## 2026-11-06 — the schedule was measured, and the recovery was rebuilt around the measurement

Between **02:52 and 07:52 UTC** (03:52–08:52 WAT) nothing in this repo ran at all: not the brain's
03:14 slot, not produce's 06:14 slot, not the monitor's two checks, not the supervisor's
fifteen-minute tick. Every workflow was `active`, there were zero queued runs, and GitHub reported
no open incident. The owner found out by asking. What the run history actually shows:

- **Cron delivery here is late, not punctual.** Over 1-6 November a scheduled run lands a median
  of ~57 min after the slot it serves, p90 ~3.3 h, p95 ~3.4 h — and the brain's 03:14 slot is
  delivered at **10:53, every day: +7 h 39 m**. The 14:14 produce slot lands 14:26–14:34.
- **High-frequency crons are thinned; low-frequency ones are not.** Comments (3 crons) got 3 runs
  a day; produce (3) got 3; brain (1) got 1; growth (1) got 1. The supervisor asked for **96**
  (`*/15`) and was delivered **~4** — at random hours. Its 15-minute cadence was an illusion.
- **So the recovery path expired before it could run.** The supervisor only dispatched a dropped
  slot between 90 min and 6 h after it was due. But it was *delivered* hours late and only a few
  times a day, so by the time it looked, the slot it exists to recover was outside its own window.
  A missed night therefore had no repair path at all.
- **And the alarm was starved.** Every verdict in `content/monitor/status.json` is recomputed by a
  cron-driven workflow; when none of them start, the file keeps its last values and still reads
  healthy. Silence was not a state the system could represent.

Fixes:

- **`_slot_window()`** — a dropped slot is recoverable until its **successor is due** (one
  occurrence period), instead of a flat 6 h. Publishing keeps a tighter 6-hour leash
  (`USEFUL_WINDOW`): a video hours late is worse than the next slot. Weekly slots cap at 24 h.
- **`_newest_per_workflow()`** — catching up dispatches **one** run per workflow (the newest
  missed slot), because three missed produce slots are three uploads otherwise.
- **`schedule_health()` + `content/monitor/schedule-health.json`** — repo-wide
  `silence_minutes`, `last_run_at`, and per-workflow `late_minutes` (the 03:14→10:53 case is now
  recorded as +459). `::error title=Schedule stalled` at 240 min, `::warning` at 120 min, both
  thresholds derived from the measured p90/max of normal delivery.
- **`pipeline_watchdog.check_schedule_health()`** — silence is now a first-class, *fatal* finding
  in the watchdog issue, measured from run history rather than from another workflow's verdict,
  so whichever pass is alive reports it. This is the first check in the file that is about the
  repository instead of about one workflow.
- **`scheduler-supervisor.yml`** — `*/15` → `47 0,3,6,9,12,15,18,21 * * *` (ask for what the
  scheduler actually delivers, never more than 3 h apart), plus `workflow_run` triggers on
  metrics, growth, thumbnails, alignment and expand-scripts so every completion is a free
  recovery chance. The dispatch ledger and the health snapshot are both committed.
- **`expand-scripts.yml`** gained the `name:` it never had — without it the workflow is addressable
  only by file path and is invisible to every `workflow_run` list.
- **Tests:** 12 new/updated (`tests/test_scheduler_supervisor.py`, `tests/test_supply.py`) pinning
  period-based recovery, newest-slot-only dispatch, produce's tighter leash, the +459 min late
  delivery, the stall annotation, the watchdog finding, and the new cadence.

## 2026-11-06 — a published video can no longer go live without a thumbnail and say it has one

The two videos on The Morning Altar published with YouTube's auto-picked frame instead of their
`ctr-v3-cinema` card. Nothing reported it, and the code was doing three things at once to hide it:

- **The uploader swallowed the failure.** `upload()` applied the thumbnail inside a bare
  `except` that printed one line into a step log (`thumbnail set failed (quota is 50
  units/day): ...`) and continued. The run stayed green, the video published.
- **The receipt lied.** `_mark_job_uploaded()` stamped `thumbnail_revision: ctr-v3-cinema`
  unconditionally — before knowing whether the thumbnail landed. The live repair pass
  (`scripts/sync_published_thumbnails.py`) trusts that stamp, so both videos were skipped
  forever as "already repaired".
- **The repair pass only knew one channel.** The monitor ran it with channel 1's token, which
  cannot touch channel 2's videos anyway.

- **`UploadResult.thumbnail_status`** — `ok` / `failed: <reason>` / `missing_file` /
  `by_design_short` / `not_requested`. A refusal now prints an `::error` annotation naming the
  channel, the video and the three things to check (phone verification, `youtube.force-ssl`,
  quota) and appears on the run summary.
- **Honest receipts**: `thumbnail_revision` is stamped only when YouTube accepted the
  thumbnail. Otherwise the receipt records `thumbnail_pending: true` + `thumbnail_error`, which
  is what queues the video for repair. `THUMBNAIL_REVISION` moved to `pipeline/thumbnail_ctr.py`
  so the uploader and the repair pass share one literal.
- **Channel-scoped repair**: `collect_pending_receipts(channel_id=...)` and
  `sync_published_thumbnails(channel=...)` only touch receipts belonging to the channel whose
  credentials are loaded; a refused repair keeps `thumbnail_pending` and records the API's own
  words. New `--all-channels` runs every channel with its own token; `monitor.yml` now passes
  both channels' secrets and runs the repair for both.
- **The two live videos un-stuck**: receipts 0036/0037 lost their false revision stamp and are
  queued for the next monitor pass.
- **Tests**: 8 new (`tests/test_production_safety.py`, `tests/test_sync_published_thumbnails.py`)
  pinning stamp-on-success-only, pending-on-refusal, channel isolation and both-channel coverage.

## 2026-11-05 — channel parity locked: one engine, every channel (no per-channel branches left)

- **New `pipeline/channel_capabilities.py`** — the only place that knows which channel is which. Each channel declares its equipment files, roadmap namespace, brand strings (title suffix, CTA, producer line, required/forbidden phrases, pinned comments, Shorts dressing), Short key namespace, supply target and legacy queue-row name. `REQUIRED_CAPABILITIES` lists the ten capabilities every channel has; there are **no per-channel feature flags**.
- **Every hardcoded channel branch removed** from `pipeline/gemini_brain.py`, `pipeline/brain_equipment/equipment_registry.py`, `pipeline/pinned_comments.py`, `pipeline/short_release.py`, `pipeline/short_script.py`, `pipeline/shorts_bridge.py`, `tools/expand_scripts.py`, `scripts/gemini_brain.py`, `scripts/continuous_research.py`, `scripts/scheduler_supervisor.py`, `scripts/automation_health.py`, `scripts/pipeline_watchdog.py`.
- **Secret Place brought up to Morning Altar's level**: same supply entry point (`--ensure-supply-for <channel>` in both workflows), per-channel watchdog rows (its empty queue now raises its own alarm instead of being folded into a legacy row), per-channel Shorts rows, channel-branded audit output, and data-gated performance steering (no longer a Secret-Place-only code path).
- **The Morning Altar brought up to Secret Place's level**: companion **Shorts** are now a capability of every channel — manifests carry `channel:`, keys are namespaced (`short-morning…`), editions/titles/tags/descriptions/end cards/pinned comments are branded per channel, selection and the pacing guard are channel-scoped, and published receipts record their channel.
- **Authoring is model-only on every channel.** The Psalm 121 "equipped template" is gone: it was emitted under other psalms' titles (the 0011 defect) and was under the 850-word publish floor anyway, so it could only ever produce a mislabelled or unpublishable file. Both channels now refuse identically and idle. Roadmap exhaustion also refuses on both (no more reusing a psalm with a fresh id).
- **Correctness fix found while doing this:** a brand rejection raised inside the authoring loop was being swallowed by the generic exception handler and fell through to the offline fallback, i.e. "this text is mislabelled" could become "publish it". `BrainAuthoringError` now propagates.
- **Workflow symmetry**: `produce.yml` and `gemini_brain.yml` no longer gate a step on `matrix.channel != 'prayer2'`; queue check, queue repair, Shorts and render run for every channel, parameterised by `CHANNEL_ID`.
- **New `tests/test_channel_parity.py` (30 tests) + `scripts/channel_parity.py`** — the lock. CI fails on: a capability missing for a channel, a channel literal in a comparison anywhere in `pipeline/`/`scripts/`/`tools/` (allowlist: the registry, profiles, roadmap map, dataclass defaults), a channel-gated workflow step, a workflow that stops covering a channel, un-namespaced/colliding Short keys, editions resolving across channels, or branding that leaks between channels. `automation-health.yml` runs the CLI daily and prints the matrix to the run summary.
- **Docs:** `docs/CHANNEL_PARITY.md` (the rule + how to add a channel), updates to `docs/MORNING_ALTAR_BRANDING.md`, `docs/SECOND_CHANNEL_SETUP.md`, `docs/GEMINI_BRAIN.md`.
- **Tests:** full suite **812 passed + 1725 subtests, 0 failed** (was 782).

---

## 2026-11-04 — closed-loop growth engine: the brain stops publishing blind, dormant engines wired ($0.00)

- **New `pipeline/performance_feedback.py` + `scripts/performance_feedback.py`** — the missing keystone. Reads the public metrics snapshot + published receipts, scores each long-form video on reach (view velocity, ≥3-day gate) and satisfaction (engagement rate, ≥25-view gate), aggregates by theme, and writes the **derived-only** `content/research/performance_feedback.json` (theme ranks + guidance; no raw counts or video IDs). Confidence-gated (<3 measured videos → neutral) and fail-soft; Shorts are a separate lane and never steer long-form.
- **`GeminiBrain.select_next_scripture()` now reads the feedback** at the sole authoring choke point: above-average themes first, unmeasured keep roadmap place, below-average last. Missing/corrupt artifact never blocks authoring.
- **New `.github/workflows/growth-autopilot.yml`** — daily 03:14 Nigeria time (02:14 UTC): metrics snapshot → feedback → **series-playlist autoplay sync** (session watch-time, idempotent) → **live-count milestone celebration**. Every engine fail-soft; commits only the derived feedback via the monitor.yml fetch+reset pattern; raw metrics + milestone card are 30-day artifacts. Uses the existing upload token; no new secret.
- **`scripts/celebrate_milestone.py`** reads the live subscriber count from `channel-metrics.json` instead of the hardcoded 1230; skips rather than guesses when unavailable.
- **`pipeline/metadata.build_tags`** wires in the dormant `seo_suggest` high-intent taxonomy (pain-point/search queries); still bounded by `fit_youtube_tags` (500-char budget, 18-tag cap, 432 gate) — verified 18 tags / cost 470 / no 432.
- **`scripts/continuous_research.py`** next-job is now feedback-aware/dynamic instead of the stale hardcoded Psalm 23 (already published).
- **Privacy:** `content/metrics.csv` added to `.gitignore` (raw API metrics can no longer be committed to the public repo).
- **Deliberately not auto-published:** multi-hour sleep compilations (static plate + ambient tone = inauthentic-content risk + multi-hour OOM) and podcast auto-grow (needs hosted per-episode audio). Honest Studio-only limits documented (Community posts, Test & Compare, end screens/cards, Shorts related-video link, per-video thumbnail CTR).
- **Docs:** `docs/GROWTH_FEEDBACK_LOOP_2026-11-04.md` (deep research + sources + limits); STATE.md §4/§7 + ledger updated.
- **Tests:** 25 new (feedback engine + brain-steering integration); 2 stale-behavior tests updated; scheduler-supervisor tests made robust to new workflows. **Full suite: 734 passed + 1632 subtests, 0 failed.**

## 2026-10-23 — branch consolidation onto `main`, 100% Enron rights clearance, and first YouTube Short release pipeline

- Consolidate all unmerged research, drafts, and strategy work (PR #11) onto `main`, close superseded partial draft PR #10, and delete all stale `arena/*` remote branches.
- Expand `tools/make_plates.py` with five deterministic procedural editorial illustrations (`enron-market-board-plate-1.png`, `enron-ledger-grid-plate-1.png`, `enron-pipeline-corridor-plate-1.png`, `enron-spe-network-plate-1.png`, `enron-courtroom-columns-plate-1.png`) registered as `status: cleared` in `image-search/LICENSES.yml`, eliminating all remaining Getty/unverified stills across both `short-enron` (10 unique cleared plates) and `deep-dive-enron` (16 scenes), fix foreshadow tease timestamps in `short-enron`, and refresh `docs/media/*`.
- Fix vertical (`9:16`) subtitle `PlayResX`/`PlayResY` scaling in `pipeline/assemble.py`, add native `#Shorts` metadata formatting in `pipeline/metadata.py`, update thumbnail branding to `Money, Explained`, and add `pipeline/short_release.py` + `produce.yml` (`inputs.short`) with fail-closed stream/aspect/duration/licence gates, YouTube upload, release ticket creation, and published receipt tracking under `content/published/`.

## 2026-10-23 — upload checklist for 0007, and a factual error caught in the draft

- `docs/UPLOAD_0007_CHECKLIST.md` — the twelve load-bearing claims with exact values and the
  document each one has to be checked against, the three conflated cancellation figures, the
  three figures the script refuses to state as fact, and the two passages (opening, verdict)
  that a human has to own before `human_rewrite: true` is true.
- **Correction:** the opening claimed Monday's $48,078 close was "already a record". It was not —
  nickel's prior all-time high was $51,800/t in May 2007. What set a record on 7 March 2022 was the
  intraday print of $55,000. Rewritten to say what happened.
- **Deletion:** "the largest cancellation of executed trades in the history of a modern exchange"
  is unsupported as a ranking. Removed rather than softened.
- Worksheet regenerated (the script hash changed); 96 checkboxes still.

## 2026-10-23 — first video drafted: the 2022 nickel squeeze (job 0007)

- `content/queue/0007-the-day-the-exchange-pressed-undo.md` — fourteen scenes,
  3,156 narration words, ~21 minutes at the pipeline's 2.5 words/second estimate.
  Draft only: `human_rewrite: false`, `status: draft`, so `select_jobs()` will not
  pick it up and `originality.enforce()` will refuse it until a human signs.
- Argues a mechanism, not a villain: the deliverable was narrower than the production
  (nickel pig iron is not LME nickel), the volatility control was switched off for
  3h26m, and finality is a clause in a private rulebook, not a property of a trade.
- Sources resolved to primary where they exist: LME Notices 22/052, 22/053 and
  22/070; FCA Final Notice 207387 (the £9,245,900 penalty and the $13.373bn
  notional); [2024] EWCA Civ 1168; OFR working paper 24-09. The three published
  figures for cancelled-trade value ($3.9bn / $12bn / $13.373bn) are named as
  reporting variants of different scope rather than averaged.
- `content/research/0007-nickel-squeeze-dossier.md` — timeline, cast, source
  register and an explicit "what the script must NOT claim" list (position sizes,
  the ~$1bn loss and the $19.75bn avoided margin call are reported, not disclosed).
- All fourteen `asset_queries` probed against the Commons search API and scored with
  `pipeline/assets.py::licence_ok_for_monetized_use`. Eight of the first-draft
  queries were replaced after returning zero usable hits — notably "nickel metal"
  (six Ni-MH battery photos, all CC BY-SA) and "canary wharf london" (six CC BY-SA).
- `content/factcheck/0007-…md` worksheet written: 96 checkboxes. A worksheet is not
  a verification; it is the list of things a human still has to check.

## 2026-10-23 — niche decided: education-categorised money-collapse documentaries

- Record the verdict on a 2-3 week monetisation request: 4,000 hours is 240,000
  minutes; YouTube review alone typically takes about a month (often a week at
  AIR). Fastest verified case 30 days; median 14-16 months.
- Record the real deadline: an application by 31 Jan 2027 is reviewed against
  4,000 hours even if the decision lands after the 1 Feb threshold change.
- Choose one niche and delete the rest: education-categorised money-collapse
  documentaries, 18-22 minutes, Tier-1 English, primary documents on screen.
- Evidence: Education & Science median RPM $10.22 vs Business & Finance $2.01
  (three channels, directional); 77% of Education views show an ad, the best
  fill rate measured. The queue already carries `category: education`.
- Set the six-video test: 20 min at 8 min AVD, 5,000 average views each = 4,000
  hours exactly; 30,000 views at 5% = ~1,500 subscribers. 1-in-5 odds, labelled
  as judgement.
- Mark the four earlier finance memos as superseded. No publishing, spending,
  approval or approval-flag change.

---

## 2026-10-23 — documentary strategy: style audit, AI-slop flood, length lever

- Audit the existing channel style: 9-minute financial-disaster documentaries
  (Lehman, LTCM, Northern Rock, Barings) with primary-source research dossiers.
  Record that the earlier paid-calculator recommendation does not fit it.
- Record live competition: the same lane is being flooded by 7-11 minute
  AI-assisted channels created in the last 58-73 days, and the current slate
  competes with 1-4M-view versions of the same stories (ColdFusion Barings 4.2M,
  FRONTLINE 1.8M, Moconomy Lehman 1.1M).
- Add the watch-hour arithmetic by runtime: 9 min needs ~106,667 views for 8,000
  hours, 20 min needs ~60,000; twelve 5,000-view videos fail at 9 minutes and pass
  at 20.
- Recommend mechanism-first case files at 18-22 minutes with the dossier as the
  paid product; re-sequence the launch slate to nickel squeeze, LDI gilts,
  Greensill; note the per-video budget must rise from 6 to ~9 hours.
- Add Revision 2 banner to the strategy decision memo. No publishing, spending,
  approval or approval-flag change.

---

## 2026-10-23 — finance strategy correction: RPM reality and product-first plan

- Add a decision memo correcting the earlier planning RPM. Real Studio data from
  300 channels (AIR Media-Tech, May 2025–May 2026) shows a $2.30 median RPM,
  $2.01 for business/finance (three channels, directional) and $10.22 for
  education; 53% of views carried an ad and subscriber size barely moved RPM.
- Record base rates: median ~16 months and 40–150 videos to 1,000 subscribers;
  89% of channels at 1,000 subscribers get under 5,000 monthly views.
- Compare three coherent strategies (media company, authority + product,
  Nigeria-first) and recommend the second: a math-forward money explainer for a
  Tier-1 audience with a paid calculation model as the product.
- Move the product ahead of the video in the 90-day plan; keep the 18-hour cap,
  no-new-spend rule, stop rules and human publishing gate.
- No rebrand, purchase, publishing, approval or private analytics disclosure.

---

## 2026-10-23 — finance demand evidence and revised topic strategy

- Add a source-checked demand/monetization study with 13 channel benchmarks,
  YouTube search snapshots, disclosed creator earnings, watch-time arithmetic and
  a plain account of why third-party earnings estimates disagree.
- Find that finance demand is large at category level but weak for dry definitions:
  top amortization/credit-interest videos have roughly 100K–340K lifetime views
  after 6–11 years, while stakes-driven rent/car/bank videos reach 400K–10M.
- Revise the first three topics to car cost, rent and bank economics; keep the
  original-calculation production model and human QA.
- Add a 12-point demand gate (9 to proceed) and revise the pilot to three videos,
  six weeks, 18 human-hours, no new spending, with explicit continue/stop rules.
- Record that watch time is private, that 4,000 hours is about 40K views at a
  6-minute average view duration, and that verified large earnings belong to
  personality/team businesses rather than passive faceless automation.
- No rebrand, purchase, publishing, approval or private analytics disclosure.

---

## 2026-10-23 — finance niche decision and low-regret pilot

- Research current YouTube originality, AI-finance-persona and YPP rules using
  official sources; distinguish policy evidence from unverified market demand.
- Recommend testing original money-mechanics explanations with worked examples,
  not an AI adviser or a high-volume scraped-news/stock-video channel.
- Add a qualitative nine-niche comparison, checked loan-cost example, 12-topic
  backlog, hypothetical revenue sensitivity and capped validation/stop rules.
- Flag overconfident income, liability, geography and payment assumptions in the
  older finance note/master plan. No RPM or monetization timeline is promised.
- No rebrand, purchases, publishing, queue approval or private analytics disclosure.

---

## 2026-10-23 — deep Lehman evidence audit and research revision

- Add a 22-entry source register, detailed research dossier, original-claim audit
  and revised-scene evidence map under `content/research/`, outside scheduler globs.
- Correct the Linklaters opinion, Repo 105/108 scope, cash-flow mechanics,
  gross/net leverage comparisons, AIG chronology and entity-specific recoveries.
- Record the Reserve Primary Fund's later NAV correction and distinguish the
  Fed participant account from the FCIC's analysis of the failed rescue.
- Rewrite all eight scenes with direct source links and explicit research limits;
  no claim that the full examiner report or every litigation docket was read.
- Regenerate 67 unticked worksheet boxes. All 19 focused factcheck/queue tests
  pass with PyYAML; the revised narration is 1,294 words (audio timing unmeasured).
- Keep `status: draft`, `human_rewrite: false` and all human certifications blank.
  Research is not human creative approval; no upload or publishing change.

---

## 2026-10-23 — explicit Analytics coverage and a private reporting path

- Add a separate, read-only Analytics collector with daily/video performance,
  traffic sources, country/device/demographic and subscription-status reports.
  Retention is opt-in per video; estimated revenue is separately opt-in.
- OAuth helper supports separate analytics and monetary-readonly consent without
  adding upload rights to Analytics tokens or changing existing upload defaults.
- No private reports in public Actions. Local output is restricted to gitignored
  `output/private-analytics/` with mode 0600. Raw error messages are withheld.
- Every report records its status, including missing permissions, empty data and
  pagination truncation. `docs/ANALYTICS.md` lists unimplemented/Studio-dependent
  fields and distinguishes implementation from verified live access.
- 12 focused metrics/Analytics tests pass. Live Analytics permission and private
  scheduled report delivery are still unverified/unconfigured.

---

## 2026-10-23 — include subscribers in the metrics snapshot

- Request channel `statistics` alongside the existing `contentDetails` using the
  existing YouTube Data API readonly permission; no new OAuth consent required.
- Report YouTube's subscriber count in logs, the Actions summary, and a
  short-lived `channel-metrics.json` artifact. Only channel ID, subscriber count,
  date and reporting caveats are exported; private video metadata stays excluded.
- Hidden/missing counts are unavailable, not zero. YouTube rounds subscriber
  counts to three significant figures; do not present them as exact live totals.
- Four focused metrics tests pass, including hidden, missing and zero counts.

---

## 2026-10-23 — replace Getty headquarters shots with original illustrations

- Both Enron renderer scene tables now use five original, abstract skyline plates
  instead of the five rights-encumbered headquarters photographs. These are
  illustrations, **not photographs of Houston or Enron Center**.
- `tools/make_plates.py` builds them from fixed seeds with Pillow, no downloaded
  images or fonts. Generated PNGs are ignored by Git and rebuilt by render setup,
  the renderer CLIs and the ledger CLI. Existing files are not silently overwritten
  by the latter two paths, so ledger drift remains visible.
- Ledger records the five originals with code provenance and pixel hashes; tests
  reproduce all five hashes and prevent the Getty HQ filenames returning.
- This is a partial clearance fix, not permission to monetize the demo videos.
  Other encumbered references and unverified downloaded images remain. No assets
  were deleted, no downloaded image was declared cleared, and no human script
  approvals or publishing settings changed.

---

## 2026-10-23 — apt hung, and the required CI check died before running a single test

PR #7 went red with `Unit tests + doctor: cancelled` — not `failure`, `cancelled`, which reads
like somebody clicked stop. Three runs in a row. The per-step statuses showed why:

```
System deps (ffmpeg)=cancelled, Python deps=skipped, Unit tests=skipped
```

It never reached the tests. The job sat inside `sudo apt-get install -y ffmpeg` for its whole
10-minute budget and was killed; two sibling jobs ran the identical apt step and passed, so the
mirror is intermittently slow, not broken. GitHub reports a job timeout as `cancelled`, so it
did not even look like a failure. Full write-up in MAINTENANCE.md §3 (2026-10-23).

### Fixed

- **Install order.** Every workflow ran apt *before* `pip install -r requirements.txt`, with no
  timeout on either apt call. Backwards: `requirements.txt` already pins `imageio-ffmpeg`, whose
  static build `pipeline.assemble.ffmpeg_bin()` can find. New composite action
  **`.github/actions/setup-render-deps`** runs pip first, then apt inside `timeout 120`/`timeout
  300` and non-fatal, then exports `FFMPEG_BINARY` from the static build if apt did not deliver.
  Used by all three `dry-run.yml` jobs, `produce.yml` and `remaster.yml`.
- **The three renderer CLIs had no fallback at all.** `tools/deep_dive.py`, `tools/shorts.py`
  and `tools/motionstudio.py` did `os.environ.get('FFMPEG_BINARY', 'ffmpeg')`, so they broke on
  any machine without system ffmpeg even though a static build was installed. All three now
  resolve through `ffmpeg_bin()`. Verified with no ffmpeg on `PATH` and `FFMPEG_BINARY` unset:
  `tools/shorts.py short-enron` rendered 1252 frames and exited 0.
- **`remaster.yml` hard-pinned `FFMPEG_BINARY: ffmpeg`** at job level — a bare name that
  `Path('ffmpeg').exists()` rejects, defeating the one resolver that did have a fallback. Removed.
- **The media check assumed `ffprobe`,** which imageio-ffmpeg does not ship. `probe_streams()`
  now falls back to the ffmpeg banner. Its first version grep'd for `Stream #0:0: Video`; the
  real banner is `Stream #0:0[0x1](und): Video:`, so it matched nothing and would have reported
  every healthy render as having no video stream.

### Added

- **11 tests in `tests/test_ffmpeg_resolution.py`.** Precedence (env → PATH → static build), a
  bare `FFMPEG_BINARY=ffmpeg` being ignored, an instructive error when nothing is found, no
  workflow re-inlining `apt-get install`, apt staying timeboxed — and one test that **executes
  the YAML's own `probe_streams()` against a real generated MP4 with no ffprobe on `PATH`**.
  That last test is what caught the broken grep: asserting the string `ffprobe` appears in the
  workflow would not have. As a negative control, restoring the broken pattern fails it with
  `'video' not found in []`.
- MAINTENANCE.md §1 ffmpeg section rewritten — its old claim "GitHub runners install real ffmpeg
  via apt, so CI never needs this" was the assumption this incident disproved.

---

## 2026-10-22 — fact-check worksheets: the mechanical half of the human gate

The human gate is the one step no machine in this repo may skip: `pipeline/originality.py`
blocks any job whose `human_rewrite` is `false`, and flipping it is the human's signature.
But the gate was slow for a boring reason — pulling every checkable claim out of a 900-word
script and finding which of six sources settles each one is an hour of extraction before the
actual judgement starts.

### Added

- **`scripts/factcheck.py`** → `content/factcheck/<id>-<slug>.md`. Extracts candidate claims
  (a sentence containing a number word, a month, or a multi-word proper noun) and prints them
  as checkboxes next to the job's own declared sources, each with a blank for the source the
  human confirmed it against, plus a sign-off block. **It verifies nothing and pre-ticks
  nothing** — an unticked box is the only correct starting state, and a test asserts that.
  Re-running without `--force` refuses to overwrite a worksheet a human has filled in.
- Worksheets generated for all four queued jobs: **41 / 39 / 35 / 37 checkboxes**
  (0003–0006). Each embeds the source script's sha256 so staleness is visible.
- 14 tests in `tests/test_factcheck.py`, including the two invariants that matter most: the
  generator never asserts a verdict, and its output never lands in `content/queue/` — that
  directory is globbed by `pipeline/run.py::select_jobs`, `scripts/doctor.py`, the
  queue-integrity tests and `dry-run.yml`, so a worksheet there would be parsed as a job.

### Notes

- Extraction is deliberately dumb: the narration spells numbers out for TTS ("two thousand
  and eight"), so digit-matching would find nothing, and a clever extractor that decided what
  matters would hide claims behind a model's judgement. A missed claim is a checkbox the human
  adds.
- **Because dumb extraction misses things, nothing is dropped silently.** In job 0003, 10
  substantive sentences carry no figure, date or proper noun — including *"That is a
  repurchase agreement — a repo — and in substance it is a secured loan"*, which is
  load-bearing. Those are listed under each scene as "Also read", and
  `test_no_substantive_sentence_is_silently_dropped` asserts every sentence of ten words or
  more appears somewhere in the worksheet. Without it a human could tick all 31 flagged boxes
  and never see them.
- `docs/SETUP.md` §6 now points at it as the shortcut for the fact-check step.

---

## 2026-10-22 — the `image-search/` licence ledger: 13 stills are not ours to publish

`docs/ASSET_SOURCING.md` had carried *"no complete per-file license ledger in this checkout"*
as known debt. This closes it, and the answer was worse than "unknown".

### Added

- **`image-search/LICENSES.yml`** — a per-file ledger for all 49 authored stills, derived by
  `scripts/licence_ledger.py` from each file's **own** metadata (EXIF `Copyright`/`Artist`/
  `ImageDescription`, embedded XMP, raw byte markers for `gettyimages`,
  `xmpRights:WebStatement`, `plus:Licensor`, `All Rights Reserved`). Every entry is keyed by
  SHA-256, so a swapped file cannot inherit its predecessor's clearance. Commands: `check`
  (CI), `scan` (evidence, writes nothing), `write` (regenerate, preserving human edits for
  unchanged bytes).
- **`pipeline/licences.py`** — `licence_note()`, `status_of()`, `is_safe_for_monetized_use()`,
  and two tiers: `unsafe_stills()` (rights-encumbered / corrupt / unrecorded — must not
  render) and `uncleared_stills()` (everything not `cleared`).
- **CI**: `dry-run.yml`'s hermetic `checks` job now runs `licence_ledger.py check`.
- **Doctor**: two new checks — the ledger covers every still and agrees with the bytes
  (re-derived from the files, not re-reading its own output), plus an explicit
  ❌ *"authored stills free of embedded rights claims"* while the 13 remain.
- 11 tests in `tests/test_licence_ledger.py`, including the two that assert `check` can
  actually fail (missing entry; changed bytes).

### Changed

- **`tools/deep_dive.py` and `tools/shorts.py` now report the real licence status.** Both
  wrote one blanket string into `scene-sources.json` for every authored still —
  *"source/license metadata unavailable in current ledger"* — which said the same thing about
  a public-domain 1889 Library of Congress plate and a rights-managed Getty frame. Each still
  now gets its own status line, and both renderers print a `!!` block naming any
  must-not-monetize file while the operator is still watching. Import is guarded, so a
  bookkeeping module can never break a render.

### What the scan found

**13 rights-encumbered, 1 corrupt, 35 unverified, 0 cleared.**

- 10 stills carry embedded **Getty Images** rights metadata — e.g. EXIF `Copyright: "2002
  Getty Images"` on `andrew-fastow-enron-cfo-trial-photo-2.jpg`, with a full `plus:Licensor`
  and `xmpRights:WebStatement` packet.
- 3 carry `"All Rights Reserved"` photographer copyrights: `Copyright 2014/2021 Steven L.
  Markos`, Johnstown Flood National Memorial.
- **Nine of the 13 are referenced by scene tables** (8 Enron, 1 Johnstown). The Enron deep
  dive and Shorts are therefore **not safe to monetize** until those files are replaced.
- `johnstown-flood-1889-ruins-destruction-h-5.png` is 68 bytes and will not decode; recorded
  as `corrupt`, referenced by no scene.
- `enron-corporation-headquarters-houston-c-3.jpg` and
  `enron-scandal-2001-newspaper-headlines-f-4.jpg` are byte-identical.
- Only 23 of the 49 stills are referenced at all; the other 26 are unused inventory.

MAINTENANCE.md §4 now carries these as three separate debt rows (encumbered / unverified /
dead weight) instead of one "no ledger" row, and the "47 files" figure there was wrong —
the directory holds 49 files, 8,988,827 bytes.

---

## 2026-10-22 — queue depth 0004–0006, and a licence hole in the keyless provider

### Fixed

- **`_wikimedia()` was accepting share-alike, non-commercial and no-derivatives images.**
  `docs/ASSET_SOURCING.md` has always promised *"only CC0, public-domain, or CC BY entries
  are accepted; NC, ND, and ShareAlike entries are skipped"* — the code did not enforce it.
  The old predicate spelled the disqualifiers out longhand (`share alike`,
  `non-commercial`, `no derivatives`), but Commons reports `LicenseShortName` in
  **abbreviated** form: `CC BY-SA 4.0`, `CC BY-NC 2.0`, `CC BY-ND 4.0`. None of the
  longhand strings appear in those, and the accept term `cc by` matches all of them, so
  every SA/NC/ND hit passed the filter and was downloaded and rendered. Wikimedia is the
  provider that runs with **no API key** — i.e. the one a keyless CI run and any
  no-secrets setup actually use — so the hole was in the hot path for a channel being
  built for monetization. `_internet_archive` (rejects `-nc`/`/by-sa/`/`-nd`) and
  `_openverse` (allowlist) were already correct.
  - New `pipeline/assets.py::licence_ok_for_monetized_use()` tokenises the licence string
    and refuses any `nc`/`sa`/`nd` token or spelled-out equivalent. Unknown licences are
    refused. Verified against the real Commons strings: `CC BY-SA 4.0`, `CC BY-NC 2.0`
    and `CC BY-ND 4.0` all went from *downloaded* to *refused*; `CC0`, `Public domain`
    and `CC BY 2.0` still pass.
  - **Consequence to watch:** a scene that was previously sourced from a CC BY-SA hit now
    correctly returns nothing. Jobs 0004–0006 were written against the tightened rule;
    job 0003's queries were chosen for CC0/PD/CC-BY coverage and its `pipeline-dry-run`
    result on this branch is the check.

### Added

- **Three long-form scripts (PLAN.md Phase 0 queue depth):** `0004-the-fund-that-broke-the-fed`
  (LTCM, 1998), `0005-the-queue-that-broke-a-british-bank` (Northern Rock, 2007),
  `0006-how-one-trader-deleted-a-bank` (Barings, 1995). ~1,050–1,100 words each, 8 scenes,
  all `status: draft` with `human_rewrite: false` — the originality gate blocks every one
  of them until a human fact-checks, rewrites and approves. Each carries its sources in
  `description` and a maintainer note naming the figures that most need checking.
- **Per-query sourcing evidence, now enforced.** Each job records
  `asset_query_verification` in frontmatter: for every `asset_queries` entry, either a
  Commons probe count (`usable: N ≥ 1`) or a `ci_verified` dry-run id, plus the evidence
  note. `tests/test_asset_query_verification.py` fails the build if a query is unverified,
  recorded with zero usable hits, or carries a stale entry. Job 0003 records CI evidence
  (run `39734567120`, main @ `af63d2c`, job *"General pipeline dry-run (needs network)"*
  = `success`); 0004–0006 record Commons probes taken 2026-10-22.
- Rejected-query notes in each job's frontmatter, so nobody re-adds a query that was
  already proven dead — e.g. `bank of england threadneedle street` returns 4/4 CC BY-SA
  (zero usable), which is why job 0005 uses the shorter `bank of england london`.

---

## 2026-10-22 — first-upload path: release tickets actually work now

PR #5 (the green pipeline) merged; attention turned to what blocks the **first upload**
(SETUP.md §6).

### Fixed

- **The release-ticket Issue would never have appeared.** `_open_release_ticket` shells
  out to `gh issue create`, but `produce.yml` exported no token — unauthenticated `gh`
  fails, and the failure was swallowed (`check=False`, output discarded). The workflow
  now exports `GH_TOKEN: ${{ github.token }}` (job already has `issues: write`), the
  helper logs success/failure with the reason, and it falls back to `GITHUB_TOKEN`.
- **Ticket body now links straight to the Studio editor**
  (`https://studio.youtube.com/video/<id>/edit`), not just the watch URL — the
  "publish in 2 clicks" promise in SETUP.md §6.4 is literal.
- **SETUP.md**: §6 pointed at archived `0001-…md` as the template (queue now holds
  `0003-…`, archive holds 0001/0002) and §5's `YOUTUBE_REFRESH_TOKEN` row cited §3
  (remasters) instead of §4 (token minting).

### Added

- Three regression tests: ticket opens in Actions with token + Studio link; failure is
  logged, never raised (upload must not die over a ticket); no ticket outside Actions.

---

## 2026-10-21 — the general pipeline completed its first ever render

`pipeline-dry-run` had never passed. It now does — run 39649621652: all three jobs
green, general queue path rendered end-to-end in 6m0s **with zero API keys**. Full
post-mortem in MAINTENANCE.md §3 (2026-10-21).

### Fixed

- **`_cache_path` read `CONFIG.ASSET_CACHE_DIR`, which never existed on `Config`** —
  only a module-level constant in `config.py`. Every provider that found a licensed
  candidate crashed with `AttributeError`, `fetch_scene_assets` swallowed it as
  "source errored", and the hard-fail blamed the scene query. The general pipeline had
  never completed a single provider download.
- **Wikimedia downloads fetched originals (100 MB+ TIFFs) instead of the 1920px
  thumburl it already requested** — and died on `upload.wikimedia.org` 429s. Photos
  now use `thumburl`; Wikimedia traffic carries a descriptive UA with the repo URL;
  search and download retry 429/5xx honouring `Retry-After` (bounded ≤8 s).
- **Dead Openverse video link**: `/v1/videos/` 404s on every call (verified) —
  dropped from the video provider list.
- **Commons HTTP-200 error bodies (`cirrussearch-too-busy`) read as "0 results."**
  API errors are now named in the attempt probe and retried once.
- **Job 0003's asset queries**: scenes 5 and 7 were swapped (courtroom ↔ bank run),
  scene 4's had a single junk hit, scene 3's one off-topic plaque. All eight
  re-verified against the Commons search API for multiple CC0/PD/CC-BY matches.

### Added

- **Per-provider attempt report** — `sourcing-attempts.json` per scene, one stdout
  line per attempt, and a compact digest inside the hard-fail message so the CI
  annotation (the only readable runner output) explains itself.
- `tests/test_config_references.py` — static scan that fails any `CONFIG.<name>`
  reference which does not resolve, in the hermetic `checks` job.
- `test_asset_queries_cover_every_scene_when_provided` — a partial `asset_queries`
  list must not silently drop later scenes onto heading-as-query.
- `test_cache_path_resolves_into_the_asset_cache_dir` — regression test for the bug
  above.

---

## Unreleased — maintenance handover (2026-10-20)

The project moved off the abandoned session branch `arena/79365da2-youtube-automation`
onto a maintained branch. Moving it surfaced a CI that had never passed.

### Fixed

- **CI was red on every run.** `dry-run.yml` selected `content/queue/*.md | head -n1`,
  which was a `niche: history` draft that `_validate_finance_niche` (added in `333767c`)
  refuses. Separately, `ENABLE_KEYLESS_SOURCES=0` disabled the only key-free stock
  providers while no Pexels/Pixabay secrets existed, so `fetch_scene_assets` had nothing
  to query and the render hard-failed. Full post-mortem in `MAINTENANCE.md` §3.
- **`tests/` was never executed by any workflow.** `dry-run.yml` had no test step at all.
- **`remaster.yml` was pinned to the abandoned branch.** Its push guard aborted unless
  `GITHUB_REF_NAME == "arena/79365da2-youtube-automation"`, and it pushed to that same dead
  branch — so the manual remaster workflow was unusable from anywhere else. Now publishes
  back to `HEAD:$GITHUB_REF_NAME`, refusing only non-branch refs.
- **Docs told maintainers to select the dead branch by name** — `PLAN.md`, `docs/SETUP.md`,
  `docs/ASSET_SOURCING.md`.
- **README Quickstart was wrong twice**: it pointed at a job that has since been archived
  and out-of-niched, and claimed the general `pipeline/` path runs with "zero network".
  It does not — that path always needs a reachable stock provider.

### Changed

- **`dry-run.yml` rewritten** into three jobs with honest guarantees: `checks` and
  `offline-render` are hermetic and required; `pipeline-dry-run` is the one networked job
  and is `continue-on-error`, so a third-party API outage cannot turn the repo red.
- **`offline-render` asserts the output is real media** — non-empty, has a video stream,
  has an audio stream, and produced a per-scene source ledger. Previously CI only checked
  that the command exited 0.
- **Out-of-niche drafts archived** to `content/archive/` with a README explaining why they
  are still needed (the Johnstown deep-dive and Shorts engines read them).
- **`pipeline-dry-run` selects an in-niche job explicitly** rather than by filename order.

### Added

- `MAINTENANCE.md` — runbook: verified local checks, what CI proves, incident log, known
  debt, operational calendar (the 31 Jan 2027 YPP deadline), how to add a video, secrets.
- `CHANGELOG.md` — this file.
- `tests/test_queue_integrity.py` — 4 tests. `test_every_queued_job_is_in_niche` is the
  guard that makes the incident above impossible to repeat.
- `content/queue/0003-how-lehman-brothers-died.md` — 901-word, 8-scene finance documentary
  draft (the queue had no in-niche job). Ships with `human_rewrite: false` **on purpose**
  so the originality gate blocks it until a human verifies the figures against the Valukas
  examiner report and rewrites the narration.

---

## 2026-10-20 — finance pivot and the Enron deep dive

- `da6685b` fix(site): link banner from published homepage
- `d3106bc` feat(site): add finance channel banner download
- `333767c` **chore(channel): keep published videos finance-only** ← added the niche gate
  that later broke CI
- `54adba1` docs: clarify remaster workflow availability
- `fb883cc` fix(actions): invalidate stock cache when sourcing changes
- `23b8b4c` feat(media): clip-first sourcing and aspect-safe remasters
- `8e33f1b` Shorts: 9:16 vertical twins of deep dive v5
- `75d1280` feat(deep-dive): 'How Enron Died' score-only audio + tease cards (v5 remaster)
- `f5a284c` feat(deep-dive): score-only audio (SFX removed) + AHEAD tease cards
- `a506535` feat(deep-dive): semantic sound design — story-cued SFX beds, sidechain mix
- `4a11d1b` feat(deep-dive): cinematic score + sound design keyed to spoken beats
- `14ddd85` feat(deep-dive): v4 documentary engine — speech-locked scenes, sub-pixel camera
- `621f350` feat(deep-dive): speech-synced motion graphics v3
- `9a52d67` feat(deep-dive): motion-design v2 — blue grade + glass cards + kinetic type
- `fef8283` feat(deep-dive): money-documentary ep1 — 'How Enron Died' (1:57)
- `d32e4e4` docs(finance): finance-niche deep dive — RPM data, policy minefield, money math

## 2026-10-19 — motion system, reels, and the Pages showcase

- `09ae56f` feat(deep-dive): archival footage + narration — 'The Canal That Broke a City'
- `5760322` chore: track deep-dive narration inputs (narrow gitignore exception)
- `1284d35` feat(reels): MotionStudio reels — THE FLOOD + THE SECRET (Johnstown 1889)
- `f776a7d` feat(motionstudio): DocOga typography motion system + 2 QA-passed reels
- `f0c89e9` docs(pages): root player page + `.nojekyll`
- `43f6195` ci(pages): make Pages deploy workflow manual-only
- `0aa117a` ci(pages): deploy showcase site to GitHub Pages via Actions
- `a760101` docs(showcase): GitHub Pages player page with first renders
- `db175bf` fix(shorts): caption scaling + cut from pre-burn source + hook overlays
- `4aaf04e` feat: growth science + metadata/Shorts automation

## 2026-10-18 — the studio

- `c8c7b88` fix: robust text rendering + render fixes after end-to-end validation
- `966d01b` **feat: ₦0 YouTube automation studio — plan, pipeline, workflows**
- `21ae307` Initial commit
