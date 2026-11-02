"""Guards for the supply loop — the thing that keeps the queue publishable.

The failure these tests exist for is not a crash. It is a queue that looks
satisfied: twenty-one approved scripts, none over the word floor, every stage
exiting 0 while the channel publishes nothing. So each test pins one of:

* supply is only "ok" when something is genuinely publishable,
* a provider that cannot write never touches a file,
* authoring cannot approve a script that is under the floor or quotes the wrong
  psalm,
* and the watchdog says so out loud instead of waiting to be asked.
"""
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from pipeline import supply as sp

FRONT = """---
id: "9001"
title: "Psalm 121: He Who Keeps You | The Secret Place"
status: {status}
format: longform
voice: Charon
---

"""

BODY = """## Scene 1 — The Watchman (Verse 1)
The Lord is thy keeper: the Lord is thy shade upon thy right hand.
Rest quietly now, because the One watching over you does not grow tired.

## Scene 2 — Coming and Going (Verse 2)
He shall preserve thy going out and thy coming in for evermore.
Sleep deeply, and let tomorrow arrive without your worry.
"""

OPENINGS = [
    "Breathe in slowly through your nose and let the room grow quiet around you",
    "Unclench your hands where they rest and let your jaw soften into the pillow",
    "Let the weight of the day slide off your shoulders and onto the floor",
    "Notice the stillness that has been waiting for you all evening long",
    "Let every muscle in your back remember that it is allowed to rest",
    "Feel the cool of the sheets and let that small comfort be enough",
]
CLOSINGS = [
    "and let the night carry what you cannot.",
    "and let tomorrow wait outside the door.",
    "and let the watchman keep the hours for you.",
    "and let your last thought be a peaceful one.",
    "and let sleep arrive without being called.",
]


def write_job(tmp: Path, status: str = "approved", body: str = BODY,
              name: str = "9001-test.md") -> Path:
    path = tmp / name
    path.write_text(FRONT.format(status=status) + body, encoding="utf-8")
    return path


def good_provider(job, target=900):
    """Additive, unique, long enough — what a good model should return."""
    parts = []
    openers = [
        "Notice how gently the promise is worded; it asks nothing of you but trust tonight.",
        "The watchman does not doze between your breaths, and He is not impatient with them.",
        "Nothing in this room is outside His notice, and nothing here surprises Him.",
    ]
    for index, (heading, paragraphs) in enumerate(job.sections()):
        parts.append(f"## {heading}")
        parts.extend(paragraphs)
        parts.append(openers[index % len(openers)])
    body = "\n\n".join(parts) + "\n"
    filler = [f"{a}, {b}" for a in OPENINGS for b in CLOSINGS]
    for sentence in filler:
        if len(body.split()) >= target:
            break
        body = body.replace("\n\n## ", f"\n\n{sentence}\n\n## ", 1)
    return body


