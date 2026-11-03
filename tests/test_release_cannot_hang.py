"""A release must fail at a named stage, never disappear for 90 minutes.

The failure these tests encode: on 2 November 2026 the long-form step ran from
17:59:57 to 19:30:09 and was killed by its own cap (run `41495990952`). The
measured encode is ~22 minutes, so about an hour was spent somewhere that never
printed a line. Two things can do that — an unbounded HTTP request, and a stage
that retries quietly — so both are now bounded and both now name themselves.
"""

from __future__ import annotations

import os
import re
import time
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]


class EveryGeminiCallGoesThroughTheBoundedClient(unittest.TestCase):
    """A bare `genai.Client(...)` is a client with no deadline."""

    def test_no_module_constructs_an_unbounded_client(self):
        offenders = []
        for directory in ("pipeline", "tools", "scripts"):
            for path in (REPO / directory).rglob("*.py"):
                text = path.read_text(encoding="utf-8", errors="replace")
                for match in re.finditer(r"genai\.Client\(", text):
                    line = text[: match.start()].count("\n") + 1
                    # The constructor inside gemini_client.py is the allowed one.
                    if path.name == "gemini_client.py":
                        continue
                    offenders.append(f"{path.relative_to(REPO)}:{line}")
        self.assertEqual(offenders, [],
                         "these build a Gemini client with no timeout: " + ", ".join(offenders))

    def test_every_call_site_uses_make_client(self):
        users = ["pipeline/gemini_tts.py", "pipeline/gemini_brain.py",
                 "pipeline/comment_replies.py", "tools/expand_scripts.py"]
        for name in users:
            text = (REPO / name).read_text(encoding="utf-8")
            self.assertIn("make_client(", text, f"{name} does not bound its Gemini client")


class TheClientCarriesATimeout(unittest.TestCase):
    def test_make_client_passes_http_options_with_a_timeout(self):
        from pipeline import gemini_client

        captured = {}

        class FakeClient:
            def __init__(self, **kwargs):
                captured.update(kwargs)

        with mock.patch("google.genai.Client", FakeClient):
            gemini_client.make_client("key-123")
        self.assertEqual(captured["api_key"], "key-123")
        options = captured["http_options"]
        self.assertGreater(options.timeout, 0, "a client without a timeout can hang")
        # milliseconds, not seconds
        self.assertGreaterEqual(options.timeout, 30_000)

    def test_the_timeout_is_configurable_and_sane(self):
        from pipeline import gemini_client

        with mock.patch.dict(os.environ, {"GEMINI_HTTP_TIMEOUT_SECONDS": "45"}):
            self.assertEqual(gemini_client.http_timeout_seconds(), 45)
        for bad in ("", "0", "-3", "soon"):
            with mock.patch.dict(os.environ, {"GEMINI_HTTP_TIMEOUT_SECONDS": bad}):
                self.assertEqual(gemini_client.http_timeout_seconds(),
                                 gemini_client.DEFAULT_HTTP_TIMEOUT_SECONDS, bad)


class AStageDeadlineActuallyBites(unittest.TestCase):
    def test_the_budget_expires_and_says_which_chunk(self):
        from pipeline.gemini_client import Deadline, GeminiRequestTimedOut

        budget = Deadline(0.05, "speech synthesis")
        time.sleep(0.06)
        with self.assertRaises(GeminiRequestTimedOut) as caught:
            budget.check("chunk 7/12")
        message = str(caught.exception)
        self.assertIn("chunk 7/12", message)
        self.assertIn("budget", message)

    def test_a_fresh_budget_does_not_raise(self):
        from pipeline.gemini_client import Deadline

        Deadline(60, "speech synthesis").check("chunk 1/12")


