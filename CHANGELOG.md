# Changelog

Notable changes to the studio. Newest first. Reconstructed from `git log` on 2026-10-20 —
there was no changelog before this file.

---

## 2026-10-22 — fact-check worksheets: the mechanical half of the human gate

The human gate is the one step no machine in this repo may skip: `pipeline/originality.py`
blocks any job whose `human_rewrite` is `false`, and flipping it is the human's signature.
But the gate was slow for a boring reason — pulling every checkable claim out of a 900-word
script and finding which of six sources settles each one is an hour of extraction before the
actual judgement starts.

### Added

- **`scripts/factcheck.py`** → `content/factcheck/<id>-<slug>.md`. Extracts candidate claims
  (a sentence containing a number word, a month, or a multi-word proper noun) and prints them
  as checkboxes next to the job's own declared sources, each with a blank for the source the
  human confirmed it against, plus a sign-off block. **It verifies nothing and pre-ticks
  nothing** — an unticked box is the only correct starting state, and a test asserts that.
  Re-running without `--force` refuses to overwrite a worksheet a human has filled in.
- Worksheets generated for all four queued jobs: **41 / 39 / 35 / 37 checkboxes**
  (0003–0006). Each embeds the source script's sha256 so staleness is visible.
- 13 tests in `tests/test_factcheck.py`, including the two invariants that matter most: the
  generator never asserts a verdict, and its output never lands in `content/queue/` — that
  directory is globbed by `pipeline/run.py::select_jobs`, `scripts/doctor.py`, the
  queue-integrity tests and `dry-run.yml`, so a worksheet there would be parsed as a job.

### Notes

- Extraction is deliberately dumb: the narration spells numbers out for TTS ("two thousand
  and eight"), so digit-matching would find nothing, and a clever extractor that decided what
  matters would hide claims behind a model's judgement. A missed claim is a checkbox the human
  adds.
- **Because dumb extraction misses things, nothing is dropped silently.** In job 0003, 10
  substantive sentences carry no figure, date or proper noun — including *"That is a
  repurchase agreement — a repo — and in substance it is a secured loan"*, which is
  load-bearing. Those are listed under each scene as "Also read", and
  `test_no_substantive_sentence_is_silently_dropped` asserts every sentence of ten words or
  more appears somewhere in the worksheet. Without it a human could tick all 31 flagged boxes
  and never see them.
- `docs/SETUP.md` §6 now points at it as the shortcut for the fact-check step.

---

## 2026-10-22 — the `image-search/` licence ledger: 13 stills are not ours to publish

`docs/ASSET_SOURCING.md` had carried *"no complete per-file license ledger in this checkout"*
as known debt. This closes it, and the answer was worse than "unknown".

### Added

- **`image-search/LICENSES.yml`** — a per-file ledger for all 49 authored stills, derived by
  `scripts/licence_ledger.py` from each file's **own** metadata (EXIF `Copyright`/`Artist`/
  `ImageDescription`, embedded XMP, raw byte markers for `gettyimages`,
  `xmpRights:WebStatement`, `plus:Licensor`, `All Rights Reserved`). Every entry is keyed by
  SHA-256, so a swapped file cannot inherit its predecessor's clearance. Commands: `check`
  (CI), `scan` (evidence, writes nothing), `write` (regenerate, preserving human edits for
  unchanged bytes).
- **`pipeline/licences.py`** — `licence_note()`, `status_of()`, `is_safe_for_monetized_use()`,
  and two tiers: `unsafe_stills()` (rights-encumbered / corrupt / unrecorded — must not
  render) and `uncleared_stills()` (everything not `cleared`).
- **CI**: `dry-run.yml`'s hermetic `checks` job now runs `licence_ledger.py check`.
- **Doctor**: two new checks — the ledger covers every still and agrees with the bytes
  (re-derived from the files, not re-reading its own output), plus an explicit
  ❌ *"authored stills free of embedded rights claims"* while the 13 remain.
- 11 tests in `tests/test_licence_ledger.py`, including the two that assert `check` can
  actually fail (missing entry; changed bytes).

### Changed

- **`tools/deep_dive.py` and `tools/shorts.py` now report the real licence status.** Both
  wrote one blanket string into `scene-sources.json` for every authored still —
  *"source/license metadata unavailable in current ledger"* — which said the same thing about
  a public-domain 1889 Library of Congress plate and a rights-managed Getty frame. Each still
  now gets its own status line, and both renderers print a `!!` block naming any
  must-not-monetize file while the operator is still watching. Import is guarded, so a
  bookkeeping module can never break a render.

