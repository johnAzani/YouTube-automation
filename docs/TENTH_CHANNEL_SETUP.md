# Tenth channel — staged setup: The Guided Path

The owner asked for an additional channel beyond The Praise Garden. The concept
and initial brand kit are prepared in [GUIDED_PATH_BRANDING.md](GUIDED_PATH_BRANDING.md).
No channel creation, handle availability, OAuth authorization, secrets, preflight,
registry entry, publishing mapping, schedule, or launch has been confirmed.
Channel nine also remains unregistered and inactive.

## Steps

1. The owner creates the channel through their signed-in YouTube account and
   applies the identity and assets. Confirm the actual handle and channel before
   any credential checks. Never assume a handle is available.
2. Follow the established dedicated Google Cloud OAuth process and secure
   GitHub Actions secrets process. Planned names are `PRAYER10_YOUTUBE_CLIENT_ID`,
   `PRAYER10_YOUTUBE_CLIENT_SECRET`, `PRAYER10_YOUTUBE_REFRESH_TOKEN`,
   `PRAYER10_YOUTUBE_CHANNEL_ID`, and `PRAYER10_GEMINI_API_KEY` (if the owner
   chooses to set one up). Do not send any secret, token or code in chat; never
   reuse another channel's credentials as a fallback. Saving secrets must not
   trigger publishing. Respect the existing $0 budget lock.
3. The standalone `python3 scripts/guided_path_preflight.py` reads only the four
   YouTube values from a secure environment, refreshes an OAuth token and reads
   the authorized channel ID; it fails closed on missing values, insufficient
   scopes and mismatched or ambiguous IDs. The staged GitHub workflow is manual
   and read-only; it is not deployed to the default branch. It has not been run
   against real tenth-channel credentials. Matching the configured ID does not
   independently prove the intended channel was selected; seek owner confirmation.
   It does not test uploading, generation, TTS, thumbnail access, quota or billing.
4. Before OAuth verification submission, ensure the shared public app, privacy
   and terms pages and demonstration accurately describe current behavior; see
   the remaining issues recorded in [NINTH_CHANNEL_SETUP.md](NINTH_CHANNEL_SETUP.md).
5. Complete channel-specific registry, queue, credentials and workflow isolation
   with comprehensive fail-closed tests; audit every write path and prevent
   inactive scheduling. Review unique drafts, Scripture, claims and rights. Verify
   feature eligibility independently. Obtain explicit owner approval before any
   activation, uploads, or other live writes. None of this is complete yet.

Do not change the existing eight channels or their videos as part of this setup.
