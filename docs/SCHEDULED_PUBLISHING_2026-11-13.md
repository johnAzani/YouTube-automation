# Scheduled publishing: videos public on the slot minute

Date: 13 November 2026. Times are Nigeria time (WAT) with UTC in brackets where
the code uses UTC.

**Status: built and tested, switched off.** With the switch off every upload is
public the moment it finishes, exactly as before. Nothing has been uploaded with
a publish time yet; the first one is the trial in "Turning it on".

## Why rendering at the slot cannot land on the slot

Measured 8–13 November (47 production runs, 96 channel legs):

| Delay | Measured |
|---|---|
| GitHub starts the scheduled run after the slot | 34 to 423 minutes, median about 218 |
| One channel's render and upload | median 44 minutes, 90th percentile 77, longest 128 |
| Ten channels in five lanes (replay of real leg times) | about 118 minutes |

The run for the 8:14pm slot of 12 November was created at 1:17am on the 13th and
was still producing, one channel at a time, at 1:19pm. Lanes shorten the run; they
cannot fix a start that is hours late. The only way to hit the minute is to
finish early, upload private with a publish time, and let YouTube publish.

## What YouTube does (sources)

From an archived copy of Google's `videos` reference page (snapshot dated
1 June 2017, `caohanyang/REST_OPENAPI` on GitHub; the live page cannot be
reached from the build sandbox) and the API description shipped with the
installed Google client (`youtube.v3.json`, revision 20261104):

- `status.publishAt` "can be set only if the privacy status of the video is
  private".
- "If your request schedules a video to be published at some time in the past,
  the video will be published right away."
- `snippet.publishedAt` for a private video read by its owner is the upload
  time; after it is made public it is the time it was made public.
- `videos.insert` can answer `invalidPublishAt` (400).
- `videos.update` costs 50 quota units (used only to publish a video that is
  still private 20 minutes late).

**Not confirmed anywhere I could read:** whether a comment can be posted on a
private video. The build does not depend on the answer (see "Pinned comment").

## How it works

A production slot is the moment work for a release becomes due: the cron in
`produce.yml`. The release goes public a fixed lead after that slot.

```
public time = production slot + lead
```

1. When a long-form is ready to upload, `pipeline/publish_schedule.py` works out
   the public time. If it is at least 15 minutes away the upload is private with
   that publish time. Otherwise it is public at once. Any doubt (no slot, bad
   value, an exception) also means public at once: scheduling can delay nothing
   and block nothing.
2. The receipt is dated with the **public** time (`published_at`), because that
   is what every reader of the field means by it, and it says the video is not
   public yet: `scheduled_publish: true`, `privacy_status: private`, and
   `uploaded_at` for when the file reached YouTube.
3. After the public time the monitor runs `scripts/confirm_scheduled_publish.py`
   (it runs every three hours, on every push to `main` and after every
   production run). It asks YouTube for the video's status and:
   - public: clears the flag and records `publish_confirmed_at`;
   - still private 20 minutes late: publishes it and warns;
   - rejected, failed or gone: marks `scheduled_publish_failed: true`, raises an
     error, and the supervisor stops counting that receipt as the slot's video,
     so the channel is produced again.

   Before the public time it makes no API call, and with no scheduled receipt it
   does not build a client.

### Why the slot accounting needs no change

"This channel is served for the slot" means "it has a long-form receipt dated at
or after the slot" (`published_channels_since`, used by the plan job and the
supervisor). A scheduled receipt is dated slot + lead, so it serves its own slot.
The one way this breaks is a lead that reaches the **next** slot: that receipt
would serve both and the next slot would never be produced. The smallest gap
between slots is five hours (3:14pm to 8:14pm). `publish_target()` refuses a lead
that does not fit inside the gap and publishes at once instead, and a test fails
the build if such a lead is ever committed.

### Details that were decided

