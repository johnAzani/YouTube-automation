"""End-to-end regression suite for Autonomous Channel Autopilot Lock-In.

Verifies:
  1. Non-Psalm & verse-specific Short keys (`short_key_for_doc`) strictly match `^short-[a-z0-9]+$`
     and never mislabel Proverbs/Isaiah/Matthew/Numbers as Psalms.
  2. Companion Shorts queue (`content/shorts-queue/`) & specs (`content/shorts-scripts/`)
     are 100% valid, collision-free, and ready to render.
  3. Shorts pacing guard (`recent_short_published_within`) prevents rapid-fire 15-minute
     Short drains while allowing normal 3x/day release windows.
  4. Quota-cooldown recognition (`active_quota_cooldown`) prevents `scheduler_supervisor`
     retry storms and `automation_monitor` false-alarm `FAILING` states when the channel
     already published within 24h and is waiting for daily free-tier TTS reset.
  5. Idempotent live metadata retrofit (`sync_published_metadata`) stamps
     `metadata_revision: "selar-seo-v1"`, skips deleted `0009`, skips already-synced
     receipts, and wires both Selar links + clean titles.
"""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import yaml

from pipeline.gemini_brain import GeminiBrain, extract_scripture_reference, short_key_for_doc
from pipeline.script_doc import parse_script
from pipeline.short_release import queue_report, recent_short_published_within, resolve_edition
from pipeline.short_script import load_spec, require_valid, validate_spec
from pipeline.shorts_bridge import enrich_short_description_with_bridge, resolve_longform_counterpart
from pipeline.social_pack import SELAR_JOURNAL_URL, SELAR_STORE_URL
from scripts import automation_monitor as am
from scripts import retrofit_published_metadata as rpm
from scripts import scheduler_supervisor as sup

REPO = Path(__file__).resolve().parents[1]


