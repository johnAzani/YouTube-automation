"""Shorts: the brain authors them, and approval follows renderability.

A Short is data — a validated spec the brain writes into `content/shorts-scripts/`,
unioned with the hand-written scene scripts in `tools/shorts.py`. Manifests may
exist without either, and previously such a manifest was written `approved`, so
three of them sat in the queue while the stage printed "nothing to do" and exited
0 — indistinguishable from success on the run page. These tests pin that a
manifest is only approved when a renderer can actually build it.
"""
import ast
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from pipeline import gemini_brain as gb
from pipeline import short_release as sr
from pipeline.script_doc import parse_script

ROOT = Path(__file__).resolve().parents[1]


def write_manifest(dirpath: Path, name: str, **fields) -> Path:
    path = dirpath / name
    path.write_text(yaml.safe_dump(fields, sort_keys=False), encoding="utf-8")
    return path


class TestQueueReport(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def report(self):
        return {r["file"]: r for r in sr.queue_report(self.dir)}

    def test_approved_with_renderer_is_ready(self):
        write_manifest(self.dir, "a.yml", short="short-psalm91", status="approved")
        self.assertEqual(self.report()["a.yml"]["verdict"], "ready")

    def test_approved_without_renderer_says_why(self):
        write_manifest(self.dir, "b.yml", short="short-psalm23", status="approved")
        row = self.report()["b.yml"]
        self.assertEqual(row["verdict"], "needs_renderer")
        self.assertIn("tools/shorts.py", row["reason"])

    def test_unknown_key_is_unusable(self):
        write_manifest(self.dir, "c.yml", short="short-not-a-thing", status="approved")
        self.assertEqual(self.report()["c.yml"]["verdict"], "unusable")

    def test_draft_is_not_approved(self):
        write_manifest(self.dir, "d.yml", short="short-psalm91", status="draft")
        self.assertEqual(self.report()["d.yml"]["verdict"], "not_approved")

    def test_empty_dir_is_empty_report(self):
        self.assertEqual(sr.queue_report(self.dir), [])


class TestNothingToDoIsVisible(unittest.TestCase):
    def test_stage_warns_and_exits_zero_when_everything_is_blocked(self):
        rows = [{"file": "a.yml", "short": "short-psalm23", "status": "approved",
                 "verdict": "needs_renderer", "reason": "no scene script"}]
        with mock.patch.object(sr, "select_next_queued_short", return_value=None), \
             mock.patch.object(sr, "queue_report", return_value=rows), \
             mock.patch.object(sr.os, "environ", {"GITHUB_ACTIONS": "true"}), \
             mock.patch("builtins.print") as printed:
            self.assertEqual(sr.main(["--next"]), 0)
        out = " ".join(str(c.args[0]) for c in printed.call_args_list)
        self.assertIn("nothing to do", out)
        self.assertIn("Shorts stalled", out)

    def test_a_ready_manifest_that_was_not_selected_is_an_error(self):
        rows = [{"file": "a.yml", "short": "short-psalm91", "status": "approved",
                 "verdict": "ready", "reason": "will render"}]
        with mock.patch.object(sr, "select_next_queued_short", return_value=None), \
             mock.patch.object(sr, "queue_report", return_value=rows), \
             mock.patch.object(sr.os, "environ", {}), \
             mock.patch("builtins.print"):
            self.assertEqual(sr.main(["--next"]), 1)


class TestCompanionShortMapping(unittest.TestCase):
    """The brain hardcoded `short-psalm91` for every job and approved it blind."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.patch = mock.patch.object(gb, "SHORTS_QUEUE_DIR", Path(self.tmp.name))
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.brain = gb.GeminiBrain(api_key="")

    def doc(self, name):
        return parse_script(ROOT / "content" / "published" / name)

    def test_key_follows_the_psalm_of_the_job(self):
        doc = self.doc("0010-psalm-121-he-who-keeps-you-will-neither-slumber-no.md")
        path, key = self.brain.generate_companion_short(doc)
        self.assertEqual(key, "short-psalm121")
        self.assertNotIn("psalm91", path.name)

    def test_without_a_renderer_the_manifest_is_a_draft(self):
        """No API key and no hand-written script: refuse, and say why in the manifest."""
        doc = self.doc("0010-psalm-121-he-who-keeps-you-will-neither-slumber-no.md")
        path, _ = self.brain.generate_companion_short(doc)
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "draft")
        self.assertFalse(data["renderer_ready"])
        self.assertFalse(data["authored_by_brain"])
        self.assertIn("authoring failed", data["notes"])
        self.assertIn("GEMINI_API_KEY", data["notes"])

    def test_a_spec_authored_by_the_brain_makes_the_manifest_renderable(self):
        """The brain writes the spec; nothing hand-authored is required.

        `_renderer_script_keys()` reads the authored specs off disk, so saving the
        spec is itself what makes the key renderable. Simulated here with a set
        that `save_spec` grows.
        """
        from pipeline import short_script as ss

        doc = self.doc("0010-psalm-121-he-who-keeps-you-will-neither-slumber-no.md")
        renderable_keys: set[str] = set()
        authored = mock.Mock(key="short-psalm121", words=120)

        def fake_save(spec):
            renderable_keys.add(spec.key)
            return Path("/dev/null")

        with mock.patch.object(gb.GeminiBrain, "author_short_spec", return_value=authored), \
             mock.patch.object(ss, "save_spec", side_effect=fake_save), \
             mock.patch.object(sr, "_renderer_script_keys", side_effect=lambda: set(renderable_keys)):
            path, key = self.brain.generate_companion_short(doc)

        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        self.assertEqual(key, "short-psalm121")
        self.assertTrue(data["authored_by_brain"])
        self.assertTrue(data["renderer_ready"])
        self.assertEqual(data["status"], "approved")
        self.assertIn("spec authored by the brain", data["notes"])

    def test_with_a_renderer_it_may_be_approved(self):
        doc = self.doc("0010-psalm-121-he-who-keeps-you-will-neither-slumber-no.md")
        with mock.patch.object(sr, "_renderer_script_keys", return_value={"short-psalm121"}):
            path, _ = self.brain.generate_companion_short(doc)
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "approved")
        self.assertTrue(data["renderer_ready"])


class TestShortThumbnails(unittest.TestCase):
    def test_thumbnail_call_is_not_made_for_shorts(self):
        """YouTube rejects custom thumbnails on Shorts; the call still costs quota."""
        source = (ROOT / "pipeline" / "short_release.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        calls = [n for n in ast.walk(tree)
                 if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "set_video_thumbnail"]
        self.assertEqual(calls, [], "set_video_thumbnail must not be called on the Shorts path")
        self.assertIn("not_supported_for_shorts", source)


class TestQueueDataMatchesReality(unittest.TestCase):
    def test_every_manifest_declares_whether_it_can_render(self):
        for path in sorted((ROOT / "content" / "shorts-queue").glob("*.yml")):
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertIn("renderer_ready", data, path.name)

    def test_approval_implies_a_renderer(self):
        renderable = sr._renderer_script_keys()
        for path in sorted((ROOT / "content" / "shorts-queue").glob("*.yml")):
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            if data.get("status") == "approved":
                self.assertIn(data.get("short"), renderable,
                              f"{path.name} is approved but has no scene script")


if __name__ == "__main__":
    unittest.main()
