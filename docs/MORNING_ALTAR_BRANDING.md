# The Morning Altar | Daily Sunrise Prayer & Declarations
## Complete Faceless Channel Branding & Identity Kit — Channel 2 (`prayer2`)

**Primary Brand Name:** **The Morning Altar | Daily Sunrise Prayer**
**Handle (claimed 2026-11-04):** `@TheMorningAltarDaily` — https://www.youtube.com/@TheMorningAltarDaily
**Unclaimed fallbacks (not used):** `@MorningAltarPrayer`, `@MorningAltarDevotional`, `@MorningAltarPrayers`
**Core Scripture Foundation:** *Psalm 5:3 — "My voice shalt thou hear in the morning, O LORD; in the morning will I direct my prayer unto thee, and will look up." (KJV)*
**Channel Format:** 100% faceless Christian **morning** prayer, declaration & sunrise devotional studio.
**Internal channel id:** `prayer2` (secret prefix `PRAYER2_`, see `pipeline/channels.py`)

> ⚠️ Handles cannot be reserved from this repo. Claim the first available
> handle in YouTube Studio at channel creation, then update the registry
> (`pipeline/channels.py`), this doc, and `CHANNEL_HANDLE` usage if you had
> to take a fallback.

---

## 1. Why this channel is deliberately *not* a copy of The Secret Place

The Secret Place owns the **night**: bedtime prayer, sleep scripture, Psalm 91
protection. The Morning Altar owns the **sunrise**: starting the day, prayer
before work, morning declarations, favour and guidance for the hours ahead.

That separation is a policy safeguard, not just branding:

- YouTube's reused/repetitious-content review looks at patterns across a
  creator's channels. Two channels uploading the same (or near-same) videos
  is the classic trap.
- **Rule: a script belongs to one channel only.** Scripts declare their owner
  in frontmatter (`channel: prayer2`); the pipeline refuses cross-channel
  runs (`pipeline/run.py`), and a video published on one channel is never
  re-uploaded to the other.

### One-Line Channel Tagline
> *"Begin every sunrise at the altar."*

