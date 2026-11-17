# The poster is the channel's. The frames are not.

17 November 2026. Times are Nigeria time (WAT, UTC+1) unless marked UTC.

Sixth reading of the day, one layer under the HUD. The last one ended "ten names
will be right, and ten navy grades will still not be". This asks what that
actually means in pixels and in hertz: **which surfaces carry a channel's own
colour and its own music, how far each one pushes, and what decides a frame when
nothing does.**

## The short answer

- **Two still surfaces carry the channel. Nothing that moves does.** The 16:9
  thumbnail reads `Brand.ctr_grade` and the 9:16 Short poster reads
  `shorts_poster.grade_for(channel)`; both give **ten distinct grades across ten
  channels**, and they agree with each other **10 of 10**. The frames underneath
  them carry the channel **0 of 10**.
- **The still is pushed five times harder than the film.** The poster's night ramp
  is **78% duotone**, brightness **0.62**, plus a **45%** navy tint. The video's
  `grade_sanctuary` is **16% duotone** and a shadow tint. On the same photograph
  the poster a channel ships and the video it ships are a median **ΔE 24.7**
  apart (min 18.2 on the noon channel, max 32.9 on the hearth channel): a viewer
  who clicks a poster gets a different palette.
- **A Short's colour is decided by its filename.** `tools/shorts.prep_plate()`
  grades a plate `grade_sanctuary` when the file name contains `prayer` or
  `psalm`, and `grade_blue` otherwise. The scene files are named after the
  Short's own key, so the rule reads "a Short whose key contains psalm or prayer
  wears the night channel's navy". **949 of 2,228 scenes (43%)** hit it, and
  every clip is `grade_blue` whatever the channel.
- **The music's "key" is a file name.** `generate_score(key, …)` uses `key` only
  to name the wav. Two scores asked for under different keys, durations, cuts,
  hushes and swells produced **byte-identical files** (10,584,044 bytes, sha256
  `820ad81a…`): one chord progression, one set of seeds, one heartbeat, for all
  ten channels and both formats.
- **The chime is in no video.** `pipeline/sonic_branding.inject_sonic_branding()`
  — the 2.5 s 528 Hz intro and 3.5 s 432 Hz outro that `PLAN.md` §12.4 says are
  injected into video and podcast intros and outros — has **no caller outside
  `tests/`**. The sleep-audio smoother (`pipeline/audio_smoother.py`) is reached
  only by `scripts/build_sleep_compilation.py`, which **no workflow runs** and
  which has left **no published receipt**.

## 1. Which surface carries the channel

| Surface | Decided by | Distinct grades | Carries the channel |
|---|---|---|---|
| 16:9 CTR thumbnail | `Brand.ctr_grade` (`pipeline/channel_capabilities.py`) | 10 | **yes** |
| 9:16 Short poster | `shorts_poster.grade_for(channel_id)` → `_GRADES` | 10 | **yes** |
| 9:16 Short frames, photograph | `prep_plate()`: `prayer`/`psalm` in the file name → `grade_sanctuary`, else `grade_blue` | 2, chosen by key string | **no** |
| 9:16 Short frames, video clip | `read_video_plate` → `grade_blue` always | 1 | **no** |
| 16:9 long-form frames | `prayer_visuals.py:209` → `grade_sanctuary` always | 1 | **no** |
| Long-form and Short music | `tools/score.py:PROG` | 1 | **no** |
| Encode | crf 20 + 4.5 Mbps cap (Shorts) / crf 21 (long-form) | 2 | **no** |

Ten channels, two of them named after a daypart each (`night`, `dawn`, `noon`,
`midnight`, `hearth`, `balm`, `harvest`, `fortress`, `garden`, `pathway`). The
two still surfaces agree on all ten; the motion agrees with neither.

## 2. How far apart a channel's poster and its film are

The same photograph (`assets/branding/short-prayer-scene-01.jpg`, cropped
identically) through the poster's ramp and through each video path; mean ΔE\*ab
per pixel, and the poster's mean L\*:

| Channel | Poster grade | Poster L\* | ΔE poster → long-form frame | ΔE poster → Short clip grade | Short scenes graded sanctuary / blue |
|---|---|---|---|---|---|
| The Secret Place | night | 10.8 | 22.4 | 26.0 | 207 / 107 (66%) |
| prayer2 | dawn | 19.0 | 24.4 | 36.9 | 176 / 160 (52%) |
| prayer3 | noon | 24.9 | **18.2** | 34.1 | 107 / 152 (41%) |
| prayer4 | midnight | 8.7 | 24.9 | 28.7 | 62 / 166 (27%) |
| prayer5 | hearth | 15.4 | **32.9** | 47.7 | 46 / 140 (25%) |
| prayer6 | balm | 18.9 | 20.3 | 33.0 | 49 / 151 (24%) |
| prayer7 | harvest | 15.4 | 31.3 | 43.7 | 57 / 150 (28%) |
| prayer8 | fortress | 13.9 | 22.6 | 26.2 | 87 / 79 (52%) |
| prayer9 | garden | 19.6 | 31.3 | 46.6 | 111 / 60 (65%) |
| prayer10 | pathway | 19.7 | 25.1 | 39.3 | 47 / 114 (29%) |

