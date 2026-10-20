# Changelog

Notable changes to the studio. Newest first. Reconstructed from `git log` on 2026-10-20 —
there was no changelog before this file.

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
