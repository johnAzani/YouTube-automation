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
| Short | Unchanged: uploaded and public when its leg runs. See "Not built". |
| Dashboard (`docs/network-state.json`) | A scheduled video shows privacy `scheduled`. |
| Comment replies | Unchanged: a private video has no comments to answer. |

## Turning it on

Three steps, in this order.

**1. One trial, one channel.** After this change is merged and no production run
is waiting:

```
gh workflow run produce.yml -f channels=prayer2 -f publish_at=2026-11-14T14:14:00Z
```

(any time at least 15 minutes after the leg will finish, within two days). Check:
the receipt carries `scheduled_publish: true`; the video is private in YouTube
Studio with the right time, thumbnail, captions and playlist; at the time it goes
public; the next monitor run clears the flag; whether the pinned comment was
posted at upload or afterwards.

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

## Not built

- **Shorts on their own times.** Each channel declares a Short time
  (`short_target_window_utc` in `pipeline/channel_capabilities.py`), the brain
  writes it into each Short manifest, and `pipeline/short_release.py` already
  passes a manifest's `publish_at` to the upload. Nothing sets that value, and
  the Short receipt writer and the confirm script do not handle a scheduled
  Short yet. Until then a Short is public when its leg runs, which with the
  crons moved is about 4.5 hours earlier in the day than now.
- **Per-channel long-form times.** The repository has no data to choose them
  from: the daily metrics (`scripts/metrics_snapshot.py`: views, likes, comments
  per video) say nothing about the hour viewers watch. Once scheduled publishing
  is live, rotate each channel through the three slots for four weeks and compare
  first-day views per slot; choose from that.
- **A receipt for a rejected scheduled video is not moved back to the queue.**
  It is marked failed and the channel is produced again from the next job.
