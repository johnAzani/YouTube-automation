# The comment that was never pinned

17 November 2026. Times are UTC unless marked otherwise.

Eighth reading of the day. The first seven looked at the picture, the sound, the
clock and the still. This one looks at the line of text under the video — the
one the pipeline posts on every upload, the one every document in this repository
calls the **pinned** comment.

Three questions were asked of the repository itself: does it get to the top, is
it written down anywhere, and does it carry anything a viewer can act on.

## The short answer

- **Nothing is pinned.** The YouTube Data API has no pin method, and this
  repository ships the proof: the discovery document its own client reads
  (`googleapiclient/discovery_cache/documents/youtube.v3.json`, revision
  **20261104**) lists exactly two `commentThreads` methods, `insert` and `list`,
  and six `comments` methods — `delete`, `insert`, `list`, `markAsSpam`,
  `setModerationStatus`, `update`. **No method in any resource of the document
  contains the string "pin"** (checked programmatically over every method name).
  A comment goes first by being early and alone; keeping it there is a Studio
  click the owner makes by hand.
- **390 comments should exist and 0 receipts say whether they do.** Of 394
  published receipts, 3 are recovered from YouTube without an upload by this
  pipeline, and 1 is a finance niche that generates no comment by design — the
  rest each ran the posting block. No receipt carries `top_comment`, none carries
  `pinned_comment_pending`, none carries `pinned_comment_failed`.
- **Success was unrepresentable.** `pinned_comment_pending` is written only when
  the post fails *and* only inside `if scheduled_at is not None`. Shorts' receipt
  writer had no comment field at all. So a receipt with no flag meant "posted",
  "failed on an immediate upload" or "never attempted", indistinguishably — and
  `docs/SCHEDULED_PUBLISHING_2026-11-13.md` reads that absence as proof of
  posting.
- **An immediate upload's failure was also unrecoverable.** The retry path
  (`scripts/confirm_scheduled_publish.py`) requires `publish_confirmed_at`, which
  only a scheduled upload ever sets. 390 of 391 uploads are immediate.
- **The comment now says what happened**: `top_comment: ok | failed | skipped`,
  on both writers. First figure to read: `top_comment: "ok"` — 0 today.

## 1. The word, and the document that contradicts it

The name is everywhere. The module is `pipeline/pinned_comments.py` and opens
`Autonomous Pinned Comment & First-Hour Engagement Engine`; the upload result
carries `pinned_comment`; the receipt flag is `pinned_comment_pending`; the
`scheduled_publishing` doc has a row headed "Pinned comment"; the community doc
has a section called "Autonomous First-Hour Pastoral Pinned Comment Engine".

The document that the code actually calls does not have the vocabulary for it.
Read straight out of the installed client:

| Resource | Methods (revision 20261104) |
| --- | --- |
| `commentThreads` | `insert`, `list` |
| `comments` | `delete`, `insert`, `list`, `markAsSpam`, `setModerationStatus`, `update` |
| any resource, any method containing "pin" | **none** |

`insert` places a top-level comment. There is no ordering, no owner-chosen
position, no `pinned: true` on the resource. What actually determines whether the
pastoral comment is the first thing a viewer reads is **when it was posted
relative to the first real comment** — a race the pipeline wins by posting within
seconds of the upload, and loses the moment a viewer comments first on a popular
video.

This is not a claim about YouTube's product; it is a claim about the document in
this repository's own dependencies. `POST`-ing a request body with an unknown
field is not the same thing as a supported method, and nothing in the code tries
to.

The honest name for what the pipeline does is **the first comment**, and that is
what the receipts and docstrings say now. The identifiers keep their historical
names — `pinned_comments.py`, `pinned_comment_pending`, `pinned_comment_failed` —
because renaming a receipt key breaks every reader for no gain; the reading is
what had to change.

## 2. What is actually posted