ΔE above ~5 is a visible difference; 24.7 is a different palette. The poster L\*
range across the network is **16.2 L\*** (8.7 for midnight to 24.9 for noon) —
the stills really are ten different rooms. The frames are one room, and it is the
night one.

The Short-clip column is the worst case, because every clip is `grade_blue`: no
channel's poster is within ΔE 26 of the grade its own footage gets when the scene
is a clip rather than a photograph.

## 3. What actually decides a Short's colour

```python
fn = os.path.basename(str(path)).lower()
if 'prayer' in fn or 'psalm' in fn:
    return grade_sanctuary(sharpened)
return grade_blue(sharpened, tint_warm=tint_warm, keep_crimson=keep_red)
```

`assets/`/`image-search/` hold no Short scene photographs in the repository — the
2,228 `img` names in `content/shorts-scripts/` are fetched at render time, and
the names are the spec's own: `short-psalm91-scene-01.jpg`,
`short-1peter5v7-scene-01.jpg`. So the test is not about what the picture shows.
A Psalm 91 Short gets the sanctuary grade on any channel and a 1 Peter 5:7 Short
gets the documentary blue on any channel, including on The Secret Place, whose
poster is navy and whose film is then blue.

Counted over every spec: **336 specs, 2,228 scenes, 949 sanctuary (43%), 1,279
blue (57%)** — and the split per channel is in the table above, from 24% on the
balm channel to 66% on the first channel, following the passages that channel
happens to have written rather than the colour it lives in.

## 4. What the video grade actually does to a photograph

On a dark devotional plate (`short-prayer-scene-01.jpg`): **63%** of pixels sit in
the shadow tint's zone (luma < 65). Mean RGB goes **(51.8, 64.1, 77.5) →
(44.3, 60.1, 85.2)** — red down 7.5, blue up 7.7 — and mean L\*ab goes
**(33.4, +0.3, −12.9) → (31.3, +3.1, −20.4)**. `grade_blue`, the clip and
documentary grade, goes much further: **L\*ab (26.0, +11.8, −38.1)** and mean RGB
(18.7, 50.8, 106.5).

So `grade_sanctuary` is a soft push — a shadow tint, contrast 1.08, colour 1.14, a
16% duotone. The poster path applies the same family of idea at **78% duotone,
brightness 0.62 and a 45% tint**. Same noun, two very different verbs.

## 5. The score: one progression, one heartbeat

`tools/score.py` builds the bed from a single constant:

```
PROG = Am, F, C(low), G, Am, Dm, F, E   # A natural minor, dominant E
```

with:

| Part | Setting |
|---|---|
| Pads | two `_pad_bed` passes, detune 0.9992 (seed 11) and 1.0008 (seed 23) |
| Chords | `round(total / 56)` cycles of `PROG` plus the tonic; one loop of 8 under 125 s |
| Sub | 55 Hz (A1) + 82.41 Hz (E2), amplitude-modulated at 0.11 Hz |
| Heartbeat | a 56/41 Hz thump every **1.18 s** (50.8 BPM) |
| Wind | band-limited noise, seed 5, 320 Hz |
| Swells | at scene cuts and big hits, ±1.6 s / +2.6 s |
| Hushes | at "amen" and "selah" only, depth 0.55, lead 0.45 s |
| Bed peak | 0.30 |
| Mix | volume 0.58, plus `voice_master.MUSIC_LIFT_DB = 3.0` |
| Voice | −15 LUFS, finished mix −14.9 LUFS, peak −1.5 dBFS |

Worked out with the real function: a 6-minute video gets **49 chords of 7.35 s
(6.1 full loops) and 304 heartbeats**; 20 minutes gets 169 chords and 1,016
beats; an hour gets 513 chords and 3,050 beats. The chord changes are at the same
intervals in every video on every channel.

The `key` argument names the file and nothing else. Asked for
`prayer-longform-ch1` and `sunrise-short-ch2` — different names, same 60 s
duration, same cuts, hushes and swells — `generate_score` wrote two files of
**10,584,044 bytes** with the same sha256 (`820ad81a47f5f025…`).

## 6. Two audio modules that are not on any publish path

- **The chime.** `pipeline/sonic_branding.inject_sonic_branding()` synthesises a
  2.5 s 528 Hz intro bell and a 3.5 s 432 Hz outro bell and concatenates them
  around an audio file. Grepped over the repository, its only importers are
  `tests/test_sonic_branding.py` and `pipeline/sacred_audio.py`; `sacred_audio`
  is imported only by `sonic_branding`. `PLAN.md` §12.4 states it "injects a
  2.5s 528 Hz Solfeggio acoustic bell strike into video/podcast intros and a 3.5s
  432 Hz peace fade into outros". **No published video carries one.**
