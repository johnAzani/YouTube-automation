# Master Specification: Duplicate & Unintentional Upload Prevention Shield

**Channel Identity:** *The Secret Place* (`@TheSecretPlace`) — Sacred Scripture, Bedtime Prayer & Faith Contemplation Studio  
**Target Invariant:** Zero Duplicate Uploads · Zero Unintentional Releases · Permanent Channel Cleanliness  
**Associated Code:** `pipeline/upload.py`, `pipeline/short_release.py`, `pipeline/run.py`, `scripts/cleanup_duplicate_shorts.py`, `.github/workflows/produce.yml`  
**Governance Invariant:** Permanent $0.00 / month hard cost lock (`docs/ZERO_DOLLAR_LOCK.md`)

---

## 1. Forensic Analysis: Why Multiple Reels Appeared on Mobile

A screenshot of the YouTube mobile app revealed **5 duplicate uploads of the Psalm 91 Short** on the channel feed:
- Reel 1 (175 views): Anchor Master (`SG69BbNlfRw`)
- Reel 2 (58 views): Duplicate upload (`pbpPdG7_DQk`)
- Reel 3 (13 views): Duplicate upload (`q1LXu0_qB3A`)
- Reel 4 (No views): Duplicate upload
- Reel 5 (No views): Duplicate upload

```
                               FORENSIC FAILURE CHAIN
                                         │
    1. Placeholders in queue manifests had `short: "short-psalm91"` and `replace: true`
                                         │
                                         ▼
    2. `replace: true` automatically forced `force = True` in `run_short_release`
                                         │
                                         ▼
    3. `force = True` bypassed the check against `content/published/`
                                         │
                                         ▼
    4. `.github/workflows/produce.yml` fired on git push to main
                                         │
                                         ▼
    5. `pipeline/upload.py` lacked remote YouTube duplicate title verification
                                         │
                                         ▼
    6. `delete_video` could not delete public YouTube videos via API
                                         │
                                         ▼
    RESULT: New videos were created on each run while older videos remained live,
            accumulating 5 duplicate Reels on the channel feed.
```

---

## 2. The 6-Layer Permanent Prevention Shield

### Layer 1: Remote YouTube Channel Duplicate Detection (`pipeline/upload.py`)
Before calling `youtube.videos().insert()`, `pipeline/upload.py::check_existing_channel_duplicate()` queries the channel's recent uploads playlist (`playlistItems.list`, 1 quota unit).
- **Exact Title Matching:** Compares candidate title with all existing channel videos.
- **Normalized Title Matching:** Strips hashtags (`#Shorts`, `#shorts`), removes punctuation, lowercases, and collapses whitespace. For example:
  ```
  "Say This Psalm 91 Prayer Before You Sleep | Divine Protection #Shorts"
  ==> "say this psalm 91 prayer before you sleep divine protection"
  ```
- **Abort Action:** If a match is found on the channel and `CONFIG.allow_duplicate_uploads` is `False` (default):
  * **The API upload is immediately aborted.**
  * `videos().insert()` is **never called**.
  * Returns `privacy_status="duplicate_prevented"` with the existing video ID.

### Layer 2: Published Ledger Quarantine in Shorts Queue (`pipeline/short_release.py`)
`select_next_queued_short()` now cross-references every candidate manifest against `content/published/*.md`:
- If an edition key (e.g. `short-psalm91`) or slug is already recorded as `published` with a valid `youtube_video_id`:
  * It logs: `🛑 DUPLICATE BLOCKED: Short 'short-psalm91' is already published. Unlinking duplicate manifest.`
  * Automatically removes the rogue manifest (`path.unlink()`).
  * Continues searching without selecting it.

### Layer 3: Long-Form Queue Duplicate Shield (`pipeline/run.py`)
`select_jobs()` inspects `content/published/` before selecting any longform Markdown script:
- If a script file already exists in `content/published/` with `status: published` and a valid `youtube_video_id`, it is immediately bypassed.

### Layer 4: Neutralized `replace: true` Override Hazard
Previously, setting `replace: true` in a YAML manifest automatically forced `force = True`, which bypassed duplicate checks.
- **Correction:** `force` now strictly requires an explicit CLI flag (`--force` or `--force-reupload`). YAML manifests cannot unilaterally bypass duplicate protection.

### Layer 5: Eliminating Git Push Production Triggers (`.github/workflows/produce.yml`)
The `on.push` trigger has been removed from `.github/workflows/produce.yml`.
- Pushing commits, merging pull requests, or updating documentation will **NEVER** trigger live video uploads to YouTube.
- Live production uploads execute strictly during:
  1. The official release cron slots (**06:14 UTC** morning & **14:14 UTC** afternoon).
  2. An explicit manual trigger by the user via GitHub Actions (`workflow_dispatch`).

### Layer 6: Queue Sanitization & Distinct Editions
- Purged duplicate `short-0002-psalm-91.yml` from `content/shorts-queue/`.
- Updated placeholder manifests (`0010-...` and `0011-...`) to `status: draft`.
- Created unique `short-psalm23` edition for the companion Short to Psalm 23 (`content/shorts-queue/0009-short-psalm-23-the-lord-is-my-shepherd.yml`).

---

## 3. How to Clean Up the Existing Duplicate Reels from YouTube

To remove the accidental duplicate uploads from your channel's public Shorts tab:

### Step 1: Run Read-Only Duplicate Audit
```bash
python scripts/cleanup_duplicate_shorts.py --audit
```
This scans your channel and identifies:
- 👑 **Master Video:** The upload with 175 views (`SG69BbNlfRw`) to **KEEP PUBLIC**.
- 🗑️ **Duplicate Copies:** The 4 accidental uploads (58 views, 13 views, 0 views).

### Step 2: Set Duplicates to Private (Recommended)
```bash
python scripts/cleanup_duplicate_shorts.py --make-private
```
* **Why Private is Best:** Setting duplicate videos to `private` immediately removes them from your channel's public Shorts tab and YouTube search feeds, while preserving your channel's historical view analytics. Only the single, 175-view Master Reel will remain visible to the public!

### Step 3: Permanent Deletion (Alternative)
```bash
python scripts/cleanup_duplicate_shorts.py --delete
```
Permanently deletes the duplicate video records from YouTube.
