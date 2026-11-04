import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import continuous_research


class ContinuousResearchTests(unittest.TestCase):
    def test_build_intelligence_report_generates_valid_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            with patch.object(continuous_research, "ROOT", tmp_root), \
                 patch.object(continuous_research, "RESEARCH_DIR", tmp_root / "content/research"), \
                 patch.object(continuous_research, "INTELLIGENCE_OUTPUT", tmp_root / "content/research/channel_intelligence.json"):
                intel = continuous_research.build_intelligence_report()
                self.assertIsNotNone(intel.audited_at)
                self.assertGreaterEqual(intel.subscriber_count, 1000)
                self.assertTrue(intel.ypp_subscriber_milestone)
                self.assertEqual(intel.ypp_watch_hours_target, 4000)
                # The next recommendation is now feedback-aware and dynamic (it used
                # to be hardcoded to the already-published Psalm 23). Assert it is a
                # valid roadmap-shaped candidate that is not already queued/published,
                # rather than pinning a specific stale scripture.
                job = intel.next_recommended_job
                self.assertTrue(job.get("scripture"))
                self.assertTrue(job.get("id"))
                self.assertTrue(job.get("theme"))
                existing = {p.name[:4] for p in continuous_research.QUEUE_DIR.glob("*.md")} | {
                    p.name[:4] for p in continuous_research.PUBLISHED_DIR.glob("*.md")
                }
                self.assertNotIn(job["id"], existing)
                self.assertTrue((tmp_root / "content/research/channel_intelligence.json").is_file())

    def test_scripture_roadmap_integrity(self):
        roadmap = continuous_research.SCRIPTURE_ROADMAP
        self.assertGreaterEqual(len(roadmap), 5)
        for entry in roadmap:
            self.assertIn("id", entry)
            self.assertIn("scripture", entry)
            self.assertIn("theme", entry)
            self.assertIn("hook", entry)
            self.assertIn("verses", entry)
            self.assertIn("target_duration", entry)
