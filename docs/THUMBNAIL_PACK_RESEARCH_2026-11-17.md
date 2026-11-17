# The pack is not the mould. The map is.

17 November 2026. Times are Nigeria time (WAT, UTC+1) unless marked UTC.

This is a reading, not a plan — and it begins with a correction of the reading
published three hours earlier (`docs/MOULD_AND_HOURS_RESEARCH_2026-11-17.md`).
Every figure below was measured from this repository's own files; each one names
the file it was read from. Where a number could not be measured from here it is
marked as such rather than estimated.

## The short answer

- **The finding in the earlier reading was about a file that no longer ships.**
  `pipeline/thumbnail.py::render_studio_thumbnail` does paint one navy grade for
  all ten channels — that is true, and it is why it was reported. But nothing on
  the publish path calls it. Every call site sits inside
  `pipeline/run.py::_disabled_legacy_process` (line 411), a function named as
  dead and never invoked: `process()` (line 386) goes straight to
  `prayer_pipeline.produce`. The frame that actually ships is built by
  `pipeline/thumbnail_ctr.py`, and that one is per channel: **30 palettes across
  the ten channels, three per channel, 30 distinct, none repeated**
  (`CTR_VARIANTS` … `PATHWAY_VARIANTS`, lines 176–408).
- **What is still wrong is smaller and more useful.** The pack renders three
  concepts per video and the pipeline uploads one
  (`prayer_pipeline.py:386`). Concepts 1 and 2 carry **the same words at the same
  size in the same place** whenever the script has an authored hero line — 202 of
  440 faith jobs — so the pair offered to Test & Compare is a recolour, which
  `docs/THUMBNAIL_RESEARCH.md` §5 explicitly forbids.
- **Half the corpus has no authored hero at all.** 238 of 440 faith-channel jobs
  carry no `thumb_text`; on those the pack falls back to the channel's fixed line
  ("PRAY THIS TONIGHT" on all 32 Secret Place jobs without one) — the exact defect
  the CTR pack was built to end.
- **The map is wrong in five places**, including two documents that describe the
  retired renderer in the present tense and a workflow input whose help text
  promises an option that cannot be reached. This is not cosmetic: the earlier
  reading of 17 November was misled by it, and so was the recommendation in it.
- **Nothing below changes a pixel.** The repairs shipped with this reading are
  pointers, labels and one test that guards nothing today.

## 1. Which renderer ships which surface

Four generators exist in the tree. Three are live and one is not, and the
repository does not say which is which.

| Generator | Reached from | Ships to | Per channel? |
|---|---|---|---|
| `thumbnail_ctr.generate_ctr_pack` | `prayer_pipeline.produce` (`:359`), `_refresh_live_thumbnail` (`:41`), `.github/workflows/set-thumbnail.yml` | every automated publish; the owner's manual "set thumbnail" run | **yes** — 3 concepts, own palette and grade per channel |
| `thumbnail_studio.generate_style_pack` | `set-thumbnail.yml` only (kept as a control) | the owner's manual run, variant `main`/`b`/`c` | no — one recipe, palette fixed |
| `shorts_poster` | Shorts path | 9:16 posters | yes — 10 `_GRADES` |
| `thumbnail.render_studio_thumbnail` | **nothing live** — `_disabled_legacy_process` (`run.py:466`, `:528`) and `tests/test_thumbnail_studio.py:72` as a historical baseline | nothing | **no** — one navy grade for all ten |

The proof that the fourth is dead is structural, not a judgement:

- `run.py:386 process()` contains no call to it; it imports `produce` and returns
  it. `run.py:411 _disabled_legacy_process` is defined, never referenced.
- `run.py:522` inside that dead function raises
  `RuntimeError("Legacy montage renderer is prohibited by the visual style lock")`
  — the code below that line, including the thumbnail call at `:528`, cannot run
  even if the function is called.
- The only other reference is a test that renders it deliberately, to compare
  legible ink against the current pack. That use is legitimate; its label is not.

So the earlier reading's headline — "the picture is the mould … the long-form
renderer never got the per-channel fix" — is true of a superseded generator and
false of the channel. The corrected statement is the one that matters: **the
long-form renderer got the per-channel fix in November; what it did not get is a
sign saying so.**

## 2. What the shipping pack actually is

Read from `pipeline/thumbnail_ctr.py`, `CTR_VARIANTS` through `PATHWAY_VARIANTS`:

