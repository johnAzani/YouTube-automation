# Tenth channel — The Guided Path (`prayer10`)

**Status: registered and active (2026-11-12).** On the owner's instruction,
The Guided Path (`@TheGuidedPathPrayer`) now runs on the same terms as the other channels:
`provisioned=True` in `pipeline/channels.py`, public uploads, and a leg in every
scheduled workflow. Brand kit: [GUIDED_PATH_BRANDING.md](GUIDED_PATH_BRANDING.md).

## What is wired

- **Registry:** `prayer10` profile with secret prefix `PRAYER10_`; aliases resolve via
  `normalize_channel_id`.
- **Capabilities:** a full `Brand` and `ChannelCapabilities` block in
  `pipeline/channel_capabilities.py` — daily KJV prayer for wisdom, discernment and guidance, anchored in Proverbs 3:5–6. Every other
  brand forbids this channel's name, handle and call-to-action, and vice versa.
- **Brain equipment:** its own system instruction and theological rubric in
  `pipeline/brain_equipment/`.
- **Roadmap:** 30 scriptures, job IDs `0800–0829`, in `scripts/continuous_research.py`.
- **Visuals:** `pathway` Shorts poster grade and 16:9 CTR thumbnail pack; Short keys
  are namespaced `short-guided…`; Shorts target `18:44` UTC.
- **Workflows:** Produce, Gemini Brain, comments, community, metrics, growth
  autopilot, monitor, manual thumbnail and the credential audit all map
  `PRAYER10_*` secrets for this channel only. A missing secret resolves to empty;
  it never falls back to another channel's credentials.
- **Launch queue:** two approved long-form prayers and two companion Shorts are
  seeded so the channel does not start empty. The scheduled brain run authors the
  rest of the runway from the roadmap under this channel's own Gemini key.

## What has and has not been verified

- The read-only [OAuth preflight](https://github.com/johnAzani/YouTube-automation/actions/runs/43244946331) matched the authorized channel to the
  configured ID and found an upload-capable scope; the read-only
  [Gemini preflight](https://github.com/johnAzani/YouTube-automation/actions/runs/43244945814) listed model metadata. The standalone preflight workflows remain available for manual re-checks.
- The owner confirmed the intended channel was selected when its ID was copied.
  There has been no independent public-channel lookup.
- **Not yet exercised for this channel:** a real upload, TTS narration, script
  generation, thumbnail upload (needs the channel's phone/feature verification in
  YouTube Studio), quota and billing. The first scheduled Produce and Brain runs
  are the first real test; watch them and the monitor issue.
- The seeded scripts quote the KJV and were written for this launch; their
  fact-check worksheets in `content/factcheck/` are mechanically generated and
  unticked. Image search strings reuse queries already verified for earlier
  channels — no new Commons query is claimed as verified.

## Known gaps shared with every channel

These were recorded while the channel was staged and are **not** specific to it;
activation did not close them:

- Live comment replies do not yet require an expected channel ID, and
  `pipeline/comment_target_guard.py` is tested but not wired into comment writes
  or reconciliation.
- The shared public app, privacy and terms pages should describe current
  behavior before any OAuth verification submission.

Registration does not guarantee YouTube Partner Programme eligibility.
