"""The owner hears a week before a channel runs short of planned passages.

The unit tests fail when any channel has fewer than 15 roadmap passages left
(`tests/test_multi_channel_resilience.py`). On 15 November 2026 The Provision
Table reached 14 with no warning at all (PR #444). `scripts/roadmap_headroom.py`
counts by the same rule, and from 22 left it keeps one issue open that says
which channel, how many, and roughly when the tests will fail.
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import ExitStack, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import yaml

from scripts import roadmap_headroom as rh

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 11, 16, 20, 14, tzinfo=timezone.utc)


def row(channel: str, left: int, planned: int = 45, name: str | None = None) -> rh.Row:
    return rh.Row(channel, name or f"Channel {channel}", planned, left)


class TheCountIsTheTestsCount(unittest.TestCase):
    def test_every_live_channel_is_counted_by_the_tests_rule(self):
        from pipeline.channels import scheduled_channels
        from scripts.continuous_research import roadmap_for_channel

        used = ({p.name[:4] for p in (ROOT / "content" / "queue").glob("[0-9]*.md")}
                | {p.name[:4] for p in (ROOT / "content" / "published").glob("[0-9]*.md")})
        rows = {r.channel: r for r in rh.headroom()}
        self.assertEqual(set(rows), set(scheduled_channels()))
        for cid in scheduled_channels():
            roadmap = roadmap_for_channel(cid)
            self.assertEqual(rows[cid].planned, len(roadmap), cid)
            self.assertEqual(rows[cid].left,
                             len([e for e in roadmap if e["id"] not in used]), cid)

    def test_the_test_and_the_warning_share_one_floor(self):
        text = (ROOT / "tests" / "test_multi_channel_resilience.py").read_text(encoding="utf-8")
        self.assertIn("from scripts.roadmap_headroom import FLOOR", text)
        self.assertEqual(rh.FLOOR, 15)

    def test_a_job_in_the_queue_or_published_is_used_up(self):
        with tempfile.TemporaryDirectory() as tmp:
            queue, published = Path(tmp, "queue"), Path(tmp, "published")
            queue.mkdir(), published.mkdir()
            (queue / "0901-a.md").write_text("x", encoding="utf-8")
            (published / "0902-b.md").write_text("x", encoding="utf-8")
            (published / "short-0903.md").write_text("x", encoding="utf-8")   # not a job id
            roadmap = [{"id": f"09{n:02d}"} for n in range(1, 6)]
            rows = rh.headroom(queue, published, channels=("prayer4",),
                               roadmap_for=lambda cid: roadmap)
        self.assertEqual((rows[0].planned, rows[0].left), (5, 3))
        self.assertEqual(rows[0].name, "The Midnight Watch")


class TheWarningComesAWeekEarly(unittest.TestCase):
    def test_it_starts_a_week_of_use_above_the_floor(self):
        self.assertFalse(row("a", 23).low)
        self.assertTrue(row("a", 22).low)
        self.assertTrue(row("a", 15).low)
        self.assertFalse(row("a", 15).below_floor)
        self.assertTrue(row("a", 14).below_floor)

    def test_it_says_how_many_days_are_left(self):
        # 22 left, one a day: 15 left after seven days (still passing), 14 on the eighth.
        self.assertEqual(row("a", 22).days_until_tests_fail, 8)
        self.assertEqual(row("a", 15).days_until_tests_fail, 1)
        self.assertEqual(row("a", 14).days_until_tests_fail, 0)
        self.assertEqual(row("a", 3).days_until_tests_fail, 0)

    def test_the_sentence_names_the_channel_the_count_and_the_date(self):
        text = rh.describe(row("prayer4", 22, name="The Midnight Watch"), NOW)
        self.assertIn("The Midnight Watch (prayer4): 22 left", text)
        self.assertIn("about 8 days", text)
        self.assertIn("24 November", text)

    def test_under_the_floor_it_says_the_tests_are_failing_now(self):
        text = rh.describe(row("prayer7", 14, name="The Provision Table"), NOW)
        self.assertIn("14 left, under the floor of 15", text)
        self.assertIn("failing on main now", text)


class TheIssueReadsPlainly(unittest.TestCase):
    def setUp(self):
        self.rows = [row("prayer4", 21, name="The Midnight Watch"),
                     row("prayer7", 14, name="The Provision Table"),
                     row("prayer2", 30, 56, name="The Morning Altar")]
        self.body = rh.issue_body(self.rows, NOW)

    def test_it_lists_only_the_short_channels_as_running_low(self):
        section = self.body.split("### Running low")[1].split("###")[0]
        self.assertIn("The Midnight Watch", section)
        self.assertIn("The Provision Table", section)
        self.assertNotIn("The Morning Altar", section)
        # Shortest first.
        self.assertLess(section.index("Provision Table"), section.index("Midnight Watch"))

    def test_it_says_nothing_has_stopped(self):
        self.assertIn("Nothing has stopped", self.body)

    def test_it_says_what_to_do_and_where(self):
        self.assertIn("### What to do", self.body)
        self.assertIn("scripts/continuous_research.py", self.body)

    def test_every_channel_is_in_the_table(self):
        for line in ("| The Midnight Watch (prayer4) | 45 | 21 |",
                     "| The Provision Table (prayer7) | 45 | 14 |",
                     "| The Morning Altar (prayer2) | 56 | 30 |"):
            self.assertIn(line, self.body)

    def test_the_time_is_given_in_nigeria_time_too(self):
        self.assertIn("2026-11-16 20:14 UTC (Monday 16 November, 9:14PM Nigeria time)", self.body)

    def test_it_carries_the_counts_it_was_written_with(self):
        self.assertEqual(rh._low_channels(self.body), {"prayer4": 21, "prayer7": 14})


class FakeGitHub:
    """Stands in for `gh`: one optional open issue, and a record of every call."""

    def __init__(self, issues: list[dict] | None = None, fail: str | None = None):
        self.issues = issues or []
        self.fail = fail
        self.calls: list[list[str]] = []

    def __call__(self, args: list[str]) -> SimpleNamespace:
        self.calls.append(args)
        verb = " ".join(args[:2])
        if self.fail == verb:
            return SimpleNamespace(returncode=1, stdout="", stderr="HTTP 502")
        if verb == "issue list":
            return SimpleNamespace(returncode=0, stdout=json.dumps(self.issues), stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    def verbs(self) -> list[str]:
        return [" ".join(c[:2]) for c in self.calls]

    def arg_after(self, verb: str, flag: str) -> str:
        call = [c for c in self.calls if " ".join(c[:2]) == verb][0]
        return call[call.index(flag) + 1]


class TheIssueIsOpenedUpdatedAndClosed(unittest.TestCase):
    def sync(self, rows, gh: FakeGitHub) -> str:
        with mock.patch.object(rh, "_gh", gh), \
             mock.patch.object(rh, "gh_available", return_value=True):
            return rh.sync_issue(rows, NOW)

    def existing(self, rows) -> dict:
        return {"number": 77, "title": rh.ISSUE_TITLE, "body": rh.issue_body(rows, NOW)}

    def test_nothing_is_written_while_every_list_is_long(self):
        gh = FakeGitHub()
        self.assertEqual(self.sync([row("a", 30), row("b", 23)], gh), "nothing to report")
        self.assertEqual(gh.verbs(), ["issue list"])

    def test_the_first_short_list_opens_one_issue(self):
        gh = FakeGitHub()
        self.assertEqual(self.sync([row("prayer4", 22), row("b", 30)], gh), "opened")
        self.assertEqual(gh.verbs(), ["issue list", "issue create"])
        self.assertEqual(gh.arg_after("issue create", "--title"), rh.ISSUE_TITLE)
        self.assertIn("prayer4", gh.arg_after("issue create", "--body"))

    def test_an_unchanged_count_writes_nothing(self):
        rows = [row("prayer4", 22), row("b", 30)]
        gh = FakeGitHub([self.existing(rows)])
        self.assertEqual(self.sync(rows, gh), "unchanged")
        self.assertEqual(gh.verbs(), ["issue list"])

    def test_a_lower_count_rewrites_the_issue_without_an_email(self):
        gh = FakeGitHub([self.existing([row("prayer4", 22)])])
        self.assertEqual(self.sync([row("prayer4", 21)], gh), "updated")
        self.assertEqual(gh.verbs(), ["issue list", "issue edit"])
        self.assertEqual(gh.calls[1][2], "77")

    def test_a_second_channel_joining_gets_a_comment(self):
        gh = FakeGitHub([self.existing([row("prayer4", 21), row("prayer2", 23)])])
        result = self.sync([row("prayer4", 20), row("prayer2", 22)], gh)
        self.assertEqual(result, "updated and commented")
        self.assertEqual(gh.verbs(), ["issue list", "issue edit", "issue comment"])
        comment = gh.arg_after("issue comment", "--body")
        self.assertIn("prayer2", comment)
        self.assertNotIn("prayer4", comment)

    def test_crossing_the_floor_gets_a_comment(self):
        gh = FakeGitHub([self.existing([row("prayer4", 15)])])
        self.assertEqual(self.sync([row("prayer4", 14)], gh), "updated and commented")
        self.assertIn("failing on main now", gh.arg_after("issue comment", "--body"))

    def test_it_closes_when_every_list_is_long_again(self):
        gh = FakeGitHub([self.existing([row("prayer4", 20)])])
        self.assertEqual(self.sync([row("prayer4", 35)], gh), "closed")
        self.assertEqual(gh.verbs(), ["issue list", "issue close"])
        self.assertEqual(gh.calls[1][2], "77")

    def test_the_open_issue_is_found_without_the_search_index(self):
        # A search lags a new issue; two runs close together would each open one.
        gh = FakeGitHub()
        self.sync([row("prayer4", 30)], gh)
        self.assertNotIn("--search", gh.calls[0])
        self.assertEqual(gh.arg_after("issue list", "--state"), "open")

    def test_another_issue_with_a_similar_title_is_not_touched(self):
        gh = FakeGitHub([{"number": 5, "title": f"Re: {rh.ISSUE_TITLE} (question)", "body": ""}])
        self.assertEqual(self.sync([row("prayer4", 35)], gh), "nothing to report")
        self.assertEqual(gh.verbs(), ["issue list"])

    def test_without_github_nothing_is_attempted(self):
        gh = FakeGitHub()
        with mock.patch.object(rh, "_gh", gh), \
             mock.patch.object(rh, "gh_available", return_value=False):
            self.assertEqual(rh.sync_issue([row("prayer4", 10)], NOW), "skipped")
        self.assertEqual(gh.calls, [])

    def test_a_dry_run_writes_nothing(self):
        gh = FakeGitHub()
        with mock.patch.object(rh, "_gh", gh), \
             mock.patch.object(rh, "gh_available", return_value=True):
            self.assertEqual(rh.sync_issue([row("prayer4", 10)], NOW, dry_run=True), "skipped")
        self.assertEqual(gh.calls, [])


class ItIsNotTheStallAlarm(unittest.TestCase):
    def test_it_has_its_own_title(self):
        from scripts import pipeline_watchdog as wd

        self.assertNotEqual(rh.ISSUE_TITLE, wd.ISSUE_TITLE)
        self.assertNotIn(wd.ISSUE_TITLE, rh.ISSUE_TITLE)
        self.assertNotIn(rh.ISSUE_TITLE, wd.ISSUE_TITLE)

    def test_the_watchdogs_sweep_does_not_close_it(self):
        # `pipeline_watchdog.cleanup_stale_issues` closes issues by these title prefixes.
        for prefix in ("Viewer in distress", "Release ticket: ", "Release failed",
                       "Release died inside"):
            self.assertFalse(rh.ISSUE_TITLE.startswith(prefix), prefix)
        self.assertNotIn("Channel Analytics Snapshot", rh.ISSUE_TITLE)

    def test_a_short_list_does_not_make_the_watchdog_unhealthy(self):
        # A warning in the watchdog's report turns the monitor red for as long as
        # it lasts. This warning must not travel that way.
        text = (ROOT / "scripts" / "pipeline_watchdog.py").read_text(encoding="utf-8")
        self.assertNotIn("roadmap_headroom", text)


class TheCommandReportsAndDoesNotCryWolf(unittest.TestCase):
    def run_main(self, rows, argv, **patches):
        out = io.StringIO()
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(rh, "headroom", return_value=rows))
            if patches:
                stack.enter_context(mock.patch.multiple(rh, **patches))
            stack.enter_context(redirect_stdout(out))
            code = rh.main(argv)
        return code, out.getvalue()

    def test_long_lists_print_a_table_and_no_annotation(self):
        code, out = self.run_main([row("prayer4", 30)], [])
        self.assertEqual(code, 0)
        self.assertIn("prayer4", out)
        self.assertNotIn("::", out)

    def test_a_short_list_is_a_warning_not_a_failure(self):
        code, out = self.run_main([row("prayer4", 20)], [])
        self.assertEqual(code, 0)
        self.assertIn("::warning title=Planned passages running low (prayer4)::", out)

    def test_under_the_floor_is_an_error_annotation(self):
        code, out = self.run_main([row("prayer4", 12)], [])
        self.assertEqual(code, 0, "the unit tests are what fail; this only reports")
        self.assertIn("::error title=Planned passages running low (prayer4)::", out)

    def test_an_annotation_title_has_no_comma(self):
        # A comma ends an annotation's title on GitHub.
        _code, out = self.run_main([row("prayer4", 20)], [])
        title = out.split("::warning title=")[1].split("::")[0]
        self.assertNotIn(",", title)

    def test_an_issue_that_cannot_be_written_is_said_and_does_not_fail(self):
        gh = FakeGitHub(fail="issue list")
        code, out = self.run_main([row("prayer4", 20)], ["--sync-issue"],
                                  _gh=gh, gh_available=lambda: True)
        self.assertEqual(code, 0)
        self.assertIn("::warning title=The planned-passages issue could not be written::", out)
        self.assertIn("prayer4", out)

    def test_no_channel_at_all_is_a_failure(self):
        code, out = self.run_main([], [])
        self.assertEqual(code, 1)
        self.assertIn("::error title=Planned passages could not be counted::", out)

    def test_a_count_that_cannot_be_made_is_not_swallowed(self):
        with mock.patch.object(rh, "headroom", side_effect=RuntimeError("roadmap unreadable")):
            with self.assertRaises(RuntimeError):
                rh.main([])


class TheHealthCheckRunsIt(unittest.TestCase):
    def step(self) -> dict:
        doc = yaml.safe_load((ROOT / ".github" / "workflows" / "automation-health.yml")
                             .read_text(encoding="utf-8"))
        steps = [s for s in doc["jobs"]["health"]["steps"]
                 if "scripts.roadmap_headroom" in str(s.get("run", ""))]
        self.assertEqual(len(steps), 1)
        return steps[0]

    def test_it_writes_the_issue(self):
        self.assertIn("--sync-issue", self.step()["run"])
        self.assertIn("GH_TOKEN", self.step()["env"])

    def test_it_runs_even_when_the_stall_check_before_it_is_red(self):
        self.assertIn("always()", str(self.step()["if"]))

    def test_a_merge_does_not_file_it(self):
        self.assertIn("github.event_name != 'push'", str(self.step()["if"]))

    def test_a_crash_is_not_hidden(self):
        step = self.step()
        self.assertNotIn("|| true", step["run"])
        self.assertIsNone(step.get("continue-on-error"))

    def test_the_job_may_write_issues_and_nothing_else(self):
        doc = yaml.safe_load((ROOT / ".github" / "workflows" / "automation-health.yml")
                             .read_text(encoding="utf-8"))
        self.assertEqual(doc["permissions"]["issues"], "write")
        self.assertEqual(doc["permissions"]["contents"], "read")


if __name__ == "__main__":
    unittest.main()