| Case | Behaviour |
|---|---|
| Leg finishes less than 15 minutes before the public time, or after it | Public at once (today's behaviour). |
| Leg runs so late that the next slot has started | It belongs to the newer slot and is scheduled for that one. |
| Supervisor recovery dispatch | Same rule. Early enough: scheduled. Late: public at once. |
| YouTube answers `invalidPublishAt` | Uploaded again, public at once, with a warning. |
| Upload meant to stay private or unlisted (auto-publish off) | Never given a publish time: a publish time would make it public. |
| Leg dies after the upload, before the receipt | The next leg finds the video by title and writes the receipt with the schedule YouTube reports. This relies on the channel's uploads list including its own private videos, which is expected but not yet seen here. |
| Pinned comment | Posted at upload as now. If YouTube refuses it on the private video, the receipt records `pinned_comment_pending: true` and the monitor posts it once the video is public. |
| Thumbnail, captions, playlist | Unchanged. All are set by video ID. A refused thumbnail is already retried by the monitor. |
| Thumbnail pass in the monitor (`sync_published_thumbnails`) | It makes a private, processed, full-length video public when its receipt wants public. It now leaves a video alone when YouTube reports a `publishAt` for it or its receipt says `scheduled_publish: true`. See "Second read". |
| Comment owed, receipt edit lost | Before posting, the monitor asks YouTube whether the channel has already commented on the video. Three refusals end the attempt (`pinned_comment_failed: true`). |
| `publish_at:` on the job, unquoted | YAML reads it as a date object; it is converted to text before the request. |
| Short | Unchanged: uploaded and public when its leg runs. See "Not built". |
| Dashboard (`docs/network-state.json`) | A scheduled video shows privacy `scheduled`. |
| Comment replies | Unchanged: a private video has no comments to answer. |

## Turning it on

Three steps, in this order.

**1. One trial, one channel.** Started on 13 November by a line on one queued
job, because the build sandbox may not start workflows (`workflow_dispatch`
answers 403 there):

```
content/queue/0406-philippians-4-6-7-peace-that-passeth-understanding-prayer.md
publish_at: next-slot
```

That is The Healing Balm's next long-form. Whichever run produces it uploads it
private and YouTube publishes it on the next production slot after the upload
(7:14am, 3:14pm or 8:14pm WAT). Less than 15 minutes before a slot it is simply
public at once. The channel was chosen because it had already released that day,
so holding one video costs it nothing, and its last thumbnail went through.
Because the receipt is dated at that slot, the scheduled run for the slot skips
the channel: the trial video is that slot's release.

What to check afterwards: the receipt carries `scheduled_publish: true` and the
slot time in `published_at`; the video is private in YouTube Studio with the
right time, thumbnail, captions and playlist; at the time it goes public; the
next monitor run sets `scheduled_publish: false` and `publish_confirmed_at`;
whether the channel's comment was posted at upload (no `pinned_comment_pending`)
or afterwards.

Other ways to schedule one video, all held to the same rules (a time with a
timezone at least 15 minutes ahead and no later than the next production slot,
or the word `next-slot`):

```
gh workflow run produce.yml -f channels=prayer6 -f publish_at=next-slot
gh api --method POST repos/johnAzani/YouTube-automation/dispatches \
       -f event_type=publish-now -f 'client_payload[channels]=prayer6' \
       -f 'client_payload[publish_at]=next-slot'
```

**2. Move the crons and set the lead, in one change.** With a lead of 4 hours
30 minutes the public times stay where they are:

| Public (WAT) | Public (UTC) | Production cron (UTC) | Production due (WAT) |
|---|---|---|---|
| 7:14am | 06:14 | `44 1 * * *` | 2:44am |
| 3:14pm | 14:14 | `44 9 * * *` | 10:44am |
| 8:14pm | 19:14 | `44 14 * * *` | 3:44pm |

Set `PUBLISH_LEAD_MINUTES = 270` in `scripts/produce_plan.py`. The smallest gap
between these crons is still five hours, so 270 fits.

**3. Watch one day.** Switching back is the repository variable
`PRODUCE_PUBLISH_LEAD_MINUTES=0`: every upload is public at once again, without a
code change. (The crons would then be 4.5 hours early; move them back if it
stays off.)

### How much room 4 hours 30 minutes gives

The supervisor dispatches production itself 30 minutes after a slot whose
scheduled run has not started. From that dispatch, five lanes finish ten channels
in about two hours on measured leg times, so the last channel is ready roughly
2.5 to 3 hours after the slot, 1.5 hours before its public time. This has not
been observed live: no five-lane run had started when this was written. A leg
that does miss publishes at once, minutes late rather than hours.

## Second read (13 November, afternoon)

A second pass over every file that touches a live video's privacy, a receipt's
date or the pinned comment, before the first live upload. Four things were wrong
or missing; all four are fixed in the same change as the trial.

**1. The monitor would have published a scheduled video early.**
`scripts/sync_published_thumbnails.py` has a hygiene rule: a long-form whose
receipt wants `public`, that is at least three minutes long, processed, and
private or unlisted on YouTube, is made public. A scheduled video is exactly
that. The rule only runs for receipts still waiting for a thumbnail, and on
13 November that was 32 of 76 long-form receipts:

| Channel | Long-form receipts | Thumbnail still pending | Latest reason |
|---|---|---|---|
| The Secret Place | 12 | 0 | |
| The Morning Altar | 20 | 4 | rate limit |
| The Midday Watch | 12 | 0 | |
| The Midnight Watch | 9 | 9 | permission |
| The Family Altar | 6 | 6 | permission |
| The Healing Balm | 6 | 3 | |
| The Provision Table | 6 | 5 | rate limit |
| The Covenant Shield | 3 | 3 | permission |
| The Praise Garden | 1 | 1 | permission |
| The Guided Path | 1 | 1 | permission |

A receipt blocked on permission is skipped by that pass, and a rate-limited one
waits out its cooldown, so not all 32 would have been hit. Any that was would
have gone public at the next monitor run, and the monitor runs when production
finishes. The rule now skips a video YouTube is holding (`status.publishAt`
present) or whose receipt says `scheduled_publish: true`. A test also lists
every file that writes `privacyStatus` to a live video, so a new one cannot be
added without deciding what it does with a scheduled video. The writers today:
`confirm_scheduled_publish.py` (owns scheduled videos), `sync_published_thumbnails.py`
(guarded), `cleanup_duplicate_shorts.py` (a manual tool, Shorts only, makes
private), and the upload itself.

**2. The owed comment could be posted twice, or never.** The receipt was the
only record that the comment had been posted. The monitor's commit skips a
receipt that changed on `main` during its pass and can fail to push; either way
the next pass would have posted the comment again. And a comment YouTube refused
at confirmation was never retried, because the receipt no longer said
`scheduled_publish: true`. Now the monitor asks YouTube first whether the
channel's own comment is already under the video (2 quota units), retries a
refused comment on later passes, and stops after three refusals.

**3. A time written on the job skipped every check.** `publish_at:` in a job's
front matter went straight into the request: no 15-minute margin, no limit, and
an unquoted value is a date object the request cannot carry. A date weeks ahead
would have kept the video private that long and, because the receipt is dated
with it, stopped the channel being produced for the whole time. It now goes
through the same checks as a time given on a dispatch.

**4. A refused time on such a job failed the release.** The fallback to "public
at once" only covered times the pipeline chose itself.

Read and found correct, no change:

| What | Finding |
|---|---|
| `post_pastoral_pinned_comment` | Returns the comment ID on success and nothing on failure, so the receipt's `pinned_comment_pending` means what it says. |
| Monitor commit step | Carries receipt edits made by its own steps onto `main`, for receipts that did not change on `main` meanwhile. A lost edit is redone on the next pass (confirmation is repeatable; the comment is now checked first). |
| `retrofit_published_metadata`, `update_live_video_metadata`, the Short title fix | Send `snippet` (and `localizations`) only. They cannot change privacy or the publish time. |
| `pipeline/comment_replies.py` | Its `published_at` is the comment's time, not the video's. |
| `scripts/metrics_snapshot.py` | Skips anything YouTube does not report as public. |
| `pipeline/performance_feedback.py` | Ignores a row whose date is after the snapshot. |
| `scripts/release_report.py` | Counts a scheduled receipt as a release and closes that job's stale failure issue. Correct: the video is uploaded and will go public. |
| `scripts/pipeline_watchdog.py` | Per-channel age was already clamped. The network line printed a negative age for a receipt dated ahead; it now says "scheduled; public in N h". |
| Shorts (`recent_short_published_within`, `_recent_short_visuals`) | Read Short receipts only. |
| Fact-check worksheet | Embeds the job file's hash. Editing a queued job (as the trial line does) needs `python scripts/factcheck.py <id> --force`, or a test fails. |

Still only confirmable by the trial: that YouTube accepts a comment, a
thumbnail, captions and a playlist entry on a private video; that the channel's
uploads list includes its own private videos; that `publishAt` fires on the
minute.

### What the trial costs the channel

A receipt dated at a slot serves that slot. A video uploaded in the 3:14pm
slot's run and held for 8:14pm therefore serves both: The Healing Balm gets one
long-form across those two slots instead of two. That is the price of a trial
without moving the crons, and it is why the general switch is slot + lead with
the crons moved earlier, not "hold for the next slot".

## Trial result (13 November, evening)

Job `0406` on The Healing Balm, video `jaeiK1qh8Wk`.

| Step | Nigeria time | Result |
|---|---|---|
| Upload with a publish time | 6:32pm | Accepted. Receipt: `scheduled_publish: true`, `privacy_status: private`, `published_at` 8:14pm |
| Pinned comment at upload | 6:32pm | Not posted; the receipt recorded it as owed (`pinned_comment_pending: true`) |
| Thumbnail at upload | 6:32pm | Refused: "uploaded too many thumbnails recently" (a rate limit, unrelated to scheduling) |
| Scheduled time | 8:14pm | - |
| First monitor pass after it | 8:53pm | Found the video already public (`state: confirmed public`), posted the pinned comment, cleared the flag |

What this proves: YouTube accepts the publish time, publishes the video itself
(the monitor did not have to), and the owed comment is posted afterwards.

What it does not prove: the minute it went public. No monitor ran between
6:54pm and 8:53pm, so the receipt only shows it was public by 8:53pm; the
YouTube API cannot be queried from the build sandbox.

Found by the trial: the pinned comment arrived up to 39 minutes after the video
went public, because the monitor does not run on a fixed short interval. Before
the switch-on, the monitor needs a run a few minutes after each slot.

The thumbnail is still owed and the monitor keeps retrying it.

## Not built

- **Per-channel long-form times (step 7): decided, not built.** Every channel
  already declares the time of day it is for, and nothing uses it for long-form:

  | Channel | Declared time (WAT) |
  |---|---|
  | The Morning Altar | 7:14am |
  | The Covenant Shield | 9:44am |
  | The Praise Garden | 10:44am |
  | The Provision Table | 11:44am |
  | The Midday Watch | 1:14pm |
  | The Secret Place | 3:14pm |
  | The Healing Balm | 4:44pm |
  | The Family Altar | 6:14pm |
  | The Guided Path | 7:44pm |
  | The Midnight Watch | 12:14am |

  (`short_target_window_utc` in `pipeline/channel_capabilities.py`; the brain
  writes it into Short manifests and the dashboard shows it.) Decision: once the
  trial has passed and the crons are moved, one of each channel's three daily
  long-forms goes public at its declared time and the other two stay on the
  shared slots. That needs a per-channel public time in `publish_target()`
  instead of one lead for all, and a slot rule that counts a receipt by the slot
  it was produced for (`uploaded_at`), so a time later than the next slot does
  not cancel that slot. Whether the declared times are the right ones is then
  measured, not assumed: first-day views per channel per public time from
  `scripts/metrics_snapshot.py`, compared after four weeks.

- **Shorts on their own times.** Each channel declares a Short time
  (`short_target_window_utc` in `pipeline/channel_capabilities.py`), the brain
  writes it into each Short manifest, and `pipeline/short_release.py` already
  passes a manifest's `publish_at` to the upload. Nothing sets that value, and
  the Short receipt writer and the confirm script do not handle a scheduled
  Short yet. Until then a Short is public when its leg runs, which with the
  crons moved is about 4.5 hours earlier in the day than now.
- **A receipt for a rejected scheduled video is not moved back to the queue.**
  It is marked failed and the channel is produced again from the next job.
