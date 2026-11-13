# Stale checkouts in the production matrix — findings and fix (13 November 2026)

Scope: `.github/workflows/produce.yml`, the receipts in `content/published/`, and the
47 production runs created between 8 and 13 November. Everything below was read from
`git log`, the GitHub Actions API and the code. Nothing was dispatched, cancelled or
uploaded, and no YouTube API was called, so live channel state is **not** verified here.

All clock times are Nigeria time (WAT). UTC is given only where it is needed to match a
commit or a receipt field.

## Summary

| | |
|---|---|
| Fault | Every leg of a production run worked on the commit the *run* was created at, not on `main` as it was when the *leg* started. |
| Cause | `actions/checkout@v4` with no `ref` checks out `github.sha`. Runs wait behind the `content-state` lock and the matrix is serial, so that commit was hours old: 7½ hours in the case traced below. |
| Effect so far | Four long-form receipts re-stamped and three real Short receipts replaced by "recovered" stubs. Three Shorts were rendered a second time. No duplicate upload: all video IDs are unchanged. |
| Effect once a run uses the commit guard (PR #395, on `main` since 13 Nov 9:55am) | The overwrite is refused, but the whole state commit is refused with it — including the receipt for the video that leg really uploaded. Shown by a test, not yet seen live. |
| Fix in this change | Each leg fast-forwards to current `main` before it reads any content state, and stops if it cannot. |
| Not changed | `max-parallel` is still 1. The damaged receipts are not repaired (see "Left for the owner"). |

## What happened

A run is created with a fixed `head_sha`. It then waits for the `content-state`
concurrency group, and its legs run one after another. Measured over the 47 runs since
8 November:

| Channels in the run | Total leg time (legs are serial, so this is how long the run holds the lock) |
|---|---|
| 3 | 97–132 min |
| 5 | 202–253 min |
| 8 | 303–403 min (all three such runs were cancelled during the last leg) |
| 10 | 537 min (run 43310591718, the only ten-leg run so far) |

Waiting comes on top of that: run 43335854790 was created at 1:17am and its first leg
started 401 minutes later.

So when the previous run has just published for a channel, the next run's leg for the
same channel starts on a tree in which that video is still in `content/queue/` and that
Short still has a manifest and no receipt. The Midnight Watch leg of run 43335854790 is
the clearest case, because every timestamp lines up:

| Time (WAT, 13 Nov) | Event |
|---|---|
| 1:17am | Run 43335854790 is created. Its commit is `ea9d95e`, the tip of `main` at 12:52am. |
| 1:41am | The previous run records job 0207 and its Short on `main` (`344fcf7`). |
| 8:22am | The Midnight Watch leg of 43335854790 starts, on `ea9d95e`. |
| 8:23–8:27am | "Render the Short" runs for four minutes. The Short is rendered again; the upload is stopped by the title match against the channel and a recovered stub is written. |
| 8:27:44am | "Record videos that are live" finds 0207 on YouTube and stamps a new receipt. The receipt's `published_at` is `07:27:44Z` — this second, not the upload time `00:40:37Z`. |
| 8:27–9:25am | Job 0208 is rendered and uploaded normally. |
| 9:26am | The commit step stages the leg's working tree over `main` (`1e4286c`). |

The four commits and what each changed in receipts that already existed:

| Commit (UTC) | Channel | Long-form receipt re-stamped | Short receipt replaced by a stub |
|---|---|---|---|
| `e19ed94` 8 Nov 20:03 | Morning Altar | 0043: `published_at` 19:01:40Z → 19:10:43Z | none |
| `c34235b` 12 Nov 06:54 | Provision Table | 0501: 02:17:58Z → 06:15:11Z | `short-provisiondeuteronomy28v12-stewardship-prayer` (real at `8f0e205`) |
| `56983d3` 13 Nov 04:53 | Provision Table | 0503: 12 Nov 21:39:13Z → 13 Nov 03:52:37Z; `thumbnail_pending` false → true | `short-provisionphilippians4v19-stewardship-prayer` (real at `a9449ab`) |
| `1e4286c` 13 Nov 08:26 | Midnight Watch | 0207: 00:40:37Z → 07:27:44Z | `short-midnight2corinthians10v3-midnight-prayer` (real at `344fcf7`) |

In 0043, 0501 and 0207 the real `thumbnail_error` became `not_requested` and the retry
fields (`thumbnail_retry_after`, and `thumbnail_retry_reason` where present) were
removed. 0503 had a delivered thumbnail (`thumbnail_revision: "ctr-v3-cinema"`); it lost
that field and was marked pending again.

### What it cost

- **Thumbnail backoff.** The monitor has since rewritten the thumbnail fields on all
  four long-forms, so that state is correct again. But removing `thumbnail_retry_after`
  ended a backoff early: 0207 and 0501 were each retried against a permission refusal
  that had a seven-day hold, and the hold restarted from the later date.
- **Publish times.** `published_at` on the four long-forms is still the later, wrong
  value (up to 6h47m late). 0503 also has the wrong `published_on` (13 instead of 12
  November). Anything that reads recency from the receipt sees those videos as newer
  than they are.
- **Short receipts.** The three stubs lost the script body, `youtube_studio_url`,
  `width` / `height` / `duration_seconds`, `scenes_verified` and `metadata_revision`,
  and gained `metadata_retrofit_approved: false`. Their `published_at` differs from the
  original by 7–19 seconds because it now comes from YouTube rather than the runner.
- **Speech quota and time.** The three legs that wrote a stub each spent 4–6 minutes
  rendering a Short that was already published.
- **One layer of duplicate protection.** On a stale tree the repository cannot say a
  Short is already published. The only thing that stopped a second upload was the title
  match over the channel's recent uploads.

## Why the 13 November commit guard does not close it

`scripts/guard_produce_commit.py` compares each touched path at the leg's starting
commit, on `origin/main` and in the working tree, and refuses the commit if `main`
changed a path to something other than what the leg wants to write. On a stale tree
that is exactly the recovered stub, so the guard fires — correctly.

But the commit step is all-or-nothing. A refused commit also drops the receipt for the
long-form the leg just uploaded. The next run then finds that video on YouTube and
writes a recovered stub for it. The clobbering stops; the stubs do not.

`tests/test_produce_leg_rehearsal.py::test_without_the_refresh_a_stale_leg_loses_the_receipt_of_its_own_upload`
runs the workflow's own commit step in that situation and shows the refusal and the
missing receipt. It has not been observed in production: as of 10:38am on 13 November
no production run had been created from a commit that contains the guard.

## The fix

`produce.yml`, step **"Advance to latest main and snapshot starting commit"**, replaces
the old one-line snapshot step. It runs straight after checkout and the credentials
check, before queue repair, the Short, receipt recovery and the release:

- On `refs/heads/main` (every scheduled run, every `publish-now` dispatch, and manual
  runs from `main`): `git fetch origin main`, then `git merge --ff-only FETCH_HEAD`, up
  to three attempts.
- If that fails, the leg stops with a `Stale checkout` error before anything is
  rendered or uploaded. A leg that cannot fetch `main` could not record a publish
  either.
- On any other ref the leg keeps the commit it was asked to run and says so.
- `START_SHA` is written by this step only, after the fast-forward, so the commit guard
  compares against the tree the leg really worked on.

`gemini_brain.yml` and `growth-autopilot.yml` already pull `main` at the start of each
leg (and carry on if the pull fails); production was the workflow that did not.

One consequence to know about: a leg now runs the Python on current `main` with the
workflow file from the run's creation commit. If a change to `main` renames a script or
an argument that `produce.yml` calls while a run is queued, that run's later legs fail
at the renamed step. That is loud and uploads nothing, and the brain workflow has had
the same property since it was written.

## Tests

`tests/test_produce_leg_rehearsal.py` (nine tests, about three seconds). It reads the
two steps out of `produce.yml` and runs them with `bash -e` against a bare Git
repository standing in for `origin`, with a depth-1 checkout pinned to a SHA as the
runner makes it. It covers:

- a leg of a run created before the previous publish ends up on current `main`, sees the
  existing receipt, and its own commit leaves that receipt byte-identical;
- the same leg without the refresh is refused and loses its own receipt;
- a leg already at the tip, a run on another ref, an unreachable remote and a diverged
  history;
- step order, and that `START_SHA` has exactly one writer;
- two channels finishing together: `main` moves between one leg's fetch and its push,
  the push is rejected, the second attempt lands, both receipts are on `main`, the later
  commit carries only its own channel's files, and `docs/network-state.json` describes
  both videos.

The last test is the "mock rehearsal" asked for in
`docs/AUTOMATION_REMEDIATION_2026-11-13.md`. It is evidence for the parallelism
decision; it does not make that decision.

## Evidence on channel isolation

Collected for the same decision. Of the 86 `chore(content): publish job` commits between
7 and 13 November, every one touches `content/` files of exactly one channel.
`docs/network-state.json` changes in 82 of them and is the only file shared between
channels; it is derived, and the commit step rebuilds it from the staged tree on each
attempt.

Not yet examined, and needed before `max-parallel` is raised:

- `PEXELS_API_KEY` and `PIXABAY_API_KEY` are shared by all ten channels, so parallel
  legs share those rate limits.
- The `assets-v2-*` Actions cache has one key for all channels.
- A non-uploading run of the real workflow with several legs, as the remediation plan
  requires.

## Left for the owner

1. **Repair the seven receipts, or leave them.** The originals are in history at the
   commits listed above and the video IDs match, so the three Short receipts can be
   restored with `git show <commit>:<path>` and the four `published_at` values put back.
   Not done here because the monitor is still writing thumbnail fields to those same
   files, and because restoring a Short receipt removes
   `metadata_retrofit_approved: false`, which lets the metadata sync touch that video
   again. That is the behaviour issue #382 is about, so it should be a deliberate
   choice.
2. **Run 43335854790** was still in progress when this was written, on `ea9d95e`, which
   predates both the guard and this fix. Its remaining legs (Family Altar onward) can
   repeat the pattern for any channel whose state changed on `main` after 12:52am on
   13 November. Check
   their publish commits for modified files under `content/published/`:
   `git log --diff-filter=M --format='%h %ci' -- content/published | head`.
3. **After this merges,** the first scheduled run created from the new commit should
   show a `Checkout advanced` notice on any leg that started after `main` moved, and no
   publish commit should modify an existing receipt.
4. **`comments.yml`** has the same pinned checkout in a serial matrix and commits one
   shared ledger, `content/comments/replied.json`. A duplicate reply is prevented by a
   live check for the channel's own reply on the thread, so this is not the same risk,
   but the ledger commit there uses `git pull --rebase` and was not examined further.
