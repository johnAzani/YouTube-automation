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


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
