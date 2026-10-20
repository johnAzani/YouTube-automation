# Free, clip-first visual sourcing

The video pipeline attempts scene-matched moving footage first, then a scene-matched still. It uses these free sources, in order:

1. **Pexels** — free video and photo API; optional `PEXELS_API_KEY` GitHub Actions secret.
2. **Pixabay** — free video and photo API; optional `PIXABAY_API_KEY` secret.
3. **Openverse** — anonymous search; the adapter only accepts CC0, public-domain, and CC BY results for commercial adaptation, and records attribution.
4. **Wikimedia Commons** — keyless API; only CC0, public-domain, or CC BY entries are accepted; NC, ND, and ShareAlike entries are skipped.
5. **Internet Archive** — keyless metadata/search; only items with explicit CC BY/CC0/public-domain rights and downloadable media are considered.
6. **NASA Image and Video Library** — keyless search; public-domain default, but the item must be checked for third-party material.

Pexels/Pixabay keys are optional. They are free to obtain from their respective platforms; never place a key in code or commit it. The scheduled `produce.yml` workflow already reads these GitHub secrets. When no source returns a legal, downloadable match, the general automation stops that job with a clear scene/query error rather than publishing a generic card. The authored Johnstown/Enron deep dives and Shorts retain a story-specific photo for every scene, so an unavailable API or a bad video decode cannot leave a blank shot.

## Aspect-ratio and quality rules

- API searches request portrait or landscape media matching the target format.
- **The complete downloaded source frame is preserved:** renderers scale proportionally into a safe inset and use a designed navy matte for the unused canvas. No `force_original_aspect_ratio=increase`, source crop, or anisotropic stretch is used.
- The small camera move stays inside the matte safety margin, rather than zooming through the source edges.
- In vertical Shorts, a landscape source therefore appears fully visible within the 9:16 frame (with designed top/bottom space); this is preferable to cutting off the scene. A native 9:16 source fills more of the frame naturally.
- Each run writes `credits.json` and a Shorts/deep-dive `scene-sources.json` with query, provider, URL, licence, dimensions, and whether the authored photo fallback was used. The older `image-search/` stills have no complete per-file license ledger in this checkout; the report marks that gap. Verify their original source/license or replace them with a newly acquired, logged free asset before monetized reuse.
- Downloaded assets are cached under ignored `output/`; they are not committed to Git. The cache is free storage, not a third-party API cost.

## Reproducible controls

The manual GitHub Actions workflow is `Remaster documentary assets` (`.github/workflows/remaster.yml`). Run it from `arena/79365da2-youtube-automation`, choose `all`/`deepdives`/`shorts`, and leave `use_free_stock` on to search providers. If GitHub does not list the workflow yet, the file must first be merged to the repository's default branch; select the Arena branch as the workflow ref so its push guard cannot write to another branch.

- `ENABLE_STOCK_BROLL=0` skips online search in the authored Shorts/deep-dive remaster engines and uses their scene-specific story stills.
- `ENABLE_KEYLESS_SOURCES=0` disables Openverse, Wikimedia, Internet Archive, and NASA while keeping configured Pexels/Pixabay.
- `PEXELS_API_KEY` and `PIXABAY_API_KEY` are optional free-tier secrets. Do not put them in an `.env` committed to Git.
- Provider errors, absent credentials, no matching item, or a broken codec degrade to a still/fallback; they do not fail the whole render.

External stock endpoints are not reachable from every sandbox/network. A failed local search is recorded in the render log and does not mean those free providers are unavailable to the GitHub-hosted runner. Never describe an unverified fallback as stock footage: the per-scene source ledger distinguishes video, stock photo, and authored archive-photo fallback.
