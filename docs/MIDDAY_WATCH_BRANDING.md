# The Midday Watch | Noonday Prayer & Scripture
## Complete Faceless Channel Branding & Identity Kit — Channel 3 (`prayer3`)

**Primary Brand Name:** **The Midday Watch | Noonday Prayer**
**Handle (claimed 2026-11-06):** `@TheMiddayWatch` — the first choice, no fallback needed
**Fallbacks, unused:** `@TheMiddayWatchDaily`, `@MiddayWatchPrayer`, `@NoondayWatch`
**Core Scripture Foundation:** *Psalm 55:17 — "Evening, and morning, and at noon, will I pray, and cry aloud: and he shall hear my voice." (KJV)*
**Channel Format:** 100% faceless Christian **noonday** prayer & midday devotional studio.
**Internal channel id:** `prayer3` (secret prefix `PRAYER3_`, see `pipeline/channels.py`)
**Status:** channel **live** on 2026-11-06 — name, handle, avatar and banner are on
`@TheMiddayWatch`. Publishing is **not provisioned**: no Google Cloud project, no
`PRAYER3_*` secrets, `provisioned=False` in `pipeline/channels.py`. See
`docs/THIRD_CHANNEL_SETUP.md`.

> ⚠️ A handle cannot be reserved from this repository. Claim the first available
> in YouTube Studio at channel creation, then update `pipeline/channels.py`,
> `pipeline/channel_capabilities.py` and this file if you took a fallback.

---

## 1. Why this channel is deliberately not a copy

Three channels, three hours of the day, one code path:

| Channel | Owns | Scripture |
|---|---|---|
| The Secret Place (`secret-place`) | the **night** — bedtime prayer, sleep, protection | Psalm 91, Psalm 4:8 |
| The Morning Altar (`prayer2`) | the **sunrise** — starting the day, declarations, favour | Psalm 5:3, Lamentations 3:22–23 |
| **The Midday Watch (`prayer3`)** | **the middle of the day** — patience under pressure, work, integrity, strength for the afternoon | **Psalm 55:17, Psalm 91:6** |

That separation is a policy safeguard, not decoration. YouTube's reused-content
review looks across a creator's channels, and the repository enforces the rule
structurally: scripts declare their owner in frontmatter (`channel: prayer3`), the
pipeline refuses a cross-channel run, every channel's brand **forbids** the other
two by name and handle, and a leaked phrase fails the build.

### One-Line Channel Tagline
> *"Pause and pray at noon."*

### Core Content Pillars
1. **The Middle-Hour Pause** (Psalm 55:17, Psalm 63:1) — stepping out of the day's noise for six minutes.
2. **The Noonday Shadow** (Psalm 91:6, Isaiah 58:10) — the dangers that arrive when we are least watchful: sudden news, heat, haste.
3. **The Work of the Hands** (Proverbs 16:3, Psalm 37:5) — committing the afternoon's labour, decisions and outcomes.
4. **Strength for What Remains** (Isaiah 40:31, Psalm 119:114) — renewal that is given, not summoned.
5. **Noonday Shorts** — 30–60 second midday declarations, keys namespaced `short-midday…` so they can never collide with, or be dressed in, another channel's branding.

### Voice & Editorial Identity
- Locked production voice (**Gemini `Charon`**) and the same $0.00 stack, on its **own** GCP project, Gemini project, quota pools and secrets — never borrowed.
- Editorial studio persona only; zero personal creator names, zero prosperity claims.
- The register is a person who has stepped away from a demanding day — unhurried, steady, unglamorous. Not a morning person starting out, not a night person winding down.

---

## 2. Channel "About" Description (copy-paste, under 1,000 characters)

```text
Welcome to The Midday Watch — a pause in the middle of the day, at the altar of God.

At noon the day is loudest: work, decisions, heat, and the weight of everything still to come. Psalm 55:17 says, "Evening, and morning, and at noon, will I pray, and cry aloud: and he shall hear my voice." This channel exists for that middle hour.

Every video is a short, unhurried prayer of five to six minutes — Scripture read in the King James Version, exposition drawn from Charles Spurgeon and Matthew Henry, and room to breathe before you step back into the day.

Pray with us for strength that is given rather than summoned, for integrity in the unglamorous hours, for a clean heart when no one is watching, and for peace over the afternoon that remains.

Faceless, Scripture-first, daily. Type Amen to agree.
```

## 3. Channel Keywords (Studio → Settings → Channel → Basic info → Keywords)

```text
Midday Prayer, Noon Prayer, Afternoon Prayer, Prayer at Noon, Midday Devotional, Daily Prayer, Prayer for Strength, Prayer for Work, Prayer for Guidance, Psalm 55, Psalm 91, KJV Prayer, Christian Prayer, Scripture Meditation, The Midday Watch
```

## 4. Visual Identity & Brand Assets

| Asset | Dimensions | Workspace File | Where it goes in YouTube Studio |
|---|---|---|---|
| Profile picture / avatar | `800 × 800 px` (PNG) | `docs/media/midday-watch-avatar.png` | Customization → Branding → Picture |
| Banner | `2560 × 1440 px` (PNG; type inside `1235 × 338 px`, scenery inside the band a phone shows) | `docs/media/midday-watch-banner.png` | Customization → Branding → Banner image |
| Video watermark | `150 × 150 px` (PNG, transparent) | `docs/media/midday-watch-watermark.png` | Customization → Branding → Video watermark (Entire video) |
| Thumbnail template | `1280 × 720 px` (PNG) | `docs/media/midday-watch-thumbnail-template.png` | Reference for the CTR system; not uploaded |
| Brand sheet | `1800 × 1760 px` (PNG) | `docs/media/midday-watch-brand-sheet.png` | Review/share: every asset and the palette on one page |
| Complete kit | `.zip` (~460 KB) | `docs/media/midday-watch-brand-assets.zip` | Download-and-hand-off: the four uploads + both docs + the sheet |