### What the scan found

**13 rights-encumbered, 1 corrupt, 35 unverified, 0 cleared.**

- 10 stills carry embedded **Getty Images** rights metadata — e.g. EXIF `Copyright: "2002
  Getty Images"` on `andrew-fastow-enron-cfo-trial-photo-2.jpg`, with a full `plus:Licensor`
  and `xmpRights:WebStatement` packet.
- 3 carry `"All Rights Reserved"` photographer copyrights: `Copyright 2014/2021 Steven L.
  Markos`, Johnstown Flood National Memorial.
- **Nine of the 13 are referenced by scene tables** (8 Enron, 1 Johnstown). The Enron deep
  dive and Shorts are therefore **not safe to monetize** until those files are replaced.
- `johnstown-flood-1889-ruins-destruction-h-5.png` is 68 bytes and will not decode; recorded
  as `corrupt`, referenced by no scene.
- `enron-corporation-headquarters-houston-c-3.jpg` and
  `enron-scandal-2001-newspaper-headlines-f-4.jpg` are byte-identical.
- Only 23 of the 49 stills are referenced at all; the other 26 are unused inventory.

MAINTENANCE.md §4 now carries these as three separate debt rows (encumbered / unverified /
dead weight) instead of one "no ledger" row, and the "47 files" figure there was wrong —
the directory holds 49 files, 8,988,827 bytes.

---

## 2026-10-22 — queue depth 0004–0006, and a licence hole in the keyless provider

### Fixed

- **`_wikimedia()` was accepting share-alike, non-commercial and no-derivatives images.**
  `docs/ASSET_SOURCING.md` has always promised *"only CC0, public-domain, or CC BY entries
  are accepted; NC, ND, and ShareAlike entries are skipped"* — the code did not enforce it.
  The old predicate spelled the disqualifiers out longhand (`share alike`,
  `non-commercial`, `no derivatives`), but Commons reports `LicenseShortName` in
  **abbreviated** form: `CC BY-SA 4.0`, `CC BY-NC 2.0`, `CC BY-ND 4.0`. None of the
  longhand strings appear in those, and the accept term `cc by` matches all of them, so
  every SA/NC/ND hit passed the filter and was downloaded and rendered. Wikimedia is the
  provider that runs with **no API key** — i.e. the one a keyless CI run and any
  no-secrets setup actually use — so the hole was in the hot path for a channel being
  built for monetization. `_internet_archive` (rejects `-nc`/`/by-sa/`/`-nd`) and
  `_openverse` (allowlist) were already correct.
  - New `pipeline/assets.py::licence_ok_for_monetized_use()` tokenises the licence string
    and refuses any `nc`/`sa`/`nd` token or spelled-out equivalent. Unknown licences are
    refused. Verified against the real Commons strings: `CC BY-SA 4.0`, `CC BY-NC 2.0`
    and `CC BY-ND 4.0` all went from *downloaded* to *refused*; `CC0`, `Public domain`
    and `CC BY 2.0` still pass.
  - **Consequence to watch:** a scene that was previously sourced from a CC BY-SA hit now
    correctly returns nothing. Jobs 0004–0006 were written against the tightened rule;
    job 0003's queries were chosen for CC0/PD/CC-BY coverage and its `pipeline-dry-run`
    result on this branch is the check.

### Added

- **Three long-form scripts (PLAN.md Phase 0 queue depth):** `0004-the-fund-that-broke-the-fed`
  (LTCM, 1998), `0005-the-queue-that-broke-a-british-bank` (Northern Rock, 2007),
  `0006-how-one-trader-deleted-a-bank` (Barings, 1995). ~1,050–1,100 words each, 8 scenes,
  all `status: draft` with `human_rewrite: false` — the originality gate blocks every one
  of them until a human fact-checks, rewrites and approves. Each carries its sources in
  `description` and a maintainer note naming the figures that most need checking.
- **Per-query sourcing evidence, now enforced.** Each job records
  `asset_query_verification` in frontmatter: for every `asset_queries` entry, either a
  Commons probe count (`usable: N ≥ 1`) or a `ci_verified` dry-run id, plus the evidence
  note. `tests/test_asset_query_verification.py` fails the build if a query is unverified,
  recorded with zero usable hits, or carries a stale entry. Job 0003 records CI evidence
  (run `39734567120`, main @ `af63d2c`, job *"General pipeline dry-run (needs network)"*
  = `success`); 0004–0006 record Commons probes taken 2026-10-22.