- **The smoother.** `pipeline/audio_smoother.py` (40 Hz high-pass, 6.5 kHz
  low-pass, two-pass `loudnorm` at −16 LUFS / −1.5 dBTP) is called from
  `pipeline/sleep_compilations.py`, which is called from
  `scripts/build_sleep_compilation.py`. No workflow in `.github/workflows/` runs
  that script and no receipt in `content/published/` is a compilation. The live
  loudness work is `pipeline/voice_master.py` (−15 LUFS voice, −14.9 LUFS mix),
  which is on both render paths.

Neither module is broken; both are unconnected. The two `PLAN.md` entries are
corrected to say so, because a reader — including the earlier readings today —
would otherwise take the chime for a live sound.

## 7. The two encodes

| | Long-form | Shorts |
|---|---|---|
| Size / rate | 1280×720, 24 fps | 720×1280, 24 fps |
| Codec | libx264 high, preset fast, **crf 21** | libx264 high, preset fast, **crf 20**, maxrate 4500k, bufsize 9000k |
| Colour | yuv420p, bt709 primaries/trc, tv range | the same |
| Audio | AAC 48 kHz, 192k | the same |
| Container | `+faststart` | the same |

Two recipes, one per format, identical for all ten channels. Nothing here is
wrong; it is one more layer with no channel in it.

## 8. Where a poster actually reached the viewer

Published Shorts carry the grade in their receipt only when the custom thumbnail
was confirmed applied (`short_release.py:903`). Of **247 published Shorts**,
**106 (43%)** carry `thumbnail_channel_grade`, and **all 106 match their
channel's current grade** — no drift since the poster pack landed on 7 November.
The other 141: **87** are `thumbnail_pending` on `HttpError: The authenticated
user doesn't have permissions to upload and set custom thumbnails` (an OAuth
scope on the owner's side, already documented in `docs/THUMBNAIL_RECOVERY.md`),
**10** posters had their text leave the UI safe zone and were refused, **2** are
unverified recoveries, **1** is deferred processing, and **41** predate the
poster.

So on those 141 Shorts the only colour identity that reached the viewer is the
one decided by the filename rule in §3.

## Measured, changed, unproven, owner-only

**Measured.** Ten channels; two still surfaces with ten distinct grades that
agree 10 of 10; zero motion surfaces with the channel's colour; median ΔE 24.7
between a channel's poster and its film; 949 of 2,228 Short scenes graded by a
`psalm`/`prayer` substring; one `PROG`, one seed set, one 1.18 s heartbeat; two
byte-identical score files from two different keys; zero callers for the chime
outside tests; zero workflows running the sleep-compilation script.

**Changed (documentation and one measurement only — no render changes):**

| Change | Figure it moves | Where it is read |
|---|---|---|
| `shorts_poster.plate_grade_name()` — the filename rule, named once instead of inline | makes "which grade a scene gets" readable: **2,228 scenes, 949 sanctuary** | `pipeline/shorts_poster.py`; `tools/shorts.prep_plate()` now calls it |
| `scripts/channel_protection.py` gains a **"Grades and score"** section: each channel's thumbnail grade, poster grade and Short scenes graded sanctuary, plus the one video grade and the one score | frames that wear the channel's own grade: **0 of 10**, visible daily | `python -m scripts.channel_protection` |
| `_GRADES`'s comment said "one plate, three dayparts" over ten ramps; `channel_capabilities` listed "(night / dawn / noon)" | the count a reader is told: **3 → 10** | both files |
| `PLAN.md` §11.3 and §12.4 | claim "injected into intros and outros" → says built, not wired | `PLAN.md` |
| `grade_sanctuary`'s docstring | says whose grade it is and that every channel wears it | `tools/shorts.py` |

Nothing visible changes: no grade, palette, plate, level, key or encode was
altered. The poster and the film are as far apart tomorrow as they were today.

**Unproven.** That a poster and a film in different palettes costs a click, or
that one progression over ten channels costs a minute of listening. There is no
retention curve, no per-second drop-off and no per-video CTR anywhere in
`content/analytics/`, and YouTube's Test & Compare is Studio-only. Both are
statements about sameness, not about effect.

**Owner-only.** Making the video grade the channel's (the ramps already exist;
the change is a `channel` in `render()` and one in `prep_plate`); giving the
score a second and third progression per daypart; switching on the chime; and
the OAuth scope behind the 87 pending thumbnails. Each changes how every future
video looks or sounds, which is a design decision and not a correction.

**One next step.** Render one real long-form and one real Short for two
opposite channels — the midnight channel and the noon one — and put the four
frames beside their four posters. If the film is still the same room in both, the
cheapest correction is to pass the poster's own ramp name into `grade_sanctuary`
and read the same ΔE table again: the figure to move is **frames whose colour is
the channel's own, 0 of 10**.