class TestShortKeyAndNonPsalmIntegrity(unittest.TestCase):
    def test_every_approved_queue_script_maps_to_unique_valid_short_key(self):
        seen_keys: dict[str, str] = {}
        for path in sorted((REPO / "content" / "queue").glob("*.md")):
            doc = parse_script(path)
            if str(doc.status).strip().lower() != "approved":
                continue
            key = short_key_for_doc(doc)
            self.assertRegex(key, r"^short-[a-z0-9]+$", f"{path.name} produced invalid key {key!r}")
            self.assertNotIn(key, seen_keys, f"collision on {key}: {seen_keys.get(key)} vs {path.name}")
            seen_keys[key] = path.name

    def test_non_psalm_short_spec_never_mislabels_psalm_number(self):
        spec = validate_spec(
            {
                "key": "short-proverbs3v24",
                "psalm": None,
                "scripture": "Proverbs 3:24-26",
                "title": ["SWEET SLEEP", "PROVERBS 3:24"],
                "poster": ["THY SLEEP", "SHALL BE SWEET", "PROVERBS 3:24", "SWEET NIGHT REST"],
                "end": ["SUBSCRIBE", "The Secret Place — prayers every day"],
                "stock_queries": ["q1", "q2", "q3", "q4", "q5", "q6"],
                "scenes": [
                    {"a": "a", "img": f"i{i}.jpg", "kicker": "PROVERBS 3", "sub": "SWEET SLEEP", "cam": "push_in", "focus": [0.5, 0.5]}
                    for i in range(6)
                ],
                "captions": [
                    [0, 15, " ".join(["peaceful"] * 32)],
                    [15, 30, " ".join(["slumber"] * 32)],
                    [30, 45, " ".join(["tonight"] * 32)],
                ],
                "kinetic_phrases": [
                    [0, 15, ["PEACEFUL"], ["PEACEFUL"], "PROVERBS 3:24"],
                    [15, 30, ["SLUMBER"], ["SLUMBER"], "PROVERBS 3:25"],
                    [30, 45, ["TONIGHT"], ["TONIGHT"], "PROVERBS 3:26"],
                ],
                "beats": [],
            }
        )
        require_valid(spec)
        self.assertIsNone(spec.psalm)
        self.assertEqual(spec.scripture, "Proverbs 3:24-26")

        ed_proverbs = resolve_edition("short-proverbs3v24")
        self.assertIsNotNone(ed_proverbs)
        self.assertIn("Proverbs 3:24-26", ed_proverbs.title)
        self.assertNotIn("Psalm 3", ed_proverbs.title)

        ed_isaiah = resolve_edition("short-isaiah26v3")
        self.assertIsNotNone(ed_isaiah)
        self.assertIn("Isaiah 26:3-4", ed_isaiah.title)
        self.assertNotIn("Psalm 26", ed_isaiah.title)

    def test_all_staged_shorts_are_ready_and_enriched_with_selar_links(self):
        rows = queue_report()
        published_shorts = list((REPO / "content" / "published").glob("short-*.md"))
        self.assertGreaterEqual(len(rows), 1)
        self.assertGreaterEqual(len(rows) + len(published_shorts), 8)
        for row in rows:
            self.assertNotIn(row["verdict"], ("unusable", "needs_renderer"), f"Broken manifest: {row}")
            if row["status"] == "approved":
                self.assertEqual(row["verdict"], "ready", f"Manifest not ready: {row}")
            else:
                self.assertEqual(row["status"], "quota_paused", f"Unexpected manifest status: {row}")
            ed = resolve_edition(row["short"], channel_id=row["channel"])
            self.assertIsNotNone(ed)
            from pipeline.channel_capabilities import brand_for, known_channels
            from pipeline.channels import get_channel

            enriched = enrich_short_description_with_bridge(
                ed.description, ed.key, channel_id=row["channel"]
            )
            if get_channel(row["channel"]).include_sanctuary_links:
                self.assertIn(SELAR_JOURNAL_URL, enriched)
                self.assertIn(SELAR_STORE_URL, enriched)
            else:
                self.assertNotIn(SELAR_JOURNAL_URL, enriched)
                self.assertNotIn(SELAR_STORE_URL, enriched)
            for other_cid in known_channels():
                if other_cid != row["channel"]:
                    self.assertNotIn(brand_for(other_cid).handle, enriched)

    def test_deleted_0009_is_never_linked_by_shorts_bridge(self):
        cp = resolve_longform_counterpart("short-psalm23")
        self.assertNotIn("JZv67RNPCEI", cp["url"])