class TestPublishability(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_a_script_under_the_floor_is_not_publishable(self):
        write_job(self.dir)
        self.assertEqual(sp.publishable_longform(self.dir), [])

    def test_a_long_approved_script_is_publishable(self):
        long_body = BODY + ("\n\nQuiet words that carry the prayer onward at a "
                            "sleeping pace, again and again through the night.\n" * 120)
        write_job(self.dir, status="approved", body=long_body)
        self.assertEqual(len(sp.publishable_longform(self.dir)), 1)

    def test_a_long_draft_is_not_publishable(self):
        long_body = BODY + ("\n\nQuiet words that carry the prayer onward at a "
                            "sleeping pace, again and again through the night.\n" * 120)
        write_job(self.dir, status="draft", body=long_body)
        self.assertEqual(sp.publishable_longform(self.dir), [])


class TestExpansion(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_a_good_expansion_makes_the_queue_publishable(self):
        write_job(self.dir)
        with mock.patch.dict("tools.expand_scripts.PROVIDERS", {"gemini": good_provider}):
            report = sp.ensure_supply(None, queue_dir=self.dir)
        self.assertTrue(report.ok)
        self.assertEqual(report.publishable_before, 0)
        self.assertGreaterEqual(report.publishable_after, 1)
        self.assertTrue(report.expanded[0]["written"])

    def test_a_failing_provider_writes_nothing_and_says_so(self):
        path = write_job(self.dir)
        before = path.read_text(encoding="utf-8")
        with mock.patch.dict("tools.expand_scripts.PROVIDERS",
                             {"gemini": mock.Mock(side_effect=RuntimeError("GEMINI_API_KEY is not set"))}):
            report = sp.ensure_supply(None, queue_dir=self.dir)
        self.assertFalse(report.ok)
        self.assertEqual(path.read_text(encoding="utf-8"), before)
        self.assertTrue(any("GEMINI_API_KEY" in b for b in report.blocked))

    def test_the_word_floor_is_never_lowered_to_make_a_run_green(self):
        write_job(self.dir)
        with mock.patch.dict("tools.expand_scripts.PROVIDERS",
                             {"gemini": lambda job, target: job.body}):
            report = sp.ensure_supply(None, queue_dir=self.dir)
        self.assertFalse(report.ok)
        self.assertEqual(sp.publishable_longform(self.dir), [])

    def test_expansion_budget_is_respected(self):
        for i in range(6):
            write_job(self.dir, name=f"900{i}-test.md")
        calls = []

        def counting(job, target=900):
            calls.append(job.job_id)
            return good_provider(job, target)

        with mock.patch.dict("tools.expand_scripts.PROVIDERS", {"gemini": counting}):
            sp.ensure_supply(None, limit=2, queue_dir=self.dir)
        self.assertEqual(len(calls), 2)


class FakeBrain:
    """Stands in for GeminiBrain.replenish_pipeline."""

    def __init__(self, queue_dir: Path, words: int = 900, status: str = "draft",
                 body: str = BODY):
        self.queue_dir = queue_dir
        self.words = words
        self.status = status
        self.body = body
        self.calls = 0

    def replenish_pipeline(self, min_runway_days=2.0):
        self.calls += 1
        path = self.queue_dir / f"00{len(list(self.queue_dir.glob('*.md'))) + 10}-authored.md"
        filler = " ".join(["stillness"] * max(0, self.words - len(self.body.split())))
        path.write_text(FRONT.format(status=self.status) + self.body + "\n" + filler,
                        encoding="utf-8")
        result = mock.Mock()
        result.job_id = path.name[:4]
        result.longform_path = path
        result.word_count = self.words
        result.short_manifest_path = None
        return result


class TestAuthoring(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_authoring_approves_a_script_that_clears_the_floor(self):
        brain = FakeBrain(self.dir, words=900)
        with mock.patch("pipeline.supply.expand_backlog", return_value=[]):
            report = sp.ensure_supply(brain, queue_dir=self.dir)
        self.assertEqual(brain.calls, 1)
        self.assertTrue(report.ok, report.as_dict())
        self.assertTrue(report.authored["approved_by_brain"])
        text = Path(report.authored["longform_path"]).read_text(encoding="utf-8")
        self.assertIn("status: approved", text)
        self.assertIn("approved_by: brain", text)

    def test_authoring_never_approves_an_under_floor_script(self):
        brain = FakeBrain(self.dir, words=200)
        with mock.patch("pipeline.supply.expand_backlog", return_value=[]), \
             mock.patch.dict("tools.expand_scripts.PROVIDERS",
                             {"gemini": mock.Mock(side_effect=RuntimeError("no key"))}):
            report = sp.ensure_supply(brain, queue_dir=self.dir)
        self.assertFalse(report.ok)
        text = Path(report.authored["longform_path"]).read_text(encoding="utf-8")
        self.assertIn("status: draft", text)
        self.assertIn("under the 650-word floor", report.blocked[-1])

    def test_a_script_quoting_the_wrong_psalm_is_never_approved(self):
        wrong = BODY.replace("The Lord is thy keeper", "The Lord is my light and my salvation")
        brain = FakeBrain(self.dir, words=900, body=wrong)
        with mock.patch("pipeline.supply.expand_backlog", return_value=[]):
            report = sp.ensure_supply(brain, queue_dir=self.dir)
        self.assertFalse(report.ok)
        self.assertIn("quotes Psalm 27", report.blocked[-1])
        text = Path(report.authored["longform_path"]).read_text(encoding="utf-8")
        self.assertIn("status: draft", text)

    def test_a_healthy_queue_spends_nothing(self):
        long_body = BODY + ("\n\nQuiet words that carry the prayer onward at a "
                            "sleeping pace, again and again through the night.\n" * 120)
        write_job(self.dir, status="approved", body=long_body)
        brain = FakeBrain(self.dir)
        with mock.patch("pipeline.supply.expand_backlog", return_value=[]):
            report = sp.ensure_supply(brain, queue_dir=self.dir)
        self.assertTrue(report.ok)
        self.assertEqual(brain.calls, 0)


class TestStatusRewrite(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = write_job(Path(self.tmp.name), status="draft")

    def test_only_the_status_line_changes(self):
        before = self.path.read_text(encoding="utf-8").split("---", 2)[2]
        sp.set_status(self.path, "approved", approved_by="brain")
        after = self.path.read_text(encoding="utf-8")
        self.assertIn("status: approved", after)
        self.assertEqual(after.split("---", 2)[2], before)

    def test_an_existing_comment_on_the_status_line_survives(self):
        text = self.path.read_text(encoding="utf-8").replace(
            "status: draft", "status: draft  # awaiting expansion")
        self.path.write_text(text, encoding="utf-8")
        sp.set_status(self.path, "approved")
        self.assertIn("# awaiting expansion", self.path.read_text(encoding="utf-8"))


class TestWatchdog(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def healthy_rows(self):
        return [{"queue": "longform", "ready": 2, "note": "fine"},
                {"queue": "shorts", "ready": 1, "note": "renderable now"}]

    def receipt(self, days_ago: float = 0.5) -> Path:
        stamp = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
        path = self.dir / "0010-published.md"
        path.write_text(f"---\nid: '0010'\nyoutube_video_id: abc123\npublished_at: {stamp}\n---\n\nbody\n",
                        encoding="utf-8")
        return path

    def report(self, rows=None, workflow_rows=()):
        from scripts import pipeline_watchdog as wd

        self.receipt()
        with mock.patch("scripts.automation_health.queue_health",
                        return_value=rows or self.healthy_rows()):
            return wd.build_report(published_dir=self.dir, workflow_rows=list(workflow_rows))

    def test_a_working_pipeline_is_healthy(self):
        report = self.report()
        self.assertTrue(report.healthy, report.as_dict())

    def test_an_empty_longform_queue_is_blocking(self):
        rows = [{"queue": "longform", "ready": 0, "note": "approved and above the word floor"},
                {"queue": "shorts", "ready": 1, "note": "ok"}]
        report = self.report(rows=rows)
        self.assertFalse(report.healthy)
        self.assertTrue(any("650-word floor" in f.detail for f in report.findings))

    def test_an_empty_shorts_queue_is_a_warning_not_a_block(self):
        rows = [{"queue": "longform", "ready": 2, "note": "ok"},
                {"queue": "shorts", "ready": 0, "note": "nothing renderable"}]
        report = self.report(rows=rows)
        self.assertTrue(report.healthy)
        self.assertTrue(any(f.area == "shorts queue" for f in report.findings))

    def test_a_workflow_that_never_ran_is_reported(self):
        from scripts.automation_health import Row

        report = self.report(workflow_rows=[Row("expand-scripts.yml", "daily", None,
                                                "NEVER RAN", "no run recorded")])
        self.assertTrue(any("NEVER RAN" in f.detail for f in report.findings))

    def test_a_stale_publish_is_reported(self):
        from scripts import pipeline_watchdog as wd

        self.receipt(days_ago=9)
        with mock.patch("scripts.automation_health.queue_health",
                        return_value=self.healthy_rows()):
            report = wd.build_report(published_dir=self.dir, workflow_rows=[])
        self.assertTrue(any(f.area == "publishing" for f in report.findings))


class TestIssueSync(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def report(self, healthy: bool):
        from scripts.pipeline_watchdog import Report

        report = Report()
        report.checked.append("longform queue: 1 ready")
        if not healthy:
            report.add("long-form queue", "nothing publishable")
        return report

    def run_sync(self, report, open_issue=None, dry_run=False):
        from scripts import pipeline_watchdog as wd

        calls = []

        def fake_gh(args):
            calls.append(args)
            if args[:2] == ["issue", "list"]:
                out = f'[{{"number": {open_issue}}}]' if open_issue else "[]"
                return mock.Mock(returncode=0, stdout=out, stderr="")
            return mock.Mock(returncode=0, stdout="", stderr="")

        with mock.patch.object(wd, "_gh", side_effect=fake_gh), \
             mock.patch.object(wd, "gh_available", return_value=True), \
             mock.patch.object(wd, "ensure_label"):
            action = wd.sync_issue(report, dry_run=dry_run)
        return action, calls

    def test_unhealthy_opens_exactly_one_issue(self):
        action, calls = self.run_sync(self.report(healthy=False))
        self.assertEqual(action, "opened")
        creates = [c for c in calls if c[:2] == ["issue", "create"]]
        self.assertEqual(len(creates), 1)
        self.assertIn("pipeline-watchdog", creates[0])

    def test_still_unhealthy_updates_the_same_issue(self):
        action, calls = self.run_sync(self.report(healthy=False), open_issue=7)
        self.assertEqual(action, "updated")
        self.assertTrue(any(c[:2] == ["issue", "edit"] and "7" in c for c in calls))
        self.assertFalse(any(c[:2] == ["issue", "create"] for c in calls))

    def test_recovery_closes_the_issue(self):
        action, calls = self.run_sync(self.report(healthy=True), open_issue=7)
        self.assertEqual(action, "closed")
        self.assertTrue(any(c[:2] == ["issue", "close"] for c in calls))

    def test_healthy_and_no_issue_does_nothing(self):
        action, calls = self.run_sync(self.report(healthy=True))
        self.assertEqual(action, "healthy")
        self.assertEqual([c for c in calls if c[:2] in (["issue", "create"], ["issue", "close"])], [])

    def test_dry_run_never_touches_issues(self):
        action, calls = self.run_sync(self.report(healthy=False), dry_run=True)
        self.assertEqual(action, "skipped")
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()


class TestBrainApiReporting(unittest.TestCase):
    """'No key' and 'key present but broken' are different faults.

    The key has been configured since week one and narrates every video. Authoring
    still reported "GEMINI_API_KEY unavailable" whenever the client failed to
    start, which sent the whole project chasing a secret that was never missing.
    """

    def test_no_key_says_the_key_is_missing(self):
        from pipeline.gemini_brain import GeminiBrain

        brain = GeminiBrain(api_key="")
        status = brain.api_status()
        self.assertFalse(status["key_present"])
        self.assertFalse(status["client_ready"])
        self.assertIn("not present", status["reason"])

    def test_a_key_that_cannot_start_is_not_reported_as_missing(self):
        from pipeline.gemini_brain import GeminiBrain

        with mock.patch("google.genai.Client", side_effect=RuntimeError("transport broke")):
            brain = GeminiBrain(api_key="configured-key")
        status = brain.api_status()
        self.assertTrue(status["key_present"])
        self.assertFalse(status["client_ready"])
        self.assertIn("transport broke", status["reason"])
        self.assertNotIn("not present", status["reason"])

    def test_short_authoring_blames_the_real_cause(self):
        from pipeline.gemini_brain import BrainAuthoringError, GeminiBrain
        from pipeline.script_doc import parse_script

        root = Path(__file__).resolve().parents[1]
        doc = parse_script(root / "content" / "published" /
                          "0010-psalm-121-he-who-keeps-you-will-neither-slumber-no.md")
        with mock.patch("google.genai.Client", side_effect=RuntimeError("transport broke")):
            brain = GeminiBrain(api_key="configured-key")
        with self.assertRaises(BrainAuthoringError) as caught:
            brain.author_short_spec(doc)
        self.assertIn("transport broke", str(caught.exception))
        self.assertNotIn("GEMINI_API_KEY unavailable", str(caught.exception))

    def test_preflight_fails_when_the_client_is_not_ready(self):
        from scripts import gemini_brain as cli
        from pipeline.gemini_brain import GeminiBrain

        brain = GeminiBrain(api_key="")
        self.assertEqual(cli.cmd_preflight(brain), 1)

    def test_watchdog_calls_a_broken_brain_fatal_in_ci(self):
        from scripts import pipeline_watchdog as wd

        broken = {"key_present": True, "client_ready": False,
                  "model": "gemini-2.5-flash", "reason": "key present but client failed: boom"}
        with mock.patch("pipeline.gemini_brain.GeminiBrain") as brain_cls:
            brain_cls.return_value.api_status.return_value = broken
            report = wd.Report()
            with mock.patch.dict("os.environ", {"EXPECT_BRAIN_API": "1"}):
                wd.check_brain_api(report)
            self.assertTrue(any(f.area == "brain api" and f.fatal for f in report.findings))

            local = wd.Report()
            with mock.patch.dict("os.environ", {}, clear=True):
                wd.check_brain_api(local)
            self.assertFalse(any(f.fatal for f in local.findings))

    def test_github_actions_alone_does_not_make_it_fatal(self):
        """The unit-test job and the health job run in Actions without the secret."""
        from scripts import pipeline_watchdog as wd

        broken = {"key_present": False, "client_ready": False,
                  "model": "gemini-2.5-flash", "reason": "no key"}
        with mock.patch("pipeline.gemini_brain.GeminiBrain") as brain_cls:
            brain_cls.return_value.api_status.return_value = broken
            report = wd.Report()
            with mock.patch.dict("os.environ", {"GITHUB_ACTIONS": "true"}, clear=True):
                wd.check_brain_api(report)
        self.assertFalse(any(f.fatal for f in report.findings))

    def test_watchdog_is_quiet_when_the_brain_is_connected(self):
        from scripts import pipeline_watchdog as wd

        ok = {"key_present": True, "client_ready": True,
              "model": "gemini-2.5-flash", "reason": "connected"}
        with mock.patch("pipeline.gemini_brain.GeminiBrain") as brain_cls:
            brain_cls.return_value.api_status.return_value = ok
            report = wd.Report()
            wd.check_brain_api(report)
        self.assertEqual(report.findings, [])
        self.assertTrue(any("connected" in c for c in report.checked))
