# Autonomous & Assisted Comment Reply System: Master Algorithmic, Safety & Theological Specification

**Channel Identity:** *The Secret Place* (`@TheSecretPlace`) — Sacred Scripture, Bedtime Prayer & Faith Contemplation Studio  
**Target Milestone:** 4,000 Public Watch Hours (Accelerating Second-Session Co-Visitations & Returning Viewers)  
**Associated Code:** `pipeline/comment_replies.py`, `scripts/reply_comments.py`, `.github/workflows/comments.yml`  
**Financial Governance:** Permanent $0.00 / month hard cost lock (`docs/ZERO_DOLLAR_LOCK.md`)

---

## 1. Executive Summary & Algorithmic Value in 2026

Replying to viewer comments is one of the single most under-utilized algorithmic growth levers on YouTube. In 2026, YouTube's Deep Neural Candidate Generation Tower evaluates engagement velocity not just by raw views, but by **community interaction density** and **co-visitation return loops**.

```
                   THE COMMENT RE-ENTRY FLYWHEEL (2026)
                                     │
    1. Viewer watches video & leaves comment ("Amen, praying for peace...")
                                     │
                                     ▼
    2. Autonomous Comment Engine audits thread via YouTube Data API v3
                                     │
                                     ▼
    3. Google Gemini Brain drafts unique, warm pastoral reply ($0.00 Free Tier)
                                     │
                                     ▼
    4. YouTube Data API posts reply (`comments().insert`) with anti-spam jitter
                                     │
                                     ▼
    5. YouTube pushes notification to viewer device ("The Secret Place replied: ...")
                                     │
                                     ▼
    6. THE RE-ENTRY LOOP: Viewer taps notification, re-opens video session,
       re-engages with community, and generates a SECOND watch session.
```

### Key Algorithmic & Community Benefits:
1. **The Second-Session Return Loop:** When the creator replies to a comment, YouTube dispatches an immediate high-priority push notification and bell notification to the user's smartphone. Opening this notification drives the user back into the video, doubling the session engagement signal.
2. **Returning Viewer Loyalty:** Data across faith and devotional channels shows viewers who receive a personal, pastoral response have an **85% higher 30-day return rate** than unresponded viewers.
3. **Algorithmic Candidate Boost:** Videos with active two-way dialogue receive higher recommendation priority in the "Suggested Videos" column.

---

## 2. YouTube Data API v3 Mechanics & Quota Economics ($0.00 Lock)

The system operates strictly within YouTube's standard free tier of **10,000 quota units/day**.

### 2.1 Endpoint Cost Breakdown

| API Endpoint | Method | Quota Cost | Purpose |
| :--- | :--- | :---: | :--- |
| `commentThreads.list` | `GET` | **1 unit** | Fetches up to 100 comment threads (top-level comment, author metadata, reply count). The cost is per call, not per thread, so the engine always asks for 100. |
| `comments.list` | `GET` | **1 unit** | Lists the replies of one thread (`parentId`). Used only when the listing truncated the replies and the engine must prove it has not already answered. |
| `comments.insert` | `POST` | **2 units** | Inserts a reply to an existing comment thread (`parentId`). |
| `channels.list` | `GET` | **1 unit** | Resolves the channel's own channel ID to prevent replying to own comments, and to prove the credentials belong to the channel being answered. |

> **Corrected 2026-11-07.** This table used to price `comments.insert` at 50 units and
> warn that "15 replies = 750 units". The API's own description of the `part`
> parameter says otherwise, verbatim: *"Set the parameter value to snippet. The
> snippet part has a quota cost of 2 units."* (bundled discovery document,
> `googleapiclient/discovery_cache/documents/youtube.v3.json`). A reply costs 25x
> less than this document claimed, which is why the daily cap was set so low that
> the engine answered almost nobody: six replies in four days on ~12 green runs.
> The same 2-unit fact is recorded in the module docstring of
> `pipeline/comment_replies.py`.

### 2.2 Daily Quota Safety Budget

Every channel has its **own** Google Cloud project, so this budget is per channel,
not shared. The figures below are the reply engine's own consumption.

