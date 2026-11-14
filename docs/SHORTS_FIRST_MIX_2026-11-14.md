# One long-form and five Shorts a day (14 November 2026)

The owner handed the decision over ("I have handed all the channels over to
you"). This is what was decided, why, what it costs, and how to undo it.

## 1. Why

Measured at 11:55pm UTC on 13 November, all ten channels
(`docs/GROWTH_EVIDENCE_2026-11-14.md`):

| | Videos | Views | Typical |
|---|---|---|---|
| Long-forms | 95 | 261 | 1 |
| Shorts | 91 | 7,513 | 65 |

Each channel was publishing up to three long-forms and three Shorts a day. Two
of every three long renders, and two of every three pairs of speech requests,
went to videos nobody opened.

## 2. What changed

**The same six uploads a day per channel, in a different mix: one long-form and
five Shorts.**

| Slot (Nigeria time) | UTC | Long-form from | Short from |
|---|---|---|---|
| 7:14am | 06:14 | The Morning Altar, The Praise Garden | all ten |
| 11:14am (new) | 10:14 | The Provision Table, The Guided Path | all ten |
| 3:14pm | 14:14 | The Midday Watch, The Family Altar | all ten |
| 8:14pm | 19:14 | The Secret Place, The Healing Balm | all ten |
| 12:14am (new) | 23:14 | The Midnight Watch, The Covenant Shield | all ten |

- The table of who gets which slot is `LONGFORM_SLOT_UTC` in
  `scripts/produce_plan.py`. Two channels to a slot, so no slot carries all ten
  long renders.
- A production leg asks `python -m scripts.produce_plan --longform-due <channel>`
  after its Short step and before the long-form step. The step is skipped only
  on an explicit "no". If the check fails, the long-form is made.
- **A slot does not come up empty.** If a Shorts-only slot has no Short to show
  (the render failed, or none was ready), the leg makes a long-form instead, as
  every slot did before. Not within 7 hours of the channel's last long-form
  (`LONGFORM_FALLBACK_MIN_GAP_HOURS`), so a day of broken Shorts gives about
  three long-forms, the old number, and not five. A Short published in the
  three hours before the check counts: that one is why the pacing guard held
  the next back.
- **Catch-up.** A channel whose newest long-form is more than 26 hours old is
  owed one at whatever slot runs next. A failed long-form slot costs hours, not
  a day.
- **"This slot is served"** (`published_channels_since` in
  `scripts/scheduler_supervisor.py`): the channel's long-form slot is served by
  a long-form receipt, every other slot by a Short receipt. A long-form serves
  any slot. The supervisor and the plan job both use this, so a Shorts-only
  slot is recovered when its Short is missing and left alone when it is not.
- By hand: the `longform` box on the Produce workflow (or
  `client_payload[longform]=true` on `publish-now`) makes a long-form in a slot
  that does not owe one. Naming a `job` still publishes that job, always.

**Shorts no longer need a long-form.** Four of the five daily Shorts have no
long-form behind them. Their passages come from, in order
(`pipeline/evergreen_shorts.py`):

1. `EVERGREEN`: 15 passages per channel that a listener is likely to know and
   to search for, chosen for what the channel is for. 150 in all, none shared
   between two channels.
2. Companions of the channel's long-forms, as before.
3. The channel's own roadmap, ahead of the long-forms: a passage that will be a
   long-form later can be a Short now. The key is the same, so the companion is
   not made twice.

A channel never gets a second Short on a passage it has one of (same book and
chapter, and the same first verse or the whole chapter).

Standalone manifests are named `0000-<key>.yml`, so they go out ahead of the
companion Shorts that were already waiting. They are written with the Short
prompt of 14 November (own opening sentence, about 105 words).

The daily brain run keeps ten Shorts ready per channel (two days), and writes
at most six standalone Shorts per channel per pass. Each production leg still
tops the channel up to three before it publishes.

**The monitor's false alarm.** "produce published nothing" compared calendar
dates: a late run that found its slot already served, and started after
midnight UTC, was reported as a failure until the next morning's upload (red
for six hours on 14 November). It is now judged against the slot the run
belonged to.

