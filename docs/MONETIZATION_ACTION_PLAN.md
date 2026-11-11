# Eight-channel monetization action plan

This is a prioritization and evidence checklist, not a promise of acceptance,
views, revenue, or a deadline. YouTube reviews each channel independently.
Metrics and Studio status must be checked per channel; we do not have current
valid public watch hours, engaged Shorts views, strikes, claims, or YPP status.
The older [MONETIZATION_AUDIT.md](MONETIZATION_AUDIT.md) is historical and is
not evidence of compliance.

## 1. Measure eligibility honestly

- Record each channel's **Earn** page: eligibility status, valid public watch
  hours in the rolling 12 months, valid public Shorts views in the rolling 90
  days, subscriber count, and any action required. Don't infer eligibility from
  a public view count or a sum of ordinary Analytics watch time.
- Full ads/Premium eligibility currently requires 1,000 subscribers and either
  4,000 valid public watch hours in 12 months or 10 million valid public Shorts
  views in 90 days. Shorts Feed watch hours do not count toward the 4,000 hours.
  Meeting a threshold does not guarantee approval; other requirements and
  YouTube's review apply. Source: [YPP eligibility](https://support.google.com/youtube/answer/72851?hl=en).
- In eligible regions including Nigeria, expanded YPP offers earlier access to
  certain fan-funding and Shopping features at 500 subscribers, three valid
  public uploads in 90 days, and either 3,000 valid public watch hours in 12
  months or 3 million valid public Shorts views in 90 days. Feature-specific
  restrictions and YouTube review still apply; this is not full ad revenue.
  Source: [Expanded YPP](https://support.google.com/youtube/answer/13429240?hl=en).
- Check Studio for current country, required verification, strikes, two-step
  verification, advanced features, and AdSense requirements before applying.
  Recheck YouTube's current rules, including any future changes, at application.
- Public baseline: [2026-11-11 snapshot](https://github.com/johnAzani/YouTube-automation/actions/runs/43110038450),
  retained as per-channel public-counter artifacts for 30 days. Secret Place
  showed 1,250 YouTube-reported subscribers; the other seven were below 1,000.
  Public counts may be rounded or delayed. No valid watch-hour, retention, CTR,
  monetization or revenue numbers were collected in that snapshot.
- Weekly public snapshots exist, but historical artifacts expire and their
  comparisons are not automatic. Compare the *same videos at similar ages*
  before deciding which topics, hooks or formats to change. Do not treat missing
  measurements as zero. CTR/impressions require Studio or a verified supported
  source; private Analytics collection in this repo is intentionally local-only
  (`scripts/channel_analytics.py`), with separate read-only consent and storage.

## 2. Fix a measurable discovery-to-watch-time bottleneck

The current Short description/comment bridge cannot be assumed clickable:
[YouTube says URLs in Shorts descriptions and comments are non-clickable](https://support.google.com/youtube/answer/13748639?hl=en).
YouTube Studio's **Related video** feature offers a clickable link below the
Short's handle; it requires advanced feature access and a public or unlisted
video from the same channel. [Official instructions](https://support.google.com/youtube/answer/14075157?hl=en).
Do not assume a description URL or a pinned comment is a clickable substitute.

Run `python scripts/audit_short_related_videos.py` to list **candidate**
same-channel, same-scripture pairs from local publication receipts. It is
read-only. Receipt status can be stale, and a matching key alone does not prove
that a video is live, relevant, or not already linked. Resolve ambiguous matches,
check both videos and existing links in Studio, and choose a suitable counterpart.
No video or metadata is edited by the audit. Recent examples to verify:

| Channel | Short | Candidate long-form prayer |
| --- | --- | --- |
| Family Altar | [Joshua 24:15](https://www.youtube.com/shorts/FNRQnoo_-cU) | [Joshua 24:15](https://youtu.be/NjhW7YUzhis) |
| Healing Balm | [Jeremiah 30:17](https://www.youtube.com/shorts/-acHo0CzsgQ) | [Jeremiah 30:17](https://youtu.be/7spe8TmewlI) |
| Provision Table | [Psalm 23:5](https://www.youtube.com/shorts/Yrmz7lHdYBk) | [Psalm 23:5](https://youtu.be/7KQUigXezRU) |
| Covenant Shield | [Psalm 121:7–8](https://www.youtube.com/shorts/q8qxvEQjdD8) | [Psalm 121:7–8](https://youtu.be/_T9qvff8ats) |

The existing automatic recovered-receipt metadata hold remains in place; do not
force a description retrofit to implement related-video links. The family Short's
current description was explicitly approved as a replacement, not an exact
restoration. Adding a Related video is a separate Studio change, not an upload.

## 3. Review content quality and rights before scaling

- Sample actual published long-form and Shorts on **every** channel for distinct
  editorial value, coherent narration, accurate scripture and on-screen text,
  misleading titles or promises, and excessive templating or cross-channel
  duplication. Record examples and fixes; checkbox flags and automated
  similarity checks are not a human quality review.
- Verify commercial-use rights and provenance for actual audio, visuals, and
  quotations. Check claims and strikes in Studio. Passing a local licence gate
  is useful but does not certify copyright or YouTube monetization approval.
- YouTube's [monetization policy](https://support.google.com/youtube/answer/1311392?hl=en)
  addresses repetitive/mass-produced and reused content at channel level. AI
  alone does not determine eligibility; originality and genuine viewer value do.
- Avoid artificial engagement, purchased watch time, sub-for-sub, misleading
  claims, re-uploads, and scaled low-value variations. Increase output only if
  quality and operational evidence support it.

## 4. Resolve the thumbnail permissions separately

Family Altar, Healing Balm and Covenant Shield have thumbnail permission
refusals. Weekly retries already exist; see [THUMBNAIL_RECOVERY.md](THUMBNAIL_RECOVERY.md).
The owner can complete phone verification and request a targeted retry. A 403
alone does not prove the cause, and success cannot be claimed until verified.
Thumbnail verification is distinct from the advanced-feature requirement for
Shorts Related videos; check both in Studio.
