# Ninth channel — staged setup: The Praise Garden

**Current status:** the owner shared a YouTube screenshot showing The Praise
Garden, `@ThePraiseGardenDaily`, its banner, avatar and description. This is
confirmation of the displayed brand and handle, not an independent verification
of the channel ID or OAuth identity. The owner has saved the four PRAYER9 YouTube
secret names, and [read-only preflight run 43221633843](https://github.com/johnAzani/YouTube-automation/actions/runs/43221633843)
succeeded: the refresh-token-authorized channel matches the configured channel ID,
and an upload-capable scope was returned. The owner confirmed The Praise Garden
was selected when copying the channel ID; this is owner confirmation, not an
independent public-channel lookup. The check does not test an upload, generation,
TTS, quota, billing or thumbnail permissions. A manual
preflight workflow is staged in this PR, not deployed to the default branch.
The owner reports saving `PRAYER9_GEMINI_API_KEY`; [read-only Gemini preflight
run 43224493481](https://github.com/johnAzani/YouTube-automation/actions/runs/43224493481)
successfully listed model metadata. This does not verify generation, TTS,
quota, billing, or project ownership. Its manual workflow is also staged only.
The authoring guidelines are not registered with the production brain. No
ninth-channel registry entry, publishing workflow mapping, queue, activation or
launch has been configured. Do not call it connected to automation or publishing.

## Delivery sequence

1. Prepare the brand identity and assets (done; see the brand kit). The owner's
   screenshot shows the channel name, handle, banner, avatar and description.
   The owner confirmed the intended channel was selected when copying its ID.
   Watermark and feature eligibility have not been verified here. Do not change
   another channel's branding.
2. Implement a ninth-channel registry and complete parity work across
   capabilities, channel-specific workflow credentials, queue selection,
   thumbnails, watchdogs, audit and tests. It must fail closed: an unknown or
   missing credential/expected channel ID must never fall back to another
   channel's credentials. Adding secrets alone must not trigger publishing.
   **The ninth channel is not registered or wired yet.** The staged changes
   strengthen empty-credential isolation, restrict several existing workflow
   mappings to the selected channel and gate unknown or inactive channels in
   the Produce, brain, comments, growth and metrics planners. The manual live
   thumbnail path now requires an active channel, a matching authorized identity
   and video ownership; missing expected IDs will block live updates. Other paths
   still need review: live comments do not yet require an expected channel ID,
   and inactive gating must be checked in all remaining write-capable paths.
   Local tests and workflow linting do not replace testing GitHub Actions or
   verifying real OAuth credentials. Do not register or activate channel nine
   until these gaps are addressed.
3. Prepare unique, scripture-grounded drafts and companion Shorts for owner
   review; verify quotations, factual claims and asset permissions. Mechanical
   checkboxes are not proof of human fact checking or monetization eligibility.
4. The owner completes Google authorization and secret configuration through
   secure interfaces, never in chat. Do not request or record passwords, OAuth
   codes, client secrets, API keys or refresh tokens in conversation. Obtain the
   channel ID through the intended secure workflow, then use a read-only preflight
   to confirm authorized identity and required permissions. The standalone
   `python scripts/praise_garden_preflight.py` reads only
   `PRAYER9_YOUTUBE_CLIENT_ID`, `PRAYER9_YOUTUBE_CLIENT_SECRET`,
   `PRAYER9_YOUTUBE_REFRESH_TOKEN`, and `PRAYER9_YOUTUBE_CHANNEL_ID` from a
   secure local environment and makes only OAuth refresh and channel-identity
   requests. It rejects missing fields, insufficient or undisclosed scopes, and
   wrong/ambiguous channel identities. It does not test an upload, TTS, quota,
   billing or thumbnail permission. An initial branch-only Actions run succeeded
   as noted above. The staged manual workflow will be usable from the default
   branch only after review and merge; it does not activate a channel. The
   separate `python scripts/praise_garden_gemini_preflight.py` reads only
   `PRAYER9_GEMINI_API_KEY` and checks model-list access without generation;
   its staged manual workflow is likewise not yet deployed.
5. The owner handles YouTube phone/feature verification. Review thumbnail and
   advanced-feature status independently; permission responses alone do not
   prove the reason for a refusal.
6. Only after explicit review/approval, identity verification, and inspection of
   all scheduling/readiness gates should activation or a controlled debut be
   considered. No first upload, metadata change, or schedule activation is
   authorized merely by creating the brand kit.

The existing eight channels and their published videos must remain untouched by
the staged ninth-channel work. A ninth channel's setup does not guarantee YPP
eligibility or make the existing channels monetized.
