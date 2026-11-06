"""Dependencies that can break production without a commit in this repo.

`google-genai 3.0.0` was published at 02:29 UTC on 6 November 2026. The pipeline
installs `-r requirements.txt` on every run, so the next narration — 08:05 UTC,
produce run 42184629022 — went out against an SDK whose TTS request shape the
service rejects:

    400 INVALID_ARGUMENT. Unknown name "speechMetadata" at 'contents[0].parts[0]';
        Unknown name "speechConfig" at 'generation_config'

Nothing in the repository changed. A release in someone else's repository took
publishing down, and the only defence is a bound. These tests keep the bound.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS = ROOT / "requirements.txt"


def _requirement(name: str) -> str:
    for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith(name):
            return line
    return ""


class TestPinnedMajors(unittest.TestCase):
    def test_google_genai_cannot_jump_a_major_on_its_own(self):
        req = _requirement("google-genai")
        self.assertTrue(req, "google-genai must be a declared requirement")
        self.assertRegex(req, r"<\s*3(\.|$)", f"the next major must stay out: {req!r}")

    def test_the_lower_bound_admits_the_version_that_last_published(self):
        """2.34.0 published 0037 at 21:51 UTC on 5 November; the bound must allow it."""
        req = _requirement("google-genai")
        version = re.search(r">=\s*([0-9.]+)", req)
        self.assertIsNotNone(version, req)
        self.assertLessEqual(
            tuple(int(part) for part in version.group(1).split(".")),
            (2, 34),
            "a lower bound above the last known-good release would force the broken one",
        )


if __name__ == "__main__":
    unittest.main()
