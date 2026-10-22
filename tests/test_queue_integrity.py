"""Queue-integrity regressions.

These tests exist because of a real outage: commit 333767c added
`_validate_finance_niche` to `pipeline/run.py`, but the two `niche: history` drafts stayed in
`content/queue/`. `dry-run.yml` selected `content/queue/*.md | head -n1`, so every CI run
crashed on the niche gate before rendering a single frame. The repo sat red.

`test_every_queued_job_is_in_niche` is the guard that makes that class of bug impossible:
anything the scheduler can pick up must already satisfy the gate it will be run against.
"""
from pathlib import Path
import unittest

from pipeline.run import _validate_finance_niche
from pipeline.script_doc import ScriptDoc, parse_script

ROOT = Path(__file__).resolve().parent.parent
QUEUE_DIR = ROOT / "content" / "queue"
ARCHIVE_DIR = ROOT / "content" / "archive"


def _niche(doc: ScriptDoc) -> str:
    return str(doc.meta.get("niche", "")).strip().lower()


def _script_files(directory: Path) -> list[Path]:
    """Markdown *job* files only — READMEs and notes in the same folder are not scripts."""
    return sorted(p for p in directory.glob("*.md") if p.stem.lower() != "readme")


class QueueIntegrityTests(unittest.TestCase):
    def test_every_queued_job_is_in_niche(self):
        """Nothing in the scheduler's glob may be refused by the niche gate at run time."""
        queued = _script_files(QUEUE_DIR)
        self.assertTrue(queued, f"{QUEUE_DIR} is empty — CI has nothing in-niche to render")
        for path in queued:
            doc = parse_script(path)
            with self.subTest(job=path.name):
                try:
                    _validate_finance_niche(doc)
                except RuntimeError as exc:
                    self.fail(f"{path.name} would fail the niche gate in CI: {exc}")

    def test_no_out_of_niche_draft_can_be_scheduled(self):
        """Out-of-niche work belongs in content/archive/, which select_jobs never globs."""
        for path in _script_files(ARCHIVE_DIR):
            doc = parse_script(path)
            with self.subTest(job=path.name):
                refused = False
                try:
                    _validate_finance_niche(doc)
                except RuntimeError:
                    refused = True
                if refused:
                    self.assertNotIn(
                        path,
                        _script_files(QUEUE_DIR),
                        f"{path.name} is out-of-niche and must not sit in content/queue/",
                    )

    def test_queued_jobs_parse_and_have_scenes(self):
        """A queued job must be renderable: frontmatter, scenes, narration."""
        for path in _script_files(QUEUE_DIR):
            with self.subTest(job=path.name):
                doc = parse_script(path)
                self.assertTrue(doc.scenes, f"{path.name} has no scenes")
                self.assertGreaterEqual(doc.word_count, 60, f"{path.name} is too thin to render")
                self.assertTrue(doc.meta.get("originality"), f"{path.name} lacks the originality checklist")

    def test_asset_queries_cover_every_scene_when_provided(self):
        """A partial asset_queries list silently drops later scenes onto
        heading-as-query ("The hook"), which sources nothing usable."""
        for path in _script_files(QUEUE_DIR):
            doc = parse_script(path)
            queries = doc.meta.get("asset_queries") or []
            with self.subTest(job=path.name):
                if queries:
                    self.assertGreaterEqual(
                        len(queries),
                        len(doc.scenes),
                        f"{path.name}: {len(queries)} asset_queries for {len(doc.scenes)} scenes",
                    )
                    for sc in doc.scenes:
                        self.assertTrue(
                            str(sc.asset_query or "").strip(),
                            f"{path.name}: scene {sc.index} has no asset query",
                        )

    def test_unverified_drafts_stay_blocked_by_the_originality_gate(self):
        """`status: approved` + `human_rewrite: false` is the dangerous combination — forbid it."""
        for path in _script_files(QUEUE_DIR):
            doc = parse_script(path)
            flags = doc.meta.get("originality") or {}
            with self.subTest(job=path.name):
                if doc.status == "approved":
                    self.assertIs(
                        flags.get("human_rewrite"),
                        True,
                        f"{path.name} is approved but not human-verified (PLAN.md §4.4)",
                    )


if __name__ == "__main__":
    unittest.main()