class TestShortPacingAndQuotaCooldown(unittest.TestCase):
    def test_recent_short_published_within_detects_sub_3h_upload(self):
        now = datetime(2026, 11, 3, 20, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            pub = Path(tmp)
            (pub / "short-0005-test.md").write_text(
                '---\nyoutube_video_id: "KkPAtMLoGf4"\npublished_at: "2026-11-03T18:58:39Z"\n---\n',
                encoding="utf-8",
            )
            hit = recent_short_published_within(hours=3.0, published_dir=pub, now=now)
            self.assertIsNotNone(hit)
            self.assertAlmostEqual(hit[1], 61.35, delta=1.0)

            old_now = now + timedelta(hours=4)
            self.assertIsNone(recent_short_published_within(hours=3.0, published_dir=pub, now=old_now))

    def test_active_quota_cooldown_suppresses_supervisor_retry_and_monitor_blocking(self):
        now = datetime(2026, 11, 3, 20, 0, tzinfo=timezone.utc)
        reset_at = datetime(2026, 11, 4, 8, 0, tzinfo=timezone.utc)

        with mock.patch("pipeline.run.quota_blocked_until", return_value=reset_at), \
             mock.patch("scripts.pipeline_watchdog.last_publish", return_value=(Path("x.md"), now - timedelta(hours=1))):
            cd = am.active_quota_cooldown(now)
            self.assertEqual(cd, reset_at)

            # Supervisor does not retry a failed produce.yml slot during active cooldown
            state = {"produce.yml@2026-11-03T14:14:00+00:00": {"at": "2026-11-03T18:30:00+00:00", "attempts": 1}}
            latest = {"produce.yml": (datetime(2026, 11, 3, 18, 45, tzinfo=timezone.utc), "failure")}
            self.assertEqual(sup._failed_dispatches(state, latest, now), [])

            # Monitor classifies produce.yml as non-blocking QUOTA WAIT instead of FAILING
            auto = am.Automation(workflow="produce.yml", name="Produce video", crons=["14 6 * * *"])
            auto.last_run = now - timedelta(minutes=30)
            auto.last_conclusion = "failure"
            auto.last_edited = now - timedelta(days=2)
            am._verdict(auto, now, quota_cooldown=cd)
            self.assertEqual(auto.verdict, "QUOTA WAIT")
            self.assertEqual(auto.severity, "info")

    def test_quota_cooldown_never_hides_stale_channel_without_recent_publish(self):
        now = datetime(2026, 11, 3, 20, 0, tzinfo=timezone.utc)
        reset_at = datetime(2026, 11, 4, 8, 0, tzinfo=timezone.utc)
        with mock.patch("pipeline.run.quota_blocked_until", return_value=reset_at), \
             mock.patch("scripts.pipeline_watchdog.last_publish", return_value=(Path("x.md"), now - timedelta(hours=30))):
            self.assertIsNone(am.active_quota_cooldown(now))


class TestIdempotentLiveMetadataRetrofit(unittest.TestCase):
    def test_sync_published_metadata_stamps_receipt_and_skips_second_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            pub = Path(tmp)
            p10 = pub / "0010-psalm-121.md"
            p10.write_text(
                "---\n"
                'id: "0010"\n'
                'title: "Psalm 121: Truncated — Peace & Di"\n'
                "slug: psalm-121\n"
                "status: published\n"
                "format: longform\n"
                "niche: faith and prayer\n"
                'youtube_video_id: "6M6oV8MxD9s"\n'
                "---\n\n## Scene 1 — Hills\nI will lift up mine eyes unto the hills.\n",
                encoding="utf-8",
            )
            p09 = pub / "0009-deleted.md"
            p09.write_text(
                "---\n"
                'id: "0009"\n'
                'title: "Psalm 23"\n'
                "slug: psalm-23\n"
                "status: published\n"
                "format: longform\n"
                "niche: faith and prayer\n"
                'youtube_video_id: "JZv67RNPCEI"\n'
                'youtube_status: "deleted_or_missing"\n'
                "---\n\n## Scene 1\nThe Lord is my shepherd.\n",
                encoding="utf-8",
            )

            calls: list[tuple] = []

            def fake_updater(vid, *, new_title=None, new_description=None, new_tags=None, localizations=None):
                calls.append((vid, new_title, new_description, new_tags, localizations))
                return {"id": vid}

            rows1 = rpm.sync_published_metadata(published_dir=pub, only_pending=True, updater=fake_updater)
            self.assertEqual(len(rows1), 1)
            self.assertEqual(rows1[0]["video_id"], "6M6oV8MxD9s")
            self.assertEqual(rows1[0]["status"], "updated")
            self.assertEqual(calls[0][1], "Psalm 121 Night Prayer for Sleep & Peace | He Never Slumbers")
            self.assertIn(SELAR_JOURNAL_URL, calls[0][2])
            self.assertIn(SELAR_STORE_URL, calls[0][2])
            self.assertIn("es", calls[0][4])
            self.assertIn("pt", calls[0][4])

            doc_after = parse_script(p10)
            self.assertEqual(doc_after.meta.get("metadata_revision"), rpm.METADATA_REVISION)

            # Second pass is a 0-API-call no-op
            calls.clear()
            rows2 = rpm.sync_published_metadata(published_dir=pub, only_pending=True, updater=fake_updater)
            self.assertEqual(rows2, [])
            self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
