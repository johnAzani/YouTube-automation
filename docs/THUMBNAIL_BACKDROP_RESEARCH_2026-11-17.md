# One picture, ten skies

17 November 2026. Times are Nigeria time (WAT, UTC+1) unless marked UTC.

Fourth reading of the day. The third one found that the pack's *colour* is per
channel (30 palettes, none repeated). This one asks the next question down: if the
colour is different, is the **picture**? Measured from this repository's own files
and its own renderer.

## The short answer

- **The composition is one.** Rendering the `hook` concept for all ten channels
  with the same seed and no backdrop, then correlating the grayscale art half of
  the frames (x 600–1280 — no type in it), any two channels are **0.963 median
  alike** (lowest 0.897, highest 0.995). The moon, the ridge, the house and the
  reflection are at the same coordinates on every channel; only the sky's colour
  and the noise seed differ. Thirty concepts across ten channels reduce to **three
  arrangements** — moon right at 0.78/0.20 scale, moon right at 0.80/0.19, moon
  centre at 0.55/0.24 — with ±0.02 of jitter.
- **The fallback photographs are a pool of thirteen.** When a job's own footage
  yields no usable still, `thumbnail_ctr.curated_backdrop_for` hashes the job id
  into a pool of cleared 16:9 plates: **7 for the night grades, 6 for the
  daylight ones**. The 136 published faith long-forms map onto **7 plates**; the
  most-used plate carries **29 videos across all ten channels**, and of the
  **1,471** video pairs that share a plate, **1,307 (89%) are cross-channel**.
  Counting the queue as well, 202 videos fall onto the same 7 plates and the
  most-used carries **35 videos on all ten channels**.
- **The owner's manual path always takes that fallback.** `set-thumbnail.yml`
  passes `curated_backdrop_for(...)` directly and never calls `pick_backdrop`, so
  every thumbnail set by hand from that workflow is one of those photographs. The
  automated path tries the job's own footage first.
- **The writing does not converge on a shared passage** — and that is worth
  recording as a negative. Of 202 videos, 38 passages are prayed on more than one
  channel, giving **120 cross-channel same-passage pairs**. Their author's own
  words (6-word shingles with every King James phrase removed) are **0.0028**
  alike on average; 400 cross-channel pairs on *different* passages are **0.0028**
  alike. Sharing a passage does not make the scripts converge. The risk is in the
  picture and the frame, not the prose.
- **One small live defect found and fixed.** Nine published descriptions ended
  their **first line** — the snippet YouTube and Google show — with a doubled full
  stop ("…peace for the hours ahead**..**") because the authored `seo_hook`
  carried one. `metadata._end_once` now closes the sentence once; re-read over all
  202 faith long-forms: **9 → 0**, and a corpus test keeps it at 0.

## The measurement, in full

### 2.1 The art half of the frame, channel against channel

| | Reading |
|---|---|
| Channels compared | 10 (45 pairs) |
| Grayscale correlation of the art half, `hook` concept, same seed, no backdrop | min **0.897** · median **0.963** · max **0.995** |
| Most alike | prayer6–prayer7, prayer7–prayer10, prayer8–prayer10 (**0.99**) |
| Least alike | prayer2–prayer4 (**0.90**) |

The palettes from the previous reading differ by up to 19 components of hue in
their sky; the geometry does not move. A viewer scrolling past three of these sees
one picture in three tints.

### 2.2 The plates

| | Reading |
|---|---|
| Pool | `_ALL_CURATED_PLATES` **7**, `_DAYLIGHT_CURATED_PLATES` **6** |
| Named plates for the night channels | 6 (`CURATED_SANCTUARY_PLATES`) |
| Published faith long-forms | 136 |
| Distinct plates they fall back to | **7** |
| Most-used plate | `long-prayer-scene-03.jpg` — 29 videos on 10 channels |
| Videos per plate, published | 3 to 29 (3, 16, 17, 23, 23, 25, 29) |
| Video pairs sharing a plate | 1,471 — of which **1,307 cross-channel (89%)** |
| With the queue included | 202 videos → 7 plates; most-used 35 videos on 10 channels |

The id space is clean — all 202 video ids are unique, so the hash spreads as well
as seven buckets allow. The figure that would move is the **pool size**, not the
hash: with 7 plates and 30 videos a channel, a viewer meets every plate within its
first nine videos whatever the hash does. Changing the hash would move the
coincidence around without reducing it, so it was not changed.

### 2.3 What the metadata pack is already doing right

Measured so as not to over-report sameness:

- **Line 1 of the description.** 202 faith long-forms, **202 distinct** snippets,
  **186 distinct skeletons** once the scripture reference is replaced — the
  opposite of the Short titles, where 237 of 237 share one frame.
- **Tags.** 1,156 distinct tags, 15–18 per video on 197 of 202. The five below ten
  are the finance-era jobs (`0003`–`0007`) that still live in the faith folder.
- **Description size.** The largest assembled description is 2,062 bytes against
  YouTube's 5,000 and the pack's own 4,900 ceiling: nothing is truncated, and the
  hashtag line survives on all 202.
- **Prose cut.** `build_description` stops the body at 1,800 characters. Two jobs
  exceed it and are cut mid-sentence — `0003-how-lehman-brothers-died.md` and
  `0007-the-day-the-exchange-pressed-undo.md`, both finance-era.

## What changed, and what it moves

| Change | Figure it moves | Where it is read |
|---|---|---|
| `scripts/channel_protection.py` gains **"Thumbnail backdrops"** — pool sizes, videos, plates, most-used plate and channel count, cross-channel pair share | the picture now has a number in the daily report it did not have | `python -m scripts.channel_protection`, step summary |
| `pipeline/metadata._end_once` closes the snippet once | snippets ending "..": **9 → 0** of 202 | `content/published/*.md` front matter, `_synthesize_seo_hook` |
| No palette, geometry or plate was changed | 0 pixels | — |

Three tests guard the new section and the snippet; one existing test renders the
report text and now sees the block.

## What this does not prove

- **How often the fallback fires.** The pack prefers the job's own footage
  (`pick_backdrop`) and only falls back to a plate when that yields nothing. The
  rendered outputs of past runs are not in this repository, so the share of
  shipped frames that are a plate cannot be measured from here — the new report
  says so in as many words. The **0.963** figure is the painted scene, which is
  what ships whenever there is no backdrop at all — the pack's own default art.
- **Whether the sameness costs anything.** No per-video thumbnail CTR exists in
  `content/analytics/`, and Test & Compare is Studio-only.

## Owner-only, and one next step

- **Owner-only:** clearing more plates (each must be licensed — `image-search/`
  holds the pool and its provenance), or making the workflow use the job's own
  footage the way `produce` does (it would have to download the scene assets
  inside the workflow). Either changes what a viewer sees; neither is mine to
  take.
- **One next step:** run `set-thumbnail.yml` once for one job on each of the ten
  channels in `dry_run`, and put the ten frames side by side. The correlation says
  they are one picture; ten pairs of eyes on the ten images settles whether that
  is a studio look or ten channels wearing one coat.
