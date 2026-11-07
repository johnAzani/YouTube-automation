# Why the automation is red: cron delivery, the model roster, and quota arithmetic

**Measured 7 November 2026, 08:00–09:40 WAT. Rounds 1 and 2.** Every number below
comes from this repository — the Actions API, the supervisor's own ledger, the run
annotations, and the code that runs — not from a vendor blog. Where a source is
external it is cited in §11 and §16.1.

> **Newest (§63):** the free engine is already installed. `pipeline/tts.py` falls back
> Gemini → **edge-tts** (free, no key) → placeholder, and `edge-tts>=6.1` is a declared
> dependency. But `run.py:251` routes every faith script to `prayer_pipeline`, which calls
> Gemini directly with **no fallback at all** — so the one branch that would catch the
> live "returned no audio content" error is unreachable. A three-line `except` publishes
> tonight at $0.
>
> **Corrected in §56:** the empty `200` and the `429` are *not* one condition. On
> 6 November the day was nineteen minutes old and had spent nothing when the first
> `200`-with-no-audio arrived. Empty audio is its own defect — and it still counts as a
> request, which is how two of them plus a Short become a day's quota. §54–§60 also find
> the root cause: **25 of 27 queued scripts declare no channel at all**, so a script the
> brain writes for prayer3 is published as secret-place, and nothing in `verify_and_stage`
> checks.
>
> **The one-paragraph version (§53):** prayer3 has no scripts, so the coverage test can
> never be satisfied, so the supervisor dispatches `produce.yml -f channel=prayer3` on
> every pass; each pass re-renders the same 882-word narration against a **10-request
> per day** speech budget; when the budget is gone the endpoint returns 200 with no
> audio and the pipeline reports "SDK drift, set GEMINI_TTS_MODEL"; and the health job
> fails on the parity assertion and skips the step that would file the issue. Produce
> has not succeeded since 5 Nov 13:14Z.
>
> **§42–§48 reproduce the central claims by execution** — the supervisor's own
> functions, driven with a synthetic run list, build `gh workflow run produce.yml -f
> channel=prayer3`, and its ledger counter goes 1-2-3-1 from one stale checkout.
>
> **Read §31–§40 if you read nothing else.** Round 4 found the two things that
> decide whether fixing narration actually helps: the channels have published **nine
> long-form videos in ten days** against a plan of six a day (§31), and the
> supervisor's "was this slot served?" test requires a receipt from a provisioned
> channel that has **no scripts at all**, so `produce` is dispatchable on nearly every
> pass and will move onto that empty channel the moment the others recover (§32).
>
> **Read §13 first if you only read one section.** Round 1 (below, §0–§12) counted
> *scheduled* deliveries and concluded the scheduler was the problem. Round 2
> (§13–§21) pulled every run rather than every scheduled run and found that **~350 of
> this repo's ~450 daily runs are watchers triggering each other**, that the dispatch
> ledger silently resets its own attempt counter, and that the narration failure the
> channels are red for today is a *fourth*, undocumented failure mode. Round 1's
> numbers are still correct; they are simply not the largest term.

Scope: the three failures that turned the board red this week (produce, gemini_brain,
automation-health), the watchdog that reports them, and the schedule those three
believe they run on.

---

## 0. The one-paragraph answer

GitHub delivers this repository's cron events **1–8 hours late and drops 10–85 % of
them**, so the wall-clock schedule printed in every workflow comment is fiction. The
supervisor compensates, but it is itself cron-driven and was delivered 17 times in 12
days out of ~96 due. When the brain finally runs it needs a Gemini call for a channel
with no queue; each channel has **its own project** (confirmed), so the 500-request
lite pools have 6–25× headroom and are not the constraint — but the two fallback models
are **20 requests/day per channel**, and the retry policy can spend **25 requests and 9
minutes on a single logical call**, which is more than a 20-request day and more than
the 30-minute job timeout can absorb across the 8 logical calls one supply pass may
attempt. The pass is therefore **killed before
it can report**, and the annotation says *"nothing in content/queue can publish"*.
That is the truth of the symptom and none of the cause.

---

## 1. Method

| Source | Endpoint / file | Sample |
| :--- | :--- | :--- |
| cron delivery | `GET /repos/{repo}/actions/workflows/{wf}/runs?event=schedule` | 12 days, 10 workflows |
| run timing | `created_at`, `run_started_at`, `updated_at` per run | 30 runs/workflow |
| failure reasons | `GET /repos/{repo}/check-runs/{job}/annotations` | every failed brain job since 25 Oct |
| the supervisor's decisions | `content/monitor/dispatched.json` | 23 ledger entries, 2–7 Nov |
| watchdog verdicts | issue #307 body, `content/monitor/schedule-health.json` | 6–7 Nov |
| code | `pipeline/gemini_brain.py`, `pipeline/supply.py`, `tools/expand_scripts.py`, `.github/workflows/*.yml`, `scripts/scheduler_supervisor.py` | line numbers cited inline |

Run creation time is the right clock for "did GitHub honour the schedule": on every
run sampled, `created_at == run_started_at` to the second, so **no runner queueing is
involved** in the lateness — the scheduler itself is hours behind.

---

## 2. Finding 1 — the cron line is a wish, and the delivery numbers are brutal

Declared crons compared with what actually arrived over 12 days:

| Workflow | Declared | Delivered | Median delay | p90 | Worst |
| :--- | :--- | ---: | ---: | ---: | ---: |
| `gemini_brain.yml` | 1/day (03:14Z) | **8/12 (67 %)** | **+457 min** | +460 | +468 |
| `produce.yml` | 3/day (06:14, 14:14, 19:14Z) | 32/36 (89 %) | +240 min | +400 | +478 |
| `comments.yml` | 3/day | 25/36 (69 %) | +215 min | +410 | +468 |
| `automation-health.yml` | 1/day (20:14Z) | **5/12 (42 %)** | +278 min | +283 | +362 |
| `growth-autopilot.yml` | 1/day (02:14Z) | **2/12 (17 %)** | +428 min | +426 | +431 |
| `metrics.yml` | 1/week | 2/2 | +262 min | +237 | +288 |
| `community.yml` | 2/week | 2/3 | +263 min | +216 | +309 |
| `keepalive.yml` | 1/week | 2/2 | +414 min | — | +484 |
| `monitor.yml` | 8/day (`*/3`) | **14/96 (15 %)** | +84 min | +109 | +155 |
| `scheduler-supervisor.yml` | 8/day (`*/3`) | **17/96 (18 %)** | +107 min | +163 | +169 |

Two shapes, both bad, and they are not the same problem:

* **Low-frequency workflows are delivered but hours late, in a very tight band.**
  The brain's 03:14 slot lands at 09:37, 09:59, 10:25, 10:50, 10:51, 10:53, 11:02 —
  seven consecutive days inside 85 minutes. That is a *stable offset of ~7 h 35 m*,
  not jitter, and it is the number the supervisor's own comment already quotes
  (`.github/workflows/scheduler-supervisor.yml:47-49`).
* **High-frequency workflows are mostly dropped.** `*/3` asks for eight events a day
  and receives **1.2 on average** — 15–18 % delivery. The monitor and the supervisor
  are the two things whose job is to notice that nothing ran, and they are the two
  things GitHub is most likely not to run.

Consequence in wall-clock terms, per the user's own timezone: **the "4:14am Nigeria
time" brain run actually lands at 11:50 WAT**, i.e. after the 07:14 slot it exists to
supply, and `produce.yml`'s 07:14 slot lands at 16:12 WAT. The pipeline's *ordering*
survives by accident (everything shifts by roughly the same amount); its *promises*
do not.

---

## 3. Finding 2 — the supervisor is the real scheduler, and it knows

`content/monitor/dispatched.json`, 2–7 November:

| Ledger entry | Dispatched at | Attempts | Result |
| :--- | :--- | ---: | :--- |
| `gemini_brain.yml@2026-11-06T03:14Z` | 14:02Z (**+10 h 48 m**) | 1 | dispatched |
| `gemini_brain.yml@2026-11-07T03:14Z` | 05:39Z (+2 h 25 m) | 2 | dispatched |
| `produce.yml@2026-11-06T06:14Z` | 08:31Z | 5 | "dispatched secret-place; prayer2 next pass (`content-state` takes one pending run)" |
| `comments.yml@2026-11-06T19:14Z` | 20:48Z | 1 | dispatched |

23 ledger entries in 6 days: 9 comments, 6 brain, 4 produce, 2 growth, 1 community,
1 keepalive. **The supervisor, not cron, has been carrying this pipeline**, and its
own delivery rate is 18 %. That is the structural weakness: the backstop runs on the
same scheduler it backs up.

The code already contains the measurements that led here —
`scheduler-supervisor.yml:44-56` documents "median ~57 minutes late, p95 ~3.4 hours,
and the brain's 03:14 slot is delivered at ~10:53 — 7 hours 39 minutes late, every
single day", and widened the recovery window from a flat 6 h to "until the successor
is due" (`_slot_window`, `scripts/scheduler_supervisor.py:164-186`).

---

## 4. Finding 3 — the concurrency group is *not* the starvation (measured, dismissed)

`gemini_brain.yml:24` and `produce.yml` both use `concurrency: group: content-state`,
`cancel-in-progress: false`. Since both are long jobs, this was the obvious suspect.

| Job | Runs | Median | p90 | Max |
| :--- | ---: | ---: | ---: | ---: |
| `gemini_brain.yml` | 30 | 7.0 min | 22.9 | 40.6 |
| `produce.yml` | 30 | 8.5 min | 43.5 | 54.5 |

Lock occupancy is roughly `3 × 8.5 + 1 × 7.0 ≈ 32 min/day` — **2 % of the day**. A
shared lock cannot explain a 7.6-hour delay. It does explain one specific behaviour
worth keeping: `produce` and `brain` can never overlap, which is why the 6 Nov produce
dispatch ran secret-place and deferred prayer2 to the next pass
(`_failed_dispatches` / one-pending-run rule). Keep the group; do not blame it.

**What it does contribute:** a wedged `produce` run holds the lock and blocks the brain
and the supervisor's own dispatches — the comment at `scheduler_supervisor.py:80-93`
records a run that sat `in_progress` for 2.5 h past both its step and job caps and
stalled everything downstream. With `timeout-minutes: 240` on the produce job
(`produce.yml:118`), the worst case is a 4-hour global content freeze.

---

## 5. Finding 4 — what the model layer actually returned

Every failure annotation on every failed brain job since 25 October, by title:

| Annotation title | Count | Meaning |
| :--- | ---: | :--- |
| *(no title — the step exit)* | 40 | "Process completed with exit code 1" |
| **Gemini service unavailable** | **18** | 503 after all retries (`scripts/gemini_brain.py:256`) |
| **Gemini call failed (GitHub Actions)** | **16** | non-retryable API error |
| **Gemini text model retired** | **8** | 404 on `2.5-flash` (11 mentions) and `2.0-flash` (8) |
| **Long-form supply empty** | **4** | "nothing in content/queue can publish" |

Models named inside failure text: `gemini-3.8-flash` **29**, `gemini-2.5-flash` 11,
`gemini-2.0-flash` 8. `gemini-3.8-flash` — a **20-request-per-day** model — is the one
the chain hits hardest, because it is the last live model before the retired ones.

One more detail from the same summary, and it is the one that made the outage
unreadable: the chain starts at `gemini-3.5-flash-lite` (no workflow sets
`GEMINI_TEXT_MODEL`), and its answer never appears in the log at all. An empty
response hit `if not text: continue`, which printed nothing and recorded nothing. The
first visible line is therefore model **two**. A silent first model plus three retired
models means the log describes five attempts while seven were made.

Date shape: 6 November carries 33 failures + 18 service-unavailable + 15 call-failed
(the afternoon outage); 7 November carries 8 retired + 4 supply-empty (the prayer3
morning). The two are different events that produced the same annotation.

---

## 6. Finding 5 — the arithmetic that guarantees failure

### 6.1 The free-tier roster

| Model | RPM | RPD | Position in our chain |
| :--- | ---: | ---: | :--- |
| `gemini-3.5-flash-lite` | 15 | **500** | primary (`DEFAULT_TEXT_MODEL`) |
| `gemini-3.1-flash-lite` | 15 | **500** | fallback 1 |
| `gemini-3.6-flash` | 15 | **20** | fallback 2 |
| `gemini-3.8-flash` | 15 | **20** | fallback 3 |
| `gemini-3.7-flash` | routed → 3.8 | 20 | deprecated alias |
| `2.5 / 2.0 / 1.5-flash` | — | **0 — retired** | removed from the chain by this branch |

Quotas are **per project *and* per model**; a second API key in the same Google Cloud
project does not add allowance — so whether the three keys share a project decides
every arithmetic question in this section.

> **Confirmed by the owner, 7 November 09:55 WAT: the three keys are in three separate
> Google Cloud projects.** `gemini_brain.yml:33-35` ("its own Gemini quota pool") is
> therefore accurate, and the rest of this section is rewritten for that fact.

Per-channel allowance, per day:

| Resource | Per channel per day | Consumed by a declared day | Headroom |
| :--- | ---: | ---: | --- |
| `3.5/3.1-flash-lite` text | **500** | ~20–80 requests (see 6.2) | **6–25×** |
| `3.6/3.8-flash` text | **20** | one bad logical call = 25 | **negative** |
| TTS `3.8-flash-tts` | **10** | 9 (see 6.4) | **1 request** |

Two consequences, and they point in opposite directions:

* **The 500-RPD pool is not the constraint.** Even two processes per pass at the
  40-request ceiling is 80 of 500 — 16 %. Quota exhaustion on the lite models cannot
  explain a week of failures.
* **The 20-RPD pools are the trap.** A single 503-heavy logical call spends 25 requests
  (6.2). That is 125 % of `3.8-flash`'s *entire day* for that channel, and 125 % of
  `3.6-flash`'s. One busy minute removes both fallback models until midnight Pacific,
  which is precisely why `gemini-3.8-flash` is named 29 times in the failure text and
  why the retry storm feeds itself.

### 6.2 The retry policy

`pipeline/gemini_brain.py:236` — `_TRANSIENT_BACKOFF = (5, 15, 30, 60)`: five attempts
per model, 110 s of sleeping, no jitter. The SDK's own retry is disabled (`attempts=1`,
`pipeline/gemini_client.py`) so these numbers are the whole truth.

| Quantity | Value |
| :--- | ---: |
| Requests per model, worst case | 5 |
| Sleep per model, worst case | 110 s |
| Live models in the chain | 5 |
| **Requests per logical call, worst case** | **25** |
| **Wall clock per logical call, worst case** | **9 min 10 s** |
| Per-pass request ceiling (`MAX_CALLS_PER_RUN`) | 40 |
| **Logical calls before the ceiling trips** | **1.6** |
| Job timeout (`gemini_brain.yml:59`) | 30 min |
| **Logical calls before the runner kills the job** | **~3.2** |

Now the demand side, from `pipeline/supply.py`:

| Constant | Value | Effect |
| :--- | ---: | :--- |
| `MAX_EXPANSIONS_WHEN_EMPTY` | 5 | up to 5 lengthening jobs |
| `MAX_AUTHORS_PER_RUN` | 2 | up to 2 authored scripts |
| `MAX_ATTEMPTS` in `tools/expand_scripts.py` | 3 | ×3 model calls per lengthening job |
| `min-publishable` demanded by the workflow | **6** | `gemini_brain.yml:97` |
| `SLOTS_PER_DAY` | 3 | the number the target is derived from |

An empty queue (`prayer3` today) makes `ensure_supply` raise `limit` to 5 expansions
plus 2 authors — **up to 8 logical calls against a ceiling of 3.2 before timeout**.
On a quiet service that fits; on a busy one it is arithmetically impossible, and the
failure is a *killed job*, which leaves no verdict beyond "supply empty".

### 6.3 The 20-request trap

One 503-heavy logical call spends 25 requests. That is:

* **125 % of a 20-RPD model's entire day** — one busy call removes `3.8-flash` and
  `3.6-flash` from the chain until midnight Pacific;
* 5 % of a 500-RPD model, i.e. three channels × two processes can spend 240 of 500 in
  a night before `produce`'s own repair pass (which asks for 3 publishable, 3×/day).

This is why `3.8-flash` appears 29 times in failure text and why the wording of the
retired-model errors ("please update your code to use models/gemini-3.8-flash") is a
trap: the model Google recommends is the one with 4 % of the lite model's allowance.

### 6.4 The TTS side has the same shape

`pipeline/gemini_tts.py:84-102`: 10 requests/day **per project**, 4,000-character
chunks. Measured on the queue that exists right now (27 scripts, front matter and
headings stripped):

| Script size | Scripts | TTS requests |
| :--- | ---: | ---: |
| 4,646–7,994 chars (min 4,646, median **5,330**) | 25 | **2** |
| 9,039 chars | 1 | 3 |
| 26,033 chars (`0007-the-day-the-exchange-pressed-undo`) | 1 | 7 |

Shorts: caption text median **697** chars (max 1,003) → **1** request.

Now the day, per channel, at the declared three slots (each produce run renders one
long-form *and* one Short — `produce.yml:255-280`):

```
3 × long-form (2 requests)   = 6
3 × Short    (1 request)     = 3
                              ---
total                        = 9 of 10      → exactly one retry for the whole day
```

One script over 8,000 characters makes it 10 of 10 — zero margin. Two, or one transient
failure, makes it 11 and the third slot pauses itself. That is Issue #311 verbatim,
6 Nov 23:52Z: *"Gemini's free-tier TTS allowance (10 requests/day) is spent until
2026-11-07T08:00:00+00:00 UTC. The next slot after that will publish."* The reset is
midnight Pacific (08:00Z in November = 09:00 WAT).

So TTS is not oversubscribed by the schedule — it is subscribed to **90 %**, and the
remaining 10 % is the only thing standing between a normal day and a paused slot. Every
narration retry is paid out of that last request; the 13-request chunking bug (three
days ago) spent the whole day on one video.

---

## 7. Finding 6 — the causal chain, with timestamps

Saturday 7 November, all UTC:

```
03:14  gemini_brain.yml's slot (04:14 WAT).                            no run exists
05:39  supervisor dispatches it — ledger attempts=2                     run 42345045418
05:54  brain, prayer3, chain as the job summary shows it:
         3.5-flash-lite  → returned nothing (silent: the loop `continue`d
                           on an empty answer without printing — fixed here)
         3.1-flash-lite  → text, but no `## Scene` heading
         3.6-flash       → 503 busy, then text with no YAML envelope
         3.8-flash       → 503 UNAVAILABLE through 5/15/30/60 s
         3.7-flash       → 503 UNAVAILABLE through 5/15/30/60 s
         2.5-flash       → 404 NOT_FOUND (retired)
         2.0-flash       → 404 NOT_FOUND (retired)
         1.5-flash       → 404 NOT_FOUND (retired)
       → "nothing in content/queue can publish"                 exit 1, 7 min
