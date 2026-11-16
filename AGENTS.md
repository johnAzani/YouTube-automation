# Standing orders for anyone, human or AI, who works in this repository

Read this first, every session. The owner set these on 16 November 2026 and
does not want to repeat them: "constantly and always improve on the
intelligence, revenue intelligence, all channel protection. Don't ever forget
these. I don't want to always remind you. Lock it in."

`STATE.md` holds the project's history and its fixed choices (voice, cost
lock, no personal names, Nigeria time). This file holds what every piece of
work must serve.

## The three standing priorities

Every change, and every next step proposed to the owner, is weighed against
all three. A session that improved none of them has not done the job.

1. **Protection of all ten channels.** Losing the channels ends everything
   else, so this comes first when the three pull apart.
2. **Revenue intelligence.** Know, from measured figures, how far each channel
   is from being paid and what moves it closer.
3. **Intelligence of the automation.** The program learns from what its own
   videos did and writes, titles and schedules better for it.

## 1. Protection

What threatens the channels, in order (sources and figures:
`docs/PROTECTION_AND_REVENUE_RESEARCH_2026-11-16.md`):

- YouTube ends channels, and all of an owner's channels together, for many
  similar AI-made videos across linked channels. It refuses to pay channels
  whose videos look made from a template.
- One program is meant to use one Google Cloud project.
- A health or money channel that gives advice in an AI voice cannot be paid.

Rules for any change:

- **Never raise how many videos a channel publishes a day** without the owner
  saying so in that conversation. More volume is more exposure and, for
  Shorts, earns no counted watch hours.
- **Never make the channels more alike.** A change that gives every channel
  the same new title wording, description block, comment, poll or thumbnail
  layout is a change for the worse. Prefer changes that make each video, and
  each channel, more its own.
- **Never weaken a check that refuses a video**: scripture quoted word for
  word, the narration matching the script, another channel's wording, a
  duplicate upload, the wrong channel's token. Fix the cause.
- Prayer stays prayer. No medical, financial or legal advice, no promised
  outcome, on any channel.
- Never do anything meant to hide from YouTube that the channels are related,
  or to get round a quota or a limit. Report the limit to the owner.
- Read `python -m scripts.channel_protection` before and after a change to
  titles, descriptions, scripts or the schedule. If its figures get worse, the
  change is not finished.

## 2. Revenue intelligence

- The real figures are in `content/analytics/` (YouTube Analytics, about two
  days behind). Read them; do not estimate what can be read.
- Only long-form watch hours count toward the Partner Programme. Shorts views
  do not. Judge a change by counted hours and by views of long-forms, not by
  uploads or Shorts views.
- State the distance to the threshold in numbers whenever monetisation is
  discussed, and say plainly when a date cannot be met.
- Never print a revenue estimate taken from a website as if it were this
  channel's. Never write real revenue figures into the repository.
- The thresholds change (8,000 hours for new applicants from 1 February
  2027). Check YouTube's own pages again before relying on a number older than
  a month.

## 3. Intelligence

- A change to how videos are written, titled or scheduled states what figure
  it expects to move and where that figure will be read. Go back and read it.
- Prefer what was measured on these channels to general advice. Say how many
  videos a figure rests on; a handful is not a finding.
- When the program refuses or fails something, make it say why in words the
  owner can read, and make the same failure impossible to miss next time.

## How to work

- Research before changing. Read YouTube's own page, not only a summary of it,
  and record what was read and what was not.
- Measure before and after, in the repository's real files.
- Every change comes with tests, goes through a pull request, and is merged
  only when its checks pass.
- Report to the owner in plain words and Nigeria time: what was measured, what
  was changed, what is not proven, what only he can do, and one next step.
- Do not tell the owner something works until it has been seen to work.

## When this file may change

Only when the owner changes the order. `tests/test_standing_orders.py` fails
if the three priorities or the rules above are removed.
