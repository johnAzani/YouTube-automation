"""Morning Altar (prayer2) brain autonomy guards.

The failure these tests exist for is a brain that quietly serves the wrong
channel: Secret Place night scripts counted as Morning Altar supply, a
prayer2 script staged with a Secret Place Short, or a healthy channel-1
queue making an empty Morning Altar queue look supplied.
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pipeline import supply as sp
from pipeline.brain_equipment.equipment_registry import compile_full_brain_prompt
from pipeline.gemini_brain import BrainAuthoringError, GeminiBrain
from scripts.continuous_research import MORNING_ALTAR_ROADMAP, roadmap_for_channel

FRONT = """---
id: "{job_id}"
title: "{title}"
channel: {channel}
status: {status}
format: longform
voice: Charon
---

"""

BODY = """## Scene 1 — Morning Mercy (Verse 8)
Cause me to hear thy lovingkindness in the morning; for in thee do I trust.
We direct our prayer to You at sunrise and look up for the day ahead.

## Scene 2 — The Way to Walk (Verse 8)
Cause me to know the way wherein I should walk; for I lift up my soul unto thee.
Lead us into this day with quiet confidence in Your faithfulness.
"""


def write_job(tmp: Path, job_id="9101", channel="prayer2", status="approved",
              words=900, name=None):
    filler = " ".join(["mercy"] * max(0, words - len(BODY.split())))
    path = tmp / (name or f"{job_id}-test.md")
    title = ("Psalm 143:8 Morning Prayer | The Morning Altar" if channel == "prayer2"
             else "Psalm 143:8 Night Prayer | The Secret Place")
    path.write_text(FRONT.format(job_id=job_id, title=title, channel=channel,
                                 status=status) + BODY + "\n" + filler,
                    encoding="utf-8")
    return path


class TestMorningPromptAndRoadmap(unittest.TestCase):
    def test_morning_prompt_is_sunrise_not_secret_place_night(self):
        prompt = compile_full_brain_prompt("prayer2")
        self.assertIn("The Morning Altar", prompt)
        self.assertIn("The Morning Altar to begin every sunrise", prompt)
        self.assertNotIn("subscribe to The Secret Place to pray with us every night", prompt)

    def test_secret_place_prompt_is_unchanged(self):
        prompt = compile_full_brain_prompt()
        self.assertIn("The Secret Place", prompt)
        self.assertIn("pray with us every night", prompt)

    def test_morning_roadmap_is_morning_only_and_unique(self):
        ids = [c["id"] for c in MORNING_ALTAR_ROADMAP]
        self.assertEqual(len(ids), len(set(ids)))
        text = " ".join(f"{c['scripture']} {c['theme']} {c['primary_intent']}"
                        for c in MORNING_ALTAR_ROADMAP).lower()
        for night_word in ("sleep", "bedtime", "insomnia", "before you sleep"):
            self.assertNotIn(night_word, text)
        self.assertIs(roadmap_for_channel("prayer2"), MORNING_ALTAR_ROADMAP)

    def test_prayer2_brain_selects_from_morning_roadmap(self):
        brain = GeminiBrain(api_key="", channel_id="prayer2")
        cand = brain.select_next_scripture()
        self.assertIn(cand, MORNING_ALTAR_ROADMAP)
        self.assertEqual(brain.channel_id, "prayer2")
        self.assertIn("PRAYER2_GEMINI_API_KEY", brain.api_status()["key_names"])

    def test_prayer2_offline_authoring_refuses_secret_place_template(self):
        brain = GeminiBrain(api_key="", channel_id="prayer2")
        with self.assertRaises(BrainAuthoringError):
            brain.author_longform_script(
                {"id": "0037", "scripture": "Psalm 143:8",
                 "theme": "Morning Mercy", "hook": "MERCY"})

    def test_prayer2_never_stages_a_companion_short(self):
        brain = GeminiBrain(api_key="", channel_id="prayer2")
        with tempfile.TemporaryDirectory() as tmp:
            path = write_job(Path(tmp))
            from pipeline.script_doc import parse_script
            with self.assertRaises(BrainAuthoringError):
                brain.generate_companion_short(parse_script(path))

    def test_model_output_with_wrong_channel_branding_is_rejected(self):
        brain = GeminiBrain(api_key="", channel_id="prayer2")
        bad = ('---\nid: "0037"\ntitle: "Psalm 143 | The Secret Place"\n---\n'
               "Type Amen, and subscribe to The Secret Place to pray with us every night.")
        with self.assertRaises(BrainAuthoringError):
            brain._enforce_channel_metadata(bad, {})


class TestPerChannelSupplyCounting(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_secret_place_publishable_does_not_count_for_prayer2(self):
        write_job(self.dir, job_id="9201", channel="secret-place", name="9201-sp.md")
        self.assertEqual(sp.publishable_longform(self.dir, channel_id="prayer2"), [])
        self.assertEqual(len(sp.publishable_longform(self.dir, channel_id="secret-place")), 1)

    def test_under_gate_never_crosses_channels(self):
        write_job(self.dir, job_id="9202", channel="secret-place", words=100,
                  name="9202-sp.md")
        write_job(self.dir, job_id="9203", channel="prayer2", words=100,
                  name="9203-ma.md")
        from tools.expand_scripts import under_gate
        paths = sorted(self.dir.glob("*.md"))
        self.assertEqual([j.job_id for j in under_gate(paths, channel_id="prayer2")],
                         ["9203"])
        self.assertEqual([j.job_id for j in under_gate(paths, channel_id="secret-place")],
                         ["9202"])

    def test_queue_health_reports_each_channel_separately(self):
        from scripts.automation_health import queue_health
        rows = queue_health()
        by_queue = {r["queue"]: r for r in rows}
        self.assertIn("longform:prayer2", by_queue)
        self.assertIn("longform:secret-place", by_queue)
        self.assertGreater(by_queue["longform:secret-place"]["ready"], 0)

    def test_watchdog_alarms_when_morning_altar_is_empty(self):
        from scripts import pipeline_watchdog as wd
        rows = [{"queue": "longform", "ready": 2, "note": "ok"},
                {"queue": "longform:prayer2", "ready": 0, "note": "approved and above the word floor"},
                {"queue": "shorts", "ready": 1, "note": "ok"}]
        with mock.patch("scripts.automation_health.queue_health", return_value=rows):
            report = wd.build_report(published_dir=self.dir, workflow_rows=[])
        self.assertTrue(any(f.area == "morning altar queue" for f in report.findings))


class PrayerFakeBrain:
    channel_id = "prayer2"

    def __init__(self, queue_dir, channel="prayer2"):
        self.queue_dir = queue_dir
        self.declared = channel
        self.calls = 0

    def replenish_pipeline(self, min_runway_days=2.0):
        self.calls += 1
        path = self.queue_dir / "9301-authored.md"
        body = BODY + "\n" + " ".join(["sunrise"] * 880)
        path.write_text(FRONT.format(job_id="9301",
                                     title="Psalm 143:8 Morning Prayer | The Morning Altar",
                                     channel=self.declared, status="draft") + body,
                        encoding="utf-8")
        result = mock.Mock()
        result.job_id = "9301"
        result.longform_path = path
        result.word_count = 900
        result.short_manifest_path = None
        return result


class TestChannelApprovalGate(unittest.TestCase):
    def test_prayer2_brain_approves_only_prayer2_scripts(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            brain = PrayerFakeBrain(d)
            with mock.patch("pipeline.supply.expand_backlog", return_value=[]):
                report = sp.ensure_supply(brain, queue_dir=d, channel_id="prayer2")
            self.assertTrue(report.ok, report.as_dict())
            self.assertEqual(report.channel, "prayer2")

    def test_wrong_channel_authoring_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            brain = PrayerFakeBrain(d, channel="secret-place")
            with mock.patch("pipeline.supply.expand_backlog", return_value=[]):
                report = sp.ensure_supply(brain, queue_dir=d, channel_id="prayer2")
            self.assertFalse(report.ok)
            self.assertIn("declares channel", report.blocked[-1])


class TestWorkflowWiring(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[1]

    def test_brain_workflow_runs_both_channels_with_prayer2_key(self):
        text = (self.ROOT / ".github/workflows/gemini_brain.yml").read_text()
        self.assertIn('channels=\'["secret-place","prayer2"]\'', text)
        self.assertIn("PRAYER2_GEMINI_API_KEY", text)
        self.assertIn("--ensure-supply-for prayer2", text)
        self.assertIn("matrix.channel != 'prayer2'", text)  # no Shorts for prayer2

    def test_produce_repair_covers_prayer2_but_shorts_stay_secret_place(self):
        text = (self.ROOT / ".github/workflows/produce.yml").read_text()
        self.assertIn('if [ "$CHANNEL_ID" = "prayer2" ]; then', text)
        self.assertIn("--ensure-supply-for prayer2", text)


if __name__ == "__main__":
    unittest.main()
