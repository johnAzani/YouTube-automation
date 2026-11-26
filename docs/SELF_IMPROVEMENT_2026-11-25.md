# Auto always learn and self improve — what was true, and what is now

25 November 2026. Asked for the system to "auto always learn and self improve".
The honest first step was to check which loops actually learn, because a pipeline
can be full of readings that nothing acts on — and this one was.

## 1. The audit: two loops closed, three did not

`pipeline/learning_audit.py` reads the code, not the documents, and grades every
loop in one of four states. Only one of them is learning.

| loop | state before today | why |
| :--- | :--- | :--- |
| **shorts steering** | **acting** | 35 Shorts measured; 4 books carry two or more; the ranking reorders 10 channels' roadmaps |
| **night-tail length** | **acting** | the measured ceiling (16.3 min) is below the tail's floor, so the tail is off on every channel — the measurement changed the build |
| **thumbnail choice** | **unwired** | the campaign measured a click rate per concept every day and **no release ever read it** |
| **overlay lessons** | **waiting** | 11 phrases under test on 10 channels, **0 verdicts**: a verdict needs 5 videos each side with 100 views |
| **first-frame composition** | **measuring** | one composition across 641 Shorts, but 434 of them (68%) still open on a citation — the design has one level; the citation-versus-need choice inside it has two, and that split is the only variable the repository has varied |

Two of those five states moved while this page was being written, and both moves
were downwards — which is the audit doing its job. `thumbnail_choice` was
reported as fixed the moment the release path could *read* the leader; it is
**measuring** again until a Short actually goes out on it, because a loop is not
closed by wiring (`_adopted_release()`). And `first_frame_composition` said "one
composition across 639 Shorts", which read as though nothing had been varied at
all while 434 Shorts opened on a citation — the same plate, kicker, subtitle and
camera move with the citation's words in the kicker slot. The split is now named
instead of averaged away.

That table is the real answer to the request. Before today, **two of five loops
learned**. Not because nobody wrote a learning module, but because three modules
had no seam through which their answer could reach a build.

## 2. The loop that was built and never wired

`pipeline/thumbnail_campaign.py` has computed the click rate of each of the three
thumbnail concepts since it landed, and says every day which one leads. The
release path called:

```python
concept = concept_for(doc.id or doc.slug)      # a rotation nothing can influence
```

There was no argument a measurement could reach. So the channels would have
rotated the three concepts forever, and **adopted nothing, no matter how much
traffic arrived.** Every day of measurement was being discarded at the one point
it mattered.

What is true now (`thumbnail_campaign.live_concept`):

* once **every** concept has cleared 300 impressions and one leads, the winner
  goes live on the next release;
* until then the release takes its turn in the rotation, and
  `concept_decision()` records **which of the two it did and why** — "quiet,
  poster is under the 300-impression floor, so a click-rate comparison is not a
  comparison yet";
* the rotation continues behind the winner, so the losing concepts keep
  collecting impressions on published videos and a winner can be displaced if the
  traffic changes its mind.

Refusing to copy a winner while the others are unmeasured is deliberate: copying
the only concept that happened to receive traffic is a self-fulfilling choice, not
a test.

## 3. The other loop worth closing: a citation frame cannot be queued

The first-frame audit found **26 of the 53 queued Shorts** opening on a scripture
citation. Fixing those by re-authoring would pay a model to rewrite words that
were already good — one line was in the wrong place. `pipeline/first_frame_repair.py`
moves an existing line instead:

* it **only** acts on a kicker that is a citation;
* the replacement is text the spec already contains (its `sub`, or its first
  kinetic line), never a generated phrase;
* it refuses when no existing line fits — 80 specs are left exactly as they are
  and reported as `no need line to promote`. **A repair that writes copy is
  authoring, and this module is not allowed to author.**
* the citation is not deleted; it moves to the scene that reads the verse.

**And it refused to touch the published archive.** 354 published Shorts open on a
citation. Those are the **control**: rewrite them and there is nothing left to
compare a need-first frame against. The first draft of this repair rewrote all 376
promotable specs, which would have deleted the experiment it was built to serve.
The receipt→spec mapping made it worse: receipt slugs are
`<key>-<human suffix>`, so matching on the stem found **zero** published Shorts and
every one of them looked repairable.

Result on the repository: 434 citation frames of 639 (was 456); **21 queued
Shorts repaired and still valid**; 354 held as the control; 80 left alone.

## 4. What is still honest to say "no" about

* **Overlay lessons: 11 phrases, 0 verdicts.** The loop exists, judges honestly and
  offers its phrases to the title writer. It has produced no verdict because a
  verdict needs five videos on each side of a phrase with 100 views, and this
  channel's long-forms rarely reach 25 views. Making the bar lower would manufacture
  a result, so the bar stays and the audit says `waiting`.
* **The first frame can now be compared on one variable, not designed.** Citation-
  first against need-first is a real comparison with 354 videos on one side and 21
  on the other. The *visual design* has still never varied — that needs a renderer
  change and a way to read per-frame response, which no API here provides.
* **No loop that "acts" is thereby improving.** Acting means the measurement
  changes the next build. Whether the build does better is what the next reading is
  for, and the module says exactly that.

## 5. What runs now, every day, with nothing installed

The growth job (`growth-score.yml`, $0.00, no credential) now also:

* repairs unpublished citation frames (`first_frame_repair --write`),
* grades every loop (`learning_audit`),
* and commits both readings alongside the supply and first-frame audits.

All four run on the standard library only, so they cannot fail because a package
did not resolve — the mistake that turned this job red on the previous change.

---

*Files: `pipeline/learning_audit.py`, `pipeline/first_frame_repair.py`,
`pipeline/thumbnail_campaign.py` (`live_concept`, `concept_decision`),
`content/research/learning_audit.json`, `content/research/first_frame_repair.json`.
Tests: `tests/test_learning_audit.py` (8), `tests/test_thumbnail_loop_closed.py`
(10), `tests/test_first_frame_repair.py` (13).*

## 6. One correction to an earlier page

`docs/FIRST_FRAME_AND_SUPPLY_2026-11-25.md` said the five `passage_short` specs
were "the other composition". They are not: the composition is unchanged (plate,
kicker, sub, three stacked lines). They are the other **level of one variable** —
the need on the first frame instead of the citation. The audit
(`first_frame.json`) kept reporting `1 composition`, which is what caught it.
