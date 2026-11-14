# Monetisation: what the rules require, where the channels stand, what was built

14 November 2026. Times are Nigeria time (WAT) unless marked UTC.

## The short answer

- **Monetising tomorrow is not possible on any channel.** YouTube pays ad revenue only after a channel passes fixed thresholds and a human review. No channel here has passed the watch-time threshold.
- **One channel can get there: The Secret Place.** It is the only one with the 1,000 subscribers (1,250). What it lacks is watch time.
- **There is a deadline.** A channel still outside the programme on 1 February 2027 needs twice as much. From today that is 78 days.
- **What was built today:** The Secret Place's nightly long-form now runs about three hours (the prayer, then quiet music for sleep) instead of seven minutes. It is not yet proven on YouTube; the first one publishes at 8:14pm tonight.

## 1. What YouTube requires

Sources are creator guides read on 14 November 2026, not YouTube's own help pages (those hosts cannot be reached from the build machine). The thresholds agree across all of them.

| | Today | For a channel applying from 1 Feb 2027 |
|---|---|---|
| Subscribers | 1,000 | 1,000 |
| Public watch hours, last 12 months | 4,000 | 8,000 |
| or public Shorts views, last 90 days | 10 million | 20 million |

Also needed before applying: 2-step verification on the Google account, no active strikes, an AdSense account, and a review of the channel as a whole. The review is done by YouTube and cannot be automated or hurried.

What does not count:

- Time spent watching Shorts in the Shorts feed does not count toward the 4,000 hours.
- Private, unlisted and deleted videos, and views bought through ads, do not count.
- Bought views or subscribers break the rules and cost money. Not an option.

A lower tier exists (500 subscribers, 3,000 hours) that opens memberships and Super Thanks but no ads, in listed countries. Whether Nigeria is listed is not confirmed.

## 2. Where the channels stand

Measured from the channel snapshots of 13 November (about 12:55am on the 14th). No newer measurement exists yet; the next one is tomorrow at 3:14am.

| Channel | Subscribers | Long-forms · views | Shorts · views |
|---|---|---|---|
| The Secret Place | 1,250 | 14 · 55 | 23 · 2,676 |
| The Morning Altar | 31 | 22 · 98 | 24 · 1,973 |
| The Midday Watch | 10 | 14 · 39 | 15 · 1,198 |
| The Midnight Watch | 13 | 10 · 7 | 9 · 688 |
| The Family Altar | 0 | 8 · 20 | 5 · 187 |
| The Healing Balm | 2 | 7 · 1 | 5 · 101 |
| The Provision Table | 3 | 8 · 19 | 6 · 342 |
| The Covenant Shield | 0 | 5 · 15 | 2 · 7 |
| The Praise Garden | 2 | 4 · 4 | 1 · 292 |
| The Guided Path | 0 | 3 · 3 | 1 · 49 |
| All ten | | 95 · 261 | 91 · 7,513 |

What that means against the thresholds:

- **Watch hours.** The exact figure is only in YouTube Studio (the automation has no Analytics permission). It can be bounded: The Secret Place's 14 measured long-forms had 55 views, each video six to eight minutes, so at most about 7 hours from them. The threshold is 4,000.
- **Shorts views.** 10 million in 90 days is about 111,000 a day. All ten channels together have 7,513 Shorts views in their whole life. The best Short has 393.
- **Subscribers.** Nine of ten channels are between 0 and 31. They need 1,000 each before watch time even matters.

To reach 4,000 hours on The Secret Place by 31 January 2027 takes about 51 watch hours every day from now.

## 3. Why a seven-minute prayer cannot get there, and what can

A seven-minute video watched to the end is 0.12 hours. Fifty-one hours a day would need about 440 complete views a day. The Secret Place's long-forms get between 0 and 4 views each.

The watch-time format in this niche is a different kind of video: a prayer or a reading followed by one to eight hours of gentle sound, played at bedtime and left on (for example the channel "The Night Psalm"). One listener for one hour is worth eight complete views of a seven-minute prayer. The Secret Place is the bedtime channel, so the format fits what it already is.

## 4. What was built: the night tail