06:38  monitor files issue #307: "Nothing can publish right now"   (07:38 WAT)
06:39  manual re-dispatch (the screenshot)                            same result
07:00  manual re-dispatch                                             same result
06:14  produce's morning slot (07:14 WAT) — no run created by 08:40Z yet
```

Three red workflows, one cause, and the cause was reported as a content problem.

---

## 8. Finding 7 — three blind spots in the retry logic

1. **The supervisor cannot see a quota or a content failure.**
   `UPSTREAM_MARKERS` (`scheduler_supervisor.py:358-359`) is
   `("service unavailable", "503", "high demand", "upstream capacity", "unavailable —",
   "deadline exceeded", "timed out")`. It does **not** include `quota`,
   `resource_exhausted`, `busy after retries`, `supply empty`, or `no candidate model`.
   A 429-shaped failure is retried only if `code_changed_since()` fires; a supply
   failure is not retried at all — the ledger marks the slot served by a run that
   failed.

2. **The attempt budget renews on a code hash that includes `pipeline/` and `scripts/`**
   (`_CODE_ROOTS`, line 187) — good: this branch's fix will renew `03:14` for today.
   But the renewal only helps if the supervisor itself is *delivered*, which brings us
   back to Finding 1.

3. **Parity has no cold-start concept.** `scripts/channel_parity.py` fails because
   `prayer3` has never had a queued script — correct, but indistinguishable from a
   broken channel, and it is what makes `automation-health` red on every push
   (42 % delivery, 5/5 failures). One empty channel currently takes down three
   workflows' signal.

---

## 9. Design options, ranked by effect per unit of risk

Nothing here spends money; all of it is `$0`-lock compatible.

> **Superseded order.** §20 re-ranks these after the Round 2 measurements. R1 and R2
> shipped; the next three are R8 (TTS forensics), R9 (break the watcher loop) and R10
> (an honest dispatch ledger), because §13–§15 show the per-day multiplier matters more
> than the per-pass budget. The entries below are kept for their reasoning.

### R1 — Make the retry budget honest — **implemented, `57367ca`+**

Cap **total** transient wait per pass, not per model: e.g. 6 requests / 3 minutes of
sleep, with jitter (`5 + U(0,5)`, `15 + U(0,10)`, …), and stop trying a model after 2
attempts when its RPD is 20. Fail with the per-model outcomes already produced by this
branch (`_authoring_failure`) instead of being killed at 30 minutes.
*Effect:* the job always reports a reason; ~60 % less wall clock on a 503 morning.
*Verify:* `tests/test_brain_authoring_resilience.py` extended with a time-budget test.

**As built** (the numbers below replace the 25-request / 9m10s worst case):

| Rule | Before | After |
| :--- | ---: | ---: |
| Attempts per 20-RPD model | 5 | **2** |
| Attempts per 500-RPD model | 5 | **3** |
| Requests per logical call | 25 | **11** |
| Sleep per logical call | 550 s | **45–55 s, jittered ±20 %** |
| Sleep per *pass* (all models, all calls) | unbounded | **120 s, then the pass reports** |

The per-pass budget is the important half: the old policy was frugal per model and
ruinous in aggregate, which is how a 30-minute job died without a verdict. The failure
now ends with "the pass spent its whole 120 s backoff budget on 503s; a later slot has a
different capacity moment", which is also the sentence that tells a human to wait rather
than re-dispatch.

### R2 — Teach the supervisor the words it is missing — **implemented**

Add `quota`, `resource_exhausted`, `busy after retries`, `no candidate model`,
`supply empty` to `UPSTREAM_MARKERS`, and treat "supply empty" as downstream-fixable
(dispatch produce's repair path rather than the brain again).
*Effect:* a 429 at 05:39 is retried at 09:47 instead of losing the day.
*Risk:* retry storms — bounded already by `UPSTREAM_RETRY_AFTER = 30 min` and
`UPSTREAM_MAX_ATTEMPTS = 8`.

**As built:** `quota`, `resource_exhausted`, `rate limit`, `busy after retries` were
added. `no candidate model` and `supply empty` were deliberately *not* added — they wrap
every authoring failure, including the deterministic ones (retired model, wrong
branding, missing envelope) that a retry cannot fix and where `code_changed_since` is the
correct lever. `tests/test_watchers_do_not_ping_pong.py` pins both directions.

### R2a — Reserve the TTS margin (code, ~15 lines)

With 9 of 10 requests committed, nothing may spend the last one casually. Count the day's
narration requests in the receipt/ledger and refuse a *retry* when it would cross the
allowance, deferring to the next slot instead of pausing mid-render. Cheapest possible
form: read `content/monitor/tts-usage.json` before `synthesize_gemini_audio`.

### R3 — A per-model usage ledger (code, ~80 lines) — now per project, so it works

`content/monitor/model-usage.json`: `{date_pacific: {model: requests}}`, incremented in
`_call_model`, consulted by `text_model_candidates`. Skip a 20-RPD model once it has
spent 18. Reset keyed on midnight Pacific, the same clock Google uses.
*Effect:* stops burning 3.8/3.6 on retries that cannot succeed; makes the daily budget
observable in a file a human can read. With three separate projects this is a *per-channel*
budget of 20 — one 25-request logical call still wipes it, which is why R1 (fewer attempts
per pass) and R3 belong together.

### R4 — Take the supervisor off GitHub's scheduler (config, zero code, needs the owner)

`repository_dispatch: types: [watchdog-tick]` already exists in the workflow. A free
external cron (cron-job.org, a VPS timer, a Cloudflare Worker) POSTing the dispatch API
every 15 minutes turns 1.2 deliveries/day into 96. Cost: one fine-grained PAT with
`Actions: write`. This is the single highest-leverage change on the board, and it is
also the only one I cannot do: the token is yours.

### R5 — Cold start for a new channel (code + content, medium) — **now the top content blocker**

`--min-publishable 6` cannot be satisfied by one pass (`MAX_AUTHORS_PER_RUN = 2`), so
`prayer3` needs **three successful passes** to reach parity. Either (a) the brain
should accept `--min-publishable 2` for a channel with `publishable_before == 0` and
say "cold start: 2 of 6", or (b) author the first three Midday Watch scripts in one
sitting for owner approval. The content is brand voice, so (b) needs your read; (a) is
pure policy.

### R6 — Refuse to publish outside a brand window (code, ~30 lines)

`produce` delivered at 16:12 WAT will publish a *morning* edition. Add a local-hour
guard: a `sunrise` channel may only publish 04:00–11:00 WAT, `midday` 11:00–15:00,
`night` 19:00–01:00; otherwise defer with a receipt note. The content is evergreen but
the *promise* ("begin your day with us") is not.

### R7 — Do nothing about cron, and say so (documentation)

Every workflow comment states a wall-clock promise that GitHub does not keep. Either
keep them as intent (and mark them "intent, delivery ±8 h") or delete the times. The
watchdog's `alarm_minutes: 240` in `schedule-health.json` is already below the observed
brain delay (457 min), so it alarms every day by construction.

---

## 10. Predictions to check

After this branch merges (it changes `pipeline/`, so `code_fingerprint` changes):

1. At the supervisor's next delivery, the ledger should gain
   `gemini_brain.yml@2026-11-07T03:14Z` with `attempts: 3` and a new `code_id`.
   Check: `git show main:content/monitor/dispatched.json | grep 11-07T03:14`.
2. That run should show `busy after retries` / `retired (404)` **nowhere**, and either
   an accepted script or a per-model failure list.
3. If the run still fails on 503 for all five live models, the free tier is saturated at
   that hour — the answer is R3 + R4, not more models.

---

## 11. Sources

**Measured in this repository (primary):** Actions API run history and annotations,
`content/monitor/dispatched.json`, `content/monitor/schedule-health.json`, issue #307,
issue #311, and the code cited by line above.

**GitHub scheduled-workflow behaviour:**
`https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule`
— "The schedule event can be delayed during periods of high loads… High load times
include the start of every hour… some queued jobs may be dropped"; 5-minute minimum;
schedules only run on the default branch; disabled after 60 days of inactivity in a
public repo. Independent measurements agree with ours in shape: 64 % of 15-minute
slots delivered with a 7.4-minute median delay in October 2026 (hyperping.com), and
"consistently delayed 8–14 hours, one day dropped entirely" (will-github-run-my-cron).
GitHub's own `actions/runner-images` workflow started 1 h 39 m late on 4 October 2026.

**Gemini free-tier limits and retry guidance:**
Google's troubleshooting guide (`ai.google.dev/gemini-api/docs/troubleshooting`) —
exponential backoff **with jitter** for 429/503; the Python SDK retries 4× from ~1 s up
to 60 s by default. AI Studio rate-limit page (2026-10-23): 500 RPD for
`3.5-flash-lite` / `3.1-flash-lite`, 15 RPM; 20 RPD for `3.8-flash` / `3.6-flash`.
Quotas are per project **and model** — "creating another API key in the same project
does not double the allowance". RPD resets at midnight Pacific. A community measurement
on 6 November 2026 (AI4RA/promptulus #33) found 3.8-flash "many 503s, some requests
hung past 2 minutes" against 1 503 in 107 requests on 3.5-flash-lite.

**Round 2 additions:**

**Empty candidate semantics (the `mime_types=none` failure):**
`https://ai.google.dev/api/generate-content` — an empty `candidates` list arrives with
HTTP 200 when an input or output safety stage blocks the request or generation fails;
`candidates[0].finish_reason` and `response.prompt_feedback.block_reason` are the fields
that distinguish them, and a filtered request is still billed for prompt tokens.
Corroborated by two 2026 fixes with the same diagnosis: `harry0703/MoneyPrinterTurbo`
#1721 (28 Oct 2026) — "when Gemini TTS returns no audio, the current error omits the
provider's finish reason or prompt-block reason… log `finish_reason` and
`prompt_block_reason` before returning failure" — and `tetsuo-ai/agenc-core` #2106,
"Gemini responses with a prompt-level block and no candidates are parsed as successful
empty completions".

