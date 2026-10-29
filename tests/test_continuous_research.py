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
                self.assertIn("Psalm 23", intel.next_recommended_job["scripture"])
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