### Core Content Pillars
1. **Sunrise Prayers & Morning Declarations** (Psalm 5, Psalm 143:8, Lamentations 3:22–23, Mark 1:35).
2. **Prayer Before Work & Daily Guidance** (decisions, favour, protection on the road, God's leading — Psalm 5:8, Proverbs 3:5–6, Psalm 90:17).
3. **Morning Warfare & Blessing** (putting on the day: Ephesians 6, Psalm 5:12 favour shield, Numbers 6 blessing over family).
4. **Sunrise Shorts** (30–60 second first-light declarations). Shorts are a
   capability of *every* channel: manifests declare their channel, keys are
   namespaced (`short-morning…`), and the brand gate dresses them in this
   channel's title/tags/description. See `docs/CHANNEL_PARITY.md`.

### Voice & Editorial Identity
- Same locked production voice (**Gemini `Charon`**) and $0.00 stack, but its
  own GCP project, Gemini project, quota pools and secrets — see
  `docs/SECOND_CHANNEL_SETUP.md`.
- Editorial studio persona only; zero personal creator names (the persona
  invariant from The Secret Place applies unchanged).

---

## 2. Channel "About" Description (copy-paste, under 1,000 chars)

*YouTube Studio → Customization → Basic info → Description:*

```text
Welcome to The Morning Altar — begin every sunrise in the presence of God.

Before the day makes its demands, we lay our requests before the Lord: morning prayers, sunrise declarations, and scripture devotionals to send you into work, family and every decision under God's favour and shield.

🌅 WHAT WE SHARE:
• Psalm 5 Sunrise Prayers to start your day with God
• Morning Declarations of favour, guidance & protection
• Prayer Before Work and for daily decisions
• Blessing prayers over your family, home & journey

📖 "My voice shalt thou hear in the morning, O LORD; in the morning will I direct my prayer unto thee, and will look up." — Psalm 5:3

🔔 Subscribe and join us at the altar every morning. Need prayer? Leave your request in the comments — we pray over every name.
```

## 3. Channel Keywords (Studio → Settings → Channel → Basic info → Keywords)

```text
Morning Prayer, Prayer to Start Your Day, Psalm 5 Prayer, Sunrise Prayer, Morning Devotional, Daily Prayer, Morning Declarations, Prayer Before Work, Begin Your Day With God, Christian Morning Prayer, Prayer for Favour, Prayer for Guidance, Morning Blessing, KJV Prayer, The Morning Altar
```

## 4. Visual Identity & Brand Assets

| Asset | Dimensions | Workspace File | Where to Upload in YouTube Studio |
|---|---|---|---|
| Profile Picture / Avatar | `800 × 800 px` (PNG) | `docs/media/morning-altar-avatar.png` | Customization → Branding → Picture |
| Banner | `2560 × 1440 px` (PNG, safe area `1546 × 423 px`) | `docs/media/morning-altar-banner.png` | Customization → Branding → Banner image |
| Video Watermark | `150 × 150 px` (PNG, transparent) | `docs/media/morning-altar-watermark.png` | Customization → Branding → Video watermark (Entire video) |

Assets are generated in code (Pillow, navy/gold sunrise system) so the text is
always crisp. If the brand ever changes, redraw them with the same palette
below (2560×1440 banner with all text inside the 1546×423 safe area,
800×800 avatar, 150×150 transparent watermark) rather than stretching or
re-typing over the PNGs.

### Color Palette (sunrise counterpart to The Secret Place's midnight set)
- **Altar Navy:** `#04122b` (primary background, pre-dawn sky)
- **Deep Indigo:** `#081c3f` (secondary panels)
- **Divine Gold:** `#ffc93c` (headings, sunrise disc, declarations)
- **Soft Amber:** `#ffd75a` (secondary highlights)
- **Pure Ivory:** `#f7fafc` (primary text)
- **Dawn Mist:** `#d7ebff` (sub-headers, verse references)

### Thumbnail System (differs from Secret Place on purpose)
- Pre-dawn navy background, rising gold sun arc low in frame, ivory/gold
  2–4 word declaration text (e.g. `BEGIN AT THE ALTAR`, `FAVOUR LIKE A SHIELD`).
- Never reuse a Secret Place thumbnail, title or script on this channel.

## 5. Launch Checklist

- [x] Create the channel and claim the handle — `@TheMorningAltarDaily` (2026-11-04)
- [x] Upload avatar (§4) — confirmed on the live channel page, 2026-11-04
- [x] Re-upload banner **v2** (§4) — v1 text was cropped on mobile ("HE MORNING ALT…"); v2 keeps all text inside the 1546×423 safe area and displays in full on the channel page (the Edit-channel screen zoom-crops it; that preview is not what viewers see)
- [ ] Upload watermark (§4) — YouTube Studio on desktop only (Customization → Branding)
- [x] Verify the Name field is exactly `The Morning Altar | Daily Sunrise Prayer` — confirmed 2026-11-04 (extra characters removed); handle `@TheMorningAltarDaily`, first subscriber recorded the same day
- [ ] Paste About description + channel keywords (§2–§3)
- [ ] Enable 2-step verification + custom thumbnails (Studio → Settings)
- [ ] Create the **separate** GCP + Gemini projects and GitHub secrets
      (`docs/SECOND_CHANNEL_SETUP.md`) — never reuse Channel 1's token
- [x] First script published: `content/published/0036-psalm-5-morning-prayer-begin-your-day.md`
      (`channel: prayer2`, Psalm 5, uploaded `_vp27ZYPYaY`, public)
- [x] Brain supply is autonomous: the channel-scoped brain
      (`scripts/gemini_brain.py --ensure-supply-for prayer2`) authors,
      verifies and approves Morning Altar scripts from
      `MORNING_ALTAR_ROADMAP` on the `PRAYER2_` Gemini pool, stages no
      companion Short, and idles safely when the free tier is exhausted
- [ ] First scheduled production is automatic since 2026-11-05: Produce
      runs The Morning Altar after The Secret Place in every slot,
      uploading **public with auto-publish** (YouTube may still clamp an
      unaudited API project's upload to private server-side)