**Gemini 3.8 TTS request shape and limits:**
`https://ai.google.dev/gemini-api/docs/speech-generation` — the documented call is
`client.interactions.create(...)` with `input=[{"type": "user_input", "content":
[{"type": "text", "text": …, "annotations": [{"type": "speech_metadata", "style": …}]}]}]`,
`response_format={"type": "audio"}`, `generation_config={"speech_config": [{"voice": …}]}`;
the part `text` is a **verbatim transcript** and `style` is a short attribute list
("whispering", "out of breath"), not prose; unary requests return complete
`audio/wav` (24 kHz mono 16-bit) rather than headerless PCM. Model card,
`https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash-tts` — **input 8,192
tokens, output 16,384 tokens** (serving limit), last updated September 2026, plus
`gemini-3.8-flash-lite-tts` as the throughput alternative. A third-party integration
(`mozilla-ai/any-llm` #1574, 2026) notes it could not verify live that
`Part.speech_metadata.style` is honoured by `generateContent` — so "styled but silent"
is a shape this codebase should be able to distinguish from "blocked".

**GitHub concurrency semantics:**
`https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency`
— by default a group admits one running and **one pending** run; a newly queued run
replaces the pending one (`queue: single`), which is why the loop of §13 also produced
300 cancelled Pages builds.

---

## 12. Open questions only the owner can answer

1. ~~Are the three keys in separate projects?~~ **Answered 7 Nov: yes, three separate
   projects.** Per-channel pools are real; the 500-RPD pool is not the constraint and
   the 20-RPD pools are the trap (§6.1).
2. **Is the channel YPP-approved?** `thumbnails.set` needs it (§ Shorts work).
3. **Will you add an external 15-minute tick** (R4)? It needs a PAT with `Actions:
   write`; it is the only change that fixes the root of Finding 1.
4. **Brand windows** (R6): should a morning edition be withheld if it lands at 16:12 WAT?
5. **TTS margin** (R2a): accept *deferral* rather than *pause* when the day's tenth
   request would be spent on a retry? That is a product decision (a late video) not a
   technical one.

---

# Round 2 — the telemetry, read to the thinnest detail

Round 1 counted cron deliveries and annotations. That was the wrong grain: it measured
the *scheduled* firings and concluded the scheduler was unreliable. Pulling every run
between 2 and 7 November instead shows that **most of this repo's runs are not
scheduled at all** — they are triggered by each other. The scheduled drop is real, but
it is the smaller half of the story, and the larger half is self-inflicted.

Everything below comes from the Actions API, the commit history and the run
annotations, not from inference:

```
gh api repos/johnAzani/YouTube-automation/actions/workflows/<id>/runs
gh api repos/johnAzani/YouTube-automation/check-runs/<job>/annotations
gh api repos/johnAzani/YouTube-automation/commits?since=...
```

## 13. Finding 8 — the watchers are running 350–450 times a day, and most of
## those runs are caused by the watchers

Whole-repo run counts, all workflows, including cancelled ones:

| Day | Workflow runs |
| :--- | ---: |
| 5 Nov | 514 |
| 6 Nov | **912** |
| 7 Nov (to 08:45Z) | 179 |

Per workflow since 2 November (the day the current monitors were merged):

| Workflow | Runs | Per day | Scheduled runs in that window |
| :--- | ---: | ---: | ---: |
| `scheduler-supervisor.yml` | 970 | ~187 | 8/day requested |
| `monitor.yml` | 859 | ~165 | 8/day requested |
| `automation-health.yml` | 110 | ~21 | 1/day requested |
| `produce.yml` | 106 (since 21 Oct) | 3–12 | 3/day requested |
| `gemini_brain.yml` | 35 (since 30 Oct) | 1–19 | 1/day requested |

**870 of the supervisor's 970 runs and 768 of the monitor's 859** were `workflow_run`
triggers, not cron. The supervisor received **17 of the ~42 cron events** it asked for
since 2 November (40 %), which is Round 1's finding reproduced — it is just no longer
the reason it runs so often. In the 24 hours from 6 Nov 08:00Z:

| Trigger | Supervisor | Monitor |
| :--- | ---: | ---: |
| `workflow_run` (another workflow finished) | 254 | 155 |
| `push` | 27 | 27 |
| `schedule` | 3 | 3 |

Median gap between supervisor runs in that window: **1.2 minutes**. p90: 8.1 minutes.
It ran 50 times in the 08:00 hour and 46 times in the 09:00 hour.

### 13.1 The chain, proved from `head_sha`

Every supervisor run's `head_sha` is the default-branch commit it checked out, so the
commit message names what caused it. Sample from 04:00–05:00Z on 7 November:

```
04:16:57 supervisor  be31781  chore(monitor): record dispatched slots and scheduler health
04:18:13 supervisor  84ff97f  chore(monitor): automation status snapshot & live thumbnail sync
04:18:47 supervisor  84ff97f  chore(monitor): automation status snapshot & live thumbnail sync
04:38:20 supervisor  1fdaa2d  chore(monitor): automation status snapshot & live thumbnail sync
04:38:33 supervisor  1fdaa2d  chore(monitor): automation status snapshot & live thumbnail sync
04:38:54 supervisor  1fdaa2d  chore(monitor): automation status snapshot & live thumbnail sync
04:41:12 supervisor  c822abd  chore(monitor): automation status snapshot & live thumbnail sync
04:55:23 supervisor  2db15e1  chore(monitor): automation status snapshot & live thumbnail sync
```

Not one of them is a code commit. They are **telemetry commits written by the other
watcher**, and they close a loop:

1. a supervisor pass or a monitor pass writes `content/monitor/*.json` and commits it;
2. the push triggers `pages build and deployment` — Pages is not a workflow and is
   *not* suppressed by the `GITHUB_TOKEN` rule that stops bot pushes from starting
   `on: push` workflows;
3. the Pages build completing fires `scheduler-supervisor.yml`, because its
   `workflow_run.workflows` list contains `pages build and deployment`;
4. the supervisor writes its own `schedule-health.json`, which contains a fresh
   `generated_at`, so `git diff --staged --quiet` is **never** true and it always
   commits;
5. go to 2.

The loop needs no cron, no user and no failure. It sustains itself at roughly one
supervisor run per minute for hour-long bursts. In 24 hours it produced:

| Artefact | Count |
| :--- | ---: |
| Commits to `main` | 385 |
| …of which `chore(monitor): record dispatched slots…` | 174 |
| …of which `chore(monitor): automation status snapshot…` | 130 |
| Pages builds | 353 (300 cancelled, 47 success, 6 failure) |
| CI runs | 95 (67 push, 28 pull_request), 72 failed |

`content/monitor/status.json` and `content/monitor/schedule-health.json` both stamp
`generated_at: datetime.now(...)` (`scripts/automation_monitor.py:115`,
`scripts/scheduler_supervisor.py:651`). A wall-clock field inside a committed file is a
commit generator: the "did anything change?" test can never pass.

### 13.2 Why 300 Pages builds were cancelled

`concurrency` defaults to `queue: single` — at most one running and one pending
member per group; a newly queued run *replaces* the pending one. Every supervisor run
that arrives while another is running cancels the queued one (57 of 284 in 24 hours;
88 of 174 on 2 November). So the loop does not just run a lot, it also churns the
queue: the runs that get cancelled are the ones that would have done the work, and
the ones that survive are the ones that started earliest, with the stalest checkout.

## 14. Finding 9 — the dispatch ledger is a race, so the cap it enforces does not exist

`scheduler_supervisor.py` is careful: one dispatch per slot, at most `_attempt_cap()`
retries (default 3, 8 for upstream outages), 90 minutes before a slot counts as
missed, a `code_changed_since` escape hatch, and an upstream-outage cooldown. All of
it is stored in one committed JSON file, `content/monitor/dispatched.json`, written
read-modify-write by every pass.

With ~187 passes a day, that file has ~187 concurrent writers that each check out a
*different* commit. The counter therefore does not climb, it **sawtooths**. Actual
`attempts` values for the `gemini_brain.yml@2026-11-06T03:14` slot, in commit order:

```
08:45  1        09:34  1        12:30  1        13:53  4
08:50  2        10:33  2        12:40  2        14:02  1
09:07  3        10:47  3        12:48  3
09:16  1  ←reset 12:30? →  1
09:24  2
09:27  3
```

`1 → 2 → 3 → 1` three times in six hours. A pass that checked out main *before* the
increment wrote its stale+1 over the newer value. Consequences:

* `_attempt_cap()` and `UPSTREAM_MAX_ATTEMPTS = 8` never bind — the counter is
  perpetually small;
* `dispatched.json` on `main` records **one** brain dispatch and **one** produce
  dispatch per day, while the run history shows **19 brain runs and 11 produce runs**
  on 6 November;
* every restart of the counter is a fresh authorisation to dispatch again.

This is the single most expensive bug in the repository, because the thing it fails
to bound is the thing that spends quota.

## 15. Finding 10 — 19 dispatches is not a retry policy, it is a quota fire

Per brain run, the ceilings in `pipeline/supply.py` are:

| Knob | Value | Meaning |
| :--- | ---: | :--- |
| `MAX_EXPANSIONS_WHEN_EMPTY` | 5 | lengthen up to 5 under-floor scripts |
| `MAX_MODEL_CALLS_PER_RUN` | 10 | total expansion calls per run |
| `MAX_AUTHORS_PER_RUN` | 2 | new editions authored per run |
| `--min-publishable` | 6 | runway the pass must leave behind |

An empty queue therefore authorises roughly 10 expansion calls plus 2 authoring
chains in **one** run, and the run is executed **once per channel job**. Worst case
per dispatch, two channels: ~24–40 model requests. The daily allowance for the
20-RPD models (3.6/3.8/3.7-flash, per project) is 20.

`gemini_brain.yml` dispatches on 6 November, all `workflow_dispatch`, all from the
supervisor:

```
08:00:33  08:03:33  08:09:32  08:45:25  08:50:45  09:07:14  09:16:33  09:24:10
09:27:50  09:34:11  10:33:32  10:43:46  10:47:00  10:51:09  12:30:12  12:40:48
12:48:57  13:53:37  14:02:17
```

And the annotations from those runs, verbatim, showing what each attempt returned:

| Time (UTC) | What the run got back |
| :--- | :--- |
| 08:00, 08:03 | `404 NOT_FOUND: models/gemini-2.5-flash is no longer available to new users` |
| 08:45–09:27 | `503 UNAVAILABLE: This model is currently experiencing high demand` |
| 09:34 → 13:53 | `gemini-3.8-flash did not answer after 5 attempts (503 UNAVAILABLE — upstream capacity, not this code)` |
| 14:02 | **success** (queue replenished once the afternoon capacity window opened) |

The 14:02 run proves the outage was capacity, not code — and it took 19 attempts,
six hours of queue churn and most of two projects' daily allowance to arrive at the
one pass that would have worked. This is the mechanism by which a dip in capacity
becomes a whole-day outage: **the retries spend the resource whose exhaustion causes
the retries.** R1 shrank the per-pass spend from 25 requests to 11; it did not touch
the per-day multiplier, which is the dispatch count.

## 16. Finding 11 — "no audio content" is a different failure, and it is the current blocker

The produce leg has been failing at narration since 4 November 20:56Z. The message
has changed three times, and the three messages are three *different* causes that the
code currently reports in the same vocabulary:

| When | Message | What it actually is |
| :--- | :--- | :--- |
| 5 Nov 08:38 | `400 INVALID_ARGUMENT: Developer instruction is not enabled for this model` | a request *shape* the model refuses (system instruction) |
| 6 Nov 08:05, 08:10 | `400 INVALID_ARGUMENT: Invalid JSON payload … Unknown name "speechMetadata"` | SDK/API contract drift (`google-genai 3.0.0`, shipped 02:29 UTC) |
| 4 Nov 20:56 · 5 Nov 09:41, 09:46, 14:39 · 6 Nov 08:24, 08:28 · **7 Nov 08:29, 08:46** | `RuntimeError: Gemini API returned no audio content for model gemini-3.8-flash-tts (mime_types=none)` | **HTTP 200, zero audio parts** — a refusal or a generation failure, reported as neither |
| 5 Nov 00:26 · 6 Nov 08:36 | `429 RESOURCE_EXHAUSTED` → `GeminiQuotaExceededError`, job paused | the allowance is gone |

The last row is the only one the code handles well. The third row is what is failing
*today*, and it fails in **4.6–7.5 seconds** — not a timeout, not a rate limit, not a
quota pause. `pipeline/gemini_tts.py` walks its candidate parts, finds no
`inline_data`, prints `mime_types=none`, and raises. It never inspects
`candidates[0].finish_reason`, and never inspects `response.prompt_feedback`, so the
one field that would say *why* (blocked input? blocked output? MAX_TOKENS? an internal
generation failure?) is discarded.

### 16.1 What Google documents about an empty response

Three facts from the TTS and `generateContent` documentation decide the fix:

1. **An empty `candidates` list is not an error.** The API returns HTTP 200 with a
   valid response object and no candidates when a safety stage blocks the input or the
   output, or when generation itself fails. `finish_reason` on the candidate and
   `prompt_feedback.block_reason` on the response are the two fields that distinguish
   them.
2. **Filtered requests are still charged.** A blocked/empty response bills prompt
   tokens. So every one of those 5-second failures consumed one of the day's ten TTS
   requests.
3. **`gemini-3.8-flash-tts` has an 8,192-token input limit and a 16,384-token output
   limit** (model card, "Gemini API serving limit"). The output limit is the one that
   matters here: the audio *is* the output, so a request can only narrate as much as
   16,384 audio tokens will hold.

The documented call shape is `client.interactions.create(...)` with
`input=[{"type": "user_input", "content": [{"type": "text", "text": …, "annotations":
[{"type": "speech_metadata", "style": "calm and reverent"}]}]}]`,
`response_format={"type": "audio"}`, and `generation_config={"speech_config":
[{"voice": "Charon"}]}`. That is what the code's primary path does. The code's
*fallback* path (`models.generate_content` with `response_modalities=["AUDIO"]`) is
the older schema — and the docs are explicit that Gemini 3.8 TTS treats the part
`text` as a verbatim transcript and expects style as a **short attribute list**
("whispering", "out of breath", "mature and calm"), not a paragraph of direction.
`style_text()` returns whatever `prompt_style` the caller passes, so the length of
that string is a live variable nobody has measured.

### 16.2 The arithmetic of a ten-request day, with retries

At `DEFAULT_CHUNK_CHARS = 4000`:

| Item | Words | Characters | Requests | Notes |
| :--- | ---: | ---: | ---: | :--- |
| Long-form `0034` Psalm 91 | 1,039 | 5,886 | 2 | |
| Long-form `0035` Psalm 23 | 1,089 | 6,146 | 2 | |
| Long-form `0015` (paused) | 929 | 5,535 | 2 | |
| A Short | ~110 | ~700 | 1 | |
| **Per day, 3 slots × 2 channels** | | | **6 + 3 Shorts = 9** | one spare request |

One spare request is not a retry budget. It is a coin flip. And because an empty
response is *charged*, a single failing chunk can burn the spare and the next slot's
first chunk with it — which is precisely what the `quota_paused` Short `0015` records.

The 16,384-token output cap implies roughly **8.5 minutes of speech per request**
(at Google's ~32 audio tokens/second — an estimate, not a documented figure). Every
long-form in this queue is **6.2–7.3 minutes at 150 spoken words per minute**, which is
also an estimate, and both are cheap to confirm with one probe call.
So the 4,000-character chunk is a *quota* choice, not a technical one, and it is
currently spending two requests where one would fit. A duration-aware chunker —
cap the estimated audio at ~7 minutes and refuse to exceed 16,384 tokens — turns the
day into **3 long-form requests + 3 Short requests = 6**, leaving **four** for the
retries that R8 needs. That is the difference between "cannot retry" and "can".

### 16.3 What is still unproven

The cause of the empty candidate is not established from here: it could be a safety
stage on the style string, a generation failure under capacity pressure, or a silent
refusal of the `speech_metadata` part by the fallback transport. The point is that
**the code cannot tell us, and one run with `finish_reason` and
`prompt_feedback.block_reason` in the error would.** The 2026 MoneyPrinterTurbo fix
(#1721) did exactly this and is the pattern to copy: report the two metadata fields,
nothing else in the payload, and change no retry behaviour until the cause is known.

## 17. Finding 12 — reading the queue writes to the queue, and that kept CI red

`pipeline/short_release.py:506` — inside `select_next_queued_short()`, a *reader* —
rewrites a manifest with `yaml.safe_dump` and flips `quota_paused` to `approved` when
`quota_reset_utc` has passed. `build_schedule_audit()` called that selector *after*
counting the queue, so its own report described a queue that no longer existed one
line later:

```
[queue] Quota reset time passed (2026-11-07T08:00:00+00:00). Auto-unpausing 0015-short-psalm91v5.yml...
AssertionError: 5 != 6
```

That is the failure CI has been showing on every push since the 08:00Z reset — 72 of
95 CI runs in 24 hours were red — and CI completing is one of the supervisor's
`workflow_run` triggers, **on every branch**. A red test suite is therefore not just
noise: it is another pump in the loop of §13. Fixed in this branch by settling the
queue before counting it, with a test that pins the order rather than the file.

Two structural notes that are *not* fixed, because they are design decisions:

* a read path that writes is how `0015` kept reappearing as `approved` (it was flipped
  three times by automated passes, and reverted by hand each time);
* the unpause is **time-only**: it re-arms a Short whose narration failed, without
  asking whether the day's ten TTS requests can afford it. That is R2a's job.

## 18. Finding 13 — a monitor that is red 96 times a day is not a monitor

In 24 hours the monitor ran 185 times: 35 success, 96 failure, 54 cancelled. Every
failure is *correct* — it is reporting a genuinely stalled automation — and every
failure also writes a commit. The job fails on purpose (`Fail the job if the audit
found a stalled automation`), which means the owner's signal is 96 red X's and one
issue, and the difference between "the pipeline is stalled" and "the monitor is
broken" is invisible in the run list.

The queue-stall constraint says a stalled queue must not look satisfied. It does not
require the *runner* to be red — the issue is the alarm, and the run's exit code is a
poor one: it cannot be distinguished from a crash, and each red run feeds the trigger
loop. The honest split is:

| Condition | Exit | Alarm |
| :--- | :--- | :--- |
| It measured, and something is stalled | 0 | the issue (as today) |
| It could not measure (API down, auth refused, no runs visible) | non-zero | the issue |

Do not change this without the owner: it is the one place where "red" is currently
doing useful work, and it is also the one place where red is most ambiguous.

## 19. The picture in one table

| Layer | Scheduled request | Actual delivery | Verdict |
| :--- | :--- | :--- | :--- |
| GitHub cron → workflows | ~150 events/day | a handful, 4–7 h late | unreliable, and known |
| Watcher self-triggering | 0 | **~350 runs/day** | the dominant traffic |
| Commits to `main` | 0 | **385/day** | self-sustaining |
| Dispatch dedupe | ≤3 attempts/slot | unbounded (counter resets) | **broken** |
| Brain model calls | 20/day/project | ~19 dispatches × 24–40 | **burns the day by 09:00** |
| TTS requests | 10/day/project | 9 committed, 0 spare | **no retry is affordable** |
| TTS failure reporting | names the model | says `mime_types=none` | **cannot diagnose itself** |
| Queue reads | pure | rewrite manifests | **breaks CI, re-arms pauses** |

## 20. Revised ranking (Round 2)

Ordered by *publishing unblocked per unit of risk*, superseding §9's order.

| # | Change | Kind | Why it moves the needle |
| :-- | :--- | :--- | :--- |
| **R8** | TTS: report `finish_reason` + `prompt_feedback.block_reason`, treat an empty candidate as retryable **once**, and chunk by estimated audio minutes (≤7 min / ≤16,384 tokens) | code, ~60 lines | the only thing standing between three queued videos and the channel; also makes the next failure legible |
| **R9** | Break the loop: drop `pages build and deployment` from the supervisor's `workflow_run` list; exclude `generated_at`/`last_run_at` from the "did anything change" test | 2 lines + 1 test | removes ~350 runs and ~300 commits a day; every other fix is cheaper afterwards |
| **R10** | Dedupe dispatches from the Actions API (or an append-only `dispatches/` directory) instead of a read-modify-write JSON | code, ~40 lines | restores the attempt cap that §14 proves does not exist |
| **R2a** | Reserve the tenth TTS request; only unpause a `quota_paused` item when the day's ledger can afford it | code, ~30 lines | prerequisite for R8's retry, and stops the flip-flop of `0015` |
| **R3** | Per-model, per-project daily usage ledger (`content/monitor/model-usage.json`) | code, ~80 lines | the only way "20/day" is enforced across 19 dispatches |
| **R11** | Reads never write: move the unpause into one reconciliation step that edits only the `status:` line | code, ~40 lines | fixes silent manifest rewrites; already fixed the audit's count |
| **R5** | Cold start: allow `max_authors = shortfall` when a channel has zero publishable scripts (6 calls is a fifth of a 20-RPD day) | code, ~10 lines | prayer3 currently needs 3 pristine days to reach parity |
| **R4** | External 15-minute `repository_dispatch: watchdog-tick` | owner + PAT | still the root-cause fix for cron, now *after* R9 (the loop must stop first, or 96 ticks become 96 more pumps) |
| R6/R7 | Brand windows; fix the wall-clock comments (`alarm_minutes: 240`) | code/docs | unchanged |

R4's order changed because of §13: adding an external tick to a supervisor that
already runs 187 times a day adds nothing but load. Stop the loop, then add the tick.

> **Round 3 supersedes this table's head.** §29 adds four changes the Round 2 data
> could not see (R12 preflight, R13 quota-window cron, R14 window-based evidence,
> R15 honest cooldown label). With those counted, the five cheapest high-effect
> changes are **R12, R13, R9, R10, R8′** — one cron value, two YAML/logic lines, and
> two small code changes.

## 21. What the next run will tell us

Three predictions, all falsifiable from the run list alone:

1. If R9 lands, supervisor runs drop from ~187/day to ~12–15/day (8 crons + real
   completions) within one day, and commits to `main` drop to ~20/day.
2. If R8 lands and the empty candidate is a *block*, the new error will name
   `block_reason: SAFETY` (or a style-related refusal) and the fix is the style
   string, not the transport.
3. If R8 lands and the empty candidate is a *generation failure under load*, the
   retry will succeed within two attempts on most passes, and the remaining failures
   will cluster in the 08:00–10:00Z window where 503s already cluster.

If none of those happen, the empty audio is something else, and the diagnostic will
say what.

---

# Round 3 — the code paths behind the numbers

Round 2 counted the traffic. Round 3 opens the functions that produce it, and adds
three findings that change the priority order again: the *liveness probe* is the
biggest spender of the scarcest quota, the schedule sits in the worst corner of the
quota day, and the watchdog's own evidence window collapses under load.

## 22. Finding 14 — the liveness probe is the largest consumer of the scarcest quota

`gemini_brain.yml` runs, per channel job, before anything else:

```yaml
- name: Can this runner reach Gemini?
  run: python scripts/gemini_brain.py --preflight
```

and `--preflight` is not a connectivity check. It is a **full generateContent call**:

```python
text = (brain._call_model(brain.model, "Reply with the single word: ready") or "").strip()
```

`_call_model` is the same retrying path authoring uses. On 6 November, 18 of the 19
brain dispatches died *at this step*, and the annotation says the model "did not
answer after 5 attempts" — five billed requests per channel, per dispatch, to ask
whether the service is up:

| Quantity | Value |
| :--- | ---: |
| Brain dispatches on 6 Nov that failed at `--preflight` | **18** |
| Channel jobs per dispatch (secret-place + prayer2) | 2 |
| Attempts per call before R1 | 5 |
| **Requests spent purely on liveness probes** | **180** |
| Daily allowance for `gemini-3.8-flash`, per project | 20 |
| Two projects | 40 |

**180 requests against a 40-request day.** The probe alone spent the allowance
four and a half times over, before a single script was authored. R1 reduces each
call to two attempts, which brings it to 72 — still 1.8 days' worth.

This is the missing term in Round 1's arithmetic. The retry ladder was not the
problem; **the probe multiplied by the dispatch count** was. It also explains the
shape of the 6 November timeline exactly: the probes failed first (08:45–09:16),
then the quota was gone, then every later attempt had nothing to spend and the
`503 → 24 RPD exhausted` confusion began.

A liveness probe does not need a completion. Two options, both cheaper than one
`generateContent`:

* `client.models.get(model=...)` — a metadata read, no token spend, and it answers
  "is this model still served for this key" (the 404 retirement case);
* or delete the probe and let the first real authoring call report the failure with
  the vocabulary R1/R2 already added. The probe exists because authoring once
  mis-reported a client-construction failure as "GEMINI_API_KEY unavailable" — that
  is now a distinct `api_status()` branch, which does not need a model call.

**R12: preflight must not spend completion quota** (code, ~15 lines).

## 23. Finding 15 — the schedule sits in the worst corner of the quota day

Daily quotas reset at midnight Pacific. On 7 November that is **08:00Z**. Line the
repo's slots up against that boundary:

| Slot (UTC) | Hours into the quota day that starts 08:00Z | Meaning |
| :--- | ---: | :--- |
| brain 03:14 | 19.2 h | last hours of the day — whatever the previous day's produce runs left |
| produce 06:14 | 22.2 h | the *last* consumer of an exhausted day |
| produce 14:14 | 6.2 h | first real consumer of the fresh day |
| produce 19:14 | 11.2 h | second |
| (next day) brain 03:14 | 19.2 h | back to the tail |
| (next day) produce 06:14 | 22.2 h | tail again |

Three consequences, none of which are visible in any comment in the repo:

1. The brain's one daily authoring pass runs **19 hours into the quota day**, i.e.
   after the three produce slots have already been spent. Any day that used its
   allowance leaves the night's authoring with nothing — which is what the 03:14
   failures look like from the outside.
2. The morning release at 06:14Z is the **last** consumer of the day and cannot use
   the reset that arrives two hours later. A quota-starved morning is not
   recoverable until 14:14Z, which is why the morning video is the one that
   disappears from the channel.
3. The one dispatch that "worked" on 6 November was at **14:02Z** — six hours after
   the reset, at 6 hours into the fresh day. The supervisor was, by accident,
   doing the right thing for the wrong reason: it re-dispatched a slot until it
   landed in the fresh budget window.

The fix is a cron line, not code. The queue is maintained to `--min-publishable 6`,
so nothing depends on an 03:14 authoring pass existing *before* the 06:14 release:
six publishable scripts means five more days of runway. Moving the brain to
**08:14Z** puts the only authoring pass of the day in the only window where its
allowance is guaranteed, and removes the reason the supervisor keeps re-dispatching
the night slot.

**R13: brain 03:14Z → 08:14Z; give the morning release a post-reset catch-up**
(config, 1–2 lines).

## 24. Finding 16 — the TTS failure is two different texts, two lengths, one shape

Round 2 could not name the empty-audio cause. Round 3 narrows what it *cannot* be.

**It is not the text.** Today's 08:29Z run failed at narration for the long-form
(882 words) *and* for the Short (107 words):

* `0034` Psalm 91 — narration 5,513 characters / 975 words → chunks `[3833, 1678]`;
* `0035` Psalm 23 — narration 5,781 characters / 1,025 words → chunks `[4000, 1781]`;
* `short-psalm91v5` — 107 words, **one** chunk of ~700 characters.

A safety block on a specific passage would not hit a 107-word Short and a 975-word
prayer with the same message on the same run. **It is not a length cap**: 700
characters is nowhere near the 8,192-token input limit, and the estimated audio for
the Short is well under a minute against the 16,384-token output ceiling.

**It is not the style string.** Every call site uses the default:

```
pipeline/prayer_pipeline.py:206  synthesize_gemini_audio(doc.full_narration, audio, voice='Charon', model=DEFAULT_MODEL)
pipeline/short_release.py:831    synthesize_gemini_audio(spec.narration_text, audio, voice="Charon")
```

`prompt_style` is never passed, so `style_text()` returns `"calm, reverent, peaceful
devotional tone"` — a short attribute list, exactly what Google's prompting guide
asks for. (Worth pinning: if someone later passes a paragraph, that *would* be a
candidate cause.)

**What is left is the request shape**, and there are exactly two variables in it:

| Variable | Current value | Google's 3.8 vocabulary |
| :--- | :--- | :--- |
| `models.generate_content(...)` fallback modality | `response_modalities=["AUDIO"]` | the migration guide names `AUDIO_WAV` / `AUDIO_L16` / `AUDIO_MULAW` / `AUDIO_ALAW`; WAV is the 3.8 default, and `AUDIO` is the 3.1 vocabulary |
| style carrier | `Part(text=…, speech_metadata=SpeechMetadata(style=…))` | documented as a `part.speech_metadata` object *or* an interactions `speech_metadata` annotation — the fallback path is the one path documented least |

The 400s already seen this week (`Unknown name "speechMetadata"`, `Developer
instruction is not enabled for this model`) show this model rejects request shapes
loudly *when it rejects them*; a silent 200 with no parts is what is left when it
accepts a shape it cannot fulfil. So the first probe should change exactly one
thing — the modality enum — and log the two fields that say why:

```
finish_reason: candidates[0].finish_reason
prompt_feedback: response.prompt_feedback.block_reason
```

**R8 (revised):** in the fallback path, ask for `AUDIO_WAV`; log `finish_reason` and
`prompt_feedback.block_reason` in the failure message; treat an empty candidate as
retryable **once** with jitter; keep the interactions path first, because that is
the documented shape. One run then decides between "blocked", "generation failure"
and "wrong modality" instead of us guessing a fourth time.

## 25. Finding 17 — the watchdog's evidence window collapses exactly when it is needed

`scripts/automation_monitor.py:135`:

```python
def fetch_runs(per_page: int = 20) -> list[dict]:
    ...
    resp = _gh(["api", f"repos/{repo_slug()}/actions/workflows/{wid}/runs?per_page={per_page}"])
```

Twenty runs per workflow, per pass. Everything the monitor believes is computed from
those twenty:

* `runs_14d` is `len([r for r in mine if within 14 days])` — it **saturates at 20**.
  In today's `status.json` seven of ten workflows report exactly `runs_14d: 20`,
  which reads as "20 runs in a fortnight" and actually means "all of the last twenty
  happened inside the window I can see".
* `missed_slots` is computed over the same twenty. During the storm, twenty
  supervisor runs span about **ninety minutes** — a monitor sampling that window
  physically cannot see a three-hour scheduling gap, which is the one thing it was
  built to see. In a quiet week the same code sees days. **The verdict's meaning
  depends on load**, which is why `missed_slots: 0` sits next to a night with no
  runs at all.
* `last_conclusion` was `None` for `automation-health`, `gemini_brain` and
  `scheduler-supervisor` in the 05:51 snapshot: the newest run was in flight when
  the monitor looked, and an in-flight run skips the `== "failure"` branch entirely.
  With 187 passes a day that sampling collision is not rare.

Nineteen API calls per pass (one `/actions/workflows` plus eighteen run lists), and
**both** watchers call it: ~352 passes/day × 19 ≈ **6,700 calls/day, ~280/hour**.
GitHub's `GITHUB_TOKEN` budget is 1,000 requests/hour per repo, so this is
*dismissed as a cause* — but it is a quarter of the budget, spent entirely on
watching, and it is paid every time a watcher wakes up.

**R14:** fetch by *window* (`created=>=now-14d`) rather than by count, and treat an
in-flight newest run as "no verdict yet" rather than as neutral. That is what makes
`missed_slots` mean the same thing on a quiet day and a storming one.

## 26. Finding 18 — "QUOTA WAIT" is the wrong label, and one channel's pause gates all three

`pipeline/run.py:548` `quota_blocked_until()` scans **every** long-form queue file
for `status: quota_paused` with a future reset, and `active_quota_cooldown()` adds
"a publish in the last 24h". If any file matches:

* `scripts/automation_monitor.py:459` labels the whole of `produce.yml`
  **`QUOTA WAIT — daily $0.00 TTS allowance spent after today's upload(s); resumes …`**;
* `scripts/scheduler_supervisor.py:311` refuses to dispatch produce at all.

Two defects, both of which the owner's own constraints already forbid:

1. **The label is asserted, not measured.** Today's failure is
   `no audio content (mime_types=none)` — a model-contract failure. The board says
   "allowance spent". A service failure is being reported as a quota failure, which
   is the mirror image of the rule in §1: *a service/quota failure must not be
   reported as a format failure*, and a contract failure must not be reported as
   quota.
2. **The gate is global.** There is no channel filter. `quota_blocked_until` does not
   look at `channel:`, so a paused **prayer2** job stops **secret-place** and
   **prayer3** from being dispatched — three separate projects, three separate
   allowances, one latch. That is the exact opposite of the "never borrow another
   channel's quota" rule, and it is why an unrelated pause can leave the 19:14 slot
   unserved.

**R15:** record *why* a job was paused (`quota_error` vs `tts_no_audio` vs
`model_retired`) and label the cooldown from that; filter the gate by channel.

## 27. Finding 19 — the loop's physical cost, and what it is not

Worth stating so nobody optimises the wrong thing. The repository is **1.09 GB** on
GitHub (`.git` is 585 MB locally, shallow). The largest tracked objects are not
videos:

| Object | Size |
| :--- | ---: |
| `docs/products/432hz-offline-bedtime-sanctuary-pack.zip.part00`–`part07` | 7 × 80 MB |
| `docs/media/shorts-enron.mp4` | 16.8 MB |

…yet **checkout is 14–23 seconds** and a whole supervisor pass is **42–72 seconds**,
stable between 2 and 7 November. So the storm's cost is not bandwidth:

| Resource | Cost of the storm |
| :--- | :--- |
| runner time | 187 × ~55 s ≈ **2.9 h/day** (free, public repo) |
| git history | 385 commits/day ≈ **1.5 MB/day** of new blobs (174 ledgers + 130 `status.json` snapshots, plus git object overhead) |
| API | ~6,700 calls/day (~280/h) — a quarter of the 1,000/h budget |
| human signal | 96 monitor reds/day, one issue |

The expensive resource is the last one. Everything else is noise that makes the
noise indistinguishable from the failure.

## 28. Finding 20 — a Short that cannot succeed, and the flip-flop that proves nobody noticed

`content/shorts-queue/0015-short-psalm91v5.yml` — one manifest, five days:

| Commit | Time | Status in that commit |
| :--- | :--- | :--- |
| `fef1b351` | 3 Nov 20:27 | `approved` |
| `e5e2aed4` | 5 Nov 21:06 | **`quota_paused`** |
| `9eb30ee8` | 6 Nov 08:06 | `approved` |
| `17561dfa` | 6 Nov 08:08 | **`quota_paused`** |
| `98a83a80` | 6 Nov 08:25 | `approved` |
| `729a0fa1` | 6 Nov 14:14 | **`quota_paused`** |
| `575366b2` | 7 Nov 08:29 | `approved` |

Pause → unpause → pause → unpause, twice inside one morning. The unpauses are
`chore(content): publish job` commits: the reader auto-unpaused it at the reset, the
release spent a request, narration came back empty, and the job paused it again. Each
cycle costs at least one of ten daily TTS requests, and this Short has never
produced audio.

A timer alone must not re-arm a job whose failure was not a quota refusal. The
pause record needs the reason (`R15`), and the unpause needs a budget check
(`R2a`). Otherwise the queue will keep spending a tenth of the day's speech
allowance on the same un-narratable Short, every day, forever.

## 29. Round 3 ranking delta

| # | Change | Size | Why now |
| :-- | :--- | :--- | :--- |
| **R12** | preflight stops spending completion quota | ~15 lines | it is the single largest consumer of the 20/day allowance — 180 requests on 6 Nov against 40 available |
| **R13** | brain 03:14Z → 08:14Z; post-reset catch-up for the morning slot | 1–2 lines | the day's only authoring pass currently runs at hour 19 of a spent day |
| **R8′** | `AUDIO_WAV` + `finish_reason`/`prompt_feedback` + one bounded retry | ~60 lines | two texts and two lengths fail identically, so the shape is the prime suspect |
| **R14** | fetch runs by window, not by count; in-flight ≠ neutral | ~30 lines | `missed_slots` currently means something different under load |
| **R15** | label the cooldown from the pause reason; filter it per channel | ~40 lines | "QUOTA WAIT" is asserted for a contract failure, and one channel's pause stops three |
| R9, R10, R2a, R3, R5, R4, R6, R11 | unchanged from §20 | | R9 still first among the loop fixes |

Combined with §20, the five cheapest high-effect changes are **R12, R13, R9, R10,
R8′** — two of them are measured in lines of YAML and one is a single cron value.

## 30. Round 3 predictions

1. If R12 lands, a 19-dispatch day costs ~38 requests instead of ~180, and the
   `503 → quota gone → nothing works` cascade stops being *self-inflicted*. The next
   storm will show 503s that end when capacity returns, not at midnight Pacific.
2. If R13 lands, the 03:14 failures disappear and the supervisor stops re-dispatching
   that slot after the reset (there is nothing left to recover).
3. If R8′ lands and the modality was the cause, narration returns on the first run.
   If it was a block, the message will name `SAFETY`; if it was generation failure,
   the one retry succeeds and the residual failures cluster in the 08:00–10:00Z
   capacity trough, exactly like the brain's 503s.
4. If R9 lands, `runs_14d` stops saturating at 20 within a day, because the same code
   will see a real fortnight of history for the first time.

---

# Round 4 — the ledger of what actually published, and the loop that cannot terminate

Round 3 explained the traffic. Round 4 asks the only question that matters — *how much
did the channels actually publish* — and then follows the newest supervisor logic
until it stops making sense, which it does in one specific place.

## 31. Finding 21 — the output ledger: nine long-forms in ten days

From `content/published/*.md` (a receipt exists only for a real upload):

| Day | Long-form uploads | Shorts |
| :--- | :--- | ---: |
| 23 Oct | — | 1 |
| 28 Oct | — | 1 |
| 29 Oct | 1 (secret-place) | — |
| 31 Oct | 1 (secret-place) | — |
| 1 Nov | 1 (secret-place) | — |
| 2 Nov | 1 (secret-place) | — |
| 3 Nov | 1 (secret-place) | 5 |
| 4 Nov | 1 (secret-place) | — |
| 5 Nov | **3** (secret-place 1, prayer2 2) | — |
| 6 Nov | **0** | 4 |
| 7 Nov | **0** | — |
| **Total** | **9** | **11** |

The plan is three long-form slots a day across two channels (six uploads) plus a Short
per leg. The demonstrated ceiling is **one long-form a day on one channel**, reached
once (5 Nov) at three. Everything the automation has ever published of substance fits
in nine receipts.

Two things follow.

**The quota arithmetic in §6 and §16.2 was written for a throughput that has never
happened.** "Nine of ten TTS requests committed" describes a day with three long-form
uploads and three Shorts. The real day has one upload attempt that fails at narration.
The allowance is not being split between videos; it is being spent on *retries of the
first* video.

**The runway metric reads the wrong number.** `--min-publishable 6` and the monitor's
"runway days" divide the queue by three slots a day. At the observed rate of one
upload a day, the 19 publishable secret-place scripts are **19 days** of runway being
reported as six. A queue depth is only meaningful against the consumption rate that
actually occurs, and nothing in the repo records that rate.

## 32. Finding 22 — the coverage test cannot be satisfied, so `produce` is dispatched forever

The supervisor decides whether a produce slot was served by receipts:

```python
missing = [c for c in _channels() if c not in published_channels_since(since)]
if not missing:
    return True, "every channel already published for this slot"
channel = missing[0]
```

and `_channels()` is `scheduled_channels()`, i.e. **every provisioned channel**:

```python
CHANNELS = {"secret-place": ..., "prayer2": ..., "prayer3": ...}
# prayer3: provisioned=True  (flipped 2026-11-07)
```

Prayer3 is provisioned, and `content/queue/` contains **zero** scripts for it, so it
cannot publish a long-form at all. The set of channels with a receipt can therefore
never equal the set of channels required, and `missing` is never empty. Measured
consequences in the current state:

* nothing has published a long-form since 5 Nov, so *all three* channels are missing;
  `missing[0]` is `secret-place`, and that is exactly what today's dispatches were:
  produce at **08:27** and again at **08:44**, both `produce (secret-place)`;
* the 6 November pattern is the same shape — 11 produce runs, one per supervisor pass
  that found the queue still short of a receipt.

And `USEFUL_WINDOW["produce.yml"]` is 6 hours with slots at 06:14, 14:14 and 19:14, so
a "recent enough to recover" slot exists for roughly **18 hours of every day**. The
dispatchable window is nearly all of the clock.

Once TTS is fixed and secret-place and prayer2 start publishing again, the order
matters in a way nobody intended: `missing[0]` moves to **prayer3**, which fails
instantly ("nothing in content/queue can publish"), so **every** subsequent pass
dispatches prayer3 again, forever, at three legs a day and ~18 dispatchable hours.

This is a *structural* pump independent of §14's counter race. Even with a perfect
ledger, the cap is `2 × 3 + 1 = 7` attempts per slot: 21 produce legs a day for a
channel with nothing to publish.

**R16:** judge a slot against the channels the plan can actually serve, and exclude a
channel with no publishable script from the coverage test (it is a *supply* problem,
not a *schedule* problem, and R5 is where it belongs). Without this, fixing TTS makes
the storm worse rather than better.

## 33. Finding 23 — every produce leg is also an authoring run, so the quota has two pumps

Step 11 of every produce leg:

```yaml
- name: Repair the queue before publishing
  run: python scripts/gemini_brain.py --ensure-supply-for "$CHANNEL_ID" --min-publishable 3
```

That is the same supply loop the brain runs, at a **different target**: the brain asks
for 6, produce asks for 3. So:

| Workflow | `--min-publishable` | Worst-case model calls per leg |
| :--- | ---: | :--- |
| `gemini_brain.yml` | 6 | ~10 expansions + 2 authoring chains |
| `produce.yml` | 3 | ~10 expansions + 2 authoring chains |

The same channel can therefore be simultaneously **healthy** to produce (3 publishable)
and **empty** to the brain (fewer than 6) — which is a scheduling disagreement encoded
as two constants. It also means a produce dispatch is not "render one video"; it is
another authoring pass, spending the same 20-request day. On 6 November: 19 brain
dispatches *plus* 11 produce legs, each able to spend 12–14 calls.

## 34. Finding 24 — the per-run budget is 60–70 % of the day, so the retry cap is set above what the day can pay for

| Knob | Value |
| :--- | ---: |
| `MAX_EXPANSIONS_WHEN_EMPTY` | 5 |
| `MAX_MODEL_CALLS_PER_RUN` | 10 |
| `MAX_AUTHORS_PER_RUN` | 2 |
| daily allowance, `gemini-3.8-flash`, per project | 20 |

One channel job with an empty queue can spend ten expansion calls plus two authoring
chains — **12–14 of 20 requests, 60–70 % of the day, in one pass.** The design is
therefore "one pass per channel per day, and no second one". The supervisor's cap of
**three** attempts per slot (seven for produce) is two to six attempts more than the
budget can fund, *before* the counter race of §14 makes the cap infinite.

This is why R1 was necessary but not sufficient: the per-call ladder is now cheap, but
`MAX_MODEL_CALLS_PER_RUN` is a *per-run* ceiling with no per-*day* ceiling behind it.
The only thing that can bound a 19-dispatch day is a ledger that counts requests across
runs — which is R3, and it is now the highest-value code change after R16 and R12.

## 35. Finding 25 — the YouTube unit budget is spent by repair loops, not by uploads

I assumed uploads were the expensive call and went to the calculator to price them.
**They are not expensive any more.** YouTube's current quota page (last updated
2026-11-03) re-priced exactly this:

> Projects that enable the YouTube Data API have a default quota allocation of 100
> `search.list` calls, **100 `videos.insert` calls**, and 10,000 units per day combined
> for all other endpoints… The `search.list` and `videos.insert` methods have their own
> quota buckets. Each of these methods has a default daily limit of 100 per day.
> **The quota cost is 1 per call.**

So the real cost table for this pipeline is:

| Call | Units | Own bucket | Where |
| :--- | ---: | :--- | :--- |
| `videos.insert` | **1** | 100/day | `pipeline/upload.py:342` |
| `thumbnails.set` | 50 | — | `pipeline/upload.py:367` (long-form only) |
| `playlistItems.insert` | 50 | — | `pipeline/upload.py:403` when `CONFIG.playlist_id` |
| `captions.insert` | 400 | — | via `pipeline/captions.py` |
| `videos.update` | 50 | — | metadata retrofit |
| `comments.insert` | **50** per the calculator; **2** per `pipeline/comment_replies.py:9` | — | autonomous replies |

The design's day — three long-form and three Shorts per project — is therefore
`6 units of insert` (6 % of its own bucket) plus the metadata calls:

```
3 × (50 thumbnail + 50 playlist + 400 captions) = 1,500 units   of a 10,000-unit day
```

**The plan fits comfortably.** The budget that does not fit is any *retry* of those
calls, because each one is 50–400 units against a pool that the uploads barely touch.
A single `thumbnails.set` retried on every monitor pass is 50 × 185 = **9,250 units a
day** — 92 % of the pool, from a repair loop (§38).

And nothing counts units: the first notification is `quotaExceeded` in
`pipeline/upload.py:352`, converted to `QuotaExceededError`, paused with the **same**
`status: quota_paused` and `quota_reset_utc` fields a TTS pause uses
(`pipeline/run.py:349`, `438`). So a YouTube-pool exhaustion is displayed as
`QUOTA WAIT — daily $0.00 TTS allowance spent` (§26) and latches **all three channels**
in the supervisor — two of which have their own untouched unit pools.

One more inconsistency worth naming: the repository's comment code believes
`comments.insert` costs **2** units and says the old docstrings (which said 50) were
"25× the real cost" (`pipeline/comment_replies.py:9`). The calculator says **50**. Whichever
is right, the code carries a units model it has not verified against today's pricing,
and the reply budget is derived from it.

**R17:** one units ledger per project per day, with the prices above, checked before a
leg starts and before any repair retries a 50-unit call; and a pause reason on the job
so the board can say *which* budget ran out.

## 36. Finding 26 — three ways this TTS code can see "no audio" while audio exists

Round 3 guessed the modality. Reading the pinned SDK (2.34.0) instead of the docs gives
a sharper answer, and corrects one thing in Round 3.

**Correction first:** `types.Modality` in 2.34.0 contains exactly `AUDIO`, `IMAGE`,
`TEXT`, `VIDEO`. There is **no `AUDIO_WAV`**: the `AUDIO_WAV`/`AUDIO_L16` names in
Google's migration guide belong to `response_format.mime_type` in the interactions API,
whose enum in this SDK is

```
AudioResponseFormatMimeType = audio/mp3 | audio/ogg_opus | audio/l16 | audio/wav | audio/alaw | audio/mulaw
```

So R8′ cannot be "ask for AUDIO_WAV in `response_modalities`" — that would be an
invented value. It must be `response_format={"type": "audio", "mime_type": "audio/wav"}`
on the interactions call, which is documented and typed.

**Then the three silent paths.** The code reads exactly one thing:

```python
output_audio = getattr(interaction, "output_audio", None)
if output_audio and getattr(output_audio, "data", None):   # ← only `data`
    ...
```

and on the fallback transport it walks `content.parts` for `inline_data`. That misses:

| What the response can be | What the code sees | What the SDK actually offers |
| :--- | :--- | :--- |
| Audio delivered as a **URI** (`response_format.delivery = "uri"`) | `data` is `None` → "no audio" | `AudioContent.uri` (`AudioResponseFormatDelivery = inline \| uri`) |
| Audio **not generated**: `status ∈ {failed, incomplete, budget_exceeded, cancelled}` | "no audio" | `Interaction.status`, `Interaction.errors[].code/message` |
| Audio **truncated at the output cap** | "no audio" | `Interaction.usage.total_output_tokens` against 16,384 |

`budget_exceeded` is a documented interaction status, and it is exactly what a TTS
request that runs into the 16,384-token output ceiling would return: HTTP 200, status
"budget_exceeded", no `output_audio`, no exception. The code would report
`mime_types=none` and a human would spend an afternoon on the model name.

**R8″** (replaces R8′): on the interactions path, when `output_audio` is absent, read
`status`, `errors`, `usage.total_output_tokens` and `output_audio.uri` before raising,
and put them in the annotation. Five fields, zero extra requests, and the next failure
names its own cause.

## 37. Finding 27 — the chunk cache saves one leg per run, and nobody can tell

`produce.yml` restores and saves speech chunks with:

```yaml
key: chunks-tts-v4-${{ github.run_id }}
restore-keys: |
  chunks-
```

`github.run_id` is shared by every job in a run, and a scheduled produce run is two
legs (secret-place, prayer2). The chunk directories are per-leg
(`output/<slug>/_gemini_chunks_<stem>`), so the two legs produce **different** content
under **one** immutable cache key: the first save wins, the second is refused. The step
carries `continue-on-error: true`, so the refusal is neither red nor visible — both
legs report `success` (verified on run `42288352182`).

Three consequences:

1. one leg's finished narration is silently discarded every run — up to two TTS
   requests re-spent on the next attempt;
2. `restore-keys: chunks-` matches *any* recent cache, including another channel's, so
   what a leg resumes from depends on which job last saved;
3. size: 24 kHz mono 16-bit is 48 kB/s, a 4,000-character chunk is ~4.8 minutes ≈
   **14 MB**, a long-form narration is two chunks ≈ 28 MB. Nine leg-saves a day is
   **~250 MB/day**, against GitHub's 10 GB per-repo cache ceiling and its LRU eviction
   — so cache reuse is least reliable exactly when the allowance is tightest.

**R18:** one key per run *and channel* (`chunks-tts-v4-<run_id>-<channel>`), and fail
the step loudly if a save is refused.

## 38. Finding 28 — the tripwire that would be catastrophic, and is not firing

For completeness, because it was the obvious suspect and it is wrong today:
`sync_published_thumbnails --all-channels` retries every receipt with
`thumbnail_pending: true` on **every monitor pass** (185 passes in 24 hours), at 50
units each. A single permanently-refused thumbnail would cost 9,250 units/day — the
whole channel's YouTube quota, from a repair loop nobody associates with uploads.

Today: **zero** receipts carry `thumbnail_pending: true` (only `0036` and `0037`, both `false`). So it
is not a current cause. It is one refused thumbnail away from being 92 % of the
channel's unit pool, and the reason it would go unnoticed is §26: the resulting
`quotaExceeded` gets written as a TTS pause.

## 39. Ranking after Round 4

| # | Change | Size | Why |
| :-- | :--- | :--- | :--- |
| **R16** | a slot is served when the channels the plan *can* serve have receipts; a channel with nothing publishable is a supply fault, not a schedule fault | ~20 lines | without it, fixing TTS converts 11 produce runs/day into prayer3 forever |
| **R12** | preflight stops spending completion quota | ~15 lines | 180 requests on 6 Nov against 40 available |
| **R8″** | interactions `response_format.mime_type="audio/wav"` + `status`/`errors`/`usage`/`uri` in the error | ~25 lines | names the failure instead of guessing a fourth time |
| **R9** | break the watcher loop (Pages trigger, wall-clock stamps) | 2 lines + test | 350 runs and 300 commits a day |
| **R10** | API-derived dispatch dedupe | ~40 lines | the cap that §14 proves does not exist |
| **R17** | YouTube units ledger per project per day | ~60 lines | uploads are 1 unit now; the pool is spent by 50–400-unit metadata repairs that nobody counts |
| **R13** | brain 03:14Z → 08:14Z | 1 line | hour 19 of a spent day |
| **R3** | per-model daily ledger | ~80 lines | the only thing that bounds `MAX_MODEL_CALLS_PER_RUN` across runs |
| **R18** | per-channel chunk cache key | ~3 lines | one leg's narration is silently discarded per run |
| R5, Rev | prayer3 cold start; the `--min-publishable` 6-vs-3 disagreement | small | both are now *loop* fixes, not content fixes |
| R2a, R11, R14, R15, R6, R7 | unchanged | | |

## 40. Round 4 predictions

1. When TTS starts returning audio again, **produce dispatches do not fall** — they
   move from secret-place to prayer3 and continue at roughly one per supervisor pass,
   because of §32. R16 is a prerequisite for R8″ being *useful*.
2. Upload volume will never exhaust the YouTube pool: six inserts cost six units of a
   100-call bucket. The first `quotaExceeded` will come from a metadata repair loop
   (§35, §38) and the board will call it a TTS problem (§26) — which is the failure
   mode to watch for, not "too many videos".
3. The first real diagnosis of the empty narration will come from `status` or
   `usage.total_output_tokens`, not from the model name — which is why R8″ is five
   fields, not a new transport.

## 41. Sources added in Round 4

**YouTube Data API pricing (primary, and it changed the finding):**
`https://developers.google.com/youtube/data/determine_quota_cost` (last updated
2026-11-03) — 100 `search.list` calls, 100 `videos.insert` calls and 10,000 units/day
for everything else; `videos.insert` costs **1** unit in its own bucket;
`thumbnails.set` 50; `playlistItems.insert` 50; `captions.insert` 400;
`videos.update` 50. This is the opposite of the 1,600-unit-per-upload model the repo's
comments assume, and it moves the risk from "too many uploads" to "retried metadata
calls".

**The pinned SDK, read rather than assumed** (`google-genai 2.34.0`, installed in
`.venv`):

| Fact | Where |
| :--- | :--- |
| `types.Modality` = `AUDIO, IMAGE, TEXT, VIDEO` — **no `AUDIO_WAV`** | `google.genai.types` |
| `AudioResponseFormatMimeType` = `audio/mp3, audio/ogg_opus, audio/l16, audio/wav, audio/alaw, audio/mulaw` | `google.genai.interactions` |
| `AudioResponseFormatDelivery` = `inline, uri` | same |
| `Interaction.status` ∈ `in_progress, requires_action, completed, failed, cancelled, incomplete, budget_exceeded, queued, requires_continuation` | same |
| `Interaction` also carries `errors[].code/message`, `usage.total_output_tokens`, `output_audio.uri` | same |
| `AudioContent` = `channels, data, mime_type, sample_rate, type, uri` | same |

`pipeline/gemini_tts.py` reads `output_audio.data` and nothing else, which is why an
`uri` delivery, a `budget_exceeded` status and a genuinely empty candidate all produce
the same sentence.

**Repository history for the flip-flop:** `gh api 'repos/{repo}/commits?path=content/shorts-queue/0015-short-psalm91v5.yml'`,
then the file contents at each commit (`contents/…?ref=<sha>`) — seven commits,
`approved`/`quota_paused` alternating (§28).

---

# Round 5 — reproduced, not inferred

Rounds 1–4 read code and run history. This round **executes it**: a throwaway script
(`python -c` against the real modules in `.venv`) that drives the supervisor's own
decision functions with a synthetic run list and a temporary
`content/published/` directory. Every number below is printed by that script, not
derived by hand.

```python
import scripts.scheduler_supervisor as S
from scripts.automation_monitor import workflow_files, prev_occurrence
from pipeline.gemini_brain import MAX_CALLS_PER_RUN, model_attempt_limit, text_model_candidates
```

## 42. Finding 29 — the four claims of Rounds 2–4, reproduced

```
== E1  who counts as a channel, and what the cap is
   scheduled_channels(): ['secret-place', 'prayer2', 'prayer3']
   _attempt_cap('produce.yml'): 7   _attempt_cap('gemini_brain.yml'): 3
   MAX_CALLS_PER_RUN (brain pass): 40
```

```
== E2  the coverage test with two channels served and prayer3 empty
   receipts since the slot: ['prayer2', 'secret-place']
   missing: ['prayer3'] -> dispatch target: prayer3
   dispatch() -> True 'dispatched prayer3'
   argv -> ['gh', 'workflow', 'run', 'produce.yml', '-f', 'channel=prayer3']
```

```
== E3  the same test once prayer3 has one receipt
   receipts: ['prayer2', 'prayer3', 'secret-place']  missing: []
   dispatch() -> True 'every channel already published for this slot'
```

That is §32, executed: with two of three channels served the supervisor's own
function builds the exact command that dispatches an empty channel, and the test only
goes quiet when that channel has published something it cannot publish.

```
== E4  the ledger write, from two checkouts of the same file
   pass A (read 0) -> 1
   pass B (read 1) -> 2
   pass C (read 2) -> 3
   pass D, stale checkout from 08:00 (read 0) -> 1
   ledger now says: 1 (cap is 3 )
```

That is §14, executed. The write is one line
(`state[key] = {..., "attempts": attempts + 1, ...}`, `scheduler_supervisor.py:796`);
a pass that checked out main before the previous writes finishes *after* them and
restores a smaller number. The cap of 3 is never reached because the counter never
survives three consecutive reads.

```
== E5  how much of the clock a slot is dispatchable for
   comments.yml                  18.8 h/day  crons=3
   gemini_brain.yml              22.5 h/day  crons=1
   growth-autopilot.yml          22.5 h/day  crons=1
   metrics.yml                   18.7 h/day  crons=1
   produce.yml                   11.3 h/day  crons=3
   community.yml / keepalive.yml  0.0 h/day  crons=1
```

A daily cron has a 24-hour recovery window and a 90-minute grace, so the brain slot is
recoverable for **22.5 of every 24 hours** — the window is not an exception handler,
it is the normal state. Produce, on three slots five to eleven hours apart, is
recoverable for 11.3 hours a day.

```
== E6  the model roster, with the attempts each is allowed
   live_model(): gemini-3.5-flash-lite
   0. gemini-3.5-flash-lite    attempts=3  (500/day)
   1. gemini-3.1-flash-lite    attempts=3  (500/day)
   2. gemini-3.6-flash         attempts=2  (20/day)
   3. gemini-3.8-flash         attempts=2  (20/day)
   4. gemini-3.7-flash         attempts=2  (20/day)
```

One logical call that no model can satisfy — the case the 7 November prayer3 pass
describes in its own source comment: *"every candidate model returned a script without
front matter"* — costs `2×3 + 3×2 =` **12 requests**, across five models, for zero
output.

## 43. Finding 30 — the pass guard is set at double the daily allowance

```python
MAX_CALLS_PER_RUN = int(os.environ.get("GEMINI_MAX_CALLS_PER_RUN", "40") or "40")
```

and it is enforced per `GeminiBrain` instance, i.e. **per channel job**
(`gemini_brain.py:651`, `:812`).

| Ceiling | Value | Against a 20-request day |
| :--- | ---: | :--- |
| `MAX_MODEL_CALLS_PER_RUN` (supply expansions only) | 10 | 50 % |
| `MAX_CALLS_PER_RUN` (**the whole pass**) | **40** | **200 %** |
| the same, per dispatch (2–3 channel jobs) | 80–120 | 400–600 % |
| observed dispatches on 6 Nov | 19 | |

So the guard that is supposed to stop "a bad morning eating the day's allowance" is
itself two days long, and the dispatcher may run it nineteen times. R1 made each call
cheap (25 → 12 requests); the *pass* and the *dispatch count* were never the ceilings
that a 20-request day requires.

The correct shape is the one R3 describes — a request ledger keyed by
(project, model, day) that the pass consults before each call — plus `MAX_CALLS_PER_RUN`
set to something a day can pay for (≤ 10 for a 20-request model). There is no
configuration in which 40 is safe.

## 44. Finding 31 — the cold start is six successes away, and each failure costs twelve

Prayer3's queue is empty and `--min-publishable 6` with `MAX_AUTHORS_PER_RUN = 2` means
three clean passes. With the roster above:

| Outcome | Requests |
| :--- | ---: |
| one authored script (first model, first attempt) | 1 |
| one rejected script, walked to the end of the chain | **12** |
| a six-script cold start, all first-attempt | 6 |
| a six-script cold start where each is rejected once | up to 72 |

The 20-request day pays for the first row and not the fourth. Today's prayer3
dispatches (04:54, 04:58, 05:39, 06:00) were all in the fourth regime: four passes, no
script, and — because prayer3 has its own project — the whole of prayer3's day spent
proving that the chain cannot write a Midday Watch script. This is why R5 (cold start)
is not a nicety: the only way prayer3 ever leaves zero is a pass that *succeeds*, and
the failure mode spends the day first.

## 45. Finding 32 — the daily health red is one assertion, and it is a content gap

`automation-health.yml` fails at `python scripts/channel_parity.py` every day.
Executed here, in one second, offline:

```
PASS  every registered channel has a capability block
PASS  secret-place: brain equipment compiles / roadmap / prompt / pinned comment
PASS  prayer2:      brain equipment compiles / roadmap / prompt / pinned comment
PASS  prayer3:      brain equipment compiles / roadmap / prompt / pinned comment
FAIL  prayer3: has a queued script to key a Short from — no queued script for this channel
PASS  short keys are unique across channels
PASS  produce.yml: schedules every channel
PASS  gemini_brain.yml: schedules every channel
==============================================================================
1 PARITY FAILURE(S)
```

Nineteen passes, one failure, and the failure is the *same* fact as §32 and §44:
prayer3 has no scripts. Three of this repository's red signals — the parity step, the
produce dispatch loop and the brain's `Long-form supply empty` — are one content gap
with three faces. That is the clearest argument yet for fixing the cold start before
touching anything else: it clears three alarms at once.

## 46. Finding 33 — the third leg pushes the run past the supervisor's canceller

`produce.yml` runs its channels as a matrix with `max-parallel: 1`, so a run's wall
clock is the **sum** of its legs. Measured:

| Observation | Value |
| :--- | ---: |
| two-leg runs that really published (4–5 Nov) | 26–44 min |
| the slow encoder outlier (5 Nov, one leg) | 54.5 min for the encode step alone |
| failed-fast legs (6 Nov, TTS failure) | 8.4 min and 12.3 min |
| supervisor cancel threshold | `JOB_CAP` 200 min + 10 min grace |
| `produce.yml`'s own job cap | 240 min |

Two legs at the published pace is 26–44 minutes. Three legs at the outlier pace is
3 × 54.5 = **164 minutes** — inside 210, but with 46 minutes of margin for a slot that
also repairs its queue, records live videos and uploads three Shorts. And a run
cancelled by the supervisor loses everything it had not yet committed, including the
TTS requests already spent.

The canceller was sized when a run had two legs. Adding a channel raises the ceiling of
a legitimate run by 50 % and does not raise the guard at all.

## 47. Round 5 ranking delta

No change to the order, but R16 and R5 are now *proven* rather than argued, and R3's
target number is explicit:

| # | Change | Evidence now |
| :-- | :--- | :--- |
| **R16** | coverage test: only channels the plan can serve, and a channel with no scripts is a supply fault | E2/E3 — the supervisor builds `channel=prayer3` with two of three served |
| **R5** | cold start: allow `max_authors = shortfall`, once, for a channel at zero | §44 — six successes, and a single rejection costs 12 requests |
| **R12** | preflight must not spend completion quota | §22 — 180 requests against 40 on 6 Nov |
| **R3** | per-day request ledger | §43 — the pass guard is 40 against a 20-request day |
| **R9** | break the watcher loop | E5 — 22.5 h/day of "the slot is recoverable" |
| **R10** | API-derived dispatch dedupe | E4 — 1,2,3,1 from one stale checkout |
| remaining | R8″, R13, R17, R18, R2a, R11, R14, R15 | unchanged |

## 48. Round 5 predictions, all falsifiable from the run list

1. Flip prayer3's queue to six scripts by hand and the parity step goes green, the
   produce dispatch pattern moves off `channel=prayer3`, and `automation-health`
   stops filing — without a single code change. (This is the cheapest possible test of
   §45, and it is reversible: six drafts, not uploads.)
2. Lower `GEMINI_MAX_CALLS_PER_RUN` to 8 and a 19-dispatch day is still *authorised*
   to spend 19 × 2 jobs × 8 = 304 requests across two projects that have 40 between
   them. Tightening the number cannot fix a ceiling that is per job and a problem that
   is per day; a green run after such a change would be luck, not a fix.
3. A third leg on a slow day produces the first `cancelled` produce run with a video
   already uploaded — because the cancellation lands inside the render, not before it.

## Appendix A — the reproduction script (Round 5)

Nothing in §42 is hand-derived; this is the whole script, run from the repository root
with `.venv/bin/python` and `PYTHONPATH=.`. It executes the supervisor's own
functions and touches nothing: `subprocess.run` is patched, so the `gh workflow run`
command is *captured*, not sent.

```python
"""Round-5 experiments: executed, not read."""
import datetime as dt, tempfile
from pathlib import Path
from unittest import mock

import scripts.scheduler_supervisor as S
from scripts.automation_monitor import workflow_files, prev_occurrence
from pipeline.gemini_brain import (TWENTY_A_DAY_MODELS, MAX_CALLS_PER_RUN,
                                   model_attempt_limit, text_model_candidates,
                                   live_model)

UTC = dt.timezone.utc
SLOT = dt.datetime(2026, 11, 7, 6, 14, tzinfo=UTC)     # the 06:14 produce slot
NOW  = dt.datetime(2026, 11, 7, 9, 0,  tzinfo=UTC)     # when the pass looks

# E1 — who counts as a channel, and what the caps are
print(S._channels(), S._attempt_cap("produce.yml"), S._attempt_cap("gemini_brain.yml"),
      MAX_CALLS_PER_RUN)

def receipt(channel, when="2026-11-07T08:40:00Z"):
    return (f"---\nid: '0040'\nformat: longform\nchannel: {channel}\n"
            f"youtube_video_id: abc123\npublished_at: \"{when}\"\n---\nbody\n")

# E2/E3 — the coverage test, with and without a prayer3 receipt
for served in (("secret-place", "prayer2"),
               ("secret-place", "prayer2", "prayer3")):
    with tempfile.TemporaryDirectory() as tmp:
        pub = Path(tmp)
        for i, ch in enumerate(served):
            (pub / f"00{40+i}-{ch}.md").write_text(receipt(ch), encoding="utf-8")
        missing = [c for c in S._channels() if c not in S.published_channels_since(SLOT, pub)]
        captured = {}
        class Fake:
            returncode = 0; stdout = ""; stderr = ""
        with mock.patch.object(S, "subprocess", mock.Mock(
                 run=lambda argv, **kw: (captured.setdefault("argv", argv), Fake())[1])), \
             mock.patch("pipeline.config.PUBLISHED_DIR", pub):
            print(missing, S.dispatch("produce.yml", SLOT.isoformat()), captured.get("argv"))

# E4 — the ledger write, from a stale checkout (scheduler_supervisor.py:796)
key = "gemini_brain.yml@" + dt.datetime(2026, 11, 7, 3, 14, tzinfo=UTC).isoformat()
state, stale = {}, {}
def write(seen):
    state[key] = {"at": NOW.isoformat(), "result": "dispatched",
                  "attempts": int(seen) + 1, "code_id": "x" * 16}
    return state[key]["attempts"]
for read in (state, state, state, stale):        # A, B, C, then the stale pass D
    print(write(read.get(key, {}).get("attempts", 0)))

# E5 — how many minutes a day each slot is dispatchable for
day = dt.datetime(2026, 11, 7, tzinfo=UTC)
for filename, _name, crons in workflow_files():
    if filename in S.NEVER_DISPATCH:
        continue
    n = sum(1 for m in range(1440)
            if (lambda now, slot: slot and now >= slot + S.DISPATCH_AFTER
                and now <= slot + S._slot_window(filename, crons, slot))(
                    day + dt.timedelta(minutes=m), prev_occurrence(crons, day + dt.timedelta(minutes=m))))
    print(filename, round(n / 60, 1), "h/day")

# E6 — the roster and the attempts each model is allowed
print(live_model(), [(m, model_attempt_limit(m), m in TWENTY_A_DAY_MODELS)
                     for m in text_model_candidates()])
```

## 49. Finding 34 — what production runs today, versus what this branch measures

Every experiment above ran against this branch. Production runs `main`, and `main` is
this branch **minus R1 and R2**:

| Fact | `main` (production) | this branch |
| :--- | :--- | :--- |
| `state[key]["attempts"] = attempts + 1` from a stale read | `main:781` | `:796` |
| coverage test returns `"every channel already published for this slot"` | `main:526` | same |
| `_attempt_cap` produce 7 / brain 3 | `main:116` | same |
| `MAX_CALLS_PER_RUN = 40`, per channel job | `main:202` | same (`:651`, `:812`) |
| `DEPRECATED_TEXT_MODELS = ("gemini-3.7-flash",)` while 3.7 stays in the chain | `main:192` | same |
| attempts per model | **2 for every model** (`main:587`) | 3 for the two 500/day models, 2 for the rest |
| requests for one fully-rejected logical call | **10** (`5 models × 2`) | 12 |
| quota-aware stop, salvage, retirement skip | absent | R1 |

So §42–§48 are production facts, with one correction: **the cost of a rejected script
is 10 requests in production today, not 12.** R1 raises it to 12 because it grants a
third attempt to the two models that have 500 requests a day — which is the wrong way
round, and worth watching when R1 lands: the cheap models can afford attempts, the
expensive ones cannot.

## 50. Finding 35 — the real ceiling is ten speech requests a day, and it is spent before the work starts

`pipeline/gemini_tts.py` states it in a comment (`:84–:99`): *"The free tier allows 10
generateContent requests per day for `gemini-3.8-flash-tts`"*, which is why chunks were
raised from 450 to 4,000 characters. The API says the same thing, in public, every time
it refuses:

```
429 RESOURCE_EXHAUSTED
  quotaMetric: generativelanguage.googleapis.com/generate_content_free_tier_requests
  quotaId:     GenerateRequestsPerDayPerProjectPerModel-FreeTier
  quotaValue:  10        model: gemini-3.8-flash-tts
  retryDelay:  81935s    → please retry in 22h45m35s
```

Three refusals, three days, read straight off the annotations:

| When (UTC) | `retryDelay` | Implied reset | Budget gone by |
| :--- | :--- | :--- | :--- |
| 5 Nov **00:26:54** | `7h33m5s` | 08:00Z | **before 00:27** — 16 hours into the window |
| 6 Nov **08:36:25** | `23h23m34s` | 08:00Z next day | **36 minutes after reset** |
| 7 Nov **09:14:24** | `22h45m35s` | 08:00Z next day | **by 08:29** (see §51) |

The budget is two requests for a long-form (882 words ≈ 2 chunks at 4,000 chars) and one
for a Short. A channel-day is three. The whole plan — three channels, one long-form and
one Short each — is nine of ten, with **one** request of slack for retries.

And the same script keeps being rendered:

| Day | Length | Result |
| :--- | :--- | :--- |
| 5 Nov 00:23:52 | 882 words | 429 after 182.3 s |
| 6 Nov 08:36:20 | 882 words | 429 after 4.9 s |
| 7 Nov 08:29:06 | 882 words | no audio after 4.6 s |
| 7 Nov 08:46:16 | 882 words | no audio after 7.5 s |
| 7 Nov 09:14:21 | 882 words | 429 after 2.5 s |

**Five attempts at one piece of narration, across three days.** Each attempt is two
requests against a budget of ten. The pipeline does not know it is re-rendering the same
text, because it never records that it spent anything.

## 51. Finding 36 — one condition, three error shapes, and the label is wrong in two of them

The same exhausted budget surfaces as three different exceptions, and only one of them
is named correctly:

| Shape | Text | What the code says | True? |
| :--- | :--- | :--- | :--- |
| 429 `RESOURCE_EXHAUSTED` | explicit quota metric, `quotaValue: 10` | `GeminiQuotaExceededError`, notes the reset | ✅ |
| **200 with no audio** | `mime_types=none`, no text | `_report_drift`: *"model-contract drift, not quota and not retryable. Set GEMINI_TTS_MODEL or update DEFAULT_MODEL"* | ❌ |
| 400 `INVALID_ARGUMENT` | `Unknown name "speechMetadata"`, `Unknown name "speechConfig"` | bubbles up as a raw `ClientError` | ❌ |

The middle row is the one that matters. Forty-five minutes apart, at 08:29 and 09:14 on
7 November, the **same request** against the **same model** returned first an empty 200
and then an explicit 429. They are one condition. The 200 case is what a spent budget
looks like when the Interactions endpoint answers politely, and it is being reported to
the operator as SDK drift with instructions to change the model name — the one action
that cannot help, and which would break a working pipeline if taken.

This breaks the rule this work is held to: **a quota failure must never be reported as a
format failure.** It also mis-times the recovery: the API hands over `retryDelay`
(81,935 s, to the second) and nothing in this repository reads `RetryInfo` — the only
references are inside `google/api_core`. `calculate_next_quota_reset_utc()` is then used
only on the path that already knows it is a quota error.

The third row is a separate defect: the `generateContent` fallback at `:648` builds
`types.SpeechConfig`, a field the endpoint rejects by name. That path fails 100 % of the
time (1.3 s, 6 Nov 08:05:20), so it is not a fallback — it is a guaranteed failure that
only adds a second, more confusing error to the first.

The fix is small and offline-testable: count speech requests per (project, model, day)
in the same state file the supervisor already writes; when a response carries no audio
**and** the day's counter is at the cap, raise `GeminiQuotaExceededError` with the
counter as evidence; delete the `generateContent` fallback or fix its field names.

## 52. Finding 37 — produce has not succeeded in 44 hours, and the health job cannot say why

| Fact | Value |
| :--- | :--- |
| last successful produce run | **5 Nov 13:14Z** (`42033981791`, 27.9 min) |
| produce runs since 6 Nov 07:00 | 12 — 11 failure, 1 cancelled, **0 success** |
| 6 Nov, 08:00–08:31 | five produce failures in 31 minutes, all inside the 882-word render |
| automation-health, last 60 runs | **12 consecutive failures**, last success 6 Nov 15:33Z |
| those 60 runs | 45 `push`, 12 `workflow_run`, 3 `schedule` |

Every health run inspected stops at the same step:

```
5 Are the crons firing?:            success
6 Prove the channels are in parity: failure
7 File or close the stall issue:    skipped
```

Step 7 carries `if: github.event_name != 'push'` and nothing else — no `always()` — so a
failing parity step skips the one step whose job is to say what is wrong. The run goes
red and reports **a step name**, which is precisely the failure mode §45 describes from
the other side: three faces of one content gap, and the alarm that could name it is
switched off by the alarm it would explain.

The 45 push-triggered runs are the second half of the problem: every chore commit
(`[skip ci]` does not prevent `push` events for the job's own paths) re-installs
dependencies and re-fails, so the one genuinely informative check is drowned in its own
retriggers.

## 53. Round 5 conclusion — the pump and the ceiling multiply

Read the three findings together and the last 44 hours have a single cause:

1. prayer3 has no scripts, so the coverage test can never be satisfied (§42), so the
   supervisor dispatches `produce.yml -f channel=prayer3` on every pass (§32, §42);
2. every one of those runs renders the **same** 882-word narration, two speech requests
   each, against a budget of ten (§50);
3. when the budget is gone the endpoint answers 200-with-no-audio, the pipeline calls it
   SDK drift and stops the run with the wrong remedy (§51);
4. the health job that could report any of this fails on an unrelated parity assertion
   and skips the step that files the issue (§52).

Nothing here is a hosting, checkout, runner or bandwidth problem. It is one missing
content input, amplified by a dispatch loop with no memory, into a 10-request ceiling
being spent before the day's work begins.

**Revised order.** R16 still leads, because it is the amplifier. It is now followed not by
R12 but by the speech-budget fix (R19 below), because a correct dispatch loop still only
buys three requests of headroom:

| # | Item | Why now |
| :-- | :--- | :--- |
| **R16** | coverage test only over channels the plan can serve; empty channel = supply fault | §42 — proven by execution |
| **R19** | speech-request ledger per (project, model, day); empty audio at cap = quota, not drift; drop the dead `generateContent` fallback | §50, §51 — the actual blocker |
| **R5** | cold start: `max_authors = shortfall` for a channel at zero | §44 |
| **R12** | preflight must not spend completion quota | §22 |
| **R3** | per-day request ledger for the brain too | §43 |
| **R9** | break the watcher loop | E5 |
| **R10** | API-derived dispatch dedupe | E4 |
| **R20** | health: `if: always()` on the filing step, `continue-on-error` on parity, and no push trigger | §52 |
| remaining | R8″, R13, R17, R18, R2a, R11, R14, R15 | unchanged |

**Predictions.** (1) Adding six scripts to `content/queue/` for prayer3 turns the parity
step green, stops the `channel=prayer3` dispatches, and produce's next run renders
without a 429 — all three at once, no code changed. (2) A speech-request counter alone,
with no other change, will make the next day's first failure say *quota* — and the run
after it will still fail, because nothing yet stops the second dispatch from trying.
(3) The `generateContent` fallback has never once returned audio; every 400 in the run
list that names `speechConfig` is it.

---

# Round 6 — the ledger says five, the quota says ten, and the channel says nothing at all

Round 5 ended with a claim I have to correct. It read the empty-200 and the 429 as one
condition. The 6 November morning shows they are two, and the order they arrived in
names the cause.

## 54. Finding 38 — the supervisor's own ledger, read from production

`content/monitor/dispatched.json` on `main` is the record §42 (E4) reproduced in a
sandbox. In production it has 25 keys. The produce slot, verbatim:

```
2026-11-02T10:47:51  produce.yml@2026-11-02T06:14:00+00:00  n=3  dispatched
2026-11-03T19:55:39  produce.yml@2026-11-03T14:14:00+00:00  n=3  dispatched
2026-11-05T09:41:38  produce.yml@2026-11-05T06:14:00+00:00  n=3  dispatched
2026-11-06T08:31:14  produce.yml@2026-11-06T06:14:00+00:00  n=5  dispatched secret-place; prayer2 next pass (content-…
2026-11-07T09:12:53  produce.yml@2026-11-07T06:14:00+00:00  n=3  dispatched secret-place; prayer2, prayer3 next pass
```

`n` is `attempts`: how many times that slot has been dispatched **today**. The cap is 7
(E1). On 6 November it reached 5.

Those five dispatches are visible as five runs, 08:00:36 → 08:31:16, and each one's
synthesis step is in its annotations:

| Run started | Synthesis at | Words | Result |
| :--- | :--- | ---: | :--- |
| 08:00:36 | 08:05:18 | 1102 | `400 INVALID_ARGUMENT` — `Unknown name "speechMetadata"`, `Unknown name "speechConfig"` (1.3 s) |
| 08:06:11 | 08:10:36 | 1102 | `400 INVALID_ARGUMENT` (1.1 s) |
| 08:13:17 | 08:24:50 | 882 | `no audio content … mime_types=none` (6.2 s) |
| 08:26:45 | 08:28:42 | 882 | `no audio content … mime_types=none` (4.7 s) |
| 08:31:16 | 08:36:20 | 882 | `429 RESOURCE_EXHAUSTED`, quota 10, `retry in 23h23m34s` (4.9 s) |

Five retries of one slot, in thirty-one minutes, ending in the day's quota at 08:36.

## 55. Finding 39 — the arithmetic that closes: attempts × requests = the day

The 06:14 slot on 6 November: `n=5` in the ledger, five runs in the log, and
`limit: 10` in the 429 twelve minutes after the fifth started. Each run attempted a
long-form narration, which this repository chunks at 4,000 characters:

```
882 words  → 5,241 characters → 2 TTS requests   (measured, §57)
```

**5 attempts × 2 requests = 10 — the whole day, spent by one slot's retry loop, before
eight in the morning.** The cap allows 7 attempts, which on a three-chunk day would be
21 requests: two days of quota for one slot. The ledger and the refusal are the same
number, and they are three lines apart in two different systems.

This is what makes R16 expensive. The dispatch pump is not only noisy — each extra
dispatch of a slot that cannot succeed is *two speech requests*, and the ledger's own
counter (n) is not connected to the quota in any way.

## 56. Finding 40 — correcting Round 5: the empty 200 is not the quota

§51 said the 429 and the empty-200 were one condition. The 6 November order disproves
it, and the arithmetic is unambiguous:

- At 08:05 and 08:10 the same pipeline made two requests and got **400s**. A malformed
  request is not served, so **it consumes nothing**.
- At 08:24 — nineteen minutes into a day that had not yet spent a single request — the
  next attempt returned **200 with no audio**. A quota that has not been spent cannot
  be the reason.

So the empty 200 is its own failure: the model accepts the request and produces nothing.
What it *does* do is count. Six minutes later the day is gone, and by 08:36 the same
request returns the honest 429.

The corrected picture:

| Shape | What it is | Costs a request? | What the code calls it |
| :--- | :--- | :--- | :--- |
| `400 INVALID_ARGUMENT` (`speechMetadata`, `speechConfig`) | malformed request — a broken path | no | raw `ClientError` |
| `200`, `mime_types=none` | the model returned no audio | **yes** | "model-contract drift" |
| `429 RESOURCE_EXHAUSTED` | the day's ten are spent | — | `GeminiQuotaExceededError` |

The middle row is the actual defect, and it is worse than a mislabel: **a failure that
produces nothing still spends the budget.** Two of them plus a retried Short is a day.
The pipeline's own advice — "not retryable, set `GEMINI_TTS_MODEL`" — is applied to the
one failure that *is* worth retrying with a different delivery recipe, and withheld from
the one that is not.

Which recipe? `DELIVERY_RECIPE = "tts-v4-speech-metadata-style"` sends the style in
`speech_metadata`. The 400s at 08:05 and 08:10 name exactly that field
(`Unknown name "speechMetadata" at contents[0].parts[0]`) and were returned by the
`generateContent` fallback (`:648`, `types.SpeechConfig`). So on the morning of
6 November this repository had two paths: one rejected by name, and one that returns
silence. The 1,102-word script never got a single request served; the 882-word script
got silence twice and then the quota.

## 57. Finding 41 — the root cause: a script's channel is whatever the model remembered to write

Round 5 said prayer3 has no scripts. Here is why, executed against the real queue:

```
declared `channel:` in content/queue/  →  {<absent>: 25, prayer2: 2}
parsed doc.channel                     →  {secret-place: 25, prayer2: 2}
publishable_longform('secret-place')   →  19
publishable_longform('prayer2')        →   2
publishable_longform('prayer3')        →   0
```

Twenty-seven queued scripts. **Twenty-five declare no channel at all**, so they parse as
`secret-place` — the default. Two declare `prayer2`. Nothing declares `prayer3`, and
nothing can, unless the model volunteers the line.

Both shapes came from the same author:

```
4880f6e gemini-brain-bot chore(brain): autonomous scripture queue replenishment [skip ci]
  content/queue/0039-mark-1-35-rising-early-to-pray.md      → channel: prayer2
  content/queue/0033-numbers-6-24-26-the-priestly-benediction-of-peace.md → (no channel line)
```

One bot commit, one channel declared, one not. And nothing checks. `verify_and_stage`
runs the finance-niche validator, writes a factcheck worksheet and generates a companion
Short — it never compares `doc.channel` to `self.channel_id`:

```python
doc = parse_script(script_path)
_validate_finance_niche(doc)
factcheck_main([doc.id, "--force"])
short_path, _ = self.generate_companion_short(doc)
return BrainGenerationResult(...)          # doc.channel is never examined
```

`docs/MIDDAY_WATCH_BRANDING.md:36` states the design: *"scripts declare their owner in
frontmatter (`channel: prayer3`), the pipeline refuses cross-channel…"*. The refusal does
not exist in the code path that writes scripts.

**The loop this closes.** A brain run for prayer3 authors a script whose front matter may
omit `channel:`; it lands in `content/queue/` attributed to secret-place. prayer3's
`publishable_longform` stays 0, so the parity gate stays red, so the coverage test stays
unsatisfiable, so the supervisor keeps dispatching `channel=prayer3`, so produce re-renders
the same head-of-queue script, so the channel's ten speech requests go, so the run fails,
so the parity gate stays red. Every finding in this document from §32 onwards is downstream
of a missing front-matter line and the missing assertion that would have caught it.

## 58. Finding 42 — two reds nobody counted, and forty-four Pages builds

Today, 00:00Z–10:00Z, every workflow run by count:

| Workflow | Runs | Result |
| :--- | ---: | :--- |
| pages build and deployment | **44** | 30 `cancelled`, 14 success |
| Scheduler supervisor | 27 | 26 success, 1 cancelled |
| Automation monitor | **12** | **12 failure** |
| Dry-run pipeline (CI proof) | **11** | 8 failure, 3 cancelled |
| Produce video | 3 | 3 failure |
| Gemini Brain | 1 | 1 failure |

- **Automation monitor: 12 of 12 failed** — and it is the one component telling the
  truth. Its annotations name the causes precisely: *"gemini_brain.yml: FAILING — failed
  3.7h ago and nothing was changed since"*, *"The Midday Watch has nothing in
  content/queue/ that is approved and over the 850-word floor … check
  `python scripts/gemini_brain.py --ensure-supply-for prayer3`"*. It fails **by design**
  when it finds a stall, so its redness is accurate reporting, drowned by the other ten
  reds.
- **Dry-run pipeline (CI proof): 8 failures on push**, from one assertion:

  ```
  AssertionError: 6 not greater than or equal to 8
  tests/test_channel_autopilot_lock.py::TestShortKeyAndNonPsalmIntegrity::
      test_all_staged_shorts_are_ready_and_enriched_with_selar_links
  ```

  Executed here: `queue_report()` returns **6** rows — `short-psalm91v5` `not_approved`,
  and five `ready`. The test requires a staging depth of 8, which the release path
  consumes faster than the poster refills. Same shape as the parity gate: an inventory
  invariant enforced as a hard CI failure with nothing that maintains the inventory. (And
  the release path selected `short-psalm91v5` — the `not_approved` one — for narration
  this morning, which is the reverse of the rule the test is trying to protect.)
- **44 Pages deployments in ten hours**, 30 of them cancelled: every content commit
  triggers a build of the docs site. That is the largest single consumer of run minutes
  in the repository.

## 59. Finding 43 — the plan does not fit the quota, even when everything works

Ten speech requests a day, per project per model (§50). The plan, per channel per day:

| Item | Requests |
| :--- | ---: |
| long-form narration (882 words → 2 chunks) | 2 |
| companion Short narration | 1 |
| **one channel-day** | **3** |
| three channels | **9** |
| remaining for every retry, every re-render, every queue repair | **1** |

One. And the supervisor's produce cap is 7 dispatches per slot per day, each of which
may attempt 3. There is no configuration of the current design in which three channels
publish daily *and* survive a single failure. That is not a bug to fix at the margin; it
is a budget the pipeline has never been able to keep, which is why the published ledger
(§31) shows 9 long-form videos in ten days rather than 30.

Two ways forward, and they are not mutually exclusive: make the requests count
(4,000-character chunks are already the maximum sensible size — 2 is the floor for a
six-minute prayer), or stop paying twice for the same narration.

The chunk cache exists for exactly the second reason and cannot help here. It is wired
properly — `actions/cache/restore@v4` on `output/*/_gemini_chunks_*`, saved with
`if: always()` under `chunks-tts-v4-${{ github.run_id }}` with the prefix key `chunks-`
— but it only ever holds chunks that were *finished*. Every one of the attempts in §55
died on the first chunk (1.1 s, 4.7 s, 4.9 s, 6.2 s), so there was nothing to restore,
and each retry paid full price. A cache rescues a run that stalls at chunk 2 of 3. It
cannot rescue a run whose narration never starts, which is the only failure this
pipeline currently has.

## 60. Round 6 ranking — attribution first, then the amplifier

| # | Item | Why here now |
| :-- | :--- | :--- |
| **R21** | stamp `channel:` at authoring from `self.channel_id` and **refuse** a script whose declared channel differs; assert it in `verify_and_stage` | §57 — the root cause; the docs already promise this |
| **R16** | coverage test only over channels the plan can serve; empty channel = supply fault, not a dispatch | §42, §55 — the amplifier, and it spends quota |
| **R19** | per-request speech counter; empty-200 at cap = quota; a request that returns no audio still counts and must be visible | §55, §56 |
| **R19b** | make the delivery recipe produce audio, and delete the `generateContent` fallback that returns `400` by name | §56 — the only failures worth a fix are the ones that produce nothing |
| **R5** | cold start (`max_authors = shortfall`) — now *after* R21, since without it the scripts still cannot be attributed | §44, §57 |
| **R12** | preflight must not spend completion quota | §22 |
| **R3** | per-day request ledger for the brain | §43 |
| **R20** | health: `always()` on the filing step, `continue-on-error` on parity, no push trigger | §52 |
| **R22** | CI proofs that assert content inventory (parity ≥1 script/channel, ≥8 staged Shorts) must run as a report, not as a gate — or be given something that maintains the inventory | §58 |
| remaining | R8″, R9, R10, R13, R17, R18, R2a, R11, R14, R15 | unchanged |

**Predictions, falsifiable from the next pass's own files.**

1. A brain run for prayer3 that succeeds will produce a file with **no `channel:` line**
   more often than not — 25 of the 27 precedents say so. Stamping it is a one-line change
   in `replenish_pipeline`, and it is the difference between a channel that can be fed and
   one that cannot.
2. With the channel stamped, prayer3 needs six scripts and the parity gate goes green —
   and the `channel=prayer3` dispatches stop without touching the supervisor at all.
3. The day's speech budget will still be spent by 09:00 until the *dispatch* count is
   connected to the request count. Fixing the labels without fixing the counter changes
   what the failure says, not whether it happens.

---

# Round 7 — the engine that was already installed, and the day the pump was born

## 61. Correction to §56: the `400` was the SDK, not a dead fallback

§56 called the `400 INVALID_ARGUMENT` a `generateContent` fallback that "has never once
returned audio". That was wrong, and `requirements.txt` on `main` says so in its own
words:

```
# PINNED BELOW THE NEXT MAJOR, deliberately. `google-genai 3.0.0` shipped on
# 2026-11-06 at 02:29 UTC and the very first narration after it was installed
# (08:05 UTC, produce run 42184629022) died with
#   400 INVALID_ARGUMENT. Unknown name "speechMetadata" at contents[0].parts[0];
#       Unknown name "speechConfig" at generation_config
# … The same code, same workflow, same model published at 21:51 UTC the night
# before on 2.34.0.
google-genai>=2.34,<3
```

The pin cites the same run I pulled the annotation from. So the two `400`s at 08:05 and
08:10 were **the primary path on SDK 3.0.0** — an unpinned `>=2.34` that resolved to a
major release at the worst possible moment — and they stopped the moment `a9a670f` landed
at 08:11. What followed (empty audio at 08:24) is a *different* failure, and it is the one
still live.

Timeline for the morning of 6 November, all times UTC:

| Time | Event |
| :--- | :--- |
| 02:29 | `google-genai 3.0.0` published |
| 07:57 | `e0e66c0` — "recover slots on the scheduler's real behaviour" |
| 08:00:36 | first produce run of the day installs 3.0.0 → `400` |
| **08:06** | **`9eb30ee` — "a produce slot is served per channel, judged by receipts"** |
| 08:11 | `a9a670f` pins `<3` → `400`s stop |
| 08:13–08:31 | three more dispatches → empty audio ×2 → `429` |
| 08:43 | `8165a42` — "never dispatch into a quota cooldown" |

## 62. Finding 44 — the narration that fails is the *long* request

Measured on the real queue, with the real chunker:

```
0015-psalm-91-5-6-deliverance-from-terror-by-night.md
  words=882  chars=5237  chunks=2  sizes=[3870, 1362]  channel=secret-place
```

The renderer chunks at `TTS_CHUNK_CHARS = 4000`, so the first request carries **3,870
characters** and the second 1,362. Every long-form failure in §54 is on that first chunk,
in 4.6–6.2 seconds.

And the same model narrated successfully on the evening of 6 November — four Shorts
published at 14:19, 20:33, 20:46 and 23:49 — whose narration is a single request of
roughly a third that size. So:

- the model is not withdrawn (four Shorts that evening say so);
- the quota was not the cause at 08:24 (nineteen minutes into a fresh day, §56);
- the request that fails is the one that carries ~3,870 characters.

That is a correlation, not a proof, and it is cheap to falsify: `TTS_CHUNK_CHARS` is
already an environment override (`500–20000`, `:108`). Set it to `2000` and the same
script becomes **three** requests of ~1,750 characters — one more request, and if the
hypothesis is right, the first working narration since 5 November.

## 63. Finding 45 — the free engine is installed, wired … and unreachable

`pipeline/tts.py:synthesize()` already implements the chain this pipeline needs:

```python
gemini_key = get_gemini_api_key()
if gemini_key:
    try:
        synthesize_gemini_audio(text, audio_path, voice=voice)
        engine = "gemini-api"
    except GeminiQuotaExceededError:
        raise                                   # $0.00 lock: fail closed
    except Exception as exc:                    # ← incl. "returned no audio content"
        print(f"[tts] gemini-api unavailable ({exc!r}); falling back to edge-tts")

if engine != "gemini-api":
    ... asyncio.run(_edge_tts(text, edge_voice, ...))       # free, no API key
    ... except: _placeholder_audio(...)                     # last resort, silence
```

`edge-tts>=6.1` is in `requirements.txt`. It needs no key. It is the engine that narrated
this channel before Gemini was adopted.

And the path that actually runs these three channels never reaches it.
`pipeline/run.py:251` routes every faith document to the prayer renderer:

```python
# "Use only the approved prayer renderer; never fall back to the old style."
from .prayer_pipeline import produce
```

and `prayer_pipeline.produce()` calls the model directly, with no `try`:

```python
with stage("speech synthesis", f"{doc.word_count} words, Charon"):
    synthesize_gemini_audio(doc.full_narration, audio, voice="Charon", model=DEFAULT_MODEL)
```

Three facts follow. The comment's intent — *never fall back to the old style* — is a
statement about **quality** (an older, worse delivery recipe). It was implemented as a
statement about **engine**, and those are not the same thing: falling back to edge-tts
would change who speaks, not how the script is written. Second, `synthesize()`'s
`except Exception` is precisely the branch that would catch "returned no audio content" —
the live failure — and it cannot be reached from `run.py` for these channels. Third, a
channel that cannot speak tonight could speak tonight, at zero cost, with a fallback that
already exists and is already tested by the old path.

That is the cheapest thing in this document. It is also the one the $0.00 lock permits:
edge-tts is free, it consumes no Gemini quota, and it cannot borrow another channel's key.

## 64. Finding 46 — the pump has a birth certificate

`git log` on `scripts/scheduler_supervisor.py`, plus the commit body of `9eb30ee`:

> *"The first live recovery pass published for one channel only. The supervisor fired
> both legs one second apart; `content-state` allows a single pending run, so GitHub
> cancelled the secret-place leg before it got a runner… Receipts, not runs, decide."*

That commit introduced `published_channels_since()` and the one-channel-per-pass
dispatch:

```python
missing = [c for c in _channels() if c not in published_channels_since(since)]
if not missing: ...
channel = missing[0]
rest = [c for c in missing[1:]]
```

The ledger shows what happened next, and it is the cleanest before/after in the whole
document:

| Slot | `attempts` (n) |
| :--- | :--- |
| 2026-11-02T06:14 | 3 |
| 2026-11-03T14:14 | 3 |
| 2026-11-05T06:14 | 3 |
| **2026-11-06T06:14** | **5** ← first day of per-channel dispatch |
| 2026-11-07T06:14 | 3 |

Three was the pattern for four days; five arrived on the first day the supervisor began
dispatching a single named channel and re-testing coverage on the next pass. The intent
was right — the cancellation problem it fixed was real — but it converted one dispatch
into a *loop*, and nothing in the loop knows what a dispatch costs.

## 65. Finding 47 — one part of this pipeline has quota memory, and it is not the part that needs it

`short_release.py` handles a quota failure by writing state:

```
[short-release] Manifest <name> marked as quota_paused.
qdata["status"] = "quota_paused"
```

and the selector re-arms it on a new day (`:504`, `:513`) — a `quota_paused` Short is
promoted back to `approved` when the window has turned. `content/shorts-queue/0015-short-psalm91v5.yml`
carries exactly that status right now, which is why this morning's first Short attempt
was that manifest.

So the repository already has the pattern R19 asks for: a per-item, persistent,
quota-aware status that survives runs. The long-form path has none of it. Its narration
cache is keyed on `DELIVERY_RECIPE + model + voice + text` and is written **only on
success** — so a failed render leaves no trace, no cooldown, and no memory that two
requests were just spent. The same idea, one directory over, is the whole fix.

## 66. Round 7 ranking — restore the free engine first

| # | Item | Cost of doing nothing |
| :-- | :--- | :--- |
| **R23** | prayer path: catch the no-audio/quota failure and fall back to `tts.synthesize()` (edge-tts, free), keeping the prayer *style* when Gemini answers | every channel silent since 5 Nov |
| **R21** | stamp + verify `channel:` at authoring | prayer3 can never be fed |
| **R16** | coverage test only over servable channels | each pass spends a slot's two requests |
| **R19** | speech-request counter + `quota_paused`-style state for long-form | the day is spent by 09:00 |
| **R24** | try `TTS_CHUNK_CHARS=2000` — one-line experiment, no code | the long-form path stays broken even after R19 |
| **R5** | cold start | prayer3 at zero |
| **R20**, R22, R12, R3 | health `always()`, inventory gates, preflight, brain ledger | alarms that cannot speak |

**Predictions.**

1. `TTS_CHUNK_CHARS=2000` on the next produce run: if the hypothesis in §62 holds, the
   first chunk request succeeds and the run gets two-thirds of the way to a video before
   its third request. If it fails identically at ~1,750 characters, the size theory is
   dead and the remaining difference is the Short path's single-call shape.
2. An edge-tts fallback in `prayer_pipeline` publishes a video **within one dispatch**
   and spends zero Gemini requests. If it does not, the failure is downstream of
   narration and every TTS finding in this document is a red herring.
3. Removing `pushed:`/`workflow_run` triggers from automation-health (R20) will not
   change a single failure — 12 of 12 are the parity assertion — but it will stop the
   alarm from being dismissed as noise, which is the only reason it is still unread.

---

# Round 8 — the pause is undone by the act of looking

R23 and R25 are implemented on this branch (§73). This round is what the code says once
narration stops being the only question.

## 67. Finding 48 — a paused script is re-armed by the next selection, so the pause lasts zero runs

The long-form path *does* keep quota state, and it is written well. Annotation from
run `42109221833`, 5 November 21:04:

> *"Gemini quota is exhausted; `0015-psalm-91-5-6-deliverance-from-terror-by-night.md` is
> paused until 2026-11-06T08:00:00+00:00 UTC and nothing was uploaded."*

That is the sentence this repository should be able to say about every failure: the item,
the reason, the time it can be tried again, and the fact that nothing went out. The
script carries `status: quota_paused` and a `paused_until`.

But the pause is released by **selection**, not by a scheduler:

```
$ python -c "from pipeline.run import select_jobs; print(select_jobs(next_flag=True))"
[run] Quota reset time passed (2026-11-07T08:00:00+00:00). Auto-unpausing
      0015-psalm-91-5-6-deliverance-from-terror-by-night.md...
[run] skip 0038-lamentations-3-22-23-new-mercies-every-morning.md: channel=prayer2
      (this run targets secret-place)
select_jobs -> ['content/queue/0015-psalm-91-5-6-deliverance-from-terror-by-night.md']
```

Two things fall out of four lines of output. First: **the first produce run after 08:00Z
un-pauses the script and immediately re-renders it** — the quota resets at 08:00Z and the
pauses are written to expire at 08:00Z, so the pause protects exactly nothing. The script
is paused until the moment it is allowed to fail again, and the next look releases it.

Second: the selector is channel-aware (`skip … channel=prayer2 (this run targets
secret-place)`), which confirms §57 from the other side — a run with no `-f channel=`
serves secret-place, and the twenty-five unattributed scripts are exactly what it finds.

So the same 882-word script is not stubborn. It is *restored*: paused at 21:04 on
5 November, released at 08:00 the next morning, attempted at 08:13, 08:26 and 08:31,
refused by the model three times, released again the next morning, attempted at 08:29 and
08:46. Five attempts at one narration across three days, each two requests, and the
mechanism that made it repeatable is the reset time being the same instant as the
release time.

## 68. Finding 49 — only a quota refusal changes the script's state; silence changes nothing

| Failure | Raises | Writes state? | Next pass |
| :--- | :--- | :--- | :--- |
| `429` on the day's ten | `GeminiQuotaExceededError` | `status: quota_paused`, `paused_until` | tries again at the reset |
| `200` with no audio | `RuntimeError` | **nothing** | tries again immediately |

The row with no state is the row that has repeated every day since 5 November. A refusal
that leaves the script approved is a refusal the next dispatch cannot see — and the
supervisor's own ledger (§54) is keyed by workflow and slot, never by script, so nothing
downstream can connect "0015 has been attempted five times" to anything.

This is the asymmetry §65 found between the Shorts path and the long-form path, seen from
the other end: the Shorts path at least writes `quota_paused` on a quota error; the
long-form path writes `quota_paused` on a quota error *and nothing at all* on the failure
that actually happens.

## 69. Finding 50 — the queue census, and what is in it that will never publish

```
content/queue/            27 files
  publishable (secret-place)  19
  status: draft                5   ← 0003–0007, finance, never approved
  status: quota_paused         1   ← 0015, released by the next look
  channel: prayer2             2   ← 0038, 0039
  channel: prayer3             0
```

The five finance drafts are the oldest files in the queue and have never been approved.
They are not blocking anything — the selector filters on `status` — but they are the
reason a naive count ("27 scripts queued!") reads as healthy while the channel that is
starving has none. Any dashboard built on `ls content/queue | wc -l` will be wrong by
27 minus 19.

## 70. Finding 51 — duplicate release tickets, and the reason there are only two

`_open_release_ticket` returns early for `privacy == "public"`, so the normal path
produces no ticket at all. When an upload does land non-public, the ticket is opened with
no dedupe key:

```
#250  Release ticket: Psalm 5 Morning Prayer | Begin Your Day in God's Presence
#255  Release ticket: Psalm 5 Morning Prayer | Begin Your Day in God's Presence
```

Two runs, one video, two identical open issues four days apart. It is the smallest defect
in this document — but it is the same shape as everything else here: an action taken
per-run with no memory of the previous run. `video_id` is in hand at the call site and
would make it idempotent.

## 71. Finding 52 — what the next dispatch will actually do

With R23 and R25 on this branch, the next produce dispatch will:

1. select `0015` (shown above, executed), un-pausing it at the same time;
2. ask Gemini for 5,237 characters in two chunks — and get the empty `200` again, because
   nothing about the request has changed;
3. catch it, log that Gemini produced no audio, and narrate with **edge-tts** instead;
4. write `narration.json` with `engine: edge-tts`, keyed to `edge-tts` so a future Gemini
   run re-synthesises rather than reusing the take;
5. spend **zero** Gemini speech requests, where the same path has spent two per attempt
   since 5 November;
6. reach the alignment, asset, encode and upload stages — which is the first time in three
   days any run has got that far.

Steps 5 and 6 are the test of this document. If the next run publishes a video narrated by
`edge-tts`, then every finding from §50 onwards was downstream of an unreachable fallback,
and the remaining list (R21, R16, R19, R24, R5) is about *quality and discipline*, not
about being able to publish at all.

## 72. Round 8 ranking

| # | Item | Status |
| :-- | :--- | :--- |
| **R23** | free-engine fallback in the prayer path | **implemented** (`3a73cdf`) |
| **R25** | the same fallback for Shorts | **implemented** (`975dc55`) |
| **R21** | stamp + verify `channel:` at authoring | open — the root cause (§57) |
| **R26** | a silent refusal must set state, and `select_jobs` must not release a pause it cannot honour | open — §67, §68 |
| **R16** | coverage test only over servable channels | open — §42 |
| **R19** | speech-request counter, honest labels | open — §55 |
| **R24** | `TTS_CHUNK_CHARS=2000` experiment | open — §62 |
| **R5**, **R20**, **R22**, **R12**, **R3** | cold start, health `always()`, inventory gates, preflight, brain ledger | open |

**Prediction.** The first produce run after 14:14Z today publishes a long-form with
`tts_engine: edge-tts` and `0015`'s status moves to published — and `automation-health`
stays red, because prayer3 still has no scripts. One of those two is a fix; the other is
content.

---

## 73. What shipped with this round

```
3a73cdf  R23: let the prayer path fall back to the free engine instead of going silent
975dc55  R25: the Shorts path had the same hole, so give it the same second engine
```

- `pipeline/tts.py`: `synthesize_edge(text, out_path, voice)` — the free engine as a named
  function, returning `(engine, word_times)`. `synthesize()` now calls it instead of
  carrying the same six lines inline.
- `pipeline/prayer_pipeline.py`: `_narrate(doc, audio)` — try Gemini, re-raise
  `GeminiQuotaExceededError` untouched, otherwise speak with edge-tts and report which
  engine spoke. `narration.json` gains `engine`, and a fallback take is cached under its
  own engine so a run with Gemini available re-synthesises. The result record no longer
  hardcodes `'tts_engine': 'gemini-api'`.
- `pipeline/short_release.py`: `_synthesise_narration(text, audio)` — same rule; if nothing
  can speak it returns `placeholder` and the caller keeps its original "refusing to render
  a silent Short" refusal.
- Six offline tests (three each) covering: no-audio falls back and asks Gemini exactly
  once; a spent allowance propagates and never reaches edge-tts; the engine is reported,
  not assumed; a placeholder is silence, not a voice. Full suite: **1050 passed**
  (one pre-existing content-inventory assertion deselected — see R22).

---

# Round 9 — who gets the dispatch, and what the prompt never showed

## 74. Finding 53 — the dispatcher is not a rotation; it is a queue in a fixed order

`dispatch()` picks `missing[0]` where `missing` preserves `_channels()` =
`scheduled_channels()` = `['secret-place', 'prayer2', 'prayer3']`. Executed against the
real function, with `published_channels_since` stubbed to describe each case:

```
channels: ['secret-place', 'prayer2', 'prayer3']

A) nothing served since the 06:14 slot
   -> gh workflow run produce.yml -f channel=secret-place
      "dispatched secret-place; prayer2, prayer3 next pass (content-state takes one pending run)"

B) secret-place served, prayer2/prayer3 not
   -> gh workflow run produce.yml -f channel=prayer2
      "dispatched prayer2; prayer3 next pass (content-state takes one pending run)"

C) secret-place + prayer2 served, prayer3 not
   -> gh workflow run produce.yml -f channel=prayer3
      "dispatched prayer3"

D) all served
   -> (nothing dispatched) "every channel already published for this slot"
```

So the "next pass" promise is conditional on the *current* dispatch succeeding: prayer2
is reached only when secret-place already has a receipt, and **prayer3 is reached only
when both of the others do**. Under a channel that fails every time, the third channel is
not starved by a race, a budget or a bug — it is last in a list and the list never
advances.

## 75. Finding 54 — correction: production has never dispatched prayer3

Round 4 (§32, §42) said the coverage test "builds the exact command that dispatches an
empty channel" and that produce was being "dispatched forever for prayer3". The first
half is true — E9 C shows the command exists — but the second half is not what happens.
In the production ledger, across all 25 keys:

```
$ git show origin/main:content/monitor/dispatched.json | grep -c "dispatched prayer3"
0
$ … | grep -o '"result": "dispatched [^"]*"' | sort | uniq -c
   1 "dispatched secret-place; prayer2, prayer3 next pass (content-state takes one pending run)"
   1 "dispatched secret-place; prayer2 next pass (content-state takes one pending run)"
```

And the runs themselves say who was targeted:

| Run | Job |
| :--- | :--- |
| 08:00:36 6 Nov | `produce (prayer2)` |
| 08:06:11 6 Nov | `produce (prayer2)` |
| 08:13:17 6 Nov | `produce (secret-place)` |
| 08:26:45 6 Nov | `produce (secret-place)` |
| 08:31:16 6 Nov | `produce (secret-place)` |
| 08:27 / 08:44 / 09:12 7 Nov | `produce (secret-place)` ×3 |

The pump's **target** is secret-place; its **cause** is still prayer3 — the coverage test
cannot be satisfied while a channel has no scripts, so no pass ever returns
`every channel already published`, so a dispatch is issued every time. But the dispatch
lands on the first unserved channel, which is secret-place, which then re-renders 0015
(§62: 882 words, `[3870, 1362]`) and spends secret-place's ten speech requests.

That is the whole engine of this outage, stated exactly: **prayer3's missing scripts cause
secret-place's quota to be spent.** R16 was right about the mechanism and wrong about the
victim, and the difference matters for the fix — stopping the loop does not require making
prayer3 publish, only making the test unsatisfiable *and* the dispatch harmless.

## 76. Finding 55 — the prompt states the rule in prose and never shows the shape

`compile_full_brain_prompt('prayer3')` is 9,352 characters. It contains the requirement
exactly once, as a sentence:

> *"Frontmatter must declare `channel: prayer3`, `privacy: public`, `voice: Charon`,
> `format: longform`, and a title ending with `| The Midday Watch`."*

and it contains no front-matter example at all: `slug:` appears **zero** times,
`target_minutes:` **zero** times, and there is no YAML block to copy. The model has to
infer the exact key names from prose, and the census of what it actually wrote is
unusually clean:

| Field | Present in the 27 queued scripts |
| :--- | :--- |
| `id`, `slug`, `title`, `status`, `format`, `niche`, `voice`, `target_minutes` | **27 / 27** |
| `privacy` | 22 / 27 |
| **`channel`** | **2 / 27** |

The model gets nine fields right every single time and omits exactly the one field that
is described only in prose and validated nowhere. That is not sloppiness; it is a prompt
that asks for a key it never shows.

The same defect has already cost one production incident, recorded in the code at
`gemini_brain.py:1128`:

> *"The old fallback here wrote `0040-devotional-0040.md` into the queue on 6 November
> when the model answered with `job_id:` and no `slug:` line, which is how an
> unvalidatable job reached main."*

Two fields, two incidents, one cause. The repair is not a smarter model: it is a literal
front-matter skeleton in the prompt **and** a validator that refuses a script whose
`channel` is absent or differs from the brain's own id (R21).

## 77. Finding 56 — the code already knows a declared channel from a defaulted one

`ScriptDoc.channel` defaults to `secret-place` when the key is missing (`script_doc.py:94`),
and there is a second property beside it:

```python
def explicit_channel(self) -> str:
    """…Docs authored before channel support carry no `channel:` key; callers that
    respect the ambient CONFIG channel (e.g. description building)…"""
```

So "declared" and "defaulted" are distinguishable in the model — and
`publishable_longform(channel_id=…)` uses the *defaulted* one (`doc.channel != wanted`).
That single choice is why 25 unattributed scripts count as secret-place's supply: 19
publishable for secret-place, 2 for prayer2, 0 for prayer3 — while the honest answer is
"19 for whoever wrote them, and nobody declared".

Switching the count to `explicit_channel` would empty secret-place's queue instead of
fixing prayer3 — which is exactly why R21 has to come before any tightening here: stamp at
authoring, then the count can afford to be strict.

## 78. Finding 57 — the five-minute floor has nine seconds of margin, and R23 changes the voice

```python
CHARON_WORDS_PER_MINUTE = 165
MIN_NARRATION_SECONDS = 300
MIN_LONGFORM_WORDS = required_words(MIN_NARRATION_SECONDS) + 25   # 850
850 words / 165 wpm = 309 s   → 9.1 s of margin over the gate
```

The floor is calibrated to *Charon's measured pace* and to nothing else. That is fine
while Charon is the only narrator — and R23 just added a second one. `en-US-DavisNeural`
at `TTS_RATE=+0%` speaks at a similar but not identical rate; if it is ~3 % faster, an
850-word script lands at 300 s or under, and the run fails *after* the narration, with:

> *"…{words} words is too short at Charon's pace — lengthen the script, the floor is 850
> words."*

Charon did not speak. That sentence would be the third mislabel in this document, and this
one I introduced. Two cheap repairs, both worth doing with R28: name the engine in the
message (`at edge-tts/en-US-DavisNeural's pace`), and pin the fallback's rate slightly slow
(`TTS_RATE=-5%`), which buys ~15 s of margin on the same script.

The measured scripts are safe — 882 words is 321 s at Charon's pace, and every queued
script is over 870 words — so this is a margin to close, not an outage to chase.

## 79. Round 9 ranking

| # | Item | Why it moved |
| :-- | :--- | :--- |
| **R27** | dispatch the *least recently attempted* unserved channel, not `missing[0]` | §74 — prayer3 is last and the list never advances; a failing first channel monopolises every dispatch |
| **R21** | literal front-matter skeleton in the prompt + refuse a script whose `channel` is missing or foreign | §76 — nine fields right, one omitted, twice |
| **R26** | a silent refusal must set state; don't release a pause the selector cannot honour | §67, §68 |
| **R16** | coverage over servable channels (now with the target corrected) | §75 |
| **R28** | the narration floor must name the engine that spoke; slow the fallback's rate | §78 — introduced by R23 |
| **R19**, **R24**, **R5**, **R20**, **R22**, **R12**, **R3** | request counter, chunk experiment, cold start, health `always()`, inventory gates, preflight, brain ledger | unchanged |

**Predictions.**

1. With R21 alone (stamp + verify), a prayer3 brain run that succeeds increments
   `publishable_longform('prayer3')` from 0 to 1 on the first script, and the parity gate
   goes green on the sixth. Nothing else needs to change.
2. With R27 alone, the next unserved channel after a secret-place dispatch is prayer2 —
   whose two scripts already exist — so a single pass would publish on prayer2 instead of
   re-rendering 0015. That is a fix that requires no content at all, only an ordering that
   remembers.
3. Leaving both undone, the dispatcher will pick secret-place on every pass for as long as
   the coverage test exists, and secret-place's ten speech requests will be spent by 09:00
   every day.

## 80. What is still unmeasured

Listed so the next round is not a repeat: the alignment model's download path in CI (does
`output/alignment-model` survive a cache miss?); the thumbnail gate's behaviour when a
render is produced by a fallback engine (does it still require a *new* thumbnail per
upload?); whether `metrics.yml`'s 18.7 dispatchable hours mask a second quota pool; and
the comment-reply workflow's `1,000 requests/hour` ceiling against its ten dispatches a
day.
## 81. Is the Midday Watch's quota spent too? No — it is blocked by three other things

Asked directly, and the answer is worth recording because the intuition ("one channel ran
out, so they all did") is wrong in every part.

**Its speech quota has never been touched.** `prayer3` has never rendered anything: no
scripts, and no produce run has ever carried a `produce (prayer3)` leg. Zero of its ten
daily TTS requests have been spent, today or on any day.

**Its text quota is not the visible cause either.** The brain's matrix did include prayer3
today — five times — and every one failed while secret-place and prayer2 succeeded in the
*same* runs:

| Run (UTC) | prayer3 | secret-place | prayer2 |
| :--- | :--- | :--- | :--- |
| 04:54 | failure | success | success |
| 04:58 | failure | — | — |
| 05:39 | failure | success | success |
| 06:00 | failure | success | success |
| 10:04 | failure | success | success |

A shared pool running dry cannot explain three jobs in one run disagreeing. What prayer3's
annotations *do* say is narrower: `Long-form supply empty :: nothing in content/queue can
publish`, and then two `Gemini text model retired` errors for `gemini-2.0-flash` and
`gemini-2.5-flash` — models `RETIRED_TEXT_MODELS` already lists, reached because every live
candidate before them refused. The pass never says *why* they refused, which is the gap
R19 exists to close. (The bot cannot fetch job logs, so "no evidence of exhaustion" is the
strongest honest claim.)

**Three gates block it, and only one of them is about quota.**

1. **No scripts** (§57, §76): 0 publishable, for the front-matter reason.
2. **Half-provisioned**: the two workflows disagree about what "ready" means.
   `gemini_brain.yml:39` gates prayer3 on `secrets.PRAYER3_GEMINI_API_KEY`, and the brain's
   matrix *does* include it — so the key exists. `produce.yml:86` gates prayer3 on
   `secrets.PRAYER3_YOUTUBE_REFRESH_TOKEN`, and no produce run has ever had a prayer3 leg —
   so on the schedule path it does not exist. The channel can author (in principle) and
   cannot publish.
3. **A global cooldown, caused by another channel.** `quota_blocked_until()` scans every
   queued script, whatever its channel, and returns the latest live
   `quota_reset_utc`. `0015` (secret-place) carries:

   ```yaml
   status: quota_paused
   quota_reset_utc: '2026-11-08T08:00:00+00:00'
   pause_reason: gemini_api_daily_quota_exhausted
   ```

   so the cooldown is live until 08:00Z tomorrow, and `supervise()` refuses to dispatch
   `produce.yml` at all while it is (`"never dispatch a publish into a quota cooldown"`,
   `:463`, `:743`). **Secret-place running out of speech idles prayer2 and prayer3 as
   well** — the opposite of the isolation the separate projects were meant to give.

So: not exhausted; starved, unattributable, half-provisioned, and held behind another
channel's pause. The cheapest of the three to settle is the provisioning question — one
secret decides whether prayer3 can ever publish on schedule — and it is a question only the
repository owner can answer.

---

## 82. Correction to §81 — the Midday Watch is fully provisioned, and its key works

The repository owner's secrets page settles it:

| Secret | Last updated |
| :--- | :--- |
| `GEMINI_API_KEY`, `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN` | 2 weeks / last week (unprefixed = secret-place) |
| `PRAYER2_GEMINI_API_KEY`, `PRAYER2_YOUTUBE_*` (id, client id, client secret, refresh token) | 3 days ago |
| `PRAYER3_YOUTUBE_CHANNEL_ID`, `_CLIENT_ID`, `_CLIENT_SECRET`, `_REFRESH_TOKEN` | **8 hours ago** |
| `PRAYER3_GEMINI_API_KEY` | **7 hours ago** |

So gate 2 in §81 is **withdrawn**: `prayer3` has every secret `produce.yml` and
`gemini_brain.yml` gate it on. The channel was provisioned within the last eight hours —
which is why the question "has it exhausted its quota too?" is the natural one, and why the
answer matters: its very first calls are failing, and they are not failing on quota.

**Why no `produce (prayer3)` leg has ever appeared** is now explained, and it is not a
provisioning gap. `produce.yml`'s plan step has two branches:

```bash
case "${{ github.event_name }}" in
  schedule)          channels="$provisioned" ;;            # all three, if ready
  workflow_dispatch) channels='["${{ inputs.channel }}"]' ;; # exactly the one asked for
  *)                 channels='["secret-place"]' ;;
esac
```

Every produce run since the secrets landed has been a **`workflow_dispatch` from the
supervisor with `-f channel=secret-place`** (§75), and that branch replaces the matrix with
a single channel. The scheduled runs that did expand (6 Nov 14:12, 20:26, 23:43) all
predate the secrets, so the matrix had only two entries. The next scheduled run is the
first chance for a prayer3 leg — 14:14Z today.

**Why the brain's prayer3 job still fails.** Its step list is decisive:

```
5 Can this runner reach Gemini?        success   ← the key is valid and the API answers
6 Keep the long-form queue publishable failure   ← --ensure-supply-for prayer3 --min-publishable 6
7 Author specs for Shorts…             skipped
```

Preflight succeeds, so this is not a bad key, not a disabled API, not a missing project.
And it is not quota either: a `429` raises `GeminiQuotaExceededError`, which stops the pass
outright (§43) — but this pass walks **past every live model** and only stops when it
reaches `gemini-2.0-flash` and `gemini-2.5-flash`, which answer `404 no longer available`
because they are retired (§61).

A chain that reaches the retired models has had a script-shaped answer from every live
model and rejected each one. That is the §76 defect seen from the inside: the prompt asks
for `channel:` in prose, shows no front-matter skeleton, the model omits a required key,
validation refuses the script, and the pass tries the next model until there are none left.
For secret-place the omission *silently attributes* the script to the wrong channel; for
prayer3, where nothing is yet approved, it fails outright and leaves the queue empty.

**Consequences for the two open questions.**

1. R21 (front-matter skeleton + a validator that names the missing key) is no longer just
   the fix for misattribution — it is the fix for prayer3's authoring failure, on a channel
   whose credentials are already in place. The next brain run after it should be the first
   to write a prayer3 script that survives validation.
2. The 14:14Z scheduled produce run will, for the first time, contain a
   `produce (prayer3)` leg. It will find nothing publishable and exit non-zero. That is
   correct behaviour and a useful receipt: it will be the first run in this repository's
   history where the third channel's leg exists and says why it cannot work.

---

# Round 10 — the refusal existed; the request never did

## 83. Finding 58 — the key was enforced but never asked for

R21 turned out to be smaller and more embarrassing than §76 described, and the reason is
worth stating precisely: **the guard already existed, and the repair path did not know the
key was required.**

`_enforce_channel_metadata` (`gemini_brain.py:726`) refuses model output that names no
channel or another channel's, and it runs before any file is written. So no unowned script
has been added to the queue since it landed. And yet:

```python
REQUIRED_JOB_KEYS = ("id", "slug", "title", "status", "niche", "thumb_text",
                     "originality")          # ← no "channel"
```

`missing_job_keys()` derives from that tuple, and `_repair_envelope` asks the model for
exactly the keys that function reports:

```python
"Return ONLY a YAML front matter block … containing at least these keys: {missing}."
```

So the sequence on every prayer3 attempt was:

1. the model writes a usable body and an envelope with seven of the eight keys;
2. `missing_job_keys()` returns `[]`, because `channel` is not on the list;
3. `_enforce_channel_metadata` raises — *"frontmatter does not declare channel: prayer3"*;
4. the loop moves to the next model, and repeats until the chain reaches the retired ones;
5. the pass ends with `Long-form supply empty`.

**We rejected the model for not supplying a key we never asked it for.** Five runs on
7 November, all of them, on a channel whose credentials were already in place (§82).

## 84. What R21 changes

| Change | File | Effect |
| :--- | :--- | :--- |
| `channel` joins `REQUIRED_JOB_KEYS` | `gemini_brain.py:118` | `missing_job_keys()` reports it, so step 3 above can never happen silently again |
| `_repair_envelope` supplies the channel verbatim | `gemini_brain.py:601` | the one key the model must not infer is handed to it: `- channel: prayer3` |
| A literal front-matter block opens the prompt | `equipment_registry.py:front_matter_skeleton` | the model sees the key names instead of a sentence about them; the block is templated with the run's channel, default from `CONFIG` |
| `_require_own_channel` gates the write | `gemini_brain.py:1067` | a script that names no channel, or another channel's, never becomes a queue item — whatever route it arrived by |

The parity rule bit immediately: the first draft of the skeleton defaulted with
`channel_id or "secret-place"`, and `tests/test_channel_parity.py::test_no_comparison_names_a_channel`
failed on it — a channel id inside an `if/else`. The default now comes from
`CONFIG.channel_id`, the branch names nothing, and the rule that "channel differences are
data, not code" held against the very change that was written to enforce it.

Eight new tests in `tests/test_brain_channel_attribution.py`, plus an honest rewrite of
`test_every_file_the_brain_wrote_before_is_accepted_today`: it now asserts that the only
thing missing from the 25 legacy scripts is their owner, rather than asserting they are
complete (they are not — that is §57). Suite: **1058 passed**.

## 85. Predictions for the next two runs

1. **The 14:14Z scheduled produce run** is the first with a `produce (prayer3)` leg
   (§82). It will report nothing publishable and exit non-zero — correct, and the first
   receipt of its kind.
2. **The next brain pass after R21 lands** will either write a prayer3 script whose
   envelope declares `channel: prayer3` — in which case `publishable_longform('prayer3')`
   goes from 0 to 1 and the parity gate starts to matter again — or fail with a message
   that names `channel` among the missing keys instead of a generic branding refusal. Both
   outcomes are strictly more informative than the five identical failures of today.

## 86. Round 11 — Post-Consolidation Audit & Multi-Channel Decoupling (2026-11-07 14:45Z)

After PR #327 consolidated `main` (`06e82b2`), live runs confirmed R21 worked (`prayer2`
and `prayer3` both authored two channel-attributed scripts in `run 42380190774`) and
exposed the remaining multi-channel coupling defects:

| Item | Defect found | Fix shipped |
| :--- | :--- | :--- |
| Multi-author summary crash | `SupplyReport.authored` became a `list` when `len(authored) >= 2`, crashing `SupplyReport.summary()` (`AttributeError: 'list' object has no attribute 'get'`) right before commit and discarding all 4 newly authored `prayer2`/`prayer3` scripts | `pipeline/supply.py::SupplyReport.summary` handles both `dict` and `list`; `gemini_brain.yml` refreshes factcheck worksheets and commits valid staged scripts before failing on partial supply |
| **R5** cold-start runway | Empty channels (`publishable_after == 0`) were capped at 2 scripts/pass | `MAX_AUTHORS_WHEN_EMPTY = 4` lets cold-start channels reach >1 day of 3-slot runway in one pass |
| Staged factcheck + expander | `factcheck.py` missed `.incoming/` staged paths and `author_new` mutated `status: approved` after hashing; `tools/expand_scripts.py` still called retired `gemini-2.5-flash` with night-only wording | `factcheck.py` accepts explicit file paths, `author_new` refreshes the sha256 worksheet after approval, and `expand_scripts.py` uses `text_model_candidates()` + `brand_for()` forbidden-phrase gates |
| **R15 + R16 + R27** | `quota_blocked_until()` scanned `content/queue/` globally (so `secret-place` job `0015` blocked `prayer2` and `prayer3`), and `scheduler_supervisor.dispatch` picked `missing[0]` in fixed order | `quota_blocked_until`, `empty_reason`, and `active_quota_cooldown` are channel-scoped; `_unserved_produce_channels` skips empty/cooldown channels and rotates least-recently-attempted channels first |
| **R9** Pages loop | Committing `schedule-health.json` triggered `pages build and deployment`, which triggered `scheduler-supervisor.yml` every ~60s (~350 empty commits/day) | Removed `"pages build and deployment"` from `scheduler-supervisor.yml` `workflow_run` and skipped no-op wall-clock writes in `save_schedule_health` |
| **R18** + 409 artifacts | `produce.yml` shared `chunks-tts-v4-${{ github.run_id }}` and `release-report`/`style-frames`/`render` artifact names across matrix legs, and ran `channel_queue` before `supply` repair | Keyed chunk caches and artifacts per `${{ matrix.channel }}` and moved `channel_queue` after `supply` repair |
| **R20 + R22 + R28 + §70** | `channel_parity.py` failed on 0-inventory channels; `automation-health.yml` skipped issue sync on step failure; fallback `edge-tts` pace/error named `Charon`; duplicate release tickets | Synthetic `Psalm 23:1` parity probe (`PARITY OK` across all 3 channels), `always() && !cancelled()` issue sync, `-5%` `edge-tts` pace + honest engine label, and receipt-backed ticket dedupe |

Suite: **1070 passed** (`tests/test_multi_channel_resilience.py` adds 11 regression guards).
