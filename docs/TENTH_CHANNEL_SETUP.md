# Tenth channel — staged setup: The Guided Path

The owner shared a screenshot of The Guided Path (`@TheGuidedPathPrayer`) showing
its avatar, banner and the opening of its description. The full description and
watermark were not established by the screenshot. The brand kit is in
[GUIDED_PATH_BRANDING.md](GUIDED_PATH_BRANDING.md). A subsequent screenshot shows
all five planned `PRAYER10_*` repository secret names, not their values. The
[read-only OAuth preflight](https://github.com/johnAzani/YouTube-automation/actions/runs/43244946331)
passed, matching the authorized channel to the configured ID and finding an
upload-capable scope. The owner confirmed The Guided Path was selected when
copying the channel ID; there has not been an independent public-channel lookup.
The [read-only Gemini preflight](https://github.com/johnAzani/YouTube-automation/actions/runs/43244945814)
passed its model-metadata listing. Neither probe verifies upload, generation, TTS,
quota, billing, thumbnail permissions or Gemini project ownership. No registry
entry, publishing mapping, schedule, or launch has been configured. Channel nine
also remains unregistered and inactive.

## Steps

1. The owner's screenshot confirms the displayed name, handle, avatar, banner
   and beginning of the description. The owner confirmed the intended channel
   was selected when copying its ID. Watermark and feature eligibility remain
   unverified.
2. Follow the established dedicated Google Cloud OAuth process and secure
   GitHub Actions secrets process. The screenshot shows `PRAYER10_YOUTUBE_CLIENT_ID`,
   `PRAYER10_YOUTUBE_CLIENT_SECRET`, `PRAYER10_YOUTUBE_REFRESH_TOKEN`,
   `PRAYER10_YOUTUBE_CHANNEL_ID`, and `PRAYER10_GEMINI_API_KEY` saved as names.
   Do not send any secret, token or code in chat; never
   reuse another channel's credentials as a fallback. Saving secrets must not
   trigger publishing. Respect the existing $0 budget lock.
3. The standalone `python3 scripts/guided_path_preflight.py` reads only the four
   YouTube values from a secure environment, refreshes an OAuth token and reads
   the authorized channel ID; it fails closed on missing values, insufficient
   scopes and mismatched or ambiguous IDs. Its initial branch-only run passed as
   linked above. The staged GitHub workflow is manual and read-only; it is not
   deployed to the default branch. Matching the configured ID does not itself
   prove the intended channel was selected; the owner has since confirmed it.
   The separate `scripts/guided_path_gemini_preflight.py` reads only the tenth
   channel's Gemini key and checks model-list access; its initial branch-only run
   passed. Its manual workflow is also staged only. Neither check tests uploading,
   generation, TTS, thumbnail access, quota or billing.
4. Before OAuth verification submission, ensure the shared public app, privacy
   and terms pages and demonstration accurately describe current behavior; see
   the remaining issues recorded in [NINTH_CHANNEL_SETUP.md](NINTH_CHANNEL_SETUP.md).
5. Complete channel-specific registry, queue, credentials and workflow isolation
   with comprehensive fail-closed tests; audit every write path and prevent
   inactive scheduling. Review unique drafts, Scripture, claims and rights. Verify
   feature eligibility independently. Obtain explicit owner approval before any
   activation, uploads, or other live writes. None of this is complete yet.

Do not change the existing eight channels or their videos as part of this setup.