One comment per upload, generated from the channel's own template in the
capability matrix — never from a hardcoded string (that is how The Morning Altar
once inherited The Secret Place's night comment).

| Channel | Long-form template | Short template | Sanctuary links | Store/journal footer |
| --- | --- | --- | --- | --- |
| `secret-place` | 373 chars | 482 | yes | **yes — two Selar URLs** |
| `prayer2` … `prayer10` (9 channels) | 312–456 chars | 283–406 | no | no |

Rendered today for a long-form on The Secret Place:

> 🕊️ Beloved family, if you are listening to this tonight, write 'AMEN' in faith
> to claim God's promise of divine protection and angelic shelter over your home,
> your children, and your mind.
>
> 📖 Psalm 91:4 — 'He shall cover you with His feathers, and under His wings you
> shall take refuge; His truth shall be your shield and buckler.'
>
> Drop your prayer requests below — our pastoral editorial team reads and
> intercedes over every single name before this night closes. Rest in holy
> stillness tonight. You are not alone. 🙏✨
>
> 📖 Printable 30-Night Bedside Prayer Journal: https://selar.com/…
> 🤍 Voluntary Ministry Support: https://selar.com/…

Three things follow from the table, none of which was written down before:

- The **AMEN invitation** — the thing the comment exists for in the first-hour
  premise — is on all ten channels.
- The **revenue footer** is on one. 9 of 10 channels post a comment with no
  outbound link at all, which is by design: `include_sanctuary_links` is false
  there because the store and journal belong to The Secret Place's funnel.
- On **Shorts**, the text is not the prayer comment but the bridge
  (`pipeline/shorts_bridge.py` → `short_pinned_comment_for`), pointing at the
  counterpart long-form. That branch is 255 of the 394 receipts.

The 1 finance receipt (`short-0001-how-enron-died.md`) is skipped by design: any
niche containing finance/business/economics/corporate returns an empty string and
the upload records `skipped`.

## 3. Where the record died

The upload decides between four states and hands one of them back:

| State | Meaning | Where it ended up, before today |
| --- | --- | --- |
| `not_attempted` | dry run, or the upload path never reached the block | nowhere (correct) |
| `skipped` | no text by design (finance niche) | nowhere |
| `ok` | `commentThreads.insert` returned a comment | **nowhere, on any path** |
| `failed` | the insert raised, or generation raised | long-form scheduled: `pinned_comment_pending: true`; **long-form immediate: nowhere**; **Shorts: nowhere** |

The gap is two lines of placement rather than intent. In `pipeline/run.py` the
flag sits inside the scheduling branch —

```python
if scheduled_at is not None:
    stamped.extend(...)
    if pinned_comment == "failed":
        stamped.append(("pinned_comment_pending", True))
```

— so an upload that goes public immediately (every upload since the schedule was
switched off) throws the failure away. And `pipeline/short_release.py`'s
`_write_published_record` had no parameter for it at all, so 255 Shorts could not
record a comment even in principle.

Downstream, `scripts/confirm_scheduled_publish.py` retries an owed comment only
when the receipt has **both** `pinned_comment_pending` and `publish_confirmed_at`
(`_comment_owed`). `publish_confirmed_at` is written by that same script when it
confirms a scheduled publish. An immediate upload never gets one, so even if the
flag had been stamped, nothing would have retried it.

### What the documentation had been reading

`docs/SCHEDULED_PUBLISHING_2026-11-13.md`, in "What to check afterwards":

> whether the channel's comment was posted at upload (no `pinned_comment_pending`)
> or afterwards

That is a two-valued read of a record that had one value. Absence of the flag
meant posted, or failed-and-discarded, or never attempted. The document was
written during the one scheduled trial, where the distinction happened to hold —
one scheduled upload exists in 394 receipts — so the reading was never wrong in
practice and never true in general.

The same document's row *"Three refusals end the attempt
(`pinned_comment_failed: true`)"* is accurate to the code
(`scripts/confirm_scheduled_publish.py` stamps it on the third refusal) and
describes a path that has never run: `pinned_comment_failed` appears in **0**
receipts.

### The trial that did happen

13 November, The Healing Balm, the only long-form ever scheduled: uploaded
17:32:45 private, public 19:14:00. Its comment was posted by the monitor after
publication, not by the upload, and the trial's own note records the cost:

> Found by the trial: the pinned comment arrived up to 39 minutes after the video
> went public, because the monitor does not run on a fixed short interval.

So the one time this pipeline could have measured a first *hour*, the comment
arrived in the fourth quarter of it.

## 4. What changed

| Change | File |
| --- | --- |
| Every upload stamps `top_comment: ok\|failed\|skipped` on its receipt (frontmatter and `doc.meta`), scheduled or not, success included | `pipeline/run.py` |
| Shorts record the same field — the writer gained a `top_comment` parameter and the release passes `UploadResult.pinned_comment` through | `pipeline/short_release.py` |
| Module header rewritten: posted, never pinned, with the discovery-document evidence and the new receipt key | `pipeline/pinned_comments.py` |
| Upload block comment and its log line say "first comment", not "pinned comment" | `pipeline/upload.py` |
| §3 of the community engine doc renamed and corrected, with the Short variant and the measured zero | `docs/COMMUNITY_AND_CTR_ENGINES.md` |
| 6 new tests: posted/failed/skipped recorded on an immediate upload; a scheduled failure says both `failed` and owed; a recovered receipt claims nothing; the Short writer records all three states | `tests/test_scheduled_publishing.py`, `tests/test_short_receipt_recovery.py` |

`pinned_comment_pending` keeps its exact meaning and its scheduled retry, and
`pinned_comment_failed` is untouched. Nothing about what is posted, when, or to
which channel changed. No receipt is edited, backfilled or invented: the 394
existing receipts keep whatever they carry, which is nothing, and the field
starts existing at the next upload.

## 5. The figure to read

```bash
grep -l 'top_comment: "ok"' content/published/*.md | wc -l   # 0 today
grep -l 'top_comment: "failed"' content/published/*.md | wc -l
```

One per successful upload should appear. A `failed` is now visible on the same
pass it happens, and — because 9 of 10 channels post a comment with no URL while
The Secret Place posts one with two — the failing set itself is diagnostic: if the
failures are all `secret-place`, the suspect is the links, not the API.

## Unproven

- **That any of this moves reach.** `content/analytics/` holds no comment data:
  no counts, no replies, no per-video traffic source. `V_{1hr}` is a premise this
  repository inherited from growth folklore, not a measurement it owns, and
  YouTube does not publish per-video CTR either.
- **Whether a comment carrying two `selar.com` URLs is visible to viewers.** This
  repository's own `docs/LONGFORM_YOUTUBE_UPLOAD_GUIDE.md` says external
  hyperlinks in descriptions and pinned comments are unlocked by channel
  verification tier — implying that below that tier they are inert or held. Those
  34 receipts' comments may be sitting in a "pending review" state that no API
  here can see. Nothing in the code checks.
- **That the comment is at the top on any existing video.** No receipt records
  the comment, and the API cannot be asked whether one is pinned; only a human
  looking at the watch page knows.

## Owner-only

- **Pinning** the first comment by hand in Studio on the videos that matter. No
  automation in this repository can do it, now or later, without a method that
  does not exist in the API.
- Deciding whether the **Selar links** belong in a comment at all, versus the
  description, given the verification-tier caveat above.
- A **retry for immediate uploads** — the small feature this reading deliberately
  did not build: `top_comment: failed` is now observable, but nothing acts on it.
  Building it means a monitor pass that re-posts, and the same "ask YouTube first"
  guard `confirm_scheduled_publish.py` already has, so a retry cannot post a
  second copy.
- Granting the **comment-analytics scope** on each channel, without which none of
  this can be tied to reach.

## One next step

Read the field on the next upload, and nothing else: `0 → 1`. If it says `ok`,
the comment exists and the question becomes whether it is first (owner's eyes, one
watch page). If it says `failed`, the failure is now attached to a channel and a
time, which is more than this pipeline has ever known about the line of text
under the video.
