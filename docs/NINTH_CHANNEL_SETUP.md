# Ninth channel — staged setup: The Praise Garden

**Current status: staged brand assets, authoring guidelines and a standalone
read-only credential preflight.** The guidelines are not registered with the
production brain; the preflight is not connected to any workflow. No new channel
registry entry, OAuth credentials, workflow mapping, queue, channel identity,
activation, or launch has been configured or verified. Do not call it connected
or live. The handle in [the brand kit](PRAISE_GARDEN_BRANDING.md) is a suggestion,
not a verified or reserved handle.

## Delivery sequence

1. Prepare the brand identity and assets (done; see the brand kit). Follow the
   previous channel setup process, with the owner completing any Google/YouTube
   account and authorization steps that require their access. Choose an available
   handle and upload the branding to the intended new channel; do not assume it
   already exists or change another channel's branding.
2. Implement a ninth-channel registry and complete parity work across
   capabilities, channel-specific workflow credentials, queue selection,
   thumbnails, watchdogs, audit and tests. It must fail closed: an unknown or
   missing credential/expected channel ID must never fall back to another
   channel's credentials. Adding secrets alone must not trigger publishing.
   **The ninth channel is not registered or wired yet.** The staged changes
   strengthen empty-credential isolation, restrict several existing workflow
   mappings to the selected channel and block unknown or inactive channels in
   the Produce matrix. Other paths still need review: comments and the manual
   thumbnail workflow do not both require verified expected channel identity,
   and an inactive gate must cover authoring and all other write-capable paths.
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
   billing or thumbnail permission, and is not yet wired into Actions.
   Credentials and identity have not yet been tested.
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