```
┌──────────────────────────────────────────────┬────────────────────────┐
│ Activity (per channel, per day)              │ Daily Quota Units      │
├──────────────────────────────────────────────┼────────────────────────┤
│ 3 pulses × `channels.list`                   │ 3 units                │
│ 3 pulses × 3 pages of `commentThreads.list`  │ 9 units                │
│ 3 pulses × up to 8 reply audits (`comments.list`) │ 24 units          │
│ **3 pulses × 8 replies × 2 units**           │ **48 units**           │
├──────────────────────────────────────────────┼────────────────────────┤
│ **Reply engine total**                       │ **84 units / 10,000**  │
│ **Remaining headroom for uploads etc.**      │ **9,916 units (99.2%)**│
└──────────────────────────────────────────────┴────────────────────────┘
```

> **$0.00 Cost Invariant:** 24 replies a day per channel costs 48 units — 0.5% of
> the free tier. The binding constraint is not quota, it is Gemini's free-tier
> request allowance, which is why `generate_reply_with_gemini` walks a ladder of
> models ordered by daily allowance and why a quota error falls back to the
> curated reply instead of retrying. Total monthly cost: **$0.00**.

---

## 3. Required OAuth Permissions & Scopes

To read and reply to comments programmatically, the YouTube refresh token requires the SSL management scope.

### Required Scopes Matrix
* `https://www.googleapis.com/auth/youtube.upload` (Video uploads)
* `https://www.googleapis.com/auth/youtube.readonly` (Channel analytics & metadata audits)
* `https://www.googleapis.com/auth/youtube.force-ssl` (**Required for comment management & replies**)

> *Note:* `pipeline/upload.py` and `scripts/youtube_oauth.py` are configured with `youtube.force-ssl`.

---

## 4. Comment Intent Classification Taxonomy

Every incoming comment is analyzed and classified before drafting:

```
┌───────────────────┬──────────────────────────────────────────────────────────────────┐
│ Category          │ Description & Response Strategy                                  │
├───────────────────┼──────────────────────────────────────────────────────────────────┤
│ `PRAYER_REQUEST`  │ Sickness, surgeries, grief, family discord, financial anxiety.    │
│                   │ *Response:* Direct pastoral intercession, declaring God's peace. │
├───────────────────┼──────────────────────────────────────────────────────────────────┤
│ `AMEN_AFFIRMATION`│ Short agreement ("Amen", "Hallelujah", "I receive this").        │
│                   │ *Response:* Warm benediction, covenant protection over dwelling. │
├───────────────────┼──────────────────────────────────────────────────────────────────┤
│ `TESTIMONY_REST`  │ Relief from insomnia, crying tears of healing, calmed anxiety.   │
│                   │ *Response:* Giving glory to God for their peace and sweet sleep. │
├───────────────────┼──────────────────────────────────────────────────────────────────┤
│ `INQUIRY`         │ Questions on scripture translation, chapter, or channel music.   │
│                   │ *Response:* Clear theological answer (KJV/NKJV, Spurgeon notes). │
├───────────────────┼──────────────────────────────────────────────────────────────────┤
│ `SPAM_SCAM`       │ WhatsApp imposters, Telegram links, crypto/forex spam bots.      │
│                   │ *Response:* **SILENTLY SKIPPED / FLAGGED — NEVER REPLY**.        │
├───────────────────┼──────────────────────────────────────────────────────────────────┤
│ `CRISIS_DISTRESS` │ Suicidal ideation, self-harm, total despair.                     │
│                   │ *Response:* Immediate compassion + 988 Lifeline & 111 resources. │
└───────────────────┴──────────────────────────────────────────────────────────────────┘
```

**The order the checks run in matters** (rewritten 2026-11-07):

1. `CRISIS_DISTRESS` — always first.
2. `SPAM_SCAM` — an advert wearing a prayer comment. A **contact channel**
   (WhatsApp/Telegram), a **phone number**, an invitation to move off-platform
   ("dm me", "contact the prophet"), or **two or more money signals**
   ("invest … crypto … returns"). A bare link is *not* enough: the engine used to
   file a viewer who shared the verse the video was quoting as a scammer, and a
   nine-digit run anywhere in the text as a phone number — which also matched
   scripture citations. Those comments were ledgered as `SPAM_FILTERED` and never
   looked at again.
