# Maintenance runbook

How to keep this studio working. Everything below was **executed and verified on
2026-10-20** on the commit that moved the project onto the maintained branch — outputs
quoted are real, not aspirational. Where something could *not* be verified here it says so.

Start here when CI goes red, when a render breaks, or before the first production upload.

---

## 1. Local setup (verified)

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Installs 33 packages on Python 3.11.2, no build failures. `requirements.txt` pins
lower bounds only — if a fresh install ever breaks, suspect an unpinned upstream
(`numpy 2.4.6`, `pillow 13.0.0`, `edge-tts 7.3.1` were the versions that worked).

### ffmpeg resolution — three different rules, know which one applies

| Code path | How it finds ffmpeg |
|---|---|
| `pipeline/assemble.py::ffmpeg_bin()` | `$FFMPEG_BINARY` → `PATH` → **`imageio_ffmpeg` fallback** |
| `tools/deep_dive.py`, `tools/shorts.py`, `tools/motionstudio.py` | `$FFMPEG_BINARY` → literal `"ffmpeg"` (**no fallback**) |

So the authored engines **require** ffmpeg on `PATH` or `FFMPEG_BINARY` set. On a machine
without system ffmpeg:

```bash
export FFMPEG_BINARY=$(.venv/bin/python -c "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())")
```

GitHub runners install real ffmpeg via apt, so CI never needs this.

---

## 2. The checks, and what each one actually proves

Run these before pushing. All four were run on the current commit.

```bash
# 1. Unit tests — 9 tests, ~0.02s
.venv/bin/python -m unittest discover -s tests -v
# → Ran 9 tests ... OK

# 2. Setup doctor — structural health
.venv/bin/python scripts/doctor.py
# → 13/18 checks passed (the 5 ❌ are secrets; expected locally)

# 3. Offline end-to-end render — no network, no keys, ~4 min
ENABLE_STOCK_BROLL=0 ENABLE_KEYLESS_SOURCES=0 .venv/bin/python tools/deep_dive.py enron
# → social/deep-dive-enron.mp4, 21,437,206 bytes, 1:55, 1280x720 H.264 + AAC stereo

ENABLE_STOCK_BROLL=0 ENABLE_KEYLESS_SOURCES=0 .venv/bin/python tools/shorts.py short-enron
# → social/short-enron.mp4, 8,181 KB, 52.2s, 720x1280 (9:16) H.264 + AAC stereo

# 4. Source ledger — the monetization audit trail
# → output/deep-stock/enron/scene-sources.json     16 scenes
# → output/short-stock/short-enron/scene-sources.json 10 scenes
```

`git status` stays clean after all of this: `output/`, `*.mp4` are gitignored and the
rendered files land in `social/`, which `.gitignore` covers.

### What CI proves (`.github/workflows/dry-run.yml`)

| Job | Blocks merge? | Needs network? | Proves |
|---|---|---|---|
| `checks` | **yes** | no | unit tests + doctor structural checks |
| `offline-render` | **yes** | no | a real render from committed assets, verified to have video **and** audio streams + a per-scene source ledger |
| `pipeline-dry-run` | no (`continue-on-error`) | **yes** | the general `content/queue/` → render path against live free stock APIs |

`pipeline-dry-run` is advisory on purpose: it depends on Openverse / Wikimedia /
Internet Archive / NASA / Pexels / Pixabay, and a third-party 5xx should not turn the
repo red. It is the only job that touches the internet.

**Status of that job — GREEN, run 39649621652 (2026-10-21).** `checks`,
`offline-render` and `pipeline-dry-run` all passed on a real runner: the general queue
path rendered job 0003 **end-to-end in 6m0s with zero API keys** (TTS → 8 scenes of
keyless sourcing → ffmpeg → thumbnail → metadata pack). It had never passed before.
The full chain of causes and fixes — one layer per CI round — is in §3 (2026-10-21).
`PEXELS_API_KEY` / `PIXABAY_API_KEY` are no longer *required* for the queue path to
complete; they still widen coverage and absorb Openverse timeouts (§7).

Note the raw runner log is **never** readable here: it lives on
`results-receiver.actions.githubusercontent.com` and `*.blob.core.windows.net`, outside
this environment's allowlist — and artifacts sit on `*.blob.core.windows.net`. The
self-emitted annotation is the only readable failure output, which is exactly why that
job writes one and why every scene leaves a per-provider attempt digest
(`sourcing-attempts.json`) in the error message.

---

## 3. Incident log

### 2026-10-21 — the general pipeline had never once completed a render

**Symptom.** `pipeline-dry-run` (advisory by design) failed on every run since it
existed, always with a message that blamed the scene query:

```
pipeline dry-run failed (exit 1) for content/queue/0003-how-lehman-brothers-died.md —
last line: [run] FAILED ...: Scene 1 has no licensed, downloadable video or photo for
'new york stock exchange trading floor'; refusing to substitute a generic title card.
```

Nothing said which provider missed or why; logs and artifacts are unreachable from the
maintainers' network (§2). The fix added a per-provider attempt report — every scene
now writes `sourcing-attempts.json` next to `credits.json`, prints one line per
attempt, and the hard-fail message carries a compact digest (that is what made each
round below diagnosable from the annotation alone).

**What the attempts revealed — one layer per CI round:**

1. **`_cache_path` read `CONFIG.ASSET_CACHE_DIR`, an attribute `Config` never had**
   (it is only a module-level constant in `config.py`). Every provider that *found* a
   licensed candidate crashed with `AttributeError`; `fetch_scene_assets` swallowed it
   as "source errored" and the hard-fail pointed at the query instead. The general
   pipeline had never completed a single provider download. → Use the module
   constant; `tests/test_config_references.py` statically scans every pipeline module
   for `CONFIG.<name>` references that do not resolve, so the whole typo class fails
   the hermetic `checks` job instead of hiding behind a swallowed exception.
2. With that fixed, Wikimedia downloads died on **HTTP 429 from
   `upload.wikimedia.org`** — the code fetched the *original* file (often a 100 MB+
   TIFF) even though it already requests `iiurlwidth=1920`. → Photos download the
   rendered 1920px `thumburl`; all Wikimedia requests carry a descriptive UA with the
   repo URL as contact; search and download retry 429/5xx honouring `Retry-After`
   (bounded ≤8 s); probe details quote the underlying exception.
3. **Openverse `/v1/videos/` 404s on every call** (the endpoint does not exist —
   verified), and **Commons answers HTTP 200 with an error body**
   (`cirrussearch-too-busy-error`) that used to read as "0 results". → The dead
   provider link was dropped from the video list; API errors are named
   (`api error: …`) in the probe and retried once.
4. Job 0003's queries were partly wrong, not just unlucky: **scenes 5 and 7 were
   swapped** (courtroom ↔ bank run), scene 4 had a single junk hit, scene 3's
   returned one off-topic plaque. → All eight queries re-verified against the Commons
   search API for multiple CC0/PD/CC-BY matches;
   `test_asset_queries_cover_every_scene_when_provided` stops a partial list from
   silently falling back to heading-as-query.

**Verification.** Run 39649621652 (2026-10-21): all three jobs green —
`pipeline-dry-run` 6m0s with no API keys configured. The queue path is usable on
keyless providers alone; keys remain optional coverage insurance (§7).

### 2026-10-20 — CI was red on every run for the whole life of the branch

**Symptom.** `dry-run.yml` failed before rendering a frame:

```
[run] FAILED content/queue/0001-the-canal-that-broke-a-city.md: Refusing out-of-niche
job 0001: niche='history'. This channel publishes finance, business, markets, or
economics only.
```

**Two independent causes**, either fatal on its own:

1. Commit `333767c` added `_validate_finance_niche` to `pipeline/run.py`, but the two
   `niche: history` drafts stayed in `content/queue/`. CI selected
   `content/queue/*.md | head -n1`, which was that history file.
2. The workflow set `ENABLE_KEYLESS_SOURCES=0` "to stay fully offline/hermetic in CI" —
   but that disables Openverse/Wikimedia/Archive/NASA, the **only** providers that need
   no API key. With no Pexels/Pixabay secrets either, `fetch_scene_assets` had zero
   providers, and `pipeline/run.py` hard-fails rather than substituting a title card
   (correct behaviour — `test_no_match_is_not_silently_replaced_with_a_title_card`
   enforces it). The general pipeline has **no** offline path, so that job could never
   pass as written.

**Fix.** Archived the out-of-niche drafts to `content/archive/` (see its README — the
Johnstown engines still read them), added an in-niche queue job, rewrote `dry-run.yml`
into the three jobs above, and added `tests/test_queue_integrity.py`.

**Guard.** `test_every_queued_job_is_in_niche` fails if anything the scheduler can glob
would be refused by the niche gate. Verified: copying the history draft back into
`content/queue/` makes the suite exit 1 with exactly the original message.

Also fixed while in there: **`tests/` was never wired into CI at all.** `checks` runs it now.

### 2026-10-20 — `remaster.yml` was pinned to the abandoned branch

**Symptom.** The manual *Remaster documentary assets* workflow refused to run at all:

```bash
if [[ "$GITHUB_REF_NAME" != "arena/79365da2-youtube-automation" ]]; then
  echo "Run this workflow from arena/79365da2-youtube-automation; refusing to push to another branch."
  exit 1
fi
```

