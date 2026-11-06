# Which Gemini model should this pipeline use — and why the answer is a quota question

*Research note, 6 November 2026. Written after a day in which nothing published and
four different causes were found stacked on top of each other. Every claim below is
either quoted from a primary source, measured in this repo, or marked as unknown.*

---

## 1. The question

On 6 November the pipeline produced nothing. Four causes were peeled off in order:

| # | Symptom | Cause | Fixed by |
|---|---------|-------|----------|
| 1 | `404 NOT_FOUND: models/gemini-2.5-flash is no longer available to new users` | the model was withdrawn on **20 October 2026** | #293 |
| 2 | `503 UNAVAILABLE — high demand` on `gemini-3.8-flash` | service capacity (or free-tier capacity — see §5) | #301, #305, #308 |
| 3 | `429 RESOURCE_EXHAUSTED` on speech | the $0.00 daily speech allowance | #294 |
| 4 | A whole day lost to #2 even after recovery | attempt budgets burned by an outage | #305, #308 |

Cause 2 raised a question this repo had never asked properly: *the model we moved to on
20 October is the newest one, but is it the one our quota can carry?*

## 2. What Google actually serves today

Primary source: the Gemini API **models** and **model-versions** pages, fetched 6 Nov
2026 ([models](https://ai.google.dev/gemini-api/docs/models),
[versions](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/model-versions)).

| Model | Status | Retires | Free tier |
|---|---|---|---|
| `gemini-4-argon` | GA, 13 Oct 2026 | Oct 2027+ | **not available** (paid only) |
| `gemini-3.8-flash` | GA, 2 Sep 2026 | Sep 2027+ | yes — **≈20 requests/day** |
| `gemini-3.7-flash` | **deprecated 8 Oct 2026**, routed to 3.8 | 28 Jan 2027 | — |
| `gemini-3.6-flash` | GA, 21 Jul 2026 | **19 Nov 2026** | yes — ≈20/day |
| `gemini-3.5-flash-lite` | GA, 21 Jul 2026 | Jul 2027+ | yes — **≈500/day** |
| `gemini-3.1-flash-lite` | GA, 7 May 2026 | May 2027 | yes — ≈500/day |
| `gemini-3.1-pro-preview` | preview | — | not available |
| `gemini-2.5-flash` / `-lite` / `-pro` | **retired 20 Oct 2026** | — | legacy keys only |
| `gemini-3.8-flash-tts` | GA, 22 Sep 2026 | — | yes — 3 RPM, **10 requests/day** |

Two facts from that page matter more than the rest:

1. Google's note on the 2.5 models: *"we are limiting access to the 2.5 models to users
   who have actively used them in the past… For any new projects, use our latest
   models: 3.5 Flash-Lite or 3.8 Flash."* — the replacement Google itself names is
   **Flash-Lite**, not Flash.
2. `gemini-3.7-flash` is not retired but is **routed to 3.8**: asking for it does not
   get you a different model, it gets you a name that hides which model ran.

## 3. The free tier: what is documented and what is not

The official [rate-limits page](https://ai.google.dev/gemini-api/docs/rate-limits),
fetched 6 Nov 2026, contains **no free-tier table at all** — only spend-based limits,
tier qualifications, and batch quotas. It says limits "can be viewed in Google AI
Studio" and that "specified rate limits are not guaranteed and actual capacity may
vary."

So the per-model daily figures below are third-party measurements of AI Studio's
rate-limit page, and they disagree with each other in places. Treat them as orders of
magnitude, not contracts:

| Model | RPM | RPD (free) | Source |
|---|---|---|---|
| `gemini-3.8-flash` | 5 | **20** | scriptbyai (19 Oct 2026), aiplug.work ("measured: 20 requests a day", 2 Sep 2026) |
| `gemini-3.6-flash` | 5 | 20 | scriptbyai |
| `gemini-3.5-flash-lite` | 10–15 | **500** | scriptbyai, and the 23 Oct 2026 correction in `mnfst/awesome-free-llm-apis` #176 (30 RPM/1,500 RPD → 15 RPM/500 RPD) |
| `gemini-3.1-flash-lite` | 10–15 | 500 | same |
| `gemini-3.8-flash-tts` | 3 | 10 (named by Google's own refusal in this repo on 3 Nov) | `pipeline/gemini_tts.py` |

**Unknown, and worth stating:** whether this project is on the free tier for *text*.
The speech refusal on 3 November named `gemini-3.8-flash-tts`'s **10 requests per day**
in Google's own words, which is the free-tier shape. Nothing in the repo asserts the
text tier, so the conservative assumption — $0.00 lock, free tier — is the one this
policy is built on.

## 4. The arithmetic that settles it

A single brain pass (`gemini_brain.yml`, one channel) runs four steps:

| Step | Gemini requests |
|---|---|
| `--preflight` | 1 |
| `--ensure-supply-for … --min-publishable 6` | up to ~6 (one per script authored) |
| `--author-shorts` (`author_missing_shorts` + `replenish_shorts_queue(min_ready=6)`) | up to 13 in the queue today |
| `--generate-next` | 1 |
| **Total** | **up to ~21** |

On a 20-request day, **one pass can consume the entire allowance before it finishes**,
and the pass after it fails. That is not a capacity problem and no amount of retrying
fixes it — it is the model choice exceeding the budget by design.

The second half of the arithmetic is the retry stack, which this repo had without
intending it:

```
one logical call = SDK attempts (2) × our attempt loop (5) = up to 10 requests
```

`pipeline/gemini_client.py` set `HttpRetryOptions(attempts=2)` — and the google-genai
SDK retries **5xx including 503** by default (`attempts=3` produces four requests, per
[googleapis/python-genai#3204](https://github.com/googleapis/python-genai/issues/3204)) —
while `_call_model` added five attempts of its own. Ten requests for one preflight
call, on a model whose whole day is twenty. That is how a 3½-hour outage became a
spent day.

## 5. Why `503` and not `429`

`503 UNAVAILABLE — high demand` is capacity, not quota: Google's own message says the
spike is temporary, and the developer forum has the same complaint running for days
([2 Nov](https://discuss.ai.google.dev/t/gemini-3-8-flash-api-continuously-returning-http-503-model-shows-operational-on-status-page/197810),
[6 Nov](https://discuss.ai.google.dev/t/gemini-model-usage-error/198545)) with the
model shown "operational" on the status dashboard. Recovery is commonly quoted at
30–120 minutes; ours lasted at least 3½ hours (09:16Z → 12:42Z).

Two consequences:

- Retrying is right, but **bounded and slowed**: it is a queue of requests against a
  pool that is refusing them, and every request counts against the day.
- A **fallback to a different model** is worth more than a retry of the same one,
  because each model has its own capacity pool — which is what the new chain does.

`HttpRetryOptions` now omits **429**: a quota refusal must reach `quota_handler`,
which pauses the work until the Pacific reset, rather than be retried inside a socket.

## 6. Decision

1. **Primary text model: `gemini-3.5-flash-lite`** — the successor Google names for the
   model this pipeline was built on, with ~25× the daily allowance of 3.8-flash.
   `GEMINI_TEXT_MODEL` still overrides it.
2. **Fallback chain, ordered by allowance first and generation second:**
   `3.5-flash-lite → 3.1-flash-lite → 3.6-flash → 3.8-flash`, with deprecated and
   retired names only after that (so an older key still works, but a retired model can
   never be what we start with).
3. **One retry authority.** The brain builds its client with `attempts=1`; the SDK does
   not retry, `_call_model` does, with 5s/15s/30s/60s and a 30-minute supervisor
   cooldown behind it.
4. **A per-pass ceiling** (`GEMINI_MAX_CALLS_PER_RUN`, default 40) so a bad morning
   stops with a named error instead of spending the day before the first script.
5. **Speech is unchanged** — `gemini-3.8-flash-tts`, voice `Charon`, 4,000-character
   chunks (two requests for a six-minute prayer) inside a 10-request day.
6. **Ask the API, don't assume.** `--probe-models [--probe-generate]` asks which models
   exist (free) and which serve (one token each), wired into
   `gemini-key-diagnostic.yml` so a push answers the question in annotations.

## 7. Measured: which models answer, at 13:52Z on 6 November 2026

Asked from CI with this repository's own `GEMINI_API_KEY` — one one-token request per
model, run `42229011296` of `gemini-key-diagnostic.yml`:

| Model | HTTP | Meaning |
|---|---|---|
| `gemini-3.5-flash-lite` | **200** | **serving** — the new primary |
| `gemini-3.1-flash-lite` | **200** | serving — fallback 1 |
| `gemini-3.6-flash` | **200** | serving — fallback 2 |
| `gemini-3.8-flash` | **503** | capacity refusal — the model the pipeline was using |
| `gemini-3.8-flash-tts` | **200** | serving — narration is fine |

Three conclusions, none of them available from the logs before this:

1. **The outage is model-specific, not project-wide.** The same key, in the same
   minute, was refused by 3.8-flash and served by four other models. "Google is down"
   was never the accurate diagnosis; "3.8-flash's pool is refusing" is.
2. **The switch is verified, not hoped for.** `gemini-3.5-flash-lite` answered a real
   request minutes before this policy was merged.
3. **Speech was never blocked by capacity** — `gemini-3.8-flash-tts` served. Today's
   missing video is a quota limit (10 requests/day), not an outage.

## 8. What this does *not* prove, and how it will be proven

Nothing above demonstrates that `gemini-3.5-flash-lite` is serving **right now**. Only
the probe can answer that, and it runs with the real key in CI. If the probe reports
`REFUSED` for the lite models too, then the outage is project-wide rather than
model-specific and the next lever is the model tier, not the model name — that is a
billing decision for the owner, not a code one, and this repo's $0.00 lock means the
pipeline idles rather than spends.

## 9. Sources

- Gemini API models — <https://ai.google.dev/gemini-api/docs/models> (fetched 6 Nov 2026)
- Gemini model versions & lifecycle —
  <https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/model-versions>
- Gemini API rate limits — <https://ai.google.dev/gemini-api/docs/rate-limits>
- Free-tier figures — <https://www.scriptbyai.com/gemini-api-free-tier-limits/>,
  <https://aiplug.work/en/blog/gemini-free-tier-limits>,
  <https://github.com/mnfst/awesome-free-llm-apis/pull/176>
- SDK retry behaviour — <https://github.com/googleapis/python-genai/issues/3204>,
  `CHANGELOG` 3.0.0 (v1 default, httpx2)
- 503 discussion — <https://discuss.ai.google.dev/t/gemini-3-8-flash-api-continuously-returning-http-503-model-shows-operational-on-status-page/197810>,
  <https://discuss.ai.google.dev/t/gemini-model-usage-error/198545>