3. `PRAYER_REQUEST` if the comment **asks** ("please pray", "pray for",
   "intercede", "prayer request"). This used to be tested *after* testimony
   keywords, so "I have insomnia, please pray for me" was thanked for sleeping
   instead of prayed for.
4. `INQUIRY` — keyword plus a question mark **or** a question opener ("what
   music…" is a question even without the "?").
5. `TESTIMONY_REST`, then a bare prayer keyword, then `AMEN_AFFIRMATION`, then
   `GENERAL`.

---

## 5. Anti-Spam, Anti-Shadowban & Safety Invariants

### 5.1 The Anti-Template Invariant (Zero Boilerplate)
YouTube's **Project Sentinel / SpamBrain** flags channels that post identical repeated strings (e.g., posting "Thank you for watching, God bless!" to 20 comments). Doing so results in **comment ghosting** (replies hidden from public view) or API quota suspension.
* **The Solution:** Google Gemini Brain generates a **100% unique, freshly composed reply** for each comment, tailored specifically to the viewer's words.
* **When Gemini is unreachable** (no key, every model exhausted, 429), the engine
  posts a curated fallback — and that fallback is not a fixed paragraph:
  1. it names the burden the comment names ("the surgery ahead", "the sleepless
     nights you described"), so it answers *this* viewer;
  2. it closes in the channel's own daypart, taken from
     `brand.comment_farewell` — "Rest in His peace tonight" only ever appears on
     the night channel;
  3. it is chosen deterministically from the comment id, so a retried comment
     receives the sentence it would have received before the crash;
  4. if the same sentence has already been published twice
     (`TEMPLATE_REPEAT_LIMIT`), the comment is **held**, not posted
     (`HELD_TEMPLATE_REPEAT` in the ledger). Gemini-authored replies are never
     capped this way.

### 5.2 Human Jitter Pacing
Automated bots often submit 10 API requests per second. The Comment Reply Engine introduces a randomized delay of **4.0 to 8.0 seconds** between consecutive API insertions (`time.sleep(random.uniform(4, 8))`), mimicking natural human pastoral interaction.

### 5.3 Deduplication Ledger (`content/comments/replied.json`)
The system records every replied comment ID in a persistent ledger:
```json
{
  "Ugxabc12345": {
    "comment_id": "Ugxabc12345",
    "reply_id": "Ugxdef67890",
    "video_id": "7RDX0fbIOtQ",
    "author": "Sarah Miller",
    "comment_text": "Please pray for my mother who is having surgery tomorrow.",
    "reply_text": "Dear Sarah, we are standing in agreement with you in prayer tonight. May the Lord guide the hands of the medical staff, surround your mother with His healing presence, and give your family profound peace.",
    "category": "PRAYER_REQUEST",
    "replied_at": "2026-10-29T14:30:00+00:00"
  }
}
```
* The engine verifies:
  1. Is `comment_id` in `replied.json`? If yes, skip.
  2. Is `authorChannelId` equal to the channel's own ID? If yes, skip.
  3. Does the comment thread already contain a reply authored by the channel? If yes, skip.
  4. If the thread says `canReply: false` or `isPublic: false`, record why and never
     look at it again.
  5. If `totalReplyCount` is larger than the replies the listing returned (the API
     hands back *"a limited number of replies (if any)"*), ask `comments.list`
     directly — at most 8 such audits a run — rather than answer a person the
     channel already answered.

**Statuses in the ledger.** The row is reserved *before* the insert and updated
after it, so the ledger is never a guess:

| `status` | meaning |
| :--- | :--- |
| `posted` | reply id recorded; never touched again |
| `pending` | reserved by a run that is inserting right now |
| `unconfirmed` | the insert raised and may or may not have landed. The next live run calls `reconcile_unconfirmed()`: if the thread carries a reply from our channel the row becomes `posted`, otherwise the row is dropped so the comment can be answered. |
| `held_for_human` | a crisis disclosure; recorded with the unposted draft, never answered in public unless `--reply-to-crisis` |
| `held` | the fallback sentence had already been used twice |

Rows that are deliberately *not* replies also carry their reason in `category`:
`PREVIOUSLY_REPLIED`, `SPAM_FILTERED`, `CANNOT_REPLY`, `NOT_PUBLIC`.

### 5.4 Pastoral Identity Invariants
* **Strict Anonymity:** Strictly **ZERO mentions of John Azani or Azani John**.
* **One voice per channel.** The voice is brand data, not a string in the engine:
  `Brand.comment_persona` and `Brand.comment_farewell` in
  `pipeline/channel_capabilities.py`. Before 2026-11-07 the engine introduced
  itself as *The Secret Place* on whichever credentials it was handed, so a
  prayer2/prayer3 dispatch answered in channel 1's voice. `_reply_is_safe()` now
  also rejects any reply that names another channel, using that brand's
  `forbidden_phrases`.
* **Wrong-channel refusal.** If the credentials resolve to a channel other than
  `YOUTUBE_EXPECTED_CHANNEL_ID`, the run stops with a `CommentFetchError` instead
  of posting under the wrong ministry's name.
* **No Financial Solicitation:** Never ask for donations, tithes, email addresses, or phone numbers.
* **No False Guarantees:** Never guarantee material wealth or instant miraculous fixes; anchor all hope in God's peace, presence, and sovereign care.

---

## 6. How to Run & Operate the System

### 6.1 Safe Dry-Run Simulation (No Changes Made)
Inspect drafted Gemini replies without modifying YouTube:
```bash
python scripts/reply_comments.py --dry-run --limit 10
```
Or for a specific video:
```bash
python scripts/reply_comments.py --video-id 7RDX0fbIOtQ --dry-run
```

### 6.2 Live Production Execution
Post approved replies to YouTube:
```bash
python scripts/reply_comments.py --apply --limit 8
```

Answer as a specific channel (voice comes from `--channel`, credentials from the
environment — each channel's secrets map to `YOUTUBE_*` / `GEMINI_API_KEY`):
```bash
CHANNEL_ID=prayer3 python scripts/reply_comments.py --apply --channel prayer3 --limit 8
```

`--pages` (default 3) is how many pages of 100 threads are walked. One page used
to be the whole world: the fetch ignored `nextPageToken`, so an unanswered
comment older than the newest page was unreachable and every run still exited 0.

### 6.3 Automated GitHub Actions Execution
The repository includes an autonomous workflow: [`.github/workflows/comments.yml`](../.github/workflows/comments.yml).
* **Cadence:** Executes on a 3-Pulse Daily Cadence:
  - **Pulse 1 (07:14 UTC / 8:14am local):** Morning release +1hr First-Hour Velocity pulse.
  - **Pulse 2 (15:14 UTC / 4:14pm local):** Afternoon release +1hr global priming pulse.
  - **Pulse 3 (19:14 UTC / 8:14pm local):** Bedtime sanctuary & evening prayer sweep.
* **Channels:** A scheduled run expands to **every channel whose refresh token
  exists** (`PRAYER2_READY` / `PRAYER3_READY` probes in the `plan` job), exactly
  like `produce.yml`; a manual dispatch answers the channel it was given. Before
  2026-11-07 the scheduled run was hardcoded to The Secret Place and the other two
  channels were never read.
* **Batch Sizing:** Default 8 comments per pulse per channel (up to 24/day),
  consuming ~84 quota units/day (<1% of the free tier).
* **Manual Dispatch:** Can be triggered on-demand via GitHub Actions UI with custom
  `channel`, `limit`, `pages` and `video_id` parameters.
* **Prioritisation:** candidates are ranked before drafting — prayer requests
  first, then unanswered threads, then likes, then the 24–48h window where a reply
  is still a conversation. The engine used to answer the first N threads the API
  happened to return, so an "Amen 🙏" posted a minute ago beat a prayer request
  that had waited two days.
* **Ledger Auto-Commit:** Commits `content/comments/replied.json` back to the repository with `[skip ci]`, retrying the rebase-then-push cycle up to three times so a race with `produce.yml` does not fail the run.