Hard-coded to a session branch that no longer receives work — and its `git push` targeted
that same dead branch. Once the project moved, the workflow was unusable either way: run
it from the new branch and the guard aborts; run it from the old one and it pushes into a
graveyard.

**Fix.** Push to `HEAD:$GITHUB_REF_NAME` — the branch the run was dispatched from — and
refuse only when `GITHUB_REF_TYPE != "branch"` (tags / PR refs). `[skip ci]` on the commit
keeps the push from re-triggering CI. Verified against `main`, a session branch, and a tag
ref: the first two push to the correct branch, the third exits 1.

`PLAN.md`, `docs/SETUP.md` and `docs/ASSET_SOURCING.md` all told maintainers to select the
dead branch by name. Those instructions are updated too.


---

## 4. Known debt — do not let these surprise you

| Debt | Severity | Note |
|---|---|---|
| **`image-search/` stills have no licence ledger** | **blocks monetized reuse** | ~10 MB, 47 files. `docs/ASSET_SOURCING.md` already flags this: *"no complete per-file license ledger in this checkout"*. The render writes `license: "…source/license metadata unavailable…verify before monetized reuse"` and `fallback: true` for all 16 Enron scenes. Verify or replace before any monetized upload. Cannot simply delete — `tools/deep_dive.py` / `tools/shorts.py` read these paths. |
| **44.9 MB of media in git** | contradicts README rule 2 | README says *"Never commit media. Git = text only"*, yet `docs/media/*.mp4` (28 MB) and `assets/deepdive/*.mp3` are deliberately un-ignored: Pages serves the first and the authored engines read the second. The rule is really "never commit *generated* media". Repo is well under any GitHub limit; the wording is what's wrong. |
| **No licence for the repo** | low | `gh repo view` reports `licenseInfo: null`. Fonts carry their own OFL (`assets/fonts/Inter-LICENSE-OFL.txt`). |

---

## 5. Operational calendar

| When | What | Why |
|---|---|---|
| **Before 31 Jan 2027** | Apply to YPP | Thresholds **double** on 1 Feb 2027: 4,000 → **8,000** watch hours (or 20M Shorts views). This is the hardest date in the project. `PLAN.md` §7 is built backwards from it. |
| Weekly, Mon 03:23 UTC | `keepalive.yml` | GitHub auto-disables scheduled workflows in public repos after **60 days** of inactivity. Never delete this workflow. |
| Twice daily, 06:14 / 14:14 UTC | `produce.yml` | Renders + uploads approved jobs as private drafts. |
| Fri 18:41 UTC | `metrics.yml` | Weekly public-video snapshot, artifact-only (30-day retention); excludes private/unlisted videos and does not commit metrics to git. |

Cron is best-effort on GitHub (can lag 15–30 min). That is fine for content.

---

## 6. Adding a video

1. Create `content/queue/NNNN-slug.md` from the frontmatter shape in
   `pipeline/script_doc.py`'s docstring. **`niche` must contain finance / financial /
   business / markets / economics** or the niche gate refuses it.
2. Write the scenes. Set `originality.human_rewrite: false` until you have verified the
   facts and rewritten in your own words — `pipeline/originality.py` will block the job
   until it is `true`. That is the human-creative / machine-labour split the channel's
   monetization depends on (PLAN.md §4.4); do not flip it as a convenience.
3. `status: draft` renders but never uploads. Flip to `approved` only when it should ship.
4. `python -m unittest discover -s tests` — `test_queue_integrity` will catch a bad niche,
   a thin script, a missing checklist, or an approved-but-unverified job.

`content/archive/` is never globbed by `select_jobs`. Moving a file back into
`content/queue/` re-arms it.

---

## 7. Secrets

`.env.example` documents all of them; `docs/SETUP.md` walks through minting them.

| Secret | Required for | Notes |
|---|---|---|
| `PEXELS_API_KEY`, `PIXABAY_API_KEY` | general pipeline b-roll | Free tier, no card. Optional: `pipeline-dry-run` is verified green without them (2026-10-21); keys widen provider coverage and absorb Openverse timeouts. |
| `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN` | upload + metrics | Store as three separate GitHub secrets. Client ID and raw client secret come from the Web client; mint the refresh token with OAuth Playground. The `youtube_oauth.py` local-server helper requires a computer. |

⚠️ External OAuth apps in **Testing** have a 7-day refresh-token limit for non-basic scopes.
Production/unverified personal-use apps avoid that Testing-specific limit but still show an
unverified-app warning and are subject to Google's token revocation/expiration rules. Public
use of sensitive scopes requires verification. `AUTO_PUBLISH` stays off; uploads remain
private drafts for human review.

**Never commit a key.** `.env` is gitignored; CI reads secrets from GitHub only.
