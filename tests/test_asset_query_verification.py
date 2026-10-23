"""Every `asset_queries` entry must carry recorded Commons verification.

Why this test exists
--------------------
`content/queue/0003-how-lehman-brothers-died.md` shipped with eight scene queries that had never
been checked against a keyless provider. `pipeline/assets.py` sources scenes from Pexels/Pixabay
(both need an API key) and then from Wikimedia Commons / Internet Archive / NASA (all keyless), so
on a CI runner with no secrets **only** the keyless providers run. Several of 0003's queries
returned nothing usable on Commons, and the advisory `pipeline-dry-run` job stayed red for weeks
while the failure message blamed the query instead of the provider. See MAINTENANCE.md §3.

The fix was to re-verify every query against the Commons search API and score the hits with
exactly the licence filter `_wikimedia()` applies. This test makes that a standing requirement:
a queued job may not carry a scene query that nobody has checked.

The test is deliberately **offline**. It does not call Commons — CI has no reason to, and a
network-dependent test would flake. It audits the recorded `asset_query_verification` block in
each job's frontmatter, so the human who adds a query has to state what they found.

Scoring rule (this is `pipeline/assets.py::licence_ok_for_monetized_use`)
----------------------------------------------------------------------
A Commons hit counts as *usable* only if its `LicenseShortName` contains one of
``cc0`` / ``public domain`` / ``cc by`` **and** carries no ``nc`` / ``sa`` / ``nd`` token
(or the spelled-out equivalents). CC BY-SA is therefore *not* usable — which matters a lot,
because Commons is dominated by CC BY-SA photography of streets and buildings, so most
"looks fine on Commons" queries have far fewer usable hits than they have hits.

Note for maintainers: the disqualifiers must be matched as *tokens*. Commons abbreviates
("CC BY-SA 4.0"), and a substring match on "share alike" silently waves those through — see
`test_licence_rule_matches_the_pipeline_filter`, which pins the regression.
"""
from pathlib import Path
import unittest

from pipeline.script_doc import ScriptDoc, parse_script

ROOT = Path(__file__).resolve().parent.parent
QUEUE_DIR = ROOT / "content" / "queue"

# Import the real predicate instead of restating it — a copy drifts, and a
# drifted copy is how the CC BY-SA / CC BY-NC hole survived as long as it did.
from pipeline.assets import licence_ok_for_monetized_use as _lic_usable  # noqa: E402


def _script_files(directory: Path) -> list[Path]:
    """Markdown *job* files only — READMEs and notes in the same folder are not scripts."""
    return sorted(p for p in directory.glob("*.md") if p.stem.lower() != "readme")


def _distinct(seq: list) -> list:
    seen: list = []
    for item in seq:
        if item not in seen:
            seen.append(item)
    return seen


