# Where the watch hours come from, and what length they reward

21 November 2026. Built in answer to a request for features that move
monetisation, views, subscribers, watch time and retention, fully automated.

This document says what was built, what it measured on the day it was built, and
what it cannot do. The short version: **one of the five things asked for is now
measured honestly, and that measurement says the other four are not the
bottleneck.** The bottleneck is that nobody stays.

---

## 1. What the request was, and what the repository already had

Asked for: monetisation, views, subscribers, watch time, retention — all moving,
all automated.

Already built and running before today (each with its own document):
playlist autoplay (`pipeline/playlists.py`), end-screen plates
(`pipeline/end_screens.py`), a three-hour night tail for the bedtime channel
(`pipeline/night_tail.py`), A/B thumbnail concepts (`pipeline/thumbnail_ctr.py`),
title variety and retitling (`pipeline/retitle.py`, `pipeline/title_variety.py`),
comment replies, community posts, closed-loop theme steering
(`pipeline/performance_feedback.py`), and per-channel Analytics reading
(`scripts/analytics_reader.py`).

So the honest question was not "what else can be added" but "which of these is
actually working, and nothing was measuring that". Everything above was built on
a belief about what moves watch time. None of it was checked against the
channel's own numbers, because the numbers were in `content/analytics/` and no
code read them for this purpose.

## 2. The reading, on 21 November 2026

From `content/analytics/secret-place.json` (The Secret Place is the only channel
with the Analytics grant), last 28 days:

| Where the hours came from | Hours | Share of all watch hours |
| :--- | ---: | ---: |
| Shorts feed | 24.68 | 46.7% |
| Suggested videos | 22.05 | 41.8% |
| Other sites and apps | 1.20 | 2.3% |
| Direct or unknown | 1.98 | 3.7% |
| Home and subscriptions | 1.05 | 2.0% |
| YouTube search | 0.95 | 1.8% |
| Channel page | 0.58 | 1.1% |
| Other YouTube pages | 0.23 | 0.4% |
| Notifications | 0.10 | 0.2% |
| Shorts sound pages | 0.00 | 0.0% |
| **Counted (everything but Shorts)** | **23.00** | **43.6%** |

Two things follow, and both change what work is worth doing:

1. **Nearly half the watch time does not count.** Shorts-feed hours never count
   toward the 4,000. The pace that matters is 23 hours a month, not 53.
2. **The door that does work is Suggested videos: 22 of the 23 counted hours.**
   Search, subscriptions, playlists and end screens are between them worth about
   one hour a month. Building more end screens, more playlists or more search
   wording is not where the hours are.

And the last long-form retention, from the same file's 365-day video table
(Shorts excluded, because a looping Short reports past 100% watched):

**median 8.9% watched.** The three-hour night tail and six-minute prayers are
abandoned in the same place — the earlier research on one measured night-tail
video said viewers left at 99 seconds.

## 3. What was built

### 3.1 `pipeline/growth_score.py` — the reading that steers the rest

Reads the committed Analytics files and writes
`content/research/growth_score.json`:

