# Channel reporting: coverage and access

The goal is a complete **accounting of coverage**, not a promise that every field
in YouTube Studio is available through the API. Missing data, permission errors,
empty reports and deliberately unrequested reports must remain distinct from zero.

## What is working versus what is implemented

- The existing public-video metrics workflow has authenticated successfully.
- PR #9 adds the channel's public subscriber count; a live count has not yet been
  collected by the changed code. Counts returned by YouTube may be rounded.
- `scripts/channel_analytics.py` is a separate private report collector. Its tests
  use mocked responses. **Live Analytics and monetary authorization are not yet
  verified.** Adding a scope string in code does not grant Google consent.

| Area | Collection path | Known boundary |
|---|---|---|
| Current subscribers | `metrics_snapshot.py`, channel statistics | Public API count, rounded; missing/hidden is not zero |
| Public video views, likes, comments | existing metrics workflow | At most 50 recent uploads; not an exhaustive channel archive |
| Daily performance | private Analytics `daily` report | Views, watch minutes, average view duration, subscriber gains/losses, likes/comments/shares |
| Video performance | private Analytics `videos` report | Views, watch time, average duration/percentage and subscriber changes; paginated with an explicit safety limit |
| Discovery | private traffic-source report | Source categories, not every individual referring URL/search term |
| Audience | country, demographics and subscription-status reports | Small groups may be withheld; availability depends on report compatibility |
| Devices | private device report | Device categories, not individual viewers |
| Retention | `--retention-video VIDEO_ID` | One selected video at a time; not yet an automated archive-wide retention scan |
| Revenue | opt-in `--revenue` | Separate monetary-readonly consent; estimates, not finalized payments |
| Impressions / CTR | Studio export until separately integrated and verified | Do not claim these are already collected |
| New/returning/unique viewers and audience interests | Studio export until separately integrated and verified | No inferred or invented audience metrics |
| Monetization eligibility / copyright / restrictions | Studio review | Not established by the performance report |
| Finalized earnings / payments | AdSense records | Not equivalent to Analytics estimated revenue |

## Private access setup

Do **not** attach raw audience/revenue artifacts to public GitHub Actions runs.
The private collector intentionally refuses to run in Actions. Reports stay under
gitignored `output/private-analytics/`, with file mode 0600. They are not uploaded,
committed, or printed in logs. A durable private store/scheduled delivery path has
not been configured; do not describe this as an always-connected dashboard.

1. In the Google Cloud project, enable YouTube Analytics API as well as the existing
   YouTube Data API. Configure the OAuth consent scopes for the requested access.
2. On a trusted local computer, mint a **separate read-only** token:
   ```bash
   python scripts/youtube_oauth.py --client-secret /private/path/client_secret.json --purpose analytics
   ```
   For revenue, use `--purpose analytics-revenue` instead. The consent belongs to
   the channel owner. The helper displays sensitive values locally: do not record,
   share or run it in public CI. Analytics tokens have no upload scope.
3. Set `ANALYTICS_CLIENT_ID`, `ANALYTICS_CLIENT_SECRET`, and
   `ANALYTICS_REFRESH_TOKEN` in a private environment. Do not place them in source
   files or chat. Existing upload secrets remain unchanged.
4. Run:
   ```bash
   python scripts/channel_analytics.py --start 2026-09-01 --end 2026-10-21
   # Optional deeper reports, after appropriate consent:
   python scripts/channel_analytics.py --retention-video VIDEO_ID --revenue
   ```
5. Inspect `output/private-analytics/report.json`. Every report has a status:
   `collected`, `no_data`, `not_requested`, `permission_or_api_error`, `error`, or
   `truncated`. All failures remain visible. Recent data may be delayed and report
   combinations may require adjustment after live verification.

An agent can analyze a report only once it is actually supplied through a private
workspace/connection. A successful public snapshot does not expose the credentials
or automatically give this session access to private Analytics. Never request a
password, refresh token or OAuth client secret in chat.
