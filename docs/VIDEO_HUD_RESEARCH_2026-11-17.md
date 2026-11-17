# The corner of the frame that said the wrong name

17 November 2026. Times are Nigeria time (WAT, UTC+1) unless marked UTC.

Fifth reading of the day, one layer under the last four: the thumbnails have 30
palettes, the posters have ten grades — and the **video** underneath them has
never been given a channel at all.

## The short answer

- **The long-form renderer takes no channel.** `pipeline/prayer_visuals.render()`'s
  signature is `(narration, scenes, words, duration, output, *, timing_source,
  width, height, fps, progress)`; its only call site is
  `prayer_pipeline.py:349`, and it passes none either. Everything the renderer
  draws that is not the video's own footage is the same on all ten channels.
- **The HUD's top line was a literal.** Line 189 of the file drew
  `hud_chapter_layer(frame, 'THE SECRET PLACE', 'PRAYER AND SCRIPTURE', …)` — the
  first channel's name, hardcoded, in the top-left card of **every frame of every
  long-form on every channel**, for the whole six minutes. **118 of the 136
  published faith long-forms are on channels that are not The Secret Place**, and
  the approved path has been the only one on main since it was wired on
  31 October 2026.
- **This one cannot be undone on the videos already out.** YouTube has no way to
  replace a published video's footage — only delete and re-upload — so the corner
  of those 118 frames is permanent. The fix reaches every render from now on.
- **What else is shared, and stays shared for now:** one colour grade
  (`grade_sanctuary`: shadow tint `(8, 20, 46)`, 16% duotone, contrast 1.08,
  colour 1.14) applied to every channel; one card layout (30 characters a line,
  3 lines a card); one encode (1280×720, 24 fps, libx264 crf 21, AAC 192k,
  mastered to -15 LUFS); and **one musical score** — the key `prayer-longform`
  with a single chord progression (`tools/score.py:PROG`, Am–F–C–G–Am–Dm–F–E),
  ducked under speech at volume 0.58 and hushed on "amen" and "selah".
- **Fixed, and measured.** `prayer_visuals.brand_hud(channel)` answers the HUD per
  channel and `render()` takes `hud_kicker`; `prayer_pipeline` passes
  `brand_hud(doc.channel)[0]`. Ten channels, **ten distinct names**, The Secret
  Place byte-for-byte unchanged. A one-second frame rendered through the fixed
  path reads `01/01 THE MIDNIGHT WATCH` where it would have read `THE SECRET PLACE`.

## 1. What the picture is made of, and what varies

| Layer | Where it is set | Varies by channel? |
|---|---|---|
| Footage | the job's own scene assets | **yes** — this is the part a viewer actually looks at |
| Words on screen | `sentence_stream()` from the narration | yes (the script) |
| Colour grade | `tools/shorts.grade_sanctuary()` | **no** |
| HUD ("THE SECRET PLACE") | `prayer_visuals.py:189`, literal | **no → fixed today** |
| Card layout (30 chars, 3 lines) | `prayer_visuals.MAX_LINES_PER_CARD`, the 30 | **no** |
| Camera move | `tools/shorts.camera_frame()` | no |
| Typography | `tools/shorts.kinetic_typography_layer()` | no |
| Music | `tools/score.py` key `prayer-longform` | **no** |
| Encode | 1280×720, 24 fps, crf 21 | no |

The thumbnail pack was given per-channel palettes and the Shorts posters ten
grades. The 16:9 video — the surface that earns the watch hours — was given
neither, and its corner carried another channel's name.

## 2. What changed, and the figure it moves

| Change | Figure it moves | Where it is read |
|---|---|---|
| `prayer_visuals.brand_hud()` + `hud_kicker` / `hud_sub` parameters | channels whose HUD names themselves: **1 of 10 → 10 of 10** | `pipeline/prayer_visuals.py`, a rendered frame |
| `prayer_pipeline` passes `brand_hud(doc.channel)[0]` | the same, on every long-form rendered from now on | `prayer_pipeline.py:349` |
| Two tests: the ten names, and a real encode that draws the kicker it is given | 1 guard, 1 rendered frame | `tests/test_prayer_visuals.py` |

Nothing else was touched: the grade, the score, the layout and the encode are as
they were, because changing any of them changes six minutes of every future video
and that is a design decision, not a correction.

## 3. Why the grade and the score are reported and not changed

- **The grade** is one set of constants — `(8, 20, 46)` in the shadows, a 16%
  duotone blend, contrast 1.08, colour 1.14 — applied by name to *The Secret
  Place* in its own docstring. On the morning channel it tints a sunrise navy.
  Making it per channel is the same job the thumbnail pack already had done
  (`shorts_poster._GRADES`, ten grades), and it would move the same figure: frames
  whose colour is the channel's own, **0 of 10 → 10 of 10**. It is a six-minute
  decision, so it is the owner's.
- **The score** is one chord progression for the entire network, Shorts included —
  `build_prayer_music_score()` says it is "the exact Shorts background music
  score". Every video on every channel loops Am–F–C–G–Am–Dm–F–E. A second
  progression per daypart would move "distinct progressions in the network: 1 →
  N", and it is one of the cheapest differentiations left — but it is a sound
  decision on a channel whose voice is permanently locked.

## 4. The honest limits of this reading

- **How many live videos carry the old corner.** At most 118 (the published
  long-forms on the nine channels). The receipts give channel and date but not
  which renderer drew which frame; the approved path has been the only one on main
  since 31 October, and the earliest published long-form is dated 3 November, so
  the true number is between "all of them" and "all since the path took over".
  Nothing here can narrow it further.
- **Whether it matters to a viewer.** No thumbnail CTR, no retention curve, no
  per-second drop-off exists in `content/analytics/`. A wrong name in the corner
  is a fact about the file, not a measured effect.
- **Whether the fix reaches a video twice.** It does not: a re-run of an
  already-published job returns early (`already_published`), so no live video is
  silently re-rendered.

## Owner-only, and one next step

- **Owner-only:** the grade, the score, and whether any of the 118 is worth
  deleting and re-uploading to shed the wrong corner. This document does not
  recommend the last one: deleting a published video loses its views, its
  comments and its place in the algorithm, which is a larger loss than a corner.
- **One next step:** the frame attached to this change was rendered by hand. Render
  one real job per channel — `set-thumbnail.yml` gives a thumbnail, not footage, so
  this means one `produce` dry-run per channel — and look at ten frames side by
  side: ten names will be right, and ten navy grades will still not be.
