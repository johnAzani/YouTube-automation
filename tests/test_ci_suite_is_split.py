"""The unit-test job on GitHub must stay well inside its time limit.

On 15 November 2026 the suite (about 1,980 tests) took 19 to 26 minutes in one
process on GitHub's runners (runs 43737911292, 43740479521, 43740476661), under
a 35-minute limit. Earlier the same day a slow runner had been cancelled at the
old 20-minute limit, and a cancelled job shows on a pull request as a failed
check with nothing to read. The same suite took 13 minutes on two processors
when split across processes.

These tests keep the split in place, and keep the two rules that make it safe:
a test that fails while split is run again alone before the job fails, and that
second run can never quietly turn into "run nothing and pass".
"""

from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "dry-run.yml"


def _job() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["checks"]


def _script() -> str:
    step = [s for s in _job()["steps"] if s.get("name") == "Unit tests"]
    assert len(step) == 1, "the checks job must have exactly one 'Unit tests' step"
    return step[0]["run"]


def _lines_running_pytest() -> list[str]:
    return [line.strip() for line in _script().splitlines()
            if line.strip().startswith("python -m pytest")]


class TheSuiteIsSplitAcrossProcessors(unittest.TestCase):
    def test_the_tool_that_splits_it_is_installed(self):
        self.assertIn("pytest-xdist", _script())

    def test_the_first_run_uses_every_processor(self):
        first = _lines_running_pytest()[0]
        self.assertIn("-n auto", first)

    def test_a_file_stays_in_one_process(self):
        # Tests in one file share module-level state and files on disk. Spreading
        # them over processes would change their order and their neighbours.
        first = _lines_running_pytest()[0]
        self.assertIn("--dist loadfile", first)

    def test_the_limit_still_fits_a_run_in_one_process(self):
        self.assertGreaterEqual(_job()["timeout-minutes"], 30)


class AFailureWhileSplitIsCheckedAlone(unittest.TestCase):
    def test_there_is_a_second_run_of_only_the_failed_tests(self):
        runs = _lines_running_pytest()
        self.assertEqual(len(runs), 2, runs)
        self.assertIn("--last-failed", runs[1])
        self.assertNotIn("-n ", runs[1], "the second run must be one process")

    def test_the_second_run_cannot_pass_by_running_nothing(self):
        # When no failure was recorded, plain `--last-failed` runs the whole
        # suite again in one process (another 20 minutes). With `none` pytest
        # runs nothing and exits non-zero, so the job fails and says so.
        self.assertIn("--last-failed-no-failures none", _lines_running_pytest()[1])

    def test_only_the_tests_failed_code_gets_a_second_run(self):
        self.assertIn('if [ "$rc" -eq 1 ]; then', _script())

    def test_a_test_that_passes_only_alone_is_named(self):
        script = _script()
        self.assertIn("::warning title=Tests passed only when run alone::", script)
        self.assertIn("${split_failures", script)

    def test_a_real_failure_still_fails_the_job(self):
        script = _script()
        self.assertIn("::error title=Unit test failure::", script)
        self.assertIn('exit "$rc"', script)
        # The verdict is taken after the second run, so its exit code decides.
        self.assertLess(script.index("--last-failed"), script.index('exit "$rc"'))


if __name__ == "__main__":
    unittest.main()