class AssetQueryVerificationTests(unittest.TestCase):
    def setUp(self):
        self.jobs = [(p, parse_script(p)) for p in _script_files(QUEUE_DIR)]
        self.assertTrue(self.jobs, f"{QUEUE_DIR} is empty — nothing to audit")

    def _block(self, doc: ScriptDoc) -> dict:
        block = doc.meta.get("asset_query_verification")
        self.assertIsInstance(
            block, dict,
            f"{doc.path.name} has asset_queries but no asset_query_verification block. "
            "Verify each query against the Commons search API and record the result — "
            "see the header of tests/test_asset_query_verification.py for the scoring rule.",
        )
        return block or {}

    def test_licence_rule_matches_the_pipeline_filter(self):
        """The recorded `usable` counts in every queued job mean nothing unless the
        pipeline's own filter scores licences the same way. This pins the rule.

        The four `assertFalse` cases below are regressions, not aspirations: before
        `licence_ok_for_monetized_use()` existed, `_wikimedia()` spelled its rejects
        out longhand ("share alike", "non-commercial") while Commons sends them
        abbreviated ("CC BY-SA 4.0", "CC BY-NC 2.0"), and the accept term "cc by"
        matched all of them — so every one of these returned True and the image was
        downloaded and rendered.
        """
        self.assertTrue(_lic_usable("CC0"))
        self.assertTrue(_lic_usable("Public domain"))
        self.assertTrue(_lic_usable("CC BY 4.0"))
        self.assertTrue(_lic_usable("CC BY 2.0"))
        self.assertFalse(_lic_usable("CC BY-SA 4.0"), "share-alike must stay rejected")
        self.assertFalse(_lic_usable("CC BY-SA 2.0"), "share-alike must stay rejected")
        self.assertFalse(_lic_usable("CC BY-SA 3.0 igo"), "share-alike must stay rejected")
        self.assertFalse(_lic_usable("CC BY-NC 2.0"), "non-commercial must stay rejected")
        self.assertFalse(_lic_usable("CC BY-NC-SA 3.0"), "non-commercial must stay rejected")
        self.assertFalse(_lic_usable("CC BY-ND 4.0"), "no-derivatives must stay rejected")
        self.assertFalse(_lic_usable("No restrictions"), "not one of the accepted strings")
        self.assertFalse(_lic_usable("Copyrighted free use"), "not one of the accepted strings")
        self.assertFalse(_lic_usable("FAL"), "not one of the accepted strings")
        self.assertFalse(_lic_usable("GPL"), "not one of the accepted strings")
        self.assertFalse(_lic_usable("see Commons page"), "an absent licence is not a usable licence")
        self.assertFalse(_lic_usable(""), "an absent licence is not a usable licence")
        self.assertFalse(_lic_usable(None), "an absent licence is not a usable licence")

    def test_every_query_is_verified_by_a_probe_or_by_a_ci_run(self):
        """Two acceptable forms of evidence, and nothing else:

        * `usable: <int >= 1>` — a Commons top-N probe, scored with the pipeline's licence
          filter. This is what a *new* query needs, because nothing else has exercised it.
        * `ci_verified: <run id>` — the advisory `pipeline-dry-run` job actually sourced this
          scene end to end on a keyless runner. Stronger than a probe, but only available
          once the job has been rendered in CI (that job renders `queue/*.md | head -n1`).

        Either way the entry must name its evidence, so a future maintainer can re-check it
        instead of taking the flag on trust.
        """
        for path, doc in self.jobs:
            queries = doc.meta.get("asset_queries") or []
            if not queries:
                continue  # heading-as-query fallback; other tests cover scene coverage
            with self.subTest(job=path.name):
                entries = {
                    str(e.get("query")): e
                    for e in (self._block(doc).get("queries") or [])
                    if isinstance(e, dict)
                }
                for query in _distinct([str(q) for q in queries]):
                    entry = entries.get(query)
                    self.assertIsNotNone(
                        entry,
                        f"{path.name}: query {query!r} has no asset_query_verification entry",
                    )
                    self.assertIs(
                        entry.get("verified"), True,
                        f"{path.name}: query {query!r} is recorded as not verified — "
                        "a keyless CI runner will source nothing for that scene",
                    )
                    self.assertTrue(
                        str(entry.get("evidence") or "").strip(),
                        f"{path.name}: {query!r} has no evidence note naming what was found",
                    )
                    usable, ci_run = entry.get("usable"), entry.get("ci_verified")
                    if ci_run is not None:
                        self.assertRegex(
                            str(ci_run), r"^\d{6,}$",
                            f"{path.name}: {query!r} ci_verified must be a numeric Actions run id",
                        )
                        continue
                    self.assertIsInstance(
                        usable, int,
                        f"{path.name}: {query!r} needs either 'usable' (a Commons probe count) "
                        "or 'ci_verified' (a dry-run run id)",
                    )
                    self.assertGreaterEqual(
                        usable, 1,
                        f"{path.name}: query {query!r} is recorded with 0 usable Commons hits — "
                        "the scene cannot be sourced without an API key; change the query or "
                        "record a Pexels/Pixabay key in the repo secrets",
                    )

    def test_no_stale_verification_entries(self):
        """A recorded query that is no longer used is a lie waiting to be trusted."""
        for path, doc in self.jobs:
            queries = {str(q) for q in (doc.meta.get("asset_queries") or [])}
            if not queries:
                continue
            with self.subTest(job=path.name):
                for entry in (self._block(doc).get("queries") or []):
                    self.assertIn(
                        str(entry.get("query")), queries,
                        f"{path.name}: verification entry for {entry.get('query')!r} "
                        "matches no current asset_query — remove it or re-add the query",
                    )

    def test_verification_block_is_dated_and_describes_its_method(self):
        for path, doc in self.jobs:
            if not (doc.meta.get("asset_queries") or []):
                continue
            with self.subTest(job=path.name):
                block = self._block(doc)
                self.assertRegex(
                    str(block.get("verified_on") or ""), r"^\d{4}-\d{2}-\d{2}$",
                    f"{path.name}: asset_query_verification.verified_on must be an ISO date",
                )
                self.assertIn(
                    "commons", str(block.get("method") or "").lower(),
                    f"{path.name}: asset_query_verification.method must name the Commons API",
                )


if __name__ == "__main__":
    unittest.main()
