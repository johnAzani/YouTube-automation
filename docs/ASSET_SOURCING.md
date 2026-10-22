# Free, clip-first visual sourcing

The video pipeline attempts scene-matched moving footage first, then a scene-matched still. It uses these free sources, in order:

1. **Pexels** — free video and photo API; optional `PEXELS_API_KEY` GitHub Actions secret.
2. **Pixabay** — free video and photo API; optional `PIXABAY_API_KEY` secret.
3. **Openverse** — anonymous search; the adapter only accepts CC0, public-domain, and CC BY results for commercial adaptation, and records attribution.
4. **Wikimedia Commons** — keyless API; only CC0, public-domain, or CC BY entries are accepted; NC, ND, and ShareAlike entries are skipped. The test lives in `pipeline/assets.py::licence_ok_for_monetized_use()`, which tokenises `LicenseShortName` — Commons sends these abbreviated (`CC BY-SA 4.0`, `CC BY-NC 2.0`), and a substring match on "share alike" silently waved them through until 2026-10-22 (MAINTENANCE.md §3).
5. **Internet Archive** — keyless metadata/search; only items with explicit CC BY/CC0/public-domain rights and downloadable media are considered.
6. **NASA Image and Video Library** — keyless search; public-domain default, but the item must be checked for third-party material.

Pexels/Pixabay keys are optional. They are free to obtain from their respective platforms; never place a key in code or commit it. The scheduled `produce.yml` workflow already reads these GitHub secrets. When no source returns a legal, downloadable match, the general automation stops that job with a clear scene/query error rather than publishing a generic card. The authored Johnstown/Enron deep dives and Shorts retain a story-specific photo for every scene, so an unavailable API or a bad video decode cannot leave a blank shot.

## Aspect-ratio and quality rules

- API searches request portrait or landscape media matching the target format.
- **The complete downloaded source frame is preserved:** renderers scale proportionally into a safe inset and use a designed navy matte for the unused canvas. No `force_original_aspect_ratio=increase`, source crop, or anisotropic stretch is used.
- The small camera move stays inside the matte safety margin, rather than zooming through the source edges.
- In vertical Shorts, a landscape source therefore appears fully visible within the 9:16 frame (with designed top/bottom space); this is preferable to cutting off the scene. A native 9:16 source fills more of the frame naturally.
- Each run writes `credits.json` and a Shorts/deep-dive `scene-sources.json` with query, provider, URL, licence, dimensions, and whether the authored photo fallback was used. The general pipeline additionally writes a per-scene `sourcing-attempts.json` recording why each provider hit or missed (no API key / request failed / no licensed results / download error) — the diagnostic trail behind MAINTENANCE.md §3. The authored `image-search/` stills now have a real per-file ledger — see below.

## The authored-still licence ledger (`image-search/LICENSES.yml`)

`tools/deep_dive.py` and `tools/shorts.py` fall back to the 49 authored stills in `image-search/`
whenever a stock provider returns nothing. Until 2026-10-22 nothing recorded where those files
came from, and both tools wrote the same blanket string into `scene-sources.json` for every one
of them — which said the same thing about a public-domain 1889 photograph and a rights-managed
Getty frame.

`scripts/licence_ledger.py` derives each file's status from **its own** metadata: EXIF
`Copyright` / `Artist` / `ImageDescription`, embedded XMP packets, and raw byte markers
(`gettyimages`, `xmpRights:WebStatement`, `plus:Licensor`, `All Rights Reserved`). Every entry
is keyed by SHA-256, so a swapped file cannot inherit its predecessor's clearance.

| status | meaning | monetized use |
|---|---|---|
| `rights-encumbered` | an embedded rights claim was found | **never** — replace the file |
| `corrupt` | will not decode | never |
| `unverified` | no claim found; absence of a claim is not a licence | not until cleared |
| `cleared` | a human verified the licence and recorded `license` + `source_url` | yes |

