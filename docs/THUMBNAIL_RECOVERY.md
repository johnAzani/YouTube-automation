# Recover pending YouTube thumbnails

A custom thumbnail refused during upload does **not** require a new video or a
re-upload. The published receipt retains the YouTube video ID and
`thumbnail_pending: true`. After the channel owner completes YouTube's phone
verification and confirms custom-thumbnail eligibility in YouTube Studio, the
automation can try that same video's thumbnail again. Verification is not a
guarantee: YouTube can also refuse because of OAuth permissions, account identity,
quota, or other platform restrictions. Shorts may have different restrictions;
if the API refuses one, its receipt remains pending and Studio may be needed.

The Automation monitor periodically tries eligible receipts for scheduled
channels with each channel's own OAuth credentials. Permission-like failures
are retried no more than once per receipt in 24 hours; Shorts with those errors
remain eligible even after five attempts. Other repeated Shorts errors stop
after five attempts, except for rate limits. YouTube thumbnail rate-limit errors use a
six-hour cooldown and defer the rest of that channel's current pass. Limits
per pass protect quota, so a backlog can take multiple monitor runs. GitHub
scheduled runs may be delayed.

## Request a retry after verification

Once this change is on the repository's default branch, a repository owner with
permission to dispatch events can request an immediate, bounded pass for The
Covenant Shield (`prayer8`):

```sh
gh api --method POST repos/johnAzani/YouTube-automation/dispatches \
  -f event_type=thumbnail-permission-verified \
  -f 'client_payload[channel]=prayer8'
```

Use an exact registered internal channel ID, not a YouTube channel ID or handle.
The command queues an **Automation monitor** run, not a confirmation that any
thumbnail was accepted. Check that run's **Sync live channel thumbnails** logs
and the corresponding files in `content/published/`. A successful thumbnail
has `thumbnail_pending: false` and a revision; a refusal remains pending with
`thumbnail_error`. A deleted or missing video is marked separately and is not
reported as a successful thumbnail. A pass can have no eligible items because
of a cooldown, and it does not necessarily include the entire backlog. Later
monitor passes continue eligible work. A red run, a warning about an unsaved
receipt, or a push conflict requires checking the logs and retrying after the
underlying problem is resolved.

The targeted pass requires that channel's configured client ID, client secret
and refresh token; it never falls back to another channel's credentials. It
only selects permission-related pending receipts, bypasses the permission
cooldown, and does not bypass rate-limit cooldowns or change video titles or
privacy. It cannot bypass YouTube verification or policy. Never share OAuth
secrets in an issue or chat.
