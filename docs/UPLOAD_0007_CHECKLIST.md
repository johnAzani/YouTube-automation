# Upload checklist — job 0007, the 2022 nickel squeeze

**Purpose:** this is the work that turns `human_rewrite: false` into an honest `true`. It is written to
be done in about 45 minutes with the sources open, not to be read and waved through.

Two things it is not: it is not a verification, and it is not a rubber stamp. Everything below was
assembled by the same process that wrote the script — which is exactly why a second pair of eyes is
the point.

---

## Part A — the twelve claims that carry the video

If any one of these is wrong, the video is wrong. Everything else in the script is connective tissue.

| # | Claim as narrated | Exact value | Where to check | Confirmed |
|---|---|---|---|---|
| 1 | Monday's close | **$48,078/t** | Court of Appeal [2024] EWCA Civ 1168, para 2 | ☐ |
| 2 | Tuesday's peak | **$101,365/t** | FCA Final Notice 207387 §2.2; contemporaneous Reuters | ☐ |
| 3 | Price at suspension | around **$80,000/t** | S&P Global, 8 Mar 2022 | ☐ |
| 4 | Suspension time | **08:15 London**, all venues | LME Notice 22/052 | ☐ |
| 5 | Cancellation time and scope | **12:05**, all nickel trades from **00:00** that day | LME Notice 22/053 | ☐ |
| 6 | Notional value cancelled | **$13.373bn** | FCA Final Notice §4.105 | ☐ |
| 7 | Trade count / span | **5,000–9,000 trades**, ~8 hours | OFR working paper 24-09 | ☐ |
| 8 | Price bands switched off | **04:49–08:15** = 3h26m | FCA Final Notice §2.28 | ☐ |
| 9 | Avoided margin call | **$19.75bn**, ≥7 members defaulting | LME's own account, via Bloomberg/Mining.com 28 Nov 2022 | ☐ |
| 10 | Independent estimate | **12 of 45** clearing members threatened | OFR working paper 24-09 | ☐ |
| 11 | FCA penalty | **£9,245,900** (30% discount from **£13,208,400**) | FCA Final Notice §1.1–1.2, 19 Mar 2025 | ☐ |
| 12 | Court outcome | Divisional Court **29 Nov 2023**; CoA **7 Oct 2024**; Supreme Court refused **29 Jan 2025** | LME litigation page; [2024] EWCA Civ 1168 | ☐ |

### The three figures that get conflated

The script says this explicitly, and you should confirm the framing is fair rather than just the numbers:

- **$3.9bn** — early Reuters reporting on the day.
- **$12bn** — shorthand used in litigation coverage.
- **$13.373bn** — the FCA's figure, attached to a formal finding with a defined scope.

These measure different slices of the book. The script uses the FCA number and names the others as
variants. **Do not average them.** If you disagree with that choice, change it — but change it
deliberately.

### The three figures the script deliberately refuses to state as fact

- Tsingshan's position size (300,000t reported by Reuters at one stage; >150,000t at the halt). **Reported.**
- Tsingshan's loss (~$1bn). **Estimated by people familiar, via Bloomberg/Fortune.** Not disclosed.
- The $19.75bn avoided margin call. **The exchange's own account.** Not audited.

Each is attributed in the narration. If you find one of them stated flatly anywhere in the body,
that is a bug — tell me and I will fix it.

---

## Part B — the two passages that are only yours

This is the part the flag is actually about. The research and the structure are mine; the judgement
has to be yours or the checklist is a formality.

### B1. The opening. Scene 1, first three sentences.

Currently:

> On the morning of the eighth of March, two thousand and twenty-two, a price appeared on a screen
> in London that should not have been possible.

**Rewrite this.** Not because it is bad — because in a 21-minute documentary, the first fifteen
seconds decide whether anyone hears claim #1, let alone #12. Write the version you would stop
scrolling for. It does not need to be elegant. It needs to be yours.

### B2. The verdict. Scene 14, the last three paragraphs.

Currently the script concludes that nothing broke — a system worked as designed, and the design had
a gap — and then closes on the year without an Asian session.

That is an argument, and arguments should be owned. Either:

- **endorse it** and I leave it, or
- **replace it** with what you actually think the episode proves, and I will cut the existing
  paragraphs to match.

A 21-minute film that argues something no one wrote is the only real defence against YouTube's
inauthentic-content policy. This paragraph is that defence.

---

## Part C — the two-line change

Only after A and B. In `content/queue/0007-the-day-the-exchange-pressed-undo.md`:

```diff
-line 5:    status: draft             # DRAFT — awaiting human fact-check…
+line 5:    status: approved
-line 134:  human_rewrite: false       # *** FALSE ON PURPOSE *** …
+line 134:  human_rewrite: true
```

Then tick the boxes in `content/factcheck/0007-the-day-the-exchange-pressed-undo.md` and write the
date and your initials at the top of it. That worksheet is the record of this review; without a
filled-in copy, the two flags above are just strings.

**Both lines change together.** `status: approved` with `human_rewrite: false` fails
`tests/test_queue_integrity.py` in CI and the PR goes red — that is the guard, not a nuisance.

---

## Part D — the run

1. Merge to `main` (the cron only runs there).
2. Actions → **Produce video** → Run workflow → branch `main`, job
   `0007-the-day-the-exchange-pressed-undo.md`, `dry_run` **unchecked**.
3. Watch for `tts engine=edge-tts`. If it says `placeholder`, the run will refuse to upload — retry.
4. Expect **12–20 min**. Then check the `render-<run_id>` artifact (it expires in 24 h).
5. A **release ticket** issue appears with a Studio link. The upload lands **private** unless
   `AUTO_PUBLISH=true`; publish from the ticket.

---

## Part E — what this checklist already caught

On 23 October, drafting this document, the opening claim was re-checked and found wrong.

The script said Monday's close of $48,078 was "already a record". It was not. Nickel's previous
all-time high was **$51,800/t, set in May 2007** — and $48,078 is below it. What *was* a record on
7 March was the intraday print of **$55,000**, which cleared the 2007 high before the market closed
lower. Sources: FCA Final Notice quoting Bloomberg; Reuters, 10 Mar 2022; Globe and Mail, 8 Mar 2022.

The line was rewritten to say what happened rather than what sounded good. A second superlative —
that this was "the largest cancellation of executed trades in the history of a modern exchange" —
was **deleted**, because no source supports the ranking.

That is the standard this document is asking you to apply. Two errors in one paragraph, found by
checking instead of trusting. Assume there are others; the twelve above are where to look first.
