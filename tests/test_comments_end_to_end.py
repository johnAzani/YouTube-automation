"""End-to-end proof that a comment gets answered, and that silence is reported.

The reply stage had the failure mode this channel is most exposed to: it printed
"no unresponded candidate comments" and exited 0 while the API call it had just
made was invalid. Nothing failed, so nothing was fixed, three times a day.

These tests drive the real CLI with a fake YouTube service — fetch, classify,
draft, insert, persist the ledger — and pin that a broken run cannot exit 0.
"""
import io
import os
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

import yaml

from pipeline import comment_replies as cr
from pipeline.config import CONFIG

ROOT = Path(__file__).resolve().parents[1]


class FakeYouTube:
    """Just enough of the Data API v3 surface for the reply path."""

    def __init__(self, comments, channel_id="UC_OWN"):
        self.channel_id = channel_id
        self.threads = comments
        self.inserted = []
        self.list_calls = []
        self._fail = None

    def fail_with(self, exc):
        self._fail = exc

    # -- API surface ---------------------------------------------------------
    def channels(self):
        outer = self

        class _Channels:
            def list(self, **kwargs):
                return mock.Mock(execute=mock.Mock(return_value={
                    "items": [{"id": outer.channel_id}]}))

        return _Channels()

    def commentThreads(self):
        outer = self

        class _Threads:
            def list(self, **kwargs):
                outer.list_calls.append(kwargs)
                if outer._fail:
                    return mock.Mock(execute=mock.Mock(side_effect=outer._fail))
                return mock.Mock(execute=mock.Mock(return_value={"items": outer.threads}))

        return _Threads()

    def comments(self):
        outer = self

        class _Comments:
            def insert(self, part=None, body=None):
                outer.inserted.append(body)
                return mock.Mock(execute=mock.Mock(return_value={"id": f"reply_{len(outer.inserted)}"}))

        return _Comments()


def thread(cid, text, author="Mary Bello", channel="UC_VIEWER", replies=None):
    """One commentThread resource. `replies` is top-level, not inside snippet."""
    item = {
        "id": cid,
        "snippet": {
            "videoId": "SG69BbNlfRw",
            "totalReplyCount": len(replies or []),
            "topLevelComment": {"snippet": {
                "authorDisplayName": author,
                "authorChannelId": {"value": channel},
                "textOriginal": text,
                "publishedAt": "2026-11-01T20:00:00Z",
            }},
        },
    }
    if replies:
        item["replies"] = {"comments": replies}
    return item


class CLITestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.log = Path(self.tmp.name) / "replied.json"

        self.creds = mock.patch.multiple(
            CONFIG, youtube_client_id="id", youtube_client_secret="secret",
            youtube_refresh_token="refresh", gemini_api_key="")
        self.creds.start()
        self.addCleanup(self.creds.stop)

        log_patch = mock.patch.object(cr, "DEFAULT_REPLIED_LOG", self.log)
        log_patch.start()
        self.addCleanup(log_patch.stop)

        env_patch = mock.patch.dict(os.environ, {"GH_TOKEN": "", "GITHUB_TOKEN": ""}, clear=False)
        env_patch.start()
        self.addCleanup(env_patch.stop)

    def run_cli(self, argv, youtube):
        import scripts.reply_comments as cli

        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "argv", ["reply_comments.py", *argv]), \
             mock.patch.object(sys.modules["scripts.reply_comments"], "_credentials",
                              return_value=mock.Mock()), \
             mock.patch("googleapiclient.discovery.build", return_value=youtube), \
             mock.patch("time.sleep", return_value=None), \
             redirect_stdout(out), redirect_stderr(err):
            code = cli.main()
        return code, out.getvalue(), err.getvalue()


class TestACommentGetsAnswered(CLITestCase):
    def test_live_run_replies_and_records_it(self):
        youtube = FakeYouTube([thread("c1", "Amen! I receive this peace tonight")])
        code, out, err = self.run_cli(["--apply"], youtube)

        self.assertEqual(code, 0, err)
        self.assertEqual(len(youtube.inserted), 1)
        body = youtube.inserted[0]["snippet"]
        self.assertEqual(body["parentId"], "c1")
        self.assertTrue(body["textOriginal"].strip())
        self.assertIn("parentId", body)

        import json
        ledger = json.loads(self.log.read_text(encoding="utf-8"))
        self.assertEqual(ledger["c1"]["reply_id"], "reply_1")
        self.assertIn("posted", out)

    def test_the_second_run_does_not_reply_twice(self):
        youtube = FakeYouTube([thread("c1", "Amen! Thank you Lord")])
        self.run_cli(["--apply"], youtube)
        code, out, _ = self.run_cli(["--apply"], youtube)
        self.assertEqual(code, 0)
        self.assertEqual(len(youtube.inserted), 1, "a replied comment must not be answered twice")

    def test_the_channel_wide_call_uses_the_real_parameter_name(self):
        youtube = FakeYouTube([])
        self.run_cli(["--apply"], youtube)
        self.assertTrue(youtube.list_calls)
        self.assertEqual(youtube.list_calls[0].get("allThreadsRelatedToChannelId"), "UC_OWN")
        self.assertNotIn("allForChannelId", youtube.list_calls[0])

    def test_a_comment_the_channel_already_answered_is_skipped(self):
        answered = thread("c2", "Please pray for me",
                          replies=[{"snippet": {"authorChannelId": {"value": "UC_OWN"}}}])
        youtube = FakeYouTube([answered])
        self.run_cli(["--apply"], youtube)
        self.assertEqual(youtube.inserted, [], "the channel already replied in that thread")

    def test_scam_comments_are_never_answered(self):
        youtube = FakeYouTube([thread("c3", "Contact Prophet John on WhatsApp +1234567890")])
        code, out, _ = self.run_cli(["--apply"], youtube)
        self.assertEqual(code, 0)
        self.assertEqual(youtube.inserted, [])

    def test_a_crisis_comment_is_held_and_escalated(self):
        youtube = FakeYouTube([thread("c4", "I want to end my life tonight", author="Ann")])
        with mock.patch("subprocess.run") as gh:
            code, out, _ = self.run_cli(["--apply"], youtube)
        self.assertEqual(code, 0)
        self.assertEqual(youtube.inserted, [], "a self-harm disclosure is not answered in public")
        self.assertIn("held", out)

    def test_a_crisis_comment_can_be_answered_when_explicitly_allowed(self):
        youtube = FakeYouTube([thread("c4", "I want to end my life tonight", author="Ann")])
        code, _, _ = self.run_cli(["--apply", "--reply-to-crisis"], youtube)
        self.assertEqual(code, 0)
        self.assertEqual(len(youtube.inserted), 1)
        self.assertIn("988", youtube.inserted[0]["snippet"]["textOriginal"])


