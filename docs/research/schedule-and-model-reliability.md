# Why the automation is red: cron delivery, the model roster, and quota arithmetic

**Measured 7 November 2026, 08:00–09:40 WAT. Rounds 1 and 2.** Every number below
comes from this repository — the Actions API, the supervisor's own ledger, the run
annotations, and the code that runs — not from a vendor blog. Where a source is
external it is cited in §11 and §16.1.

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
