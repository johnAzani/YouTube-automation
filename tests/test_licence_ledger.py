"""The `image-search/` licence ledger must exist, match the bytes, and be believed.

`tools/deep_dive.py` and `tools/shorts.py` fall back to these 49 authored stills whenever a
stock provider returns nothing. Before the ledger, both wrote one blanket string into their
credits — *"source/license metadata unavailable"* — for every still, which hid the fact that
10 of them carry embedded Getty Images rights metadata and 3 more an "All Rights Reserved"
photographer copyright. `scripts/licence_ledger.py` derives the real status from each file's
own metadata; these tests keep the ledger honest and keep the renderers reading it.
"""
from pathlib import Path
import subprocess
import sys
import unittest

from pipeline import licences
from scripts import licence_ledger as ledger_cli

ROOT = Path(__file__).resolve().parent.parent
IMG_DIR = ROOT / "image-search"
LEDGER = IMG_DIR / "LICENSES.yml"


def _stills_on_disk() -> list[Path]:
    return sorted(p for p in IMG_DIR.iterdir()
                  if p.is_file() and p.name != "LICENSES.yml" and not p.name.startswith("."))


class LicenceLedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ledger = licences.load_ledger(use_cache=False)
        cls.stills = _stills_on_disk()

    def test_ledger_exists_and_covers_every_still(self):
        self.assertTrue(LEDGER.is_file(), "image-search/LICENSES.yml is missing — run "
                                          "`python scripts/licence_ledger.py write`")
        self.assertTrue(self.ledger, "ledger parsed to nothing")
        self.assertEqual(
            sorted(self.ledger), [p.name for p in self.stills],
            "ledger and image-search/ disagree — run `python scripts/licence_ledger.py write`",
        )

    def test_recorded_hashes_match_the_actual_bytes(self):
        """A clearance keyed to content cannot silently transfer to a swapped file."""
        for path in self.stills:
            with self.subTest(file=path.name):
                self.assertEqual(
                    self.ledger[path.name].get("sha256"), ledger_cli.sha256(path),
                    f"{path.name} changed since the ledger was written",
                )

    def test_files_with_an_embedded_rights_claim_are_encumbered(self):
        """Regression: the whole point of the ledger. Getty frames and 'All Rights
        Reserved' photographs must never be reported as usable."""
        encumbered = [n for n, e in self.ledger.items() if e.get("status") == "rights-encumbered"]
        self.assertTrue(encumbered, "expected the known Getty/ARR stills to be flagged")
        for name in encumbered:
            with self.subTest(file=name):
                self.assertFalse(licences.is_safe_for_monetized_use(name, self.ledger))
                note = licences.licence_note(name, self.ledger)
                self.assertIn("RIGHTS ENCUMBERED", note)
        # Spot-check the two claims that are unambiguous in the file metadata.
        self.assertIn("Getty", self.ledger["andrew-fastow-enron-cfo-trial-photo-2.jpg"]
                      .get("rights_claim", ""), "expected the embedded '2002 Getty Images' claim")
        self.assertIn("Markos", self.ledger["south-fork-fishing-and-hunting-club-club-4.jpg"]
                      .get("rights_claim", ""), "expected the embedded photographer copyright")

    def test_corrupt_file_is_recorded_as_corrupt_not_as_unverified(self):
        """`johnstown-flood-1889-ruins-destruction-h-5.png` is 68 bytes and will not decode.
        Recording it as merely 'unverified' would imply it could be cleared."""
        name = "johnstown-flood-1889-ruins-destruction-h-5.png"
        self.assertIn(name, self.ledger)
        self.assertEqual(self.ledger[name].get("status"), "corrupt")
        self.assertFalse(licences.is_safe_for_monetized_use(name, self.ledger))

    def test_nothing_is_cleared_without_a_licence_and_a_source(self):
        for name, entry in self.ledger.items():
            if entry.get("status") != "cleared":
                continue
            with self.subTest(file=name):
                self.assertTrue(str(entry.get("license") or "").strip(),
                                "cleared with no licence recorded")
                self.assertTrue(str(entry.get("source_url") or "").strip(),
                                "cleared with no source URL recorded")

    def test_licence_notes_are_distinct_per_status(self):
        """The blanket string this replaces said the same thing about a public-domain
        Library of Congress plate and a rights-managed Getty frame."""
        notes = {
            "rights-encumbered": licences.licence_note(
                "andrew-fastow-enron-cfo-trial-photo-2.jpg", self.ledger),
            "corrupt": licences.licence_note(
                "johnstown-flood-1889-ruins-destruction-h-5.png", self.ledger),
            "unverified": licences.licence_note(
                "johnstown-flood-1889-ruins-destruction-h-1.jpg", self.ledger),
            "unrecorded": licences.licence_note("no-such-file.jpg", self.ledger),
        }
        self.assertEqual(len(set(notes.values())), len(notes),
                         "statuses must not collapse into one string again")
        self.assertNotIn("metadata unavailable", "".join(notes.values()),
                         "the old blanket string must be gone")

    def test_unsafe_and_uncleared_are_two_distinct_tiers(self):
        """`unsafe_stills` is the must-not-render list; `uncleared_stills` is the honest
        answer to "may I monetize this?". They must not be conflated: 35 of the 49 stills
        are `unverified`, and a 35-line warning would be scrolled past."""
        used = ["andrew-fastow-enron-cfo-trial-photo-2.jpg",       # encumbered
                "johnstown-flood-1889-ruins-destruction-h-1.jpg",  # unverified
                "johnstown-flood-1889-ruins-destruction-h-5.png"]  # corrupt
        self.assertEqual(
            dict(licences.unsafe_stills(used, self.ledger)),
            {"andrew-fastow-enron-cfo-trial-photo-2.jpg": "rights-encumbered",
             "johnstown-flood-1889-ruins-destruction-h-5.png": "corrupt"},
            "unverified is deliberately not a hard blocker",
        )
        self.assertEqual(
            dict(licences.uncleared_stills(used, self.ledger)),
            {"andrew-fastow-enron-cfo-trial-photo-2.jpg": "rights-encumbered",
             "johnstown-flood-1889-ruins-destruction-h-1.jpg": "unverified",
             "johnstown-flood-1889-ruins-destruction-h-5.png": "corrupt"},
            "nothing here is cleared, so nothing here is monetizable",
        )
        # An unrecorded filename is a hard blocker — nobody has even scanned it.
        self.assertEqual(licences.unsafe_stills(["no-such-file.jpg"], self.ledger),
                         [("no-such-file.jpg", "unrecorded")])

    def test_licence_report_names_hard_blockers_and_summarises_the_rest(self):
        """This block used to be inline in both renderers, where a `_len`-for-`len` typo
        shipped once: the unit suite never calls a renderer's `main()`, so only CI's
        offline render caught it. It now lives in the tested module."""
        lines = licences.licence_report(
            ["andrew-fastow-enron-cfo-trial-photo-2.jpg",       # encumbered
             "johnstown-flood-1889-ruins-destruction-h-5.png",  # corrupt
             "johnstown-flood-1889-ruins-destruction-h-1.jpg",  # unverified
             "johnstown-flood-1889-ruins-destruction-h-2.jpg"], # unverified
            self.ledger,
        )
        joined = "\n".join(lines)
        self.assertIn("2 authored still(s)", joined, "hard blockers listed by name")
        self.assertIn("andrew-fastow-enron-cfo-trial-photo-2.jpg [rights-encumbered]", joined)
        self.assertIn("johnstown-flood-1889-ruins-destruction-h-5.png [corrupt]", joined)
        self.assertIn("2 further still(s) have unverified provenance", joined,
                      "the larger unverified tier is one summary line, not a wall")
        # A fully cleared list says nothing at all.
        self.assertEqual(licences.licence_report([], self.ledger), [])

    def test_both_renderers_read_the_ledger_instead_of_the_blanket_string(self):
        """Exercises the actual import path in the tools, not a reimplementation."""
        for mod_name in ("tools.deep_dive", "tools.shorts"):
            with self.subTest(module=mod_name):
                mod = __import__(mod_name, fromlist=["LICENCE_NOTE"])
                self.assertIs(mod.LICENCE_NOTE, licences.licence_note,
                              f"{mod_name} is not wired to pipeline.licences")
                self.assertIs(mod.LICENCE_REPORT, licences.licence_report,
                              f"{mod_name} is not wired to licences.licence_report")
                note = mod.LICENCE_NOTE("andrew-fastow-enron-cfo-trial-photo-2.jpg")
                self.assertIn("RIGHTS ENCUMBERED", note)
                source = Path(mod.__file__).read_text(encoding="utf-8")
                self.assertNotIn(
                    "source/license metadata unavailable in current ledger — verify",
                    source.split("LICENCE_NOTE = lambda")[0],
                    f"{mod_name} still hard-codes the blanket licence string",
                )
                # The warning must be produced by the tested helper, not re-implemented.
                self.assertNotIn("_UNSAFE_STILLS", source,
                                 f"{mod_name} re-implements the warning inline again")

    def test_check_command_passes_on_a_clean_tree(self):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "licence_ledger.py"), "check"],
            cwd=ROOT, capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0, f"`licence_ledger.py check` failed:\n{proc.stdout}\n{proc.stderr}")
        self.assertIn("in sync", proc.stdout)

    def test_check_command_fails_when_a_file_is_missing_from_the_ledger(self):
        """The guard has to actually be able to fail, or it is decoration."""
        import tempfile
        from unittest.mock import patch

        current = LEDGER.read_text(encoding="utf-8")
        victim = self.stills[0].name
        with tempfile.TemporaryDirectory() as tmp:
            partial = Path(tmp) / "LICENSES.yml"
            # Drop the first entry so the ledger is one file short of the directory.
            head, _, tail = current.partition(f'  - file: "{victim}"')
            rest = tail.split("\n  - file: ", 1)
            partial.write_text(head + ("  - file: " + rest[1] if len(rest) > 1 else ""),
                               encoding="utf-8")
            with patch.object(ledger_cli, "LEDGER", partial):
                rc = ledger_cli.cmd_check()
        self.assertEqual(rc, 1, "check must fail when a still has no ledger entry")

    def test_check_command_fails_on_a_changed_file(self):
        """Same bytes → clearance carries over. Different bytes → it must not."""
        import tempfile
        from unittest.mock import patch

        current = LEDGER.read_text(encoding="utf-8")
        victim = self.stills[0].name
        with tempfile.TemporaryDirectory() as tmp:
            stale = Path(tmp) / "LICENSES.yml"
            stale.write_text(current.replace(
                f'sha256: "{self.ledger[victim]["sha256"]}"',
                'sha256: "' + "0" * 64 + '"', 1), encoding="utf-8")
            with patch.object(ledger_cli, "LEDGER", stale):
                rc = ledger_cli.cmd_check()
        self.assertEqual(rc, 1, "check must fail when a still's bytes no longer match its entry")


if __name__ == "__main__":
    unittest.main()