Code: `pipeline/night_tail.py`, called from `pipeline/prayer_pipeline.py` after the prayer video is rendered. Tests: `tests/test_night_tail.py` (16).

What happens on The Secret Place's long-form each night:

1. The prayer video is rendered exactly as before.
2. A ten-minute rest section is made from that video's own pictures, dimmed, with the studio's own synthesised music at a lower level. For its first 40 seconds it shows "Rest now. He that keepeth thee will not slumber." (Psalm 121:3, King James Version) and a line saying the prayer has ended and music continues. Then the words leave and the screen stays dark.
3. The rest section is repeated after the prayer until the whole video is at least three hours. The prayer is not re-encoded or re-spoken.
4. The description's first line says what the video is ("Pray along for the first 7 minutes, then rest…"), a chapter marks where the music starts, and search tags for sleep prayer are added.

Cost: no speech request, no extra upload, no extra video. The 10 free speech requests a day are untouched.

Safeguards:

- Only The Secret Place. A sunrise or noon prayer is not a sleep video.
- Before building, the code asks YouTube whether the channel may upload videos longer than 15 minutes. If not, the prayer is published as before with a warning in the run log.
- If anything in the tail fails, the prayer is published as before.
- `NIGHT_TAIL_MINUTES=0` in the workflow turns it off. Another number changes the length (20 to 600 minutes).

Measured on the build machine:

- A ten-minute rest section took 5 minutes 52 seconds to build and came to 77 MB with one moving clip among the pictures. Eighteen of them is about 1.4 GB. With still pictures only it is smaller.
- A small real join (a 20-second stand-in prayer plus four sections) decoded from start to end with no errors.

## 5. What is not known

- **Whether anyone will leave it playing.** This is the whole bet. The first week of watch time in YouTube Studio is the test. The automation cannot read watch time.
- **Whether the three-hour upload goes through on the runner.** The first live run is tonight's 8:14pm slot. Look for the line `[night-tail] secret-place: …` in the run log.
- **How YouTube's reviewers will see it.** See the next section.

## 6. The risk that could block monetisation even at 4,000 hours

YouTube does not pay channels it judges "inauthentic": mass-produced, repetitive or templated videos. It judges the channel as a whole, at the review.

What points that way here, plainly:

- Ten channels, one synthetic voice, one music score, one layout, five Shorts a day each.
- The rest section's music is the same score every night. Only the pictures and the prayer change.

What points the other way: each prayer is newly written on a different passage, the scripture is quoted and checked word for word, and the visuals differ per video.

Posting more of the same raises this risk. It is a reason not to chase volume, and a reason the nine small channels are not the path to the first payment.

## 7. What the Shorts numbers show

78 published Shorts at least a day old at the snapshot.

| Length | Shorts | Median views |
|---|---|---|
| 35 to 45 seconds | 6 | 131 |
| 45 to 52 seconds | 16 | 64 |
| 52 seconds and over | 56 | 57 |

- Shorter Shorts were watched more, but six Shorts is too few to change the writing on. The length asked of the writer was already lowered on 13 November. Nothing was changed today.
- Publishing hour shows no clear pattern (medians 43 to 78 across the day, small groups).
- Viewers left 8.4 likes and 2.2 comments per 100 views.
- "Say This…" titles (three older channels) had a median of 77 views against 23 for "Pray This…" (seven newer channels). The channels differ in age and subscribers, so this does not show the wording is the cause.

## 8. What only the owner can do

In order of value for monetisation:

1. **Read The Secret Place's watch hours** in YouTube Studio → Earn. That is the real starting number, and nothing else can supply it.
2. **Give the automation YouTube Analytics permission** on The Secret Place, so watch time is measured daily and the format can be judged.
3. **Turn on 2-step verification** on the Google account that owns The Secret Place, and open an AdSense account. Both are required before applying.
4. Phone-verify the other channels at youtube.com/verify. Until then they cannot have custom thumbnails or videos over 15 minutes.

## 9. How to undo

Set `NIGHT_TAIL_MINUTES: "0"` in the environment of the release job in `.github/workflows/produce.yml`, or empty `TAIL_MINUTES` in `pipeline/night_tail.py`. Videos already published stay as they are.
