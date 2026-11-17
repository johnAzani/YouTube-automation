# A reply that costs fifty

17 November 2026. Times are UTC unless marked otherwise.

Ninth reading of the day, and the first one about money — not dollars, of which
this pipeline spends none, but the units Google meters the free API in. Every
upload, thumbnail, comment, reply and caption track draws on them, and until
today the repository held **four different beliefs** about what they cost. One of
them was wrong by a factor of twenty-five and had been written down as a
correction.

## The short answer

- **A comment reply costs 50 units, not 2.** The method's own page opens with
  *"A call to this method has a quota cost of 50 units"* and only then explains
  that *"the snippet part has a quota cost of 2 units."* On 7 November 2026 an
  audit read the second sentence as the price of the call and wrote "25x less"
  into `pipeline/comment_replies.py` and `docs/COMMENT_REPLY_SYSTEM.md`, reversing
  a correct 50. Measured since: **109 replies** — **5,450 units**, where the
  2-unit model says 218.
- **The audit's own source could not have answered the question.** It cites the
  discovery document bundled with the client. That document contains **no
  method-level price for anything**: its only quota sentences are the `part`
  costs of the two comment inserts ("the snippet part has a quota cost of 2
  units"), the live-chat methods (20 and 5 units), and the word "quota" in the
  `key`/`quotaUser` parameter descriptions. `comments.insert`'s own description
  is "Inserts a new resource into this collection." — nothing else.
- **An upload is one unit, not 1,600.** The quota page (last updated 12 November
  2026, quoted by this repository's own
  `docs/PROTECTION_AND_REVENUE_RESEARCH_2026-11-16.md` §2.5) gives each project
  "100 `videos.insert` calls … and 10,000 units per day combined for all other
  endpoints". The receipts prove it independently: **`secret-place` uploaded
  eight videos in one Pacific quota day** (11 November), and nine channel-days
  reached seven — impossible at 1,600 units an upload, which caps a day at six.
- **The shared pool is spent on captions, not uploads.** Measured over the last
  seven days: **334 uploads costing ~70,170 units, 210 each** — and **149 caption
  tracks at 400 are 59,600 of that (85%)**. A caption track costs eight comments.
  The monitor now prints this as its **`api budget`** row.
- **Long-form caption tracks were the one big price with no receipt field.** The
  400-unit call's result was thrown away, so no receipt could say whether the
  track landed. It is recorded now (`caption_track: ok|failed`), which is also
  what makes the 59,600 legible per channel instead of in aggregate.

## 1. The four beliefs, and where they live

| Belief | Where it is written | Verdict |
| --- | --- | --- |
| `videos.insert` = 1 unit, from a separate **100 calls a day** allowance | `pipeline/upload.py` header, `requirements.txt`, `docs/SETUP.md:159` | **right**, and the receipts show it |
| `videos.insert` = 1,600 units of the shared 10,000 pool, **6 uploads a day** | `docs/FAST_TRACK_4000_WATCH_HOURS.md` §5.1, `pipeline/quota_handler.py:23`, `pipeline/channels.py:4` | stale since Google's granular change, and impossible at current volume |
| `comments.insert` = **2 units** | `pipeline/comment_replies.py` invariant 1, `docs/COMMENT_REPLY_SYSTEM.md` §2.1 (both marked "corrected 2026-11-07") | **wrong**; 50 |
| `thumbnails.set` = 50 units "against a 200-a-day limit" | `docs/THUMBNAIL_HERO_FIT_2026-11-17.md:90`, `docs/THUMBNAIL_PACK_RESEARCH_2026-11-17.md:174,223`, `CHANGELOG.md:69,76` | the price is right, the "200-a-day limit" is a misreading: 200 is 10,000 ÷ 50, i.e. the number of thumbnails that would exhaust the whole pool. There is no separate thumbnail allowance. |

The repository already contained the right answer: the 16 November protection
reading quotes the quota page verbatim, including the 100-upload allowance. It was
never carried back into the code or the four documents that describe the old
model — which is how a table in `FAST_TRACK` could still plan one upload a day at
"16% of quota" while the pipeline was doing six.

## 2. Why an upload cannot cost 1,600

Quota days reset at midnight Pacific, so the test is Pacific days, not UTC ones.
Counted over every receipt with a published video, by channel and quota day:

| Uploads in one Pacific quota day | Channel-days |
| --- | --- |
| 1 | 13 |
| 2 | 9 |
| 3 | 4 |
| 4 | 10 |
| 5 | 16 |
| 6 | 25 |
| **7** | **9** |
| **8** | **1** |

Seven uploads is 11,200 units at the old price, against a 10,000-unit day: the
old model says the seventh video of the day is impossible, and the receipts
contain ten channel-days where it happened — the largest on `secret-place`,
11 November 2026, at eight. Either every one of the ten projects carries an
approved quota extension, or the granular allowance is what is running. The
quota page says the latter; either way **nothing in this repository records
which**, so the figure cannot be planned against.

## 3. What the pool actually pays for

Prices used below are Google's method-level costs, all now in one place,
`pipeline/api_budget.py`:

| Call | Units | Note |
| --- | --- | --- |
| `videos.insert` | **1** | the 100-a-day upload allowance, not the pool |
| every `list` | 1 | `videos`, `channels`, `playlistItems`, `commentThreads`, `comments` |
| `thumbnails.set` | 50 | one per poster that lands |
| `commentThreads.insert` | 50 | the first comment under a video |
| `comments.insert` | 50 | one pastoral reply |
| `videos.update` | 50 | a metadata retrofit, a live handle repair |
| `playlistItems.insert` | 50 | only where a channel has a series playlist |
| `captions.insert` | **400** | one caption track |

Measured over the seven days ending 17 November, priced from the receipts and the
reply ledger:

- **334 uploads**, **~70,170 units**, a **median-equivalent 210 per upload**;
- **149 caption tracks = 59,600 units**, 85% of the total;
- **88 replies = 4,400 units**;
- first comments: **0 recorded** — every receipt written before today is silent on
  them, which is the subject of the previous reading
  (`docs/COMMENT_LEDGER_RESEARCH_2026-11-17.md`).

So the ordering is: **captions ≫ everything else**, and the single call this
pipeline makes most often — the upload — is the cheapest thing it does. A
channel's day, at six or seven uploads, spends roughly **1,400 units of pool on
thumbnails, comments and replies, plus 400 for every caption track it produces**:
2,600 units on a day when three uploads carry a track, 26% of a default project's
shared pool, against the 100-upload allowance that is barely touched.

The four discretionary levers, in descending order of units:

| Lever | Units | What it costs in uploads |
| --- | --- | --- |
| A caption track on every upload (6 a day) | 2,400/day | 34% of the pool |
| A reply to every AMEN (24 a day, the cap) | 1,200/day | 12% |
| A thumbnail on every poster that lands (6) | 300/day | 3% |
| A first comment on every upload (6) | 300/day | 3% |

## 4. What changed

| Change | File |
| --- | --- |
| One price table, one pricing function, and the model written down with the evidence | `pipeline/api_budget.py` (new) |
| `comment_replies.py` invariant 1: a reply is 50 units, and the 2026-11-07 correction is named as the error it was | `pipeline/comment_replies.py` |
| The reply-cost table, the dated correction blockquote and the "~84 units/day" budget recomputed (24 × 50 = 1,200, 12% of the pool) | `docs/COMMENT_REPLY_SYSTEM.md` |
| §5.1 marked superseded, with the quota page's own text and the eight-upload day | `docs/FAST_TRACK_4000_WATCH_HOURS.md` |
| "the 200-a-day limit" corrected in three places: it is 10,000 ÷ 50, not a thumbnail allowance | `docs/THUMBNAIL_HERO_FIT_2026-11-17.md`, `docs/THUMBNAIL_PACK_RESEARCH_2026-11-17.md`, `CHANGELOG.md` |
| `QuotaExceededError` says what it does and does not know: two allowances, and the API does not say which one ran out | `pipeline/quota_handler.py` |
| The channel registry describes both allowances | `pipeline/channels.py` |
| Long-form receipts record `caption_track: ok\|failed` — the 400-unit call that was invisible | `pipeline/upload.py`, `pipeline/run.py` |
| New monitor row **`api budget`**: the window priced from the receipts and the ledger, severity `ok` | `scripts/automation_monitor.py` |

Nothing was throttled, re-priced in code, or switched off. The prices are facts
about Google's API; the only behaviour change is that a long-form receipt now
says whether its caption track landed, and the monitor now totals the spend
instead of leaving it to four documents to disagree about.

## Unproven

- **Which allowance is really running on the ten projects.** The quota page says
  100 uploads a day; the receipts are consistent with that and with an approved
  extension. Only the Cloud Console knows: **APIs & Services → YouTube Data API
  v3 → Quotas & System Limits**, per project. Nothing in this repository can read
  it.
- **Whether Google's part-cost line and method-cost line are additive.** The docs
  price the call at 50 and the `snippet` part at 2; whether a call is billed 50 or
  52 does not change any decision here, and no measurement in this repo could
  resolve it.
- **Whether the captions are worth 400 units each.** 59,600 units have gone into
  149 Short caption tracks. Nothing measures whether a captioned Short is watched
  longer, because `content/analytics/` holds no retention data and the Analytics
  permission is not granted on the channels.
- **That the reply engine's cap is affordable.** 1,200 units a day is 12% of a
  pool that also pays for captions; the busiest measured day (15 November, 30
  replies, 1,500 units) is 15%. No run has ever been refused for pool exhaustion,
  so this is arithmetic, not an incident.

## Owner-only

- Read one project's **Quotas & System Limits** page. It settles the model in a
  glance and takes a minute; nothing else in this repository can.
- Decide the **caption policy** — a track on every Short (2,400 units a day at
  current volume) versus the long-forms only, which are the videos that need
  searchable text.
- Decide the **reply cap** against the real price. It is 24 a day per channel now;
  at 50 units each that is 12% of the shared pool, and it competes with captions.
- Whether to keep **`videos.update` retrofits** on the monitor's three-hourly
  pass: 390 of 394 receipts are stamped, so it costs ~4 × 51 units a pass — small,
  but it will re-pay that forever for the four that never converge.

## One next step

Open the `api budget` row of tomorrow's monitor and read the per-upload figure
(**210 today**). If it climbs, a caption track landed that nobody expected; if it
falls, one stopped landing. Both are visible for the first time, in one line,
without trusting any of the four documents this reading corrected.
