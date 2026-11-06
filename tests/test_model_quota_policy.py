"""The model choice is a quota decision, and the retry stack was multiplying it.

Measured on 6 November: a single brain pass can ask for ~21 Gemini requests
(preflight 1 + up to 6 scripts + up to 13 Short specs + 1 more), while the free tier
for `gemini-3.8-flash` is about 20 a day — the whole allowance for one pass, and the
next pass fails. On top of that the SDK retried 5xx twice *inside* our own five-attempt
loop, so one logical call could issue ten requests.

See docs/research/gemini-model-and-quota-policy.md.
"""
from __future__ import annotations

import unittest
from unittest import mock

from pipeline import gemini_brain
from pipeline.gemini_brain import (DEFAULT_TEXT_MODEL, DEPRECATED_TEXT_MODELS,
                                   FALLBACK_TEXT_MODELS, RETIRED_TEXT_MODELS,
                                   text_model_candidates)


class TestModelChoice(unittest.TestCase):
    def test_the_default_model_is_one_the_free_tier_can_carry(self):
        self.assertEqual(DEFAULT_TEXT_MODEL, "gemini-3.5-flash-lite",
                         "3.8-flash allows ~20 requests a day; one pass needs more")

    def test_the_chain_leads_with_the_highest_allowance(self):
        chain = text_model_candidates()
        self.assertEqual(chain[0], "gemini-3.5-flash-lite")
        self.assertLess(chain.index("gemini-3.5-flash-lite"), chain.index("gemini-3.8-flash"),
                        "a 20/day model must not be tried before a 500/day one")

    def test_a_retired_model_is_never_first(self):
        for retired in RETIRED_TEXT_MODELS:
            self.assertNotEqual(text_model_candidates(retired)[0], retired)

    def test_a_deprecated_alias_is_not_the_default(self):
        """gemini-3.7-flash has been routed to 3.8 since 8 October — asking for it hides
        which model actually ran."""
        for name in DEPRECATED_TEXT_MODELS:
            self.assertNotEqual(DEFAULT_TEXT_MODEL, name)
            self.assertNotIn(name, FALLBACK_TEXT_MODELS)

    def test_no_duplicates(self):
        chain = text_model_candidates("gemini-3.8-flash")
        self.assertEqual(len(chain), len(set(chain)))


class TestOneRetryAuthority(unittest.TestCase):
    def test_the_brain_client_does_not_retry_inside_the_sdk(self):
        """SDK attempts (2) × our attempts (5) = up to 10 requests per logical call."""
        from pipeline import gemini_client

        brain = gemini_brain.GeminiBrain(api_key="")
        with mock.patch("pipeline.gemini_client.make_client") as made:
            brain.__init__(api_key="key")  # noqa: PLC2801 - re-run the constructor
        self.assertEqual(made.call_args.kwargs.get("attempts"), 1)

    def test_429_is_not_retried_inside_the_socket(self):
        from pipeline.gemini_client import http_options

        codes = http_options(1).retry_options.http_status_codes
        self.assertNotIn(429, codes, "a quota refusal belongs to quota_handler")
        self.assertIn(503, codes)


class TestThePassHasACeiling(unittest.TestCase):
    def test_a_run_stops_instead_of_spending_the_day(self):
        brain = gemini_brain.GeminiBrain(api_key="")
        brain._client = mock.MagicMock()
        brain.calls_made = gemini_brain.MAX_CALLS_PER_RUN
        with self.assertRaises(gemini_brain.BrainAuthoringError) as ctx:
            brain._call_model("gemini-3.5-flash-lite", "prompt")
        self.assertIn("free-tier allowance", str(ctx.exception))
        brain._client.models.generate_content.assert_not_called()

    def test_the_counter_counts_real_requests(self):
        brain = gemini_brain.GeminiBrain(api_key="")
        brain._client = mock.MagicMock()
        brain._client.models.generate_content.return_value.text = "id: x\n## Scene 1"
        brain._call_model("gemini-3.5-flash-lite", "prompt")
        self.assertEqual(brain.calls_made, 1)


class TestTheProbe(unittest.TestCase):
    """Existence is not service: every model existed while 3.8-flash answered 503."""

    @staticmethod
    def runner():
        from scripts import gemini_brain

        return gemini_brain

    def _brain(self, *, serving: set[str], existing: set[str]):
        runner = self.runner()
        brain = mock.MagicMock()
        brain._client.models.get.side_effect = lambda model: (
            mock.MagicMock(input_token_limit=1, output_token_limit=1)
            if model in existing else (_ for _ in ()).throw(RuntimeError("404 NOT_FOUND")))

        def _generate(model, contents, config):
            if model not in serving:
                raise RuntimeError("503 UNAVAILABLE. high demand")
            return mock.MagicMock(text="r")

        brain._client.models.generate_content.side_effect = _generate
        return runner, brain

    def test_a_missing_model_is_reported_as_missing(self):
        runner, brain = self._brain(serving=set(), existing=set())
        with mock.patch("builtins.print") as printed:
            code = runner.cmd_probe_models(brain, generate=True)
        text = " ".join(str(c) for c in printed.call_args_list)
        self.assertEqual(code, 1)
        self.assertIn("MISSING", text)

    def test_a_model_that_exists_but_refuses_fails_the_probe(self):
        runner = self.runner()
        runner, brain = self._brain(serving=set(),
                                    existing=set(runner.PROBE_MODELS))
        with mock.patch("builtins.print") as printed:
            code = runner.cmd_probe_models(brain, generate=True)
        text = " ".join(str(c) for c in printed.call_args_list)
        self.assertEqual(code, 1, "existing-but-refusing must not look healthy")
        self.assertIn("REFUSED", text)
        self.assertIn("no probed model answered", text)

    def test_one_serving_model_is_enough_to_proceed(self):
        runner = self.runner()
        runner, brain = self._brain(serving={"gemini-3.5-flash-lite"},
                                    existing=set(runner.PROBE_MODELS))
        with mock.patch("builtins.print"):
            self.assertEqual(runner.cmd_probe_models(brain, generate=True), 0)

    def test_metadata_only_spends_no_generation_quota(self):
        runner = self.runner()
        runner, brain = self._brain(serving=set(),
                                    existing=set(runner.PROBE_MODELS))
        with mock.patch("builtins.print"):
            runner.cmd_probe_models(brain, generate=False)
        brain._client.models.generate_content.assert_not_called()


if __name__ == "__main__":
    unittest.main()
