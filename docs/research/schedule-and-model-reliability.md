# Why the automation is red: cron delivery, the model roster, and quota arithmetic

**Measured 7 November 2026, 08:00–09:40 WAT.** Every number below comes from this
repository — the Actions API, the supervisor's own ledger, and the code that runs —
not from a vendor blog. Where a source is external it is cited in §11.

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

### R1 — Make the retry budget honest (code, ~40 lines)

Cap **total** transient wait per pass, not per model: e.g. 6 requests / 3 minutes of
sleep, with jitter (`5 + U(0,5)`, `15 + U(0,10)`, …), and stop trying a model after 2
attempts when its RPD is 20. Fail with the per-model outcomes already produced by this
branch (`_authoring_failure`) instead of being killed at 30 minutes.
*Effect:* the job always reports a reason; ~60 % less wall clock on a 503 morning.
*Verify:* `tests/test_brain_authoring_resilience.py` extended with a time-budget test.

### R2 — Teach the supervisor the words it is missing (code, ~10 lines)

Add `quota`, `resource_exhausted`, `busy after retries`, `no candidate model`,
`supply empty` to `UPSTREAM_MARKERS`, and treat "supply empty" as downstream-fixable
(dispatch produce's repair path rather than the brain again).
*Effect:* a 429 at 05:39 is retried at 09:47 instead of losing the day.
*Risk:* retry storms — bounded already by `UPSTREAM_RETRY_AFTER = 30 min` and
`UPSTREAM_MAX_ATTEMPTS = 8`.

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