| Channel | Grade | Concepts (label → copy) | Sky, top → bottom (concept 1) |
|---|---|---|---|
| secret-place | night | hook → the script's line · quiet → same line · poster → none | (5,11,28) → (26,52,96) |
| prayer2 | dawn | hook / quiet / poster | (18,10,30) → (118,58,42) |
| prayer3 | noon | hook / quiet / poster | (14,20,30) → (106,74,34) |
| prayer4 | midnight | hook / quiet / poster | (7,9,30) → (42,34,96) |
| prayer5 | hearth | hook / quiet / poster | (9,22,15) → (68,54,26) |
| prayer6 | balm | hook / quiet / poster | (8,30,44) → (24,88,108) |
| prayer7 | harvest | hook / quiet / poster | (30,11,17) → (108,56,28) |
| prayer8 | fortress | hook / quiet / poster | (22,10,36) → (86,44,104) |
| prayer9 | garden | hook / quiet / poster | (20,30,19) → (140,74,46) |
| prayer10 | pathway | hook / quiet / poster | (7,32,36) → (28,94,96) |

30 palettes, 30 distinct names, three per channel. The three concepts also differ
geometrically — moon centre, moon scale, ridge line, dawn band strength, rays,
seed, text box — for example on prayer8 the moon sits at (0.772, 0.395) at 0.205
scale in `hook` and at (0.552, 0.432) at 0.232 in `poster`. That is design
differentiation, not recolouring, and it is the part of the pack that works.

The one element that is identical across all 30 palettes is the accent, held
between (246,202,74) and (255,216,104) — the studio's gold. That is a house
signature, not an accident, and it is not a defect.

## 3. Where the mould actually remains: concepts 1 and 2 are one idea

> **Follow-up, same day:** the hero line itself was being cut on three published
> frames — a separate defect in how the pack fits text, found after this reading:
> `docs/THUMBNAIL_HERO_FIT_2026-11-17.md`.

`generate_ctr_pack` (line 1529) replaces the copy on every concept that has copy:

```python
if hero_override and variant.hero:
    render = dataclasses.replace(variant, hero=hero_override.upper().strip())
```

`prayer_pipeline.produce` passes `hero_override=doc.meta.get("thumb_text")`
(line 360). The three concepts were designed as *imperative*, *curiosity* and
*no copy*; with an override the first two become the same string. Rendered from
this repository's own job `0010-psalm-121-he-who-keeps-you-will-neither-slumber-no.md`:

| Concept | hero | hero px | lines | contrast | mean luma |
|---|---|---:|---:|---:|---:|
| hook | `THE LORD IS YOUR KEEPER` | 125 | 3 | 9.15:1 | 73.4 |
| quiet | `THE LORD IS YOUR KEEPER` | 125 | 3 | 11.07:1 | 65.8 |
| poster | — | 0 | 0 | — | 64.8 |

Same words, same size, same position, same line count. Cropping the text box
(86,84)–(690,470) from both frames and differencing them gives a **mean absolute
difference of 5.8 / 5.3 / 5.2 out of 255** per channel — the sky showing through
the antialiased type. The two frames are not two ideas; they are one idea at two
colour temperatures.

How many videos are affected is measurable: **202 of 440 faith-channel jobs carry
a `thumb_text`, and on every one of them concepts 1 and 2 collapse into one.**

| | Jobs | thumb_text | Effect on the pack |
|---|---:|---:|---|
| secret-place | 71 | 32 | 39 fixed-line |
| prayer2 | 70 | 31 | 39 fixed-line |
| prayer3 | 54 | 24 | 30 fixed-line |
| prayer4 | 46 | 21 | 25 fixed-line |
| prayer5 | 36 | 17 | 19 fixed-line |
| prayer6 | 37 | 17 | 20 fixed-line |
| prayer7 | 38 | 18 | 20 fixed-line |
| prayer8 | 32 | 16 | 16 fixed-line |
| prayer9 | 29 | 13 | 16 fixed-line |
| prayer10 | 27 | 13 | 14 fixed-line |
| **total** | **440** | **202** | **238** |

The 238 have no authored line, so concepts 1 and 2 keep their own copy — and that
copy is a constant per channel, the same sentence on every video the channel ever
releases: "PRAY THIS TONIGHT" on thirty-two Secret Place videos, "PRAY AT SUNRISE"
on the morning channel, and so on. The pack's own docstring calls that the defect
it was written to fix. It is fixed for 46% of the corpus.

### The unreachable option

`.github/workflows/set-thumbnail.yml` offers an input whose description reads
"Override the hero text on the text variants (blank = each concept keeps its own
copy)". `resolved_hero = hero or doc.meta.get('thumb_text') or choose_hero(doc)`:
because all 202 authored jobs have a `thumb_text`, leaving the box blank cannot
reach "each concept keeps its own copy". The workflow offers a choice that does
not exist. (It is reachable only for the 238 jobs that have no line at all — the
ones where the operator most wants a line.)

## 4. Three concepts rendered, one uploaded

Per job the pack writes `thumbnail_hook.jpg`, `thumbnail_quiet.jpg`,
`thumbnail_poster.jpg` and a `report.json` (`prayer_pipeline.py:359–368`). Then
`upload(... thumbs[0] ...)` sends the first (`:386`), and
`_refresh_live_thumbnail` also applies `reports[0]` (`:48`).