Current state, scanned 2026-10-22: **13 rights-encumbered, 1 corrupt, 35 unverified, 0 cleared.**
The encumbered set is 10 stills carrying embedded Getty Images rights metadata (all Enron) and
3 carrying an "All Rights Reserved" photographer copyright (Johnstown Flood National Memorial).
Nine of those 13 are referenced by scene tables (8 Enron, 1 Johnstown), so the Enron deep
dive and Shorts are **not** safe to monetize until the files are replaced. Only 23 of the 49
stills are referenced at all — the other 26 are unused inventory. The renderers now say so at
runtime and write the real status into `scene-sources.json` instead of the blanket string.

```bash
python scripts/licence_ledger.py check   # what CI runs — drift = non-zero exit
python scripts/licence_ledger.py scan    # show the evidence per file, write nothing
python scripts/licence_ledger.py write   # regenerate; preserves human edits for unchanged bytes
```

`write` preserves `status`, `license`, `source_url`, `attribution`, `verified_on`,
`verified_by` and `notes` for any file whose SHA-256 is unchanged, so clearing a file is a
one-line edit that survives regeneration. `scripts/doctor.py` re-derives every status from
the bytes and fails if the ledger disagrees.

**To clear a still:** find its source page, confirm the licence permits commercial use with
attribution, set `status: cleared`, and fill in `license`, `source_url` and `attribution`.
To retire one: replace the file with a newly acquired, logged asset and re-run `write` — the
new bytes get a fresh `unverified` entry, which is the correct starting point.
- Downloaded assets are cached under ignored `output/`; they are not committed to Git. The cache is free storage, not a third-party API cost.

## Every scene query must be verified before it ships

`content/queue/*.md` jobs carry one `asset_queries` entry per scene. Those queries are the
only thing that decides whether a scene has a picture in it, and on a runner with no
`PEXELS_API_KEY`/`PIXABAY_API_KEY` **only the keyless providers run** — so a query that
looks fine to a human can still source nothing.

Every queued job therefore records an `asset_query_verification` block in frontmatter. For
each query, either:

- `usable: N` with `N ≥ 1` — a Wikimedia Commons probe (`generator=search`,
  `filetype:bitmap`, top 4), scored with the licence rule above; or
- `ci_verified: <run id>` — the `pipeline-dry-run` job actually rendered that scene
  end to end on a keyless runner.

…plus an `evidence` note naming what was found, and `verified_on` / `method` for the block.
`tests/test_asset_query_verification.py` fails the build on an unverified query, a query
recorded with zero usable hits, or a stale entry for a query that no longer exists. Record
rejected queries too (in the YAML comments above `asset_queries`) so nobody re-adds a
proven-dead one — e.g. `bank of england threadneedle street` returns 4/4 CC BY-SA and is
therefore worth **zero** usable hits, while the shorter `bank of england london` returns a
public-domain 1885–1895 view that passes.

Practical consequence: Commons is dominated by CC BY-SA photography of streets and
buildings, so real-world queries often have far fewer *usable* hits than hits. A query with
one usable hit still works, but it means the scene's visual is chosen for you — add a
Pexels or Pixabay key if a scene keeps rendering the wrong picture.

## Reproducible controls

The manual GitHub Actions workflow is `Remaster documentary assets` (`.github/workflows/remaster.yml`). Run it from the branch you want the refreshed demos published to, choose `all`/`deepdives`/`shorts`, and leave `use_free_stock` on to search providers. If GitHub does not list the workflow yet, the file must first be merged to the repository's default branch. The workflow publishes back to the branch it was dispatched from; it refuses to run from a non-branch ref such as a tag or pull-request ref.

- `ENABLE_STOCK_BROLL=0` skips online search in the authored Shorts/deep-dive remaster engines and uses their scene-specific story stills.
- `ENABLE_KEYLESS_SOURCES=0` disables Openverse, Wikimedia, Internet Archive, and NASA while keeping configured Pexels/Pixabay.
- `PEXELS_API_KEY` and `PIXABAY_API_KEY` are optional free-tier secrets. Do not put them in an `.env` committed to Git.
- Provider errors, absent credentials, no matching item, or a broken codec degrade to a still/fallback; they do not fail the whole render.

External stock endpoints are not reachable from every sandbox/network. A failed local search is recorded in the render log and does not mean those free providers are unavailable to the GitHub-hosted runner. Never describe an unverified fallback as stock footage: the per-scene source ledger distinguishes video, stock photo, and authored archive-photo fallback.
