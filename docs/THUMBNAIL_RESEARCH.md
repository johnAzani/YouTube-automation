# Thumbnail research → implemented constraints

The thumbnail is the highest-leverage CTR decision on the upload, and CTR feeds
the recommendation system. This document records what the research actually says,
what was wrong with the published Psalm 121 thumbnail, and the exact numbers now
enforced in `pipeline/thumbnail_studio.py` (each one has a test in
`tests/test_thumbnail_studio.py`).

---

## 1. How a thumbnail is actually seen

| Surface | Size shown | Implication |
| --- | --- | --- |
| Mobile search | ~120×67 – 168×94 px | The hardest surface; 3 words maximum |
| Mobile home feed | ~178×100 px | Default viewing context |
| Recommended sidebar | ~168×94 px | Where suggested traffic is won |
| Desktop home/search | ~320×180 – 360×202 px | Comfortable |
| Channel page / featured | up to 1280×720 px | Where quality is judged |

70–75% of YouTube viewing is mobile, so the phone rendering is the design target,
not the 1280×720 file. Specs are unchanged: 1280×720, 16:9, <2 MB, JPG/PNG,
sRGB. The API's `thumbnails.set` limit was raised from 2 MB to 50 MB in September
2026, but the 2 MB ceiling remains the safe target for every surface.

**What the eye actually resolves at 168 px:** one focal shape, one to three words
of very bold type, and a strong value contrast. Anything else is texture.

## 2. The variables, ranked by measured lift

| Factor | Effect | Source |
| --- | --- | --- |
| High vs low contrast | **+38%** (6.5% vs 4.7% CTR, ≥7:1 vs <4:1) | aggregated A/B studies, 3,200+ thumbnails |
| Standing out from the neighbouring feed | ~+30% | same |
| Expressive focal subject (face or object) | +25–33% | same; faith/music niches favour calm over shock |
| Short text (0–3 words) | +15%; 6+ words −31% | multiple |
| Warm vs cool grade | +5–15% (warm wins on mobile) | song/contemplative tests |

Contrast matters more than hue. White or gold type on a deep navy ground is the
best-tested pairing for contemplative, sleep and scripture content; muted or
desaturated palettes tested ~47% worse than vivid ones.

## 3. Typography

* Primary headline: **150–200 px at 1280×720** in the aggressive school; the
  conservative floor quoted by several 2026 guides is **60–80 px** for anything
  that must read on a phone. Our floor: **96 px font size**, which lands the cap
  height near 70 px and the line at ~13% of frame height.
* One bold sans-serif family, two weights at most. Thin, light, script or
  decorative faces dissolve at feed size.
* 3–5 words, and **never repeat the video title** — title and thumbnail are a
  pair, not clones. For a browse feed, 0–3 words is stronger.
* 4–8 px outline or directional shadow so type survives any background.
* All-caps works for 1–3 word lockups (more visual weight); sentence case reads
  better for longer phrases.

## 4. Composition

* One focal element occupying **40–60%** of the frame; **30–40%** negative space.
* Subject at a rule-of-thirds intersection; text in the top third or left side,
  opposite the focal subject; a Z-pattern flow (most important top-left).
* Keep critical content inside the central **~80%** (≈1024×576) because mobile
  views crop the edges and some placements square-crop.
* **Never** put text or logos in the bottom-right (duration badge), along the
  bottom strip (progress bar, mobile title overlay), or over a face.
* Text should cover at most ~15% of the thumbnail *area* — big, but not a wall.
* 2026 trend: simpler wins. One subject, two or three colours, three to five
  words. Maximalist collages cooled off.

## 5. Testing

YouTube's native **Test & Compare** takes up to **3** thumbnails (and up to 3
titles), splits traffic randomly, and picks the winner by **watch-time share**,
not CTR — so an honest thumbnail beats a clickbait one. It needs days to weeks
and thousands of impressions to call a winner; "Inconclusive" means not enough
data, and the first upload wins by default. Variations must be genuinely
different concepts, not recolours.

---

## 6. What the published Psalm 121 thumbnail got wrong

Measured from the actual output (`pipeline/thumbnail.py::render_studio_thumbnail`):

1. **Five text elements** — kicker pill, two-line hero, gold rule, subtitle,
   tag pill. At 168 px the kicker and tag became unreadable mush.
2. **No focal art.** A flat gradient with a rounded card outline; the only
   "image" was empty space. ~40% of the frame was unused.
3. **Hero locked at 82 px** in a two-line lockup inside a 820×484 card, so the
   type occupied ~12% of the frame instead of ~25–35%.
4. **Hard-coded strings** — "PRAYER BEFORE SLEEP · PSALM 91" and
   "16 VERSES · FULL SCRIPTURE MEDITATION" appeared on a Psalm 121 video.
5. **No validation.** Nothing checked contrast, safe zones or mobile legibility,
   so a frame that cannot be read on a phone shipped by default.

Measured "legible ink" (bright type + focal art surviving downscale):
**old 5.6% of frame → new 14.4%**, with hero type at 134 px.

## 7. The implemented rules

`pipeline/thumbnail_studio.py`:

| Constant | Value | Why |
| --- | --- | --- |
| `CANVAS` | 1280×720 | YouTube spec |
| `MIN_HERO_PX` | 96 | mobile-legible floor (cap height ≈ 70 px) |
| `MIN_CONTRAST` | 7.0 | WCAG AAA large text; the +38% A/B sweet spot |
| `MAX_HERO_WORDS` | 5 | 3–5 reads at feed size; words are never silently dropped |
| `MAX_LINES` | 3 | more lines means smaller type |
| `SAFE_BOX` | (96, 54) – (1152, 594) | central 80%, clear of the bottom overlay |
| `DURATION_BADGE_BOX` | (1040, 600) – (1280, 720) | must stay quiet; verified by variance |

Design decisions that follow directly from the research:

* **Painted focal art** — moon over still water, starfield, dawn light — so there
  is always a subject at 168 px, instead of depending on whichever stock frame
  happened to be fetched.
* **Hero left, art right** (rule of thirds); the text box is computed to stop
  short of the moon, so type never crosses the disc.
* **Three variants** for Test & Compare: `main` (moon over water, hero left),
  `b` (starfield and light break), `c` (centred dawn lockup below the art).
* **Automatic contrast repair**: if measured text-vs-background contrast falls
  under 7:1, a feathered local scrim is added and the contrast re-measured.
* **Filmic finishing** — shadow crush, cool/warm split tone, grain, unsharp mask
  — so the frame reads as photographed rather than flat vector art.
* **Self-reporting**: every render returns hero size, word count, contrast, safe
  zone and badge-zone checks, file size; `prayer_pipeline` writes `report.json`
  and a 168 px mobile preview next to each thumbnail.

## 8. Deliberate deviation from the research

The style guide (gold type, glass HUD, sapphire) is locked by the owner and is
carried into the thumbnail's palette and type. We keep gold as the **accent on
the final line only** and white for the rest, because gold-on-navy at large sizes
reads well but white carries more contrast (measured 11.5:1 in the shipped
variant). Word count sits at 5 for `THE LORD IS YOUR KEEPER` rather than 3: the
phrase is the video's own hook, and at 134 px it still resolves at 168 px — the
mobile preview is committed alongside the frame so the trade-off is visible.

## 9. Sources

- thumbmagic.co — *YouTube Thumbnail Design Principles: 2026 Conversion Guide*
- 1of10.com — *YouTube Thumbnail Design: 9 Tips for High-CTR Thumbnails*
- thumbn.so — *How to Make a YouTube Thumbnail That Gets Clicks (2026 Playbook)*
- notelm.ai — *Best Fonts & Text for YouTube Thumbnails (2026 Guide)*
- thumbnailcreator.com — *Ultimate Guide to Thumbnail Typography* / *Text Placement*
- jwtoolbox.com — *YouTube Thumbnail Size Guide 2026* (surface sizes, safe zones)
- skysnail.io — *YouTube Thumbnail Size, Specs, and Safe Zones: Definitive 2026*
- earnifyhub.com — *YouTube Thumbnail Design 2026: What Gets Clicked*
- mer.vin — *YouTube Thumbnail CTR for Song Videos: what 3,200 thumbnails teach us*
  (contrast/colour/layout tables for contemplative and prayer content)
- thumbmagic.co / thumbnailai.pro / creatorhandbook.net — Test & Compare
  mechanics: 3 variants, watch-time-share winner, inconclusive behaviour
- Google for Developers, YouTube Data API revision history (Sept 2026):
  `thumbnails.set` maximum raised to 50 MB; quota cost 50 units

---

## 10. Hero word-budget study (1 November 2026)

`docs/media/thumbnails/hero-word-budget-study.png` compares six hero options at
both sizes: the 1280×720 frame and the same file rendered at 168 px — the phone
feed. All six were produced by `pipeline/thumbnail_studio.py`, so every column
satisfies the contrast, safe-zone and legibility floors.

| Option | Hero | Variant | Hero px | Lines | Contrast | KiB |
| --- | --- | --- | --- | --- | --- | --- |
| A | YOUR KEEPER | main | 176 | 2 | 10.7:1 | 112 |
| B | HE NEVER SLEEPS | main | 140 | 2 | 10.1:1 | 108 |
| C | THE LORD IS YOUR KEEPER | main | 134 | 3 | 11.5:1 | 121 |
| D | YOUR KEEPER | b | 182 | 2 | 11.9:1 | 108 |
| E | HE NEVER SLEEPS | b | 140 | 2 | 11.8:1 | 103 |
| F | THE LORD IS YOUR KEEPER | b | 134 | 3 | 11.8:1 | 115 |

**Reading of the study**

- Dropping from five words to two buys **+42 px of hero type** (134 → 176/182)
  and removes a line. At 168 px that is the difference between a phrase that has
  to be read and one that is recognised instantly.
- `HE NEVER SLEEPS` is the strongest *hook*: it quotes the video's own verse 4,
  creates curiosity, and is not the title repeated. `YOUR KEEPER` is the most
  legible but is a label rather than a hook.
- The `b` starfield variant consistently beats `main` on measured contrast
  (11.8–11.9:1 vs 10.1–11.5:1) and is slightly smaller in file size; `main` has
  the stronger scene (moon over water).
- Recommendation: **B or E for the live video** — three words, verse-accurate,
  instant at feed size. Keep C/F only if brand recall of the full phrase matters
  more than feed legibility.

This is a legibility and typography comparison, not a CTR result. Only YouTube's
Test & Compare settles which wins, and it decides on watch-time share.