- 440 faith jobs × 3 concepts = **1,320 frames rendered**.
- 440 shipped by the pipeline; **880 (67%) reach YouTube only if a human opens
  Studio and sets them**, using `set-thumbnail.yml` or Studio's own Test & Compare.
- Test & Compare is Studio-only and cannot be automated
  (`docs/GROWTH_FEEDBACK_LOOP_2026-11-04.md:212`, `CHANGELOG.md:503`).
- Applying one frame to one video costs 50 quota units against a 10,000/day
  budget — **200 sets a day** (`docs/FAST_TRACK_4000_WATCH_HOURS.md:130`). Giving
  the 238 fixed-line videos an authored frame is 11,900 units, or about **60 days
  at 200/day** if done by hand, and it competes with uploads for the same quota.

Two consequences worth stating plainly:

1. The pipeline produces testing material it does not use and cannot use. That is
   not waste — it is the honest limit of an unattended pipeline on a surface
   YouTube keeps manual — but it means "three genuinely different concepts ship"
   (`STATE.md:471`) is true of the files, not of the channel.
2. `_refresh_live_thumbnail` overwrites whatever is live with `reports[0]` on any
   re-run of an already-published job. If the owner picked `quiet` or `poster` by
   hand in Studio, a re-run silently puts `hook` back. Nobody has been told this.

## 5. The map errors, in full

| Where | Says | Is |
|---|---|---|
| `docs/MONETIZATION_AUDIT.md:215` | "All typography in `render_studio_thumbnail()` is strictly left-aligned…" (present tense, under the safe-zone rule) | describes the retired card generator; the live pack clears the badge zone in `render_ctr` and reports `badge_zone_ok` per frame |
| `docs/THUMBNAIL_RESEARCH.md:83` | "Measured from the actual output (`pipeline/thumbnail.py::render_studio_thumbnail`)" | a historical measurement of a superseded frame, unlabelled as history |
| `docs/GROWTH.md:120` | "The pipeline generates `*_thumb_a/b/c.jpg` drafts" | `thumbnail.py` wrote `thumbnail_a/b/c.jpg`, and it no longer runs; the live pack writes `thumbnail_hook/quiet/poster.jpg` |
| `pipeline/thumbnail.py:1` | "Draft thumbnail generator… plus A/B/C variants for YouTube Studio's Test & Compare" | eight paragraphs of design reasoning for a file that ships nowhere |
| `pipeline/prayer_pipeline.py:1` | "Approved-style long-form production path (**not yet enabled on main**)" | it is the only long-form path on main |
| `tests/test_prayer_pipeline.py:164` | patches `pipeline.thumbnail.generate_thumbnail_variants` | `produce()` never imports it — the mock guards nothing, and a future re-wiring to the old renderer would pass the test |

That last one is the mechanism by which this reading was possible at all: the test
named "uses approved renderer" does not assert which renderer is used.

## 6. What a repair would move, and where that figure is read

| Repair | Figure it moves | Where it is read |
|---|---|---|
| Label `thumbnail.py` as superseded, correct the four doc pointers | 0 pixels; removes the misdirection that produced §1 | the files themselves |
| Replace the dead mock with an assertion that `produce` calls `generate_ctr_pack(channel_id=doc.channel)` | 1 test that can fail; today 0 can | `tests/test_prayer_pipeline.py` |
| Correct the `hero` input help in `set-thumbnail.yml` | an operator no longer expects an unreachable option | the workflow's dispatch form |
| Author `thumb_text` on the 238 jobs that lack it (owner/queue work, 6 words each) | the share of videos whose hero is the script's own: 202/440 → 440/440 | frontmatter; `grep -c '^thumb_text:'` |
| Give concept 2 a *different* treatment rather than a different sky (design decision, not mine to take) | the pack's "genuinely different concepts" claim: 2 of 3 → 3 of 3 | `report.json` hero per concept |

**Not proven by any of this:** which variant wins. CTR is not measurable from this
sandbox, the analyytics in `content/analytics/` do not carry per-video thumbnail
CTR, and Test & Compare requires Studio. Every claim above is about what the
files contain, not about what viewers did.

**Owner-only:** whether to spend 11,900 quota units re-thumbing 238 videos; which
of the three concepts to ship by default; whether concept 2 should carry the
channel's fixed hook (a genuine second idea, and a fixed string on every video) or
a treatment change instead.

**One next step:** author `thumb_text` on the 238 published jobs that have none,
starting with Secret Place's 39, six words each — then let
`_refresh_live_thumbnail` carry the authored line onto the live frame the next time
each job is re-run, rather than setting 238 thumbnails by hand against a 200-a-day
limit.
