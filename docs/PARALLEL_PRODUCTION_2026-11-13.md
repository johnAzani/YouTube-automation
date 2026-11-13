# Channels produced side by side: research, decision and plan (13 November 2026)

Times are Nigeria time (WAT, UTC+1) unless a line says UTC. Workflow crons and
receipts are stored in UTC, so both are given where it matters.

## Summary

Production ran the ten channels one after another inside a single run. Measured
over 8–13 November, that is why videos missed their slots and why a run took most
of a day:

- A ten-channel run took **537 minutes** (8 h 57 min). The three slots are 5, 8
  and 11 hours apart, so a run could not finish before the next slot was due.
- Production held the shared lock for **1,412 minutes of 12 November** (98% of
  the day). While it is held, nothing else can start: not the next slot, not the
  recovery run, not the script-writing brain.
- On 12 November the channels published **17 long-form videos of the 30
  scheduled**. Three channels (The Covenant Shield, The Praise Garden, The
  Guided Path) published none.
- The last video of a slot landed between **3.5 and 13.2 hours** after the slot.

This change makes the channels render side by side, five at a time by default.
Replaying the recorded leg times, the same ten-channel run takes **118 minutes**.
It also stops a late schedule event from publishing a slot twice, lets one
recovery run carry every missing channel, starts recovery 30 minutes after a
slot instead of 90, and fixes a slot-calculation error that switched recovery
off between 1:00am and 7:14am.

It does **not** make videos land exactly on the slot minute. That needs
scheduled publishing, which is step 3 of the plan below and is not built yet.

Not yet run in production. The lane setting and the queue setting were each
checked on GitHub with a throwaway workflow; the production workflow itself has
only run in tests.

## What was measured

Source: the 47 `Produce video` runs created 8–13 November and their 96 channel
legs (GitHub Actions API), the publish commits on `main`, and the receipts in
`content/published/`.

### Where the time goes

| Legs in the run | Minutes, one at a time | Longest single leg | Same legs, 5 lanes | Same legs, 10 lanes |
|---:|---:|---:|---:|---:|
| 5 | 202 | 59 | 59 | 59 |
| 5 | 252 | 85 | 85 | 85 |
| 7 | 268 | 68 | 68 | 68 |
| 8 | 303 | 56 | 86 | 56 |
| 8 | 403 | 81 | 114 | 81 |
| 10 | 537 | 100 | 118 | 100 |

The lane columns are a replay of the recorded leg durations in matrix order, not
a production measurement. A leg takes a median of 44 minutes (75th percentile
57, 90th 77, longest 128). Inside a leg nearly all of it is one step: on
13 November The Midnight Watch spent 58 of 65 minutes, and The Family Altar 83
of 92, in "Render and upload the long-form edition". Each leg has its own
runner, so the legs do not compete for processor time.

### Why slots were missed

Two separate delays stack:

1. **GitHub delivers the schedule event late.** The 14 scheduled runs were
   created 34 to 423 minutes after their slot, median about 218. This is
   GitHub's scheduler, not this repository, and no workflow setting changes it.
2. **The serial run then blocks everything behind it.** The supervisor is meant
   to recover a missed slot, but it does nothing while a production run is in
   flight, and one was in flight almost all day. A run that did get queued
   waited up to 401 minutes for the lock.

| Day | Minutes production held the lock |
|---|---:|
| 8 Nov | 450 |
| 9 Nov | 278 |
| 10 Nov | 780 |
| 11 Nov | 1,002 |
| 12 Nov | 1,412 |

The repository's own research (`docs/research/schedule-and-model-reliability.md`
§4) concluded the lock was held 2% of the day and was not the cause. That was
measured with two or three channels and no longer holds with ten.

### What the long runs cost

- Scheduled runs of 7–8 legs were cancelled during their last leg all three
  times (11 and 12 November), each after 5 to 6.7 hours. The Covenant Shield was
  that last leg each time, which is why it has no long-form on 12 November.
- Long-forms published on 12 November: The Secret Place 2, The Morning Altar 3,
  The Midday Watch 2, The Midnight Watch 2, The Family Altar 3, The Healing
  Balm 3, The Provision Table 2, The Covenant Shield 0, The Praise Garden 0,
  The Guided Path 0.