* **hours by door**, per channel and for the network, over the days every
  channel reports (the same window for all, so a stale file cannot shrink its
  channel's share);
* **the counted share** and the pace it implies, against the threshold and the
  day it doubles (1 February 2027);
* **each channel's target** — its share of counted hours, multiplied out;
* **a length budget**, and the evidence for it (below);
* **verdicts on the format changes**, each read from the hours, never assumed:
  * `night_tail` — a day whose hours rose above the channel's recent usual is a
    *bump*; three or more bumps in 15% of the days read is a `hold`, none is
    `flat`, and `flat` turns the tail off;
  * `end_screen` — hours arriving from end screens, if any;
  * `related_video` — the Short-to-prayer door that no description link can
    replace (YouTube says Shorts description URLs are not clickable).

It is pure standard library, makes no API call, holds no credential, and every
function is fail-soft: a missing file, a bad row or a channel without a grant is
named in the report, never raised.

### 3.2 The length question, answered with data instead of a guess

The night tail was 180 minutes because a document said so. It is now chosen from
**hours earned per view, by the video's own length** — the only thing a length
can be priced on:

| Length band | Videos measured | Hours a view |
| :--- | ---: | ---: |
| over 3 hours | 6 | **0.1261** |

That is the reading today: a view of a three-hour video returns 0.126 hours
(about 7.5 minutes). It is the best measured band, and it is also the *only*
band with enough videos to count — because every shorter prayer in the same file
has no recorded length (see 3.3). The budget is therefore held at the measured
figure (180 minutes, inside the 3-to-180-minute limits the render, the upload and
the night tail can all survive), and `pipeline/night_tail.py` reads it from the
report rather than a constant.

`NIGHT_TAIL_MINUTES` still wins when set, and `0` still turns the tail off.

### 3.3 A receipt now says what the video *is*

This is the smallest change and the one that makes the rest possible: **192 of
the 201 long-form receipts carried only `target_minutes`** — what the script was
*planned* at. A six-minute prayer and a three-hour one were indistinguishable in
the repository. `pipeline/run.py:_mark_job_uploaded()` now stamps
`duration_seconds`, the real length of the file that was uploaded, and
`pipeline/prayer_pipeline.py` passes it. The reading also picks up real lengths
from the reach files where a recording never stamped one, and refuses to price a
planned length at all (`videos_without_a_length` says how many it could not).

### 3.4 Automation

`.github/workflows/growth-score.yml` runs daily at 04:37 UTC, an hour after
`channel-analytics.yml` starts, and commits the reading to `main` with the usual
retry-on-race loop. A push that touches the reading runs it immediately. On a
session branch it reads and reports but commits nothing, the same rule the
analytics job follows. `scripts/automation_monitor.py` now knows both workflows,
so a stalled one is reported.

### 3.5 What was deliberately not built

* **Dashboard widgets or vanity charts.** The numbers are already in
  `content/analytics/README.md`; another view of them moves nothing.
* **More thumbnails, end screens or playlist links.** Treated as built: the
  reading shows their door is worth about one hour a month. Adding to it without
  evidence is how the repository accumulated engines that were never checked.
* **Anything that buys views or subscribers.** Against YouTube's rules and
  costing money, which the $0.00 lock rules out.
* **A per-video "bump" table.** The Analytics file does not say which video a
  day's hours came from, so a per-video claim would be invented. The reading says
  it cannot do this rather than guessing.

## 4. What only the owner can do

1. **Grant the Analytics read-only scope to the other nine channels.** Nine of
   ten channels have never had their hours read, so their targets, their doors
   and their retention are all invisible. This is one consent screen per channel
   and it is the single largest information gain available.
2. **Decide whether the night tail stays.** The reading currently says `hold`
   (days do step up) while the retention says viewers leave at about nine
   minutes. Those two are not yet reconciled, and three videos is not a finding.
   `NIGHT_TAIL_MINUTES=0` pauses it; the report turns it off on its own when the
   bumps stop.
3. **Say whether the January threshold is still the goal.** At 23 counted hours a
   month the date is not reachable, and pretending otherwise would make every
   number in this repository look like a plan. If the goal becomes the rate, this
   reading is the instrument for it.

## 5. What is not known

* Whether a shorter video with better retention earns more *per view* than a long
  one. It cannot be compared yet: the shorter bands have no measured lengths.
  After a few weeks of `duration_seconds` being stamped, they will.
* Whether Suggested-video traffic can be increased deliberately. It is the door
  with the hours, but a suggested video is chosen by YouTube, not by a line of
  metadata. The honest lever is that viewers who finish a video get shown another
  — which is the retention problem in section 2, not a distribution problem.
* Whether the night-tail bump days are the tail at all, or something else that
  happened on those days. Correlating a day's hours with the videos published
  that day needs the video-level series, and the file holds only 50 videos over
  365 days.
* Whether the other nine channels behave like this one. They have not been read.

---

*Sources read for this document: `content/analytics/secret-place.json`,
`content/analytics/README.md`, `content/published/*.md` (201 long-form receipts),
`docs/MOULD_AND_HOURS_RESEARCH_2026-11-17.md`,
`docs/MONETISATION_RESEARCH_2026-11-14.md`, `docs/FAST_TRACK_4000_WATCH_HOURS.md`,
`pipeline/night_tail.py`, `pipeline/performance_feedback.py`, `pipeline/run.py`.
Tests: `tests/test_growth_score.py` (29).*