## 3. What it costs and what it frees

| Per channel, per day | Before | Now |
|---|---|---|
| Uploads | 6 | 6 |
| Speech requests (10 free) | 9 to 15, about 10 | 7 to 9, about 7 |
| Long renders | 3 | 1 |
| Text requests for Shorts | 3 | 5 to 10 |

- The long-form roadmap lasts three times as long (15 to 29 passages left per
  channel was five to ten days; it is now two to four weeks).
- Uploads: the count is unchanged on purpose. What YouTube allows these
  projects in a day is not known (the "1,600 units an upload" figure in older
  notes is out of date, `STATE.md`). Six a day is what the channels were asked
  for before; The Morning Altar's receipts show seven in one quota day on 10,
  11 and 12 November. A refused upload pauses that job until the reset
  (`pipeline/quota_handler.py`); it does not fail the run.
- Speech, counted on the 42 long-forms ready on 14 November at 4,000
  characters a request: 27 need two requests, 12 need three, 3 need four. A
  Short needs one. Three long-forms and three Shorts was 9 to 15 requests
  against 10 free, so a day with one long script paused itself; one and five is
  7 to 9. A retry after a failed take costs one more either way.
- Still $0: no new service, no new key, fewer speech requests.

## 4. What is not known

- **Whether five Shorts a day earns five-thirds of the views.** The average
  Short drew 83 views in its first days. More Shorts is more chances, not a
  promise per Short.
- **Whether the well-known passages will lead again.** They led in the first 91
  Shorts; that is a few days of data on small channels.
- **Whether the model writes good standalone Shorts with the new prompt.** The
  authoring path is the one that wrote 137 companion Shorts; the prompt changed
  on 14 November and its first live answers had not been read when this was
  written.
- **YouTube's view of the network.** Ten channels in one voice publishing
  scripted prayer Shorts is the kind of thing its "inauthentic content" policy
  is written about, and that review decides monetisation. Each Short is
  original writing on a different passage and nothing is re-uploaded, but the
  risk is real and five a day does not lower it.

## 5. The passage lists run out

At four standalone Shorts a day a channel has 30 to 44 passages: about eight
to eleven days. A run that finds fewer than eight left says so
(`Short passages running low`). Add passages to `EVERGREEN`, or extend the
channel's roadmap, before then. With nothing left, a channel falls back to one
companion Short a day and its other slots publish nothing; nothing breaks.

## 6. Consequences elsewhere

- **Scheduled publishing** (off; `docs/SCHEDULED_PUBLISHING_2026-11-13.md`).
  The switch-on recipe there (lead 270, three crons) no longer fits: the
  smallest gap between slots is four hours, so a lead must be under 240
  minutes, and it would move the Shorts earlier too, since Shorts publish the
  moment they finish. Rework it before switching on.
- `publish_at: next-slot` on a job now means the next of five slots.
- `SLOTS_PER_DAY` in `pipeline/supply.py` stays at 3 and now means "long-forms
  of runway per day of target", so the long-form queue holds three days.

## 7. Undo

- One slot table: set `LONGFORM_EVERY_SLOT = True` in
  `scripts/produce_plan.py` **and** remove the `14 10` and `14 23` crons from
  `.github/workflows/produce.yml`. That is the mix as it was on 13 November.
- Standalone Shorts only: empty `EVERGREEN` and return early from
  `_standalone_pass` in `pipeline/gemini_brain.py`. Queued `0000-` manifests
  can be deleted; nothing else refers to them.

## 8. Tests

`tests/test_shorts_first_mix.py` (41): the slots and the table, the leg's
decision, its catch-up and its fallback when the Short is missing, the step output, the workflow condition, what
serves a slot, the monitor's check, the passage lists, and standalone
authoring with a stand-in model.
