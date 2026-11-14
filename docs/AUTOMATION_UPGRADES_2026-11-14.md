# Automation upgrades, 14 November 2026

Nine gaps were found in a review of what the studio did not yet do on its own.
This note records what each one does now, where it lives, how to turn it off,
and what is not yet known. Every part runs at $0: no new service, no paid tier.

## 1. Scripture check

**Problem.** The writer was given a reference and quoted the verse from memory.
One of the first sixteen standalone Shorts came back garbled ("He will never
permit. He will sustain the righteous to be moved.") and was caught by a person
reading it.

**Now.**

- `assets/scripture/kjv.json.gz` holds the King James Version: 66 books, 31,102
  verses, 1.2 MB. The text is public domain; the JSON edition is
  github.com/aruljohn/Bible-kjv (MIT, `assets/scripture/SOURCE_LICENSE.txt`).
- `pipeline/scripture_text.py` shows the writer the verses
  (`prompt_block`) and checks the result (`quote_problems`):
  - at least one whole verse of the passage, word for word;
  - no verse carried with a word changed, added or dropped;
  - a verse of more than 30 words may be quoted by whole clauses (8 words or
    more), and the rest of it must not follow reworded;
  - punctuation, capitals, "shew"/"show", British/American spelling, "Selah"
    and a dropped opening "And"/"For"/"But" are not misquotation.
- Shorts: `GeminiBrain.author_short_spec` refuses a spec that fails and asks
  again with the exact words; after two attempts it moves to the next model.
- Long-forms: the writer is shown the same verses; a script with no whole
  verse of its passage is refused; a near-quotation is reported as a warning
  and does not discard the script.
- Shorts written before the check: 44 of the 94 waiting quote the King James
  text exactly. The other 50 quote other translations (or paraphrase) and
  cannot be proved faithful offline. Each brain pass rewrites up to three per
  channel (`MAX_REQUOTES_PER_PASS`); the selector sends verified Shorts out
  first and falls back to an unverified one only when a channel has nothing
  verified, with a notice in the run.

**Why the King James Version.** It is the only widely known English text that
may be bundled and quoted in full without a licence. Several earlier Shorts
quote modern translations that are under copyright; that stops here.

**Turn off.** Remove the `quote_problems` call in `author_short_spec`. Not
recommended.

**Not known.** Whether the free text models copy the verse reliably on the
first attempt. A model that cannot is skipped; if none can, that Short is not
written and the run says so.

## 2. Learning from Shorts

**Problem.** `pipeline/performance_feedback.py` set Shorts aside and steered by
long-forms. No channel has ever had three long-forms with 25 views, so the loop
never produced a signal, while Shorts drew 97% of all views.

**Now.** The daily growth run's report carries a `shorts` section: for the
channel's Shorts at least two days old, the count and average views by book of
the Bible and by theme, each as a ratio to the channel's average Short (pulled
toward 1.0 for small counts). `pipeline/evergreen_shorts.candidates` puts
passages from books and themes running 1.2x or more above average first, and
0.7x or less last. A channel with fewer than six measured Shorts uses the
network's pooled numbers; with fewer than twelve across the network the list is
left as written. Aggregates only are committed, as before.

**Turn off.** Return `listed` from `_by_what_is_watched`.

**Not known.** Whether a book or theme that did well keeps doing well. The
first reports with a `shorts` section are written by the next daily growth run
(03:14am Nigeria time).

## 3. Seasonal calendar

**Problem.** Nothing in any passage list knew the date.

**Now.** `pipeline/seasonal.py` works out five seasons for any year: Advent
(from the fourth Sunday before Christmas to 23 December), Christmas (24 to 26
December), the New Year (30 December to 2 January), Holy Week (Palm Sunday to
Holy Saturday) and Easter (Easter Sunday and the two days after). Dates are
read in Nigeria time. Each channel has one or two passages per season, 80 in
all, none shared between channels and none on another channel's list.

- The brain writes a seasonal Short from two days before its first day, even
  when the queue is full, and tells the writer what day it is for.
- The selector never sends it early, sends it first while its season is open,
  and withdraws it (`status: draft`, `season_closed: true`) when the season
  ends. The brain returns it to the queue with new dates the next year.
- A channel's Shorts for a season are spread across it: Advent on 29 November
  and 11 December 2026; Christmas Eve and Christmas Day; 30 December and
  1 January.

Long-forms are not seasonal yet.

**Turn off.** Empty `PASSAGES` in `pipeline/seasonal.py`.

## 4. New titles for unwatched long-forms

**Problem.** 35 of 95 long-forms had no views. Queued long-forms lead with the
need since 14 November; published ones kept their titles.

**Now.** The daily growth run (`scripts/retitle_unwatched.py`,
`pipeline/retitle.py`) picks at most two long-forms per channel that are at
least seven days old with two views or fewer, asks the channel's text model for
a title in the form `<need>: <reference> | <channel>`, and checks it in code:
35 to 70 characters, the reference kept exactly, no digits, capitals, question
marks or words such as "miracle" and "guaranteed". The accepted title is
stamped into the receipt with `title_before`, `retitled_at` and a reset
`metadata_revision`; the monitor's existing metadata sync pushes it to YouTube
within three hours. A video is retitled once, ever.

Nine long-forms are old enough today; most are under seven days old.

**Turn off.** Remove the two "new titles" steps from
`.github/workflows/growth-autopilot.yml`.

**Not known.** Whether a new title brings views. `title_before` keeps the old
one so the two can be compared.