class ChunkedSpeechReportsAndStops(unittest.TestCase):
    """Twelve sequential requests were unbounded as a group even with a per-call cap."""

    def test_a_slow_tts_run_stops_at_the_budget(self):
        from pipeline import gemini_tts

        chunks = ["word " * 100] * 6
        calls = {"n": 0}

        def slow_chunk(client, text, voice_name, system_instruction, model, temp_raw):
            calls["n"] += 1
            time.sleep(0.25)
            temp_raw.write_bytes(b"\x00\x00")
            return "audio/pcm;rate=24000"

        with mock.patch.object(gemini_tts, "_chunk_text", return_value=chunks), \
             mock.patch.object(gemini_tts, "_synthesize_single_chunk", slow_chunk), \
             mock.patch.object(gemini_tts, "_convert_raw_audio", lambda *a, **k: None), \
             mock.patch("pipeline.gemini_client.make_client", lambda key=None: object()), \
             mock.patch.object(gemini_tts, "get_gemini_api_key", lambda: "test-key"), \
             mock.patch.dict(os.environ, {"GEMINI_STAGE_BUDGET_SECONDS": "0.4"}):
            from pipeline.gemini_client import GeminiRequestTimedOut
            with self.assertRaises(GeminiRequestTimedOut):
                gemini_tts.synthesize_gemini_audio("text", Path("/tmp/tts-test.mp3"))
        self.assertLess(calls["n"], len(chunks),
                        "the budget must stop the run rather than pay for every chunk")


class TheStallWatchdogNamesTheStage(unittest.TestCase):
    """When the step is killed at its cap, the log must already say where it was."""

    def test_a_blocked_stage_is_reported_from_outside_it(self):
        from pipeline import progress

        lines: list[str] = []
        with mock.patch.object(progress, "emit", lines.append), \
             mock.patch.object(progress, "STALL_REPORT_SECONDS", 0.05), \
             mock.patch.object(progress, "_watchdog_started", False):
            with progress.stage("encode", "6.0 min"):
                # Simulate the main thread being blocked inside the stage.
                time.sleep(0.18)
        joined = "\n".join(lines)
        self.assertIn("still inside encode", joined,
                      "a stage that blocks for minutes must announce itself")

    def test_the_open_stage_is_cleared_when_it_ends(self):
        from pipeline import progress

        with mock.patch.object(progress, "emit", lambda m: None):
            with progress.stage("upload"):
                self.assertEqual(progress._current["label"], "upload")
        self.assertIsNone(progress._current["label"])


class TheAssetLoopIsBounded(unittest.TestCase):
    def test_the_asset_stage_checks_a_budget_per_scene(self):
        text = (REPO / "pipeline" / "prayer_pipeline.py").read_text(encoding="utf-8")
        self.assertIn("asset_budget.check(", text,
                      "the per-scene asset loop must fail at a named scene, not at the step cap")
        self.assertIn("asset_budget = Deadline(", text)


class AFailureCanBeReadAfterwards(unittest.TestCase):
    """`gh run view --log-failed` returns EOF for these runs; the trail does not."""

    TRAIL = """20:09:10Z ▶ speech synthesis — 912 words, Charon
20:11:40Z ✓ speech synthesis — 912 words, Charon in 150.2s
20:11:41Z ▶ speech alignment — 372s of audio
20:13:55Z ✓ speech alignment — 372s of audio in 134.0s
20:13:56Z ▶ encode — 6.2 min, 8 scenes
20:18:05Z encode: 480/8928 frames (5%), 122s elapsed, ~36 min left
"""

    def test_it_names_the_stage_that_never_closed(self):
        from scripts import release_report

        summary = release_report.summarise(release_report.parse_trail(self.TRAIL))
        title, body = release_report.render(summary, run_id="41516057869")
        self.assertEqual(title, "Release died inside encode (run 41516057869)")
        self.assertIn("Never closed", body)
        self.assertIn("`encode`", body)

    def test_it_adds_up_the_minutes_that_were_accounted_for(self):
        from scripts import release_report

        summary = release_report.summarise(release_report.parse_trail(self.TRAIL))
        self.assertEqual([row["stage"] for row in summary["finished"]],
                         ["speech synthesis", "speech alignment"])
        _, body = release_report.render(summary)
        self.assertIn("4.7 min", body)  # 284.2s

    def test_an_explicit_failure_outranks_an_open_stage(self):
        from scripts import release_report

        trail = ("20:09:10Z ▶ encode — 6.2 min\n"
                 "20:31:00Z ✗ encode — 6.2 min failed after 1309.0s: RuntimeError: encoder died\n")
        title, body = release_report.render(release_report.summarise(
            release_report.parse_trail(trail)))
        self.assertEqual(title, "Release failed in encode")
        self.assertIn("encoder died", body)
        self.assertNotIn("Never closed", body)

    def test_an_empty_trail_says_so_instead_of_pretending(self):
        from scripts import release_report

        title, body = release_report.render(release_report.summarise([]))
        self.assertEqual(title, "Release failed")
        self.assertIn("before the first stage opened", body)

    def test_the_workflow_reports_and_keeps_a_trail(self):
        text = (REPO / ".github" / "workflows" / "produce.yml").read_text(encoding="utf-8")
        self.assertIn("PROGRESS_TRAIL:", text)
        self.assertIn("python -m scripts.release_report", text)
        self.assertIn("cancelled() || failure()", text)

    def test_the_trail_is_written_as_the_release_runs(self):
        from pipeline import progress

        with mock.patch.dict(os.environ, {"PROGRESS_TRAIL": "/tmp/trail-test.log"}):
            path = Path("/tmp/trail-test.log")
            path.unlink(missing_ok=True)
            progress.emit("▶ demo")
            contents = path.read_text(encoding="utf-8")
        self.assertIn("demo", contents)
        self.assertRegex(contents, r"^\d\d:\d\d:\d\dZ")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()