class TestFailuresAreLoud(CLITestCase):
    def test_a_broken_fetch_exits_non_zero(self):
        youtube = FakeYouTube([])
        youtube.fail_with(TypeError("Got an unexpected keyword argument allForChannelId"))
        code, out, err = self.run_cli(["--apply"], youtube)
        self.assertEqual(code, 1)
        self.assertIn("FAILED", err)
        self.assertNotIn("No unresponded candidate comments found", out)

    def test_an_empty_inbox_still_exits_zero(self):
        youtube = FakeYouTube([])
        code, out, _ = self.run_cli(["--apply"], youtube)
        self.assertEqual(code, 0)
        self.assertIn("No unresponded candidate comments found", out)

    def test_every_insert_failing_is_an_error(self):
        youtube = FakeYouTube([thread("c1", "Amen, praise God")])

        class Boom:
            def insert(self, part=None, body=None):
                return mock.Mock(execute=mock.Mock(side_effect=RuntimeError("backend error")))

        youtube.comments = lambda: Boom()
        code, _, _ = self.run_cli(["--apply"], youtube)
        self.assertEqual(code, 1)

    def test_quota_exhaustion_is_not_an_error(self):
        youtube = FakeYouTube([])
        youtube.fail_with(RuntimeError("HttpError 403 quotaExceeded"))
        code, out, _ = self.run_cli(["--apply"], youtube)
        self.assertEqual(code, 0, "the free tier resetting is not a failure")
        self.assertIn("quota", out.lower())

    def test_comments_disabled_is_not_a_failure(self):
        youtube = FakeYouTube([])
        youtube.fail_with(RuntimeError("HttpError 403 commentsDisabled"))
        code, _, _ = self.run_cli(["--apply"], youtube)
        self.assertEqual(code, 0)


class TestTheWorkflowActuallyPosts(unittest.TestCase):
    """Three scheduled pulses a day, and they must pass --apply."""

    def workflow(self):
        path = ROOT / ".github" / "workflows" / "comments.yml"
        return path.read_text(encoding="utf-8"), yaml.safe_load(path.read_text(encoding="utf-8"))

    def test_it_runs_three_times_a_day(self):
        _, data = self.workflow()
        crons = data[True]["schedule"]
        self.assertEqual(len(crons), 3)

    def test_a_scheduled_run_posts_rather_than_dreams(self):
        text, _ = self.workflow()
        # dry_run defaults false, and the script only posts when told to.
        self.assertIn("default: false", text)
        self.assertIn("--apply", text)

    def test_the_failure_is_carried_out_of_the_step(self):
        text, _ = self.workflow()
        self.assertIn("set -o pipefail", text)
        self.assertNotIn("|| true", text)

    def test_the_ledger_is_committed_so_replies_are_never_repeated(self):
        text, data = self.workflow()
        self.assertIn("content/comments/replied.json", text)
        job = data["jobs"]["reply"]
        self.assertTrue(any("git commit" in (s.get("run") or "") for s in job["steps"]))

    def test_escalation_has_a_token(self):
        text, _ = self.workflow()
        self.assertIn("GH_TOKEN", text)

    def test_the_ledger_file_exists_in_the_repo(self):
        self.assertTrue((ROOT / "content" / "comments" / "replied.json").is_file())


class TestCrisisHermeticGuards(CLITestCase):
    def test_reply_to_crisis_does_not_also_escalate_issue(self):
        youtube = FakeYouTube([thread("c4", "I want to end my life tonight", author="Ann")])
        with mock.patch("scripts.reply_comments._escalate_crisis") as esc:
            code, _, _ = self.run_cli(["--apply", "--reply-to-crisis"], youtube)
        self.assertEqual(code, 0)
        esc.assert_not_called()

    def test_simulate_and_dry_run_never_escalate_crisis_issues(self):
        youtube = FakeYouTube([thread("c4", "I want to end my life tonight", author="Ann")])
        with mock.patch("scripts.reply_comments._escalate_crisis") as esc:
            self.run_cli(["--simulate"], youtube)
            self.run_cli(["--dry-run"], youtube)
        esc.assert_not_called()

    def test_handle_author_salutation_never_leaks_at_sign(self):
        reply = cr.generate_fallback_reply("@grace-i8g", "Amen! Thank you Lord", "AMEN_AFFIRMATION")
        self.assertNotIn("@", reply)
        self.assertIn("Grace", reply)
        self.assertTrue(cr._reply_is_safe(reply))


if __name__ == "__main__":
    unittest.main()