- The run in progress while this was written started its first leg at 7:57am on
  13 November for the 8:14pm slot of 12 November, and still had four channels
  waiting at 11:45am.

### A second fault found on the way: the evening slot stopped at 1:00am

`prev_occurrence()` in `scripts/automation_monitor.py` answers "which slot are
we in?". With several cron lines it stopped searching as soon as the first line
had an answer, so from 00:00 to 06:14 UTC (1:00am to 7:14am) it returned
*yesterday 06:14* instead of *yesterday 19:14*. The supervisor therefore treated
the 8:14pm slot as expired from 1:00am, 4 h 46 min after it was due instead of
6 hours, and compared receipts against the wrong slot until 7:14am.
`comments.yml` has three cron lines and was affected the same way.

Fixed here, and checked against a minute-by-minute brute-force search for every
scheduled workflow over three days (6,180 instants, no differences).

## Is side by side safe? What was checked

The earlier remediation note said not to raise `max-parallel` until state writes
were isolated and a concurrent rehearsal existed. Each point, and what was found:

| Concern | Finding | Evidence |
|---|---|---|
| Two legs write the same file | They cannot. Job ids, Short keys and Short queue numbers are allocated in per-channel blocks (The Midnight Watch 0200–0229, The Family Altar 0300–0329, and so on); 0 ids are shared between any two roadmaps. All 86 publish commits touched one channel's files plus `docs/network-state.json`. | `test_job_ids_are_allocated_in_per_channel_blocks`, `test_no_content_file_name_is_shared_by_two_channels` |
| A leg works on an old tree | Each leg fast-forwards to current `main` before reading any state (PR #396, first commit). | `tests/test_produce_leg_rehearsal.py` |
| Two legs push at once | The commit step re-stages on the new tip and retries. Five real processes committing at once produce the full worst case every time (10 rejected pushes) and all five receipts land. Ten lanes need ten attempts; the loop had six and now has twelve, with a random extra delay so lanes do not retry in step. | `test_five_lanes_finishing_in_the_same_minute_all_record_their_publish` |
| Legs read each other's path lists | The rehearsal exposed that the commit step wrote its path lists to fixed names in `/tmp`. On GitHub each leg has its own machine, so this never fired in production, but it is now a private `mktemp -d` directory. | same test (it failed before the change) |
| The one shared file | `docs/network-state.json` is rebuilt on every attempt from the newest `main` plus the leg's own files, so the last commit describes every channel. | rehearsal asserts every lane's channel is in it |
| Credentials, speech quota | Per channel already: separate Google projects, secrets selected by `matrix.channel`, speech-chunk caches and artifacts keyed by channel. | `test_per_channel_resources_stay_per_channel` |
| Stock footage keys (the only shared quota) | A prayer long-form makes one search per scene: 6 scenes plus 1 for the thumbnail, each trying up to four provider calls. Worst case is about 28 Pexels requests per leg including the Short. Five lanes: about 140 in an hour against Pexels' 200. Ten lanes could reach 280. This is why the default is 5, not 10. On a 429 the code retries once and moves to the next provider. Request counts are from the code; job logs are stored on a host this environment cannot reach. | `pipeline/assets.py`, `pipeline/prayer_pipeline.py` |
| Stock asset cache | One cache key for all legs. A hit is never re-saved, so legs do not overwrite each other; after a code change several legs may try to save the same key and all but one log a warning. | `produce.yml` cache steps |
| GitHub limits | 20 concurrent jobs on the Free plan, 256 matrix jobs per run, 6 hours per job, runners free on a public repository. Five or ten lanes fit. | GitHub "Actions limits" |
| Does the lane setting work on this repository | Yes. A throwaway workflow with the identical expression and a value of 2 ran legs a and b together, then c and d. | run 43410965566 |
| Does the plan job see receipts published while its run waited | Yes, once it checks out the branch tip. A throwaway run created at commit `5904a11` checked out `f54375c`, pushed 12 seconds later. Without the explicit ref it is pinned to the creation commit. | run 43412594151 |

**What this does not solve.** If a leg dies after YouTube accepts an upload and
before the receipt is committed, the next run relies on the title check to avoid
a second upload, and that check is not a true idempotency key. Lanes do not
change this: a channel appears once per run and runs still take turns, so two
legs of the same channel never run together. The risk is the same as before,
and still open.

## What changed

1. **Lanes.** `produce.yml` reads the lane count from the plan job:
   `max-parallel: ${{ fromJSON(needs.plan.outputs.max_parallel || '1') }}`.
   The plan job takes the repository variable `PRODUCE_MAX_PARALLEL`, default 5,
   clamped to 1–10 and to the number of legs (`scripts/produce_plan.py`).
   **Setting the variable to `1` restores one-at-a-time with no code change.**
2. **A slot is served once.** A scheduled run drops every channel that already
   has a long-form receipt dated at or after the current slot. Before, the
   supervisor's recovery run and GitHub's late schedule event could both publish
   for the same slot. The plan job now checks out the branch tip as it is when
   the run starts, not the commit the run was created at, so a run that waited
   behind another sees what that run published. If the check itself fails, the
   run produces every channel.
3. **One recovery run for all missing channels.** `produce.yml` accepts
   `channels` (comma-separated) on manual and `repository_dispatch` triggers, and
   the supervisor sends every channel that owes the slot in one dispatch. It used
   to send one channel per dispatch because the lock holds a single waiting run.
   A channel is tried at most twice per slot; the count resets when the code
   changes.
4. **Recovery after 30 minutes, not 90.** The 90-minute wait existed so the
   supervisor would not race a late schedule event into a duplicate upload.
   Point 2 removes that risk, and the event has never arrived inside 34 minutes.
   Other workflows keep 90.
5. **Slot calculation fixed** (see above).
6. **Commit step:** twelve attempts, random extra delay, private path lists.
7. **Receipts restored** (next section).

Unchanged: the `content-state` lock still allows one production run at a time
and is still shared with the brain; credentials, quota cooldown, the unknown
channel refusal, the commit guard and the stale-checkout stop are as they were.

## Receipts restored

The stale-checkout fault overwrote more receipts than the first report listed.
`scripts/repair_clobbered_receipts.py` reads the publish commits and finds every
receipt that was overwritten for a video that was already live. It found ten:

| Receipt | Overwritten by | Restored |
|---|---|---|
| `0046-psalm-91-6-…noonday.md` (new finding, 7 Nov) | `1ae95eb` | publish time 8:25pm 7 Nov (was showing 9:35pm) |
| `0043-psalm-90-17-morning-prayer.md` | `e19ed94` | 8:01pm 8 Nov (was 8:10pm) |
| `0501-deuteronomy-28-12-provision-prayer.md` | `c34235b` | 3:17am 12 Nov (was 7:15am) |
| `0503-revelation-3-8-open-doors-prayer.md` | `56983d3` | 10:39pm 12 Nov (was 4:52am 13 Nov) |
| `0207-ephesians-6-10-18-midnight-prayer.md` | `1e4286c` | 1:40am 13 Nov (was 8:27am) |
| `0304-isaiah-32-18-household-peace-prayer.md` (new, 13 Nov) | `aed028b` | 3:04am 13 Nov (was 9:35am) |
| `short-provisiondeuteronomy28v12-…` | `c34235b` | full receipt |
| `short-provisionphilippians4v19-…` | `56983d3` | full receipt |
| `short-midnight2corinthians10v3-…` | `1e4286c` | full receipt |
| `short-familyisaiah32v18-…` (new, 13 Nov) | `aed028b` | full receipt |

Decisions taken:

- Long-forms: only `published_at` and `published_on` are put back. Everything
  else in those files is newer and legitimate.
- Shorts: the original receipt is restored, with the current `thumbnail_*`
  fields kept because the monitor has updated them since. Each original already
  carries `metadata_revision: "selar-seo-v1"`, so the metadata sync treats it as
  up to date and does not push titles or descriptions to YouTube again.
- Nothing on YouTube was changed. These are repository records only.

`aed028b` is from the production run that was still going while this was
written. That run was created before the fix and has five more legs to run, so
**it will probably overwrite more receipts before it ends.** Run
`python scripts/repair_clobbered_receipts.py` after it finishes (add `--apply`
to restore, `--check` to fail when any remain). It needs git history, so use a
full clone, not a depth-1 checkout.

## The plan

| Step | What | State |
|---|---|---|
| 1 | Lanes, slot served once, multi-channel recovery, 30-minute recovery, slot fix, receipt repair | In PR #396. Needs merging. |
| 2 | `queue: max` on the `content-state` lock, in `produce.yml` and `gemini_brain.yml` | Verified available, not applied |
| 3 | Scheduled publishing, so a video goes public on the slot minute | Designed below, not built |
| 4 | Each channel in its own posting window | After step 3 |
| 5 | Owner items | Listed below |

### Step 1: what to expect, and how to turn it off

- A ten-channel slot should take about two hours instead of nine. First videos
  about 45–75 minutes after the slot, the last about 2.5 hours after, when the
  supervisor starts the run at 30 minutes. If GitHub's own event arrives first,
  earlier.
- Watch the first run: the plan job prints `producing for: [...] (5 at a time)`;
  each leg should end with `queue state recorded on attempt N`.
- To go back to one at a time: set repository variable `PRODUCE_MAX_PARALLEL`
  to `1` (Settings → Secrets and variables → Actions → Variables). No merge
  needed.
- If stock footage starts returning 429, lower the variable to 3 or 4.

### Step 2: stop queued runs being cancelled

By default GitHub keeps one waiting run per lock and cancels it when another
arrives; three runs were lost that way on 11 November. `queue: max` keeps up to
100 waiting runs in order. Checked on this repository with a throwaway
workflow: four runs pushed 8 seconds apart ran one after another and none was
cancelled (runs 43411134671 to 43411183883). Held back from step 1 so that the
lock's behaviour changes in one small, separately revertible commit after lanes
have run in production, and because two workflows share the lock and must
change together.

### Step 3: land on the slot minute

Lanes shorten the delay; they cannot remove it, because rendering starts at the
slot. To publish *on* the slot the video has to be finished beforehand:

- Produce for the **next** slot: upload as private with YouTube's `publishAt`
  set to the slot time. `pipeline/upload.py` already accepts `publish_at`
  (lines 377–424).
- What has to change with it: the receipt needs a `scheduled_for` time and must
  not count as published until then; the supervisor's "served" rule, the
  monitor's public-video check, the thumbnail sync and the comment replies all
  assume a receipt means a public video; a failed render must leave time for a
  retry before the slot.
- Start production about four hours before each slot (lanes make this
  possible; it was not with nine-hour runs).
- This needs a careful build with its own tests. It is the only step that
  reaches "on schedule" in the strict sense.

### Step 4: per-channel windows

Each channel already declares its own Short window in
`pipeline/channel_capabilities.py` (06:14, 08:44, 09:44, 10:44, 12:14, 14:14,
15:44, 17:14, 18:44, 23:14 UTC). With scheduled publishing each channel's
`publishAt` can follow its own audience window instead of all ten sharing three
slots.

### Step 5: owner items

- **Merge PR #396.** Until it is merged, production keeps running one at a time,
  and every run created from older code keeps overwriting receipts.
- **Pexels quota.** Pexels grants a higher or unlimited limit free of charge on
  request (api@pexels.com, with proof of attribution). That would remove the
  only shared limit and allow ten lanes. Not required for five.
- **An outside trigger.** GitHub's schedule lateness (median about 218 minutes)
  can only be removed by something outside GitHub calling `repository_dispatch`
  at the slot time. The workflow already accepts it. Any such service must stay
  inside the $0 rule.

## Tests

- `tests/test_parallel_production.py` (32 tests): lane count for every input,
  channel-list parsing, slot-served decision, the real plan script from
  `produce.yml` executed for single, multi-channel, unknown-channel and
  scheduled events, plan helper importable with no third-party packages,
  per-channel id blocks, per-channel caches and secrets, commit attempts,
  supervisor batch dispatch, two-tries-per-channel, 30-minute rule, evening slot
  after midnight.
- `tests/test_produce_leg_rehearsal.py`: adds the five-lane commit race.
- `tests/test_repair_clobbered_receipts.py`: both shapes of damage found from a
  real git history, restored, idempotent, a genuine re-upload left alone.
- Updated to the new contract: `test_channels.py`, `test_produce_commit_guard.py`,
  `test_scheduler_supervisor.py`.

Full suite result is recorded in the pull request.