class AStalledHTTPSReadCannotOutlastTheStep(unittest.TestCase):
    """Run 41560585702 sat inside one speech call for 170 minutes.

    Root cause, from the library itself: the `interactions` transport is built on
    `httpx.Timeout(timeout=None, connect=5.0)` — connecting is bounded, *reading
    is not*. `HttpOptions.timeout` never reaches it. So the interpreter's own
    alarm enforces the bound, and a stall becomes a named failure with a retry.
    """

    def test_the_hard_deadline_fires_on_a_blocked_call(self):
        from pipeline.gemini_client import GeminiRequestTimedOut, hard_deadline

        with self.assertRaises(GeminiRequestTimedOut):
            with hard_deadline(0.15, "TTS chunk 3/12"):
                time.sleep(3)

    def test_the_alarm_is_always_cleared(self):
        import signal
        from pipeline.gemini_client import GeminiRequestTimedOut, hard_deadline

        with self.assertRaises(GeminiRequestTimedOut):
            with hard_deadline(0.1, "x"):
                time.sleep(2)
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL)[0], 0.0,
                         "a leftover alarm would kill an unrelated later call")
        signal.alarm(0)

    def test_a_fast_call_is_untouched(self):
        from pipeline.gemini_client import hard_deadline

        with hard_deadline(5, "fast"):
            time.sleep(0.01)

    def test_the_interactions_call_passes_its_own_timeout(self):
        text = (REPO / "pipeline" / "gemini_tts.py").read_text(encoding="utf-8")
        self.assertIn("timeout=http_timeout_seconds()", text,
                      "the interactions transport defaults to an infinite read timeout")

    def test_every_chunk_is_guarded_and_a_stall_is_retried_once(self):
        from pipeline import gemini_tts

        attempts = []
        stalls = 3

        def always_stalls(*a, **k):
            attempts.append(1)
            time.sleep(2)
            return "audio/pcm"

        with mock.patch.object(gemini_tts, "_synthesize_single_chunk", always_stalls), \
             mock.patch.dict(os.environ, {"GEMINI_HTTP_TIMEOUT_SECONDS": "1"}):
            from pipeline.gemini_client import GeminiRequestTimedOut
            with self.assertRaises(GeminiRequestTimedOut) as caught:
                gemini_tts._guarded_chunk(object(), "text", "Charon", "instr", "m",
                                          Path("/tmp/raw"), 7, 12)
        self.assertEqual(len(attempts), 2, "a stalled chunk gets exactly one retry")
        self.assertIn("TTS chunk 7/12", str(caught.exception))

    def test_a_retry_that_works_returns_the_audio(self):
        from pipeline import gemini_tts

        calls = {"n": 0}

        def flaky(*a, **k):
            calls["n"] += 1
            if calls["n"] == 1:
                time.sleep(2)
            return "audio/pcm;rate=24000"

        with mock.patch.object(gemini_tts, "_synthesize_single_chunk", flaky), \
             mock.patch.dict(os.environ, {"GEMINI_HTTP_TIMEOUT_SECONDS": "1"}):
            self.assertEqual(gemini_tts._guarded_chunk(object(), "t", "Charon", "i", "m",
                                                       Path("/tmp/raw"), 1, 3),
                             "audio/pcm;rate=24000")
        self.assertEqual(calls["n"], 2)

    def test_the_tts_call_is_wrapped_by_the_stage_budget_too(self):
        text = (REPO / "pipeline" / "gemini_tts.py").read_text(encoding="utf-8")
        self.assertIn("budget.check(", text)
        self.assertIn("TTS chunk", text, "per-chunk progress must be visible in the trail")


