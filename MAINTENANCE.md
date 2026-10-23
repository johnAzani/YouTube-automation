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

### ffmpeg resolution — one rule everywhere (since 2026-10-23)

Every code path resolves through `pipeline/assemble.py::ffmpeg_bin()`:

```
$FFMPEG_BINARY (only if it resolves) → PATH → imageio_ffmpeg static build
```

`tools/deep_dive.py`, `tools/shorts.py` and `tools/motionstudio.py` used to default to the
literal `"ffmpeg"` with **no fallback**, so they needed system ffmpeg on `PATH` or a
hand-exported `FFMPEG_BINARY`. That was the wrong way round: `imageio-ffmpeg` is already in
`requirements.txt`, so a static build is always present after `pip install -r requirements.txt`.
Nothing needs exporting any more — `.venv/bin/python tools/shorts.py short-enron` works on a
machine with no ffmpeg installed (verified 2026-10-23, 1252 frames, exit 0).

CI installs ffmpeg through `.github/actions/setup-render-deps`, which runs pip **first**, then
tries apt inside `timeout`, then exports `FFMPEG_BINARY` from the static build if apt did not
deliver. Do not inline `apt-get install ffmpeg` back into a workflow —
`tests/test_ffmpeg_resolution.py` fails the build if you do. See §3 (2026-10-23).

`ffprobe` is the exception: it ships with apt only, never with imageio-ffmpeg. Any step that
inspects media must fall back to parsing `ffmpeg -hide_banner -i` (see the
`probe_streams()` helper in `dry-run.yml`, which `tests/test_ffmpeg_resolution.py` executes
verbatim against real media).

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

### 2026-10-23 — apt hung and the required CI job died before running a single test

**Symptom.** PR #7 went red with `Unit tests + doctor: cancelled`. Not `failure` — `cancelled`,
which reads like somebody clicked stop. Three runs in a row: `39898588505`, `39899531755`,
`39899527120`.

**Diagnosis.** The per-step statuses told the story:

```
Set up job=success, checkout=success, setup-python=success,
System deps (ffmpeg)=cancelled, Python deps=skipped, Unit tests=skipped
```

It never reached the tests. The job sat inside `sudo apt-get install -y ffmpeg` for its entire
`timeout-minutes: 10` budget and was killed. Two jobs in the same run ran the identical apt
step and succeeded, so the mirror is intermittently slow, not broken. GitHub surfaces a job
timeout as `cancelled`, so it did not look like a failure at all.

**Why it could cost the whole budget.** Every workflow ran apt **before** `pip install
-r requirements.txt`, with no timeout on either apt call. That ordering is backwards:
`requirements.txt` already pins `imageio-ffmpeg`, whose static build
`pipeline.assemble.ffmpeg_bin()` knows how to find. Installing pip first means the fallback
exists before apt is even attempted.

**Second defect, found while fixing the first.** `tools/deep_dive.py`, `tools/shorts.py` and
`tools/motionstudio.py` did `os.environ.get('FFMPEG_BINARY', 'ffmpeg')` — no fallback to the
static build that was sitting right there in the venv. §1 documented this as intentional
("GitHub runners install real ffmpeg via apt, so CI never needs this"); the incident disproved
the premise. `remaster.yml` made it worse by hard-pinning `FFMPEG_BINARY: ffmpeg` at job level,
a bare name that `Path('ffmpeg').exists()` rejects, which defeated the one resolver that did
have a fallback.

**Third defect, found while testing the fix.** The media check in `offline-render` called bare
`ffprobe`. imageio-ffmpeg ships ffmpeg only — no ffprobe — so the fallback path had no probe at
all. The first ffmpeg-banner replacement grep'd for `Stream #0:0: Video`; the real banner is
`Stream #0:0[0x1](und): Video:`. It matched nothing, so a healthy render would have been
reported as having no video stream. Caught by running the YAML's shell verbatim, not by reading
it.

**Fixes.**
1. `.github/actions/setup-render-deps` — pip first, then apt inside `timeout 120`/`timeout 300`
   and non-fatal, then export `FFMPEG_BINARY` from imageio-ffmpeg if `ffmpeg` is not on `PATH`.
   Used by all three `dry-run.yml` jobs plus `produce.yml` and `remaster.yml`.
2. All three renderer CLIs resolve through `pipeline.assemble.ffmpeg_bin()`.
3. `probe_streams()` in `dry-run.yml` uses ffprobe when present, else the ffmpeg banner.
4. `tests/test_ffmpeg_resolution.py` (11 tests) pins the precedence, forbids inline
   `apt-get install` in workflows, and executes the YAML's probe against real media.

**Verify locally** (no system ffmpeg here, so the fallback is the only path):

```bash
env -u FFMPEG_BINARY .venv/bin/python -c \
  "import sys; sys.path.insert(0,'tools'); import shorts; print(shorts.FFMPEG)"
# → .../imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2
env -u FFMPEG_BINARY ENABLE_STOCK_BROLL=0 .venv/bin/python tools/shorts.py short-enron
# → 1252 frames, social/short-enron.mp4 8181 KB, exit 0
```