**Download everything:** `docs/media/midday-watch-brand-assets.zip` unpacks to
`midday-watch-brand-kit/` with a `START_HERE.txt`, the brand sheet, both
documents and the four images at full resolution. It is rebuilt by the generator
(`--kit`), and `tests/test_channel_brand_assets.py` fails if the archive ever
disagrees with the assets on disk — a stale kit is worse than none, because it
ships the wrong banner.

### Banner: the band a phone actually shows
The `1235 × 338` box is where the **type** has to fit; it is not the shape of the
window. Measured on a 1080 × 2400 Android phone against the live channel on
2026-11-06, the banner card renders `1005 × 295 px` = **3.41 : 1**, which is the
centre `2560 × 753` of the file — 415 px taller than the safe box. The first
upload followed the spec and still looked broken on the phone: the sun was sliced
by the top edge (a gold sliver in the rounded corner) and the watchtower rose out
of nothing as a black notch, because the horizon sat below the band entirely. The
sun and the tower are now laid out inside that band, and the ground is a gradient
from noon light at the horizon to furrow shadow at the foot of the frame.

**The Edit-channel preview is not the check** — it zoom-crops. Upload, then open
the channel on a phone.

The assets are **drawn in code**, not generated as pictures, because every one of
them carries type the viewer is meant to read — and generated imagery mangles
letterforms. Regenerate any time:

```bash
python tools/make_channel_brand_assets.py --channel midday-watch            # skips existing files
python tools/make_channel_brand_assets.py --channel midday-watch --sheet    # + the one-page sheet
python tools/make_channel_brand_assets.py --channel midday-watch --force    # redraw everything
python tools/make_channel_brand_assets.py --channel midday-watch --sheet --kit  # + sheet + download zip
```

Nothing is overwritten without `--force`, so approved art cannot be replaced by a
careless re-run.

### Colour Palette (noon: deep sky overhead, hard light on warm ground)

| Role | Name | Hex |
|---|---|---|
| Primary background | Zenith Blue | `#0d3350` |
| Secondary panel | Noon Sky | `#1c5d7a` |
| Headings, sun disc | High Sun | `#ffc247` |
| Secondary highlight | Warm Brass | `#e39a34` |
| Primary text | Ivory | `#fbf6ec` |
| Sub-headers, verse refs | Sand Haze | `#d9e6ea` |
| Silhouettes, scrims | Hard Shadow | `#0a1a26` |
| Sunlit field | Sunlit Field | `#b98b4e` |
| Field depth | Deep Furrow | `#74522e` |

Deliberately distinct from The Secret Place's midnight set and The Morning
Altar's pre-dawn navy: a viewer should never mistake one channel's tile for
another's in a subscription feed.

### Mark
A **high sun** over a **watchtower** on a warm field. The tower is the mark that
makes the name literal, and it appears in the avatar, the banner, the watermark
and every long-form thumbnail. There is no lettering in the avatar or the
watermark — at 48 px and 22 px, a wordmark is unreadable mush, while a tower and a
disc still read.

### Thumbnail System
- Warm noonday field along the bottom, deep blue sky above, high sun upper-right, tower bottom-right.
- Legibility scrim from ~36% height down, so 2–3 word declarations stay readable at 246 × 138 on a phone.
- Declaration in Inter-Black: **first word in High Sun**, remainder in Ivory (e.g. `PAUSE` / `AND PRAY`, `STEADY` / `IN THE STORM`).
- Verse line beneath in Warm Brass, small, tracked (`PSALM 55:17 · NOON`).
- Never reuse a Secret Place or Morning Altar thumbnail, title or script here.

## 5. Launch Checklist

- [x] Create the channel and claim the handle (§ top) — done 2026-11-06, `@TheMiddayWatch`, first choice
- [x] Upload avatar (`docs/media/midday-watch-avatar.png`) — done 2026-11-06
- [~] Upload banner (`docs/media/midday-watch-banner.png`) — uploaded 2026-11-06, **re-cut the same day** after the phone check above; re-upload this file
- [ ] Upload watermark (`docs/media/midday-watch-watermark.png`) — desktop Studio only
- [~] Name field is `The Midday Watch` (set 2026-11-06); the longer `The Midday Watch | Noonday Prayer` is optional, the tagline and Psalm 55:17 already sit in the banner
- [ ] Paste the About description (§2) and keywords (§3)
- [ ] Enable 2-step verification and custom thumbnails
- [ ] Create the **separate** GCP + Gemini projects and the six `PRAYER3_*` secrets — `docs/THIRD_CHANNEL_SETUP.md`
- [ ] Flip `provisioned=False` → `True` in `pipeline/channels.py`
- [ ] First authored script from roadmap id **0045** (Psalm 55:17) and its companion Short (`short-midday…`)
- [ ] First upload verified on `@TheMiddayWatch` — `PRAYER3_YOUTUBE_CHANNEL_ID` is what makes a wrong-token write impossible
