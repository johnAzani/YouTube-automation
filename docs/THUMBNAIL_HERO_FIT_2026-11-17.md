# The clamp certified a box nothing draws into

17 November 2026. Times are Nigeria time (WAT, UTC+1) unless marked UTC.

Third reading of the day, and the smallest thing yet: two functions disagree about
whether a line of text fits, and the loser was silent. Every figure below was
measured from this repository's own files.

## The short answer

- **The guarantee was about the wrong rectangle.** `pipeline/gemini_brain.py`
  (`_clamp_thumb_text_for_ctr`, line 252) promises to "guarantee `thumb_text` fits
  the 660px CTR hero box at >= 105px". It measured every authored line against
  `(86, 76, 746, 568)` — **660 x 492 px**. No thumbnail concept draws into that
  box. The frame the pipeline uploads draws into `(86, 84, 690, 470)` — **604 x 386
  px**, 56 px narrower and 106 px shorter.
- **Six of the 202 authored lines sit exactly on the phantom floor.** They measure
  **105 px** in the clamp's box, which is its threshold, and **96 px** in the real
  one, which is `MIN_HERO_PX` — and `_layout`'s size search ran `range(300, 95, -5)`,
  which stops at **100 px**, so 96-99 px were never tried. Every one of those
  lines fell through to the last-resort branch.
- **The last-resort branch took the first three words.** `lines = hero.split()[:3]`.
  So three published thumbnails are missing a word:

  | Job | Authored line | What the frame drew |
  |---|---|---|
  | `0037` The Morning Altar | `YOUR MERCY THIS MORNING` | `YOUR MERCY THIS` |
  | `0047` The Midday Watch | `COMMIT YOUR WORK AT NOON` | `COMMIT YOUR WORK` |
  | `0007` The Secret Place | `THE EXCHANGE PRESSED UNDO` | `THE EXCHANGE PRESSED` |

  The lost word is the daypart in two of them ("MORNING", "NOON") and the payload in
  the third ("UNDO" — the line means nothing without it). The gold accent falls on
  the last line, so those frames also ended on the wrong word in gold.
- **The report certified it.** For job `0047` the pack wrote
  `{"hero": "COMMIT YOUR WORK AT NOON", "words": 5, "lines": 3, "notes": []}` —
  `words` counted `len(active.hero.split())`, the input, not the three words the
  frame carried. Nothing downstream could disagree.
- **Four tests enforced the phantom box**, and one of them
  (`tests/test_thumbnail_ctr.py`, "fits cleanly without dropping words") already
  asserted *"dropped words in {lines} vs {hero}"* — against `(86, 76, 746, 568)`,
  where nothing dropped.

## The measurement, before and after

Run over all 202 faith jobs that carry a `thumb_text` (published and queued), via
the pack's own `_layout`:

| | Before | After |
|---|---:|---:|
| Lines that hit the 96 px floor | 7 | 7 |
| Lines that lose a word on the frame | **3** | **0** |
| Lines whose report says more words than it drew | **3** | **0** |
| Median hero size | 135 px | 135 px |
| Largest hero | 205 px | 205 px |

Only those seven frames change, and only on a re-render: nothing re-renders
automatically, and no live thumbnail was touched.

## What changed

- `pipeline/thumbnail_ctr.py` gains **`HERO_TEXT_BOX = (86, 84, 690, 470)`** — the
  narrowest, shortest text box of the three concepts — and **`hero_fit(hero)`**,
  returning `(px, dropped_words)`. One function for every caller that needs to say
  "this line fits".
- `_layout` searches `(*range(300, MIN_HERO_PX, -5), MIN_HERO_PX)`, so 96 px is
  reachable; the last-resort branch wraps inside the box (allowing four lines when
  the 386 px height holds them) instead of taking three words, and a word too wide
  for the box at the floor is dropped rather than allowed to spill into the art.
- `render_ctr` reports **the words it drew**, and appends `hero drew N of M words`
  to `notes` when any were lost — so `report.json` can no longer certify a frame it
  does not match.
- `gemini_brain._clamp_thumb_text_for_ctr` measures with `ctr.hero_fit` against
  `ctr.HERO_TEXT_BOX` and accepts a line only when every word is drawn at
  `>= MIN_HERO_PX`. Its docstring now says what it actually guarantees.
- The four tests now measure the real box; a corpus test reads **every** authored
  line in `content/published/` and `content/queue/` and fails if any would lose a
  word (195 scripts measured today).

## What this does not prove, and what is the owner's

- **Not proven:** that 96 px is comfortable at 168 px in a phone feed. The pack's
  own numbers for those frames are contrast 11.1:1 and 12% bright mass, both inside
  the published thresholds, but "legible" is a viewer question this sandbox cannot
  answer.
- **Not changed:** whether those seven lines should instead be cut shorter at
  authoring time (four words at 135 px rather than five at 96 px). The clamp now
  prefers keeping the model's whole line when it draws; a designer may prefer the
  opposite, and that is a policy decision, not a bug.
- **Owner-only:** re-rendering the three live frames and applying them with
  `thumbnails.set` costs **150 quota units** (3 x 50) against the 200-a-day limit
  in `docs/FAST_TRACK_4000_WATCH_HOURS.md`. `_refresh_live_thumbnail` will do it by
  itself if any of those three jobs is ever re-run; setting them now is a choice,
  not a necessity.

**One next step:** run `.github/workflows/set-thumbnail.yml` with `dry_run` on for
job `0047` and look at the four frames, because a rule that says "every word is
drawn" is worth one human look before it is trusted on 202 jobs.