- Rejected-query notes in each job's frontmatter, so nobody re-adds a query that was
  already proven dead — e.g. `bank of england threadneedle street` returns 4/4 CC BY-SA
  (zero usable), which is why job 0005 uses the shorter `bank of england london`.

---

## 2026-10-22 — first-upload path: release tickets actually work now

PR #5 (the green pipeline) merged; attention turned to what blocks the **first upload**
(SETUP.md §6).

### Fixed

- **The release-ticket Issue would never have appeared.** `_open_release_ticket` shells
  out to `gh issue create`, but `produce.yml` exported no token — unauthenticated `gh`
  fails, and the failure was swallowed (`check=False`, output discarded). The workflow
  now exports `GH_TOKEN: ${{ github.token }}` (job already has `issues: write`), the
  helper logs success/failure with the reason, and it falls back to `GITHUB_TOKEN`.
- **Ticket body now links straight to the Studio editor**
  (`https://studio.youtube.com/video/<id>/edit`), not just the watch URL — the
  "publish in 2 clicks" promise in SETUP.md §6.4 is literal.
- **SETUP.md**: §6 pointed at archived `0001-…md` as the template (queue now holds
  `0003-…`, archive holds 0001/0002) and §5's `YOUTUBE_REFRESH_TOKEN` row cited §3
  (remasters) instead of §4 (token minting).

### Added

- Three regression tests: ticket opens in Actions with token + Studio link; failure is
  logged, never raised (upload must not die over a ticket); no ticket outside Actions.

---

## 2026-10-21 — the general pipeline completed its first ever render

`pipeline-dry-run` had never passed. It now does — run 39649621652: all three jobs
green, general queue path rendered end-to-end in 6m0s **with zero API keys**. Full
post-mortem in MAINTENANCE.md §3 (2026-10-21).

### Fixed

- **`_cache_path` read `CONFIG.ASSET_CACHE_DIR`, which never existed on `Config`** —
  only a module-level constant in `config.py`. Every provider that found a licensed
  candidate crashed with `AttributeError`, `fetch_scene_assets` swallowed it as
  "source errored", and the hard-fail blamed the scene query. The general pipeline had
  never completed a single provider download.
- **Wikimedia downloads fetched originals (100 MB+ TIFFs) instead of the 1920px
  thumburl it already requested** — and died on `upload.wikimedia.org` 429s. Photos
  now use `thumburl`; Wikimedia traffic carries a descriptive UA with the repo URL;
  search and download retry 429/5xx honouring `Retry-After` (bounded ≤8 s).
- **Dead Openverse video link**: `/v1/videos/` 404s on every call (verified) —
  dropped from the video provider list.
- **Commons HTTP-200 error bodies (`cirrussearch-too-busy`) read as "0 results."**
  API errors are now named in the attempt probe and retried once.
- **Job 0003's asset queries**: scenes 5 and 7 were swapped (courtroom ↔ bank run),
  scene 4's had a single junk hit, scene 3's one off-topic plaque. All eight
  re-verified against the Commons search API for multiple CC0/PD/CC-BY matches.

### Added

- **Per-provider attempt report** — `sourcing-attempts.json` per scene, one stdout
  line per attempt, and a compact digest inside the hard-fail message so the CI
  annotation (the only readable runner output) explains itself.
- `tests/test_config_references.py` — static scan that fails any `CONFIG.<name>`
  reference which does not resolve, in the hermetic `checks` job.
- `test_asset_queries_cover_every_scene_when_provided` — a partial `asset_queries`
  list must not silently drop later scenes onto heading-as-query.
- `test_cache_path_resolves_into_the_asset_cache_dir` — regression test for the bug
  above.

---

## Unreleased — maintenance handover (2026-10-20)

The project moved off the abandoned session branch `arena/79365da2-youtube-automation`
onto a maintained branch. Moving it surfaced a CI that had never passed.

### Fixed

- **CI was red on every run.** `dry-run.yml` selected `content/queue/*.md | head -n1`,
  which was a `niche: history` draft that `_validate_finance_niche` (added in `333767c`)
  refuses. Separately, `ENABLE_KEYLESS_SOURCES=0` disabled the only key-free stock
  providers while no Pexels/Pixabay secrets existed, so `fetch_scene_assets` had nothing
  to query and the render hard-failed. Full post-mortem in `MAINTENANCE.md` §3.
- **`tests/` was never executed by any workflow.** `dry-run.yml` had no test step at all.
- **`remaster.yml` was pinned to the abandoned branch.** Its push guard aborted unless
  `GITHUB_REF_NAME == "arena/79365da2-youtube-automation"`, and it pushed to that same dead
  branch — so the manual remaster workflow was unusable from anywhere else. Now publishes
  back to `HEAD:$GITHUB_REF_NAME`, refusing only non-branch refs.