**Lesson.** A required check that installs its own toolchain can die before it checks anything,
and report that as a cancellation. Bound every network/install step, and put the dependency
that already ships in `requirements.txt` ahead of the one that needs a mirror.

### 2026-10-22 — the keyless provider was downloading non-commercial and share-alike images

**Symptom.** None visible. Nothing failed, which is exactly why it survived.

**Cause.** `_wikimedia()` filtered licences with a substring test:

```python
if any(term in lic_norm for term in ('noncommercial','non-commercial','share alike',
                                     'share-alike','no derivatives','no-derivatives')) \
   or not any(term in lic_norm for term in ('cc0','public domain','cc by','cc-by')):
```

Commons reports `LicenseShortName` **abbreviated** — `CC BY-SA 4.0`, `CC BY-NC 2.0`,
`CC BY-ND 4.0`. None of the spelled-out reject strings occur in those, and `cc by` is a
substring of all three. Every share-alike, non-commercial and no-derivatives hit therefore
passed and was downloaded, rendered and (in production) uploaded. `docs/ASSET_SOURCING.md`
had documented the correct behaviour the whole time; the code simply never implemented it.

**Why it mattered more than it looks.** Wikimedia is the provider that needs no API key,
so it is the one CI uses and the one any setup without `PEXELS_API_KEY`/`PIXABAY_API_KEY`
falls through to. The two providers with correct filters (Internet Archive, Openverse) are
not the ones that get exercised. And NC/ND material in a monetized video is a copyright
claim, not a warning — PLAN.md §6 lists *"Stock footage licence complaints"* as a medium
risk on the assumption the licence filter works.

**Fix.** `licence_ok_for_monetized_use()` in `pipeline/assets.py` tokenises the licence
string and refuses any `nc` / `sa` / `nd` token plus the spelled-out equivalents; unknown
licences are refused. Three tests: two drive the real `_wikimedia()` with a fake Commons
payload (all-NC/SA/ND result set → no asset, nothing downloaded, probe says `licence=3`;
plain `CC BY 2.0` → still accepted), one pins the predicate against the full set of real
Commons licence strings.

**How it was found.** Not by a test that existed — by a test written for a different
purpose. `tests/test_asset_query_verification.py` needed to state the licence rule that
the queued jobs' `usable` counts were scored against, and asserting the obvious
(`assertFalse(_lic_usable("CC BY-SA 4.0"))`) failed on the first run. Worth remembering:
the check that catches a bug is often the one you write to document an assumption.

**Cost of the fix.** A scene previously served by a CC BY-SA hit now correctly finds
nothing, so keyless runs may need a query change or a Pexels/Pixabay key. Jobs 0004–0006
were written against the tightened rule (their frontmatter records the probe counts and
lists the queries that were rejected during verification). Job 0003's coverage is the
`pipeline-dry-run` job on this branch.

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
| **13 `image-search/` stills are rights-encumbered** | **blocks monetized reuse of the Enron renders** | Ledger now exists (`image-search/LICENSES.yml`, scanned 2026-10-22): **13 rights-encumbered, 1 corrupt, 35 unverified, 0 cleared**. 10 stills carry embedded Getty Images rights metadata (EXIF/XMP — e.g. `"2002 Getty Images"` on `andrew-fastow-enron-cfo-trial-photo-2.jpg`) and 3 carry `"All Rights Reserved"` photographer copyrights (`Copyright 2014/2021 Steven L. Markos`, Johnstown Flood National Memorial). **Nine of the 13 are referenced by scene tables** — 8 in the Enron deep dive/Shorts (`enron-corporation-headquarters-houston-c-1..5`, `…-f-1`, `…-f-5`, `andrew-fastow-enron-cfo-trial-photo-2`) and 1 in Johnstown (`south-fork-fishing-and-hunting-club-club-1`) — so the Enron renders in particular must not be monetized until the files are replaced. Only 23 of the 49 stills are referenced at all; the other 26 are unused inventory. `scripts/doctor.py` reports this as a failed check; `scripts/licence_ledger.py check` runs in CI. |
| **35 `image-search/` stills have unverified provenance** | medium | No embedded rights claim, but absence of a claim is not a licence. Includes one file whose comment names a source (`johnstown-train-clean.jpg` → `File source: http://www.explar.com/File:17546u_Wreck_of_Pullman_cars_and_engines_at_Conemaugh,_Johnstown_Flood,_May_31st,_1889.tif`) and one with `Artist: Library of Congress` (`johnstown-flood-1889-ruins-destruction-h-4.jpg`). Either locate the source page and set `status: cleared`, or replace the file. Fine for private drafts. |
| **`johnstown-flood-1889-ruins-destruction-h-5.png` is dead weight** | trivial | 68 bytes, will not decode. Referenced by no scene in `tools/deep_dive.py` or `tools/shorts.py`. Recorded in the ledger as `corrupt` rather than silently deleted, so the 49-file inventory stays complete. Also note `enron-corporation-headquarters-houston-c-3.jpg` and `enron-scandal-2001-newspaper-headlines-f-4.jpg` are byte-identical (one sha256, two filenames). |
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