class OneBadTransportDoesNotCostEveryChunk(unittest.TestCase):
    """A stalled `interactions` read must demote itself, not repeat twelve times."""

    def test_a_stall_demotes_the_transport_for_the_rest_of_the_process(self):
        from pipeline import gemini_tts

        original = gemini_tts._INTERACTIONS_STALLED
        gemini_tts._INTERACTIONS_STALLED = False
        try:
            def stalls(*a, **k):
                time.sleep(2)

            with mock.patch.object(gemini_tts, "_synthesize_single_chunk", stalls), \
                 mock.patch.dict(os.environ, {"GEMINI_HTTP_TIMEOUT_SECONDS": "1"}):
                from pipeline.gemini_client import GeminiRequestTimedOut
                with self.assertRaises(GeminiRequestTimedOut):
                    gemini_tts._guarded_chunk(object(), "t", "Charon", "i", "m",
                                              Path("/tmp/raw"), 1, 12)
            self.assertTrue(gemini_tts._INTERACTIONS_STALLED,
                            "the next chunk must not pay the same stall again")
        finally:
            gemini_tts._INTERACTIONS_STALLED = original

    def test_a_finished_chunk_is_not_repaid(self):
        text = (REPO / "pipeline" / "gemini_tts.py").read_text(encoding="utf-8")
        self.assertIn("reused from this attempt", text,
                      "a run that stalls at chunk 9 must keep chunks 1-8")


class AReportMustNotHideInItsOwnNoise(unittest.TestCase):
    """Issue #216 was 85 identical stall lines and nothing else."""

    def test_repeated_stall_notices_become_one_line(self):
        from scripts.release_report import collapse_repeats

        text = "\n".join(
            [f"[progress 03:{minute:02d}:25Z] … still inside speech synthesis — "
             f"888 words, Charon after {82 + 2 * (minute - 0):.0f} min" for minute in range(0, 20)]
            + ["[progress 04:28:25Z] ✗ speech synthesis failed after 10200.0s"])
        collapsed = collapse_repeats(text)
        self.assertEqual(len(collapsed.splitlines()), 2)
        self.assertIn("20 reports", collapsed)
        self.assertIn("✗ speech synthesis failed", collapsed)

    def test_a_lone_stall_line_is_still_useful(self):
        from scripts.release_report import collapse_repeats

        text = "[progress 03:00:25Z] … still inside encode — 6.0 min after 12.0 min"
        collapsed = collapse_repeats(text)
        self.assertIn("still inside encode", collapsed)
        self.assertIn("12 min", collapsed)

    def test_the_report_says_when_not_one_stage_finished(self):
        from scripts import release_report

        trail = ("03:00:25Z ▶ speech synthesis — 888 words, Charon\n"
                 "03:02:25Z … still inside speech synthesis — 888 words after 2.0 min\n")
        _, body = release_report.render(release_report.summarise(
            release_report.parse_trail(trail)))
        self.assertIn("Not one stage finished", body)
        self.assertIn("03:00:25Z ▶ speech synthesis", body)