- **Docs told maintainers to select the dead branch by name** — `PLAN.md`, `docs/SETUP.md`,
  `docs/ASSET_SOURCING.md`.
- **README Quickstart was wrong twice**: it pointed at a job that has since been archived
  and out-of-niched, and claimed the general `pipeline/` path runs with "zero network".
  It does not — that path always needs a reachable stock provider.

### Changed

- **`dry-run.yml` rewritten** into three jobs with honest guarantees: `checks` and
  `offline-render` are hermetic and required; `pipeline-dry-run` is the one networked job
  and is `continue-on-error`, so a third-party API outage cannot turn the repo red.
- **`offline-render` asserts the output is real media** — non-empty, has a video stream,
  has an audio stream, and produced a per-scene source ledger. Previously CI only checked
  that the command exited 0.
- **Out-of-niche drafts archived** to `content/archive/` with a README explaining why they
  are still needed (the Johnstown deep-dive and Shorts engines read them).
- **`pipeline-dry-run` selects an in-niche job explicitly** rather than by filename order.

### Added

- `MAINTENANCE.md` — runbook: verified local checks, what CI proves, incident log, known
  debt, operational calendar (the 31 Jan 2027 YPP deadline), how to add a video, secrets.
- `CHANGELOG.md` — this file.
- `tests/test_queue_integrity.py` — 4 tests. `test_every_queued_job_is_in_niche` is the
  guard that makes the incident above impossible to repeat.
- `content/queue/0003-how-lehman-brothers-died.md` — 901-word, 8-scene finance documentary
  draft (the queue had no in-niche job). Ships with `human_rewrite: false` **on purpose**
  so the originality gate blocks it until a human verifies the figures against the Valukas
  examiner report and rewrites the narration.

---

## 2026-10-20 — finance pivot and the Enron deep dive

- `da6685b` fix(site): link banner from published homepage
- `d3106bc` feat(site): add finance channel banner download
- `333767c` **chore(channel): keep published videos finance-only** ← added the niche gate
  that later broke CI
- `54adba1` docs: clarify remaster workflow availability
- `fb883cc` fix(actions): invalidate stock cache when sourcing changes
- `23b8b4c` feat(media): clip-first sourcing and aspect-safe remasters
- `8e33f1b` Shorts: 9:16 vertical twins of deep dive v5
- `75d1280` feat(deep-dive): 'How Enron Died' score-only audio + tease cards (v5 remaster)
- `f5a284c` feat(deep-dive): score-only audio (SFX removed) + AHEAD tease cards
- `a506535` feat(deep-dive): semantic sound design — story-cued SFX beds, sidechain mix
- `4a11d1b` feat(deep-dive): cinematic score + sound design keyed to spoken beats
- `14ddd85` feat(deep-dive): v4 documentary engine — speech-locked scenes, sub-pixel camera
- `621f350` feat(deep-dive): speech-synced motion graphics v3
- `9a52d67` feat(deep-dive): motion-design v2 — blue grade + glass cards + kinetic type
- `fef8283` feat(deep-dive): money-documentary ep1 — 'How Enron Died' (1:57)
- `d32e4e4` docs(finance): finance-niche deep dive — RPM data, policy minefield, money math

## 2026-10-19 — motion system, reels, and the Pages showcase

- `09ae56f` feat(deep-dive): archival footage + narration — 'The Canal That Broke a City'
- `5760322` chore: track deep-dive narration inputs (narrow gitignore exception)
- `1284d35` feat(reels): MotionStudio reels — THE FLOOD + THE SECRET (Johnstown 1889)
- `f776a7d` feat(motionstudio): DocOga typography motion system + 2 QA-passed reels
- `f0c89e9` docs(pages): root player page + `.nojekyll`
- `43f6195` ci(pages): make Pages deploy workflow manual-only
- `0aa117a` ci(pages): deploy showcase site to GitHub Pages via Actions
- `a760101` docs(showcase): GitHub Pages player page with first renders
- `db175bf` fix(shorts): caption scaling + cut from pre-burn source + hook overlays
- `4aaf04e` feat: growth science + metadata/Shorts automation

## 2026-10-18 — the studio

- `c8c7b88` fix: robust text rendering + render fixes after end-to-end validation
- `966d01b` **feat: ₦0 YouTube automation studio — plan, pipeline, workflows**
- `21ae307` Initial commit
