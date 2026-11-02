"""Guards for brain-authored Shorts.

The renderer was always data-driven; only the data was hand-written into a Python
literal. Turning a Short into a spec makes it authorable, and these tests make sure
that authoring can fail safely: a plausible-but-wrong spec must be rejected rather
than uploaded.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pipeline import gemini_brain as gb
from pipeline import short_script as ss
from pipeline.script_doc import parse_script

ROOT = Path(__file__).resolve().parents[1]


def good_spec(key="short-psalm121", scripture="Psalm 121"):
    captions = [
        [0, 12, "Before you close your eyes tonight, breathe slowly and lift your eyes to the hills."],
        [13, 26, "I lift up my eyes to the hills; my help comes from the Lord, who made heaven and earth."],
        [27, 40, "He will not let your foot slip; he who watches over you will not slumber."],
        [41, 54, "He who keeps you will neither slumber nor sleep, through all the hours of this night."],
        [55, 68, "The Lord is your keeper and your shade, and the sun will not strike you by day."],
        [69, 82, "He will keep you from all harm and watch over your coming and going."],
        [83, 96, "Sleep now, and let your home rest under the watch of the One who never tires."],
        [97, 110, "If this prayer steadied you, type Amen and subscribe to pray with us each night."],
    ]
    return {
        "key": key,
        "scripture": scripture,
        "title": ["THE SECRET PLACE", "PSALM 121 · NIGHT PRAYER"],
        "poster": ["PRAYER BEFORE SLEEP", "PSALM 121", "YOUR KEEPER", "HE NEVER SLUMBERS"],
        "end": ["SUBSCRIBE", "The Secret Place — prayers every day"],
        "stock_queries": ["moon over calm lake at night"] * 8,
        "scenes": [
            {"a": "", "img": f"{key}-scene-0{i}.jpg", "kicker": "PSALM 121:1",
             "sub": "I LIFT MY EYES TO THE HILLS", "cam": "push_in", "focus": [0.5, 0.45]}
            for i in range(1, 9)
        ],
        "captions": captions,
        "kinetic_phrases": [
            [c[0], c[1], ["ON SCREEN LINE"], ["SCREEN"], "PSALM 121"] for c in captions
        ],
        "beats": [{"a": "lift up my eyes", "kind": "quote", "words": ["MY", "HELP"], "hi": 0, "slot": "C"}],
    }


class TestSchema(unittest.TestCase):
    def test_a_complete_spec_validates(self):
        spec = ss.validate_spec(good_spec())
        self.assertEqual(spec.problems, [])
        self.assertEqual(spec.psalm, 121)
        self.assertGreaterEqual(spec.words, ss.MIN_WORDS)

    def test_renderer_shape_matches_what_tools_shorts_expects(self):
        rendered = ss.validate_spec(good_spec()).to_renderer()
        for key in ("title", "poster", "end", "out", "narration", "stock_queries",
                    "scenes", "teases", "beats", "captions", "kinetic_phrases"):
            self.assertIn(key, rendered)
        self.assertEqual(rendered["out"], "short-psalm121.mp4")
        self.assertEqual(rendered["narration"], "short-psalm121.mp3")


class TestRefusals(unittest.TestCase):
    def problems(self, **changes):
        data = good_spec()
        data.update(changes)
        return ss.validate_spec(data).problems

    def test_bad_camera_move(self):
        data = good_spec()
        data["scenes"][0]["cam"] = "orbit"
        self.assertTrue(any("cam" in p for p in ss.validate_spec(data).problems))

    def test_kicker_too_long_for_a_9_16_frame(self):
        data = good_spec()
        data["scenes"][0]["kicker"] = "A KICKER THAT WILL NEVER FIT ON SCREEN"
        self.assertTrue(any("kicker" in p for p in ss.validate_spec(data).problems))

    def test_query_count_must_match_scene_count(self):
        self.assertTrue(any("stock queries" in p for p in self.problems(stock_queries=["one"])))

    def test_overlapping_captions(self):
        data = good_spec()
        data["captions"][1][0] = 5
        self.assertTrue(any("overlaps" in p for p in ss.validate_spec(data).problems))

    def test_narration_that_is_too_short(self):
        data = good_spec()
        data["captions"] = data["captions"][:2]
        data["kinetic_phrases"] = data["kinetic_phrases"][:2]
        problems = ss.validate_spec(data).problems
        self.assertTrue(any("narration words" in p for p in problems))

    def test_beat_anchor_must_be_in_the_narration(self):
        data = good_spec()
        data["beats"][0]["a"] = "a phrase nobody said"
        self.assertTrue(any("does not appear" in p for p in ss.validate_spec(data).problems))

    def test_wrong_psalm_is_refused(self):
        data = good_spec(scripture="Psalm 27")
        self.assertTrue(any("quotes Psalm" in p for p in ss.validate_spec(data).problems))

    def test_creator_name_is_refused(self):
        data = good_spec()
        data["end"] = ["SUBSCRIBE", "Narrated by John Azani"]
        self.assertTrue(any("creator name" in p for p in ss.validate_spec(data).problems))

    def test_one_kinetic_phrase_per_caption(self):
        data = good_spec()
        data["kinetic_phrases"] = data["kinetic_phrases"][:-1]
        self.assertTrue(any("kinetic phrases" in p for p in ss.validate_spec(data).problems))


class TestStorage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.patch = mock.patch.object(ss, "SPEC_DIR", Path(self.tmp.name))
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_save_then_load_round_trips(self):
        ss.save_spec(ss.validate_spec(good_spec()))
        authored = ss.load_authored()
        self.assertIn("short-psalm121", authored)
        self.assertEqual(authored["short-psalm121"]["out"], "short-psalm121.mp4")

    def test_invalid_spec_is_never_written(self):
        data = good_spec()
        data["scenes"][0]["cam"] = "orbit"
        with self.assertRaises(ss.ShortSpecError):
            ss.save_spec(ss.validate_spec(data))
        self.assertEqual(list(Path(self.tmp.name).glob("*.json")), [])

    def test_a_broken_file_is_skipped_not_fatal(self):
        ss.save_spec(ss.validate_spec(good_spec()))
        Path(self.tmp.name, "broken.json").write_text("{not json", encoding="utf-8")
        self.assertEqual(ss.authored_keys(), {"short-psalm121"})


class TestModelContract(unittest.TestCase):
    def test_parses_bare_json(self):
        self.assertEqual(ss.parse_model_json('{"a": 1}'), {"a": 1})

    def test_parses_json_wrapped_in_fences_and_prose(self):
        text = 'Here you go:\n```json\n{"a": 1}\n```\nEnjoy.'
        self.assertEqual(ss.parse_model_json(text), {"a": 1})

    def test_rejects_non_json(self):
        with self.assertRaises(ss.ShortSpecError):
            ss.parse_model_json("I cannot help with that.")


class TestBrainAuthorsTheShort(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        for patcher in (
            mock.patch.object(gb, "SHORTS_QUEUE_DIR", self.dir / "queue"),
            mock.patch.object(ss, "SPEC_DIR", self.dir / "specs"),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        (self.dir / "queue").mkdir()

    def doc(self, name="0010-psalm-121-he-who-keeps-you-will-neither-slumber-no.md"):
        return parse_script(ROOT / "content" / "published" / name)

    def test_authoring_failure_leaves_a_draft_that_says_why(self):
        brain = gb.GeminiBrain(api_key="")           # no client -> cannot author
        path, key = brain.generate_companion_short(self.doc())
        data = json.loads(json.dumps(__import__("yaml").safe_load(path.read_text())))
        self.assertEqual(key, "short-psalm121")
        self.assertEqual(data["status"], "draft")
        self.assertFalse(data["renderer_ready"])
        self.assertIn("authoring failed", data["notes"])

    def test_a_valid_model_response_is_saved_and_approved(self):
        brain = gb.GeminiBrain(api_key="fake")
        with mock.patch.object(gb.GeminiBrain, "is_api_available", return_value=True), \
             mock.patch.object(brain, "_client", create=True) as client:
            client.models.generate_content.return_value.text = json.dumps(good_spec())
            path, key = brain.generate_companion_short(self.doc())
        import yaml
        data = yaml.safe_load(path.read_text())
        self.assertEqual(data["status"], "approved")
        self.assertTrue(data["authored_by_brain"])
        self.assertTrue((self.dir / "specs" / "short-psalm121.json").is_file())

    def test_an_invalid_model_response_is_refused_not_saved(self):
        broken = good_spec()
        broken["scenes"][0]["cam"] = "orbit"
        brain = gb.GeminiBrain(api_key="fake")
        with mock.patch.object(gb.GeminiBrain, "is_api_available", return_value=True), \
             mock.patch.object(brain, "_client", create=True) as client:
            client.models.generate_content.return_value.text = json.dumps(broken)
            path, key = brain.generate_companion_short(self.doc())
        import yaml
        data = yaml.safe_load(path.read_text())
        self.assertEqual(data["status"], "draft")
        self.assertIn("rejected twice", data["notes"])
        self.assertFalse((self.dir / "specs" / "short-psalm121.json").exists())


class TestBackfillingAStalledQueue(unittest.TestCase):
    """Manifests written before the brain could author must still drain themselves."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        for patcher in (
            mock.patch.object(gb, "SHORTS_QUEUE_DIR", self.dir / "queue"),
            mock.patch.object(ss, "SPEC_DIR", self.dir / "specs"),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        (self.dir / "queue").mkdir()
        self.manifest = self.dir / "queue" / "0010-short-psalm-121.yml"
        self.manifest.write_text(
            "short: short-psalm121\n"
            "companion_longform_id: '0010'\n"
            "status: draft\n"
            "renderer_ready: false\n"
            "notes: needs a scene script\n",
            encoding="utf-8",
        )

    def read(self):
        import yaml
        return yaml.safe_load(self.manifest.read_text(encoding="utf-8"))

    def test_the_brain_authors_the_missing_spec_and_approves_it(self):
        brain = gb.GeminiBrain(api_key="fake")
        with mock.patch.object(gb.GeminiBrain, "is_api_available", return_value=True), \
             mock.patch.object(brain, "_client", create=True) as client:
            client.models.generate_content.return_value.text = json.dumps(good_spec())
            rows = brain.author_missing_shorts()
        self.assertEqual([r["verdict"] for r in rows], ["authored"])
        data = self.read()
        self.assertEqual(data["status"], "approved")
        self.assertTrue(data["renderer_ready"])
        self.assertTrue(data["authored_by_brain"])
        self.assertTrue((self.dir / "specs" / "short-psalm121.json").is_file())

    def test_a_failed_authoring_leaves_the_manifest_blocked_and_honest(self):
        brain = gb.GeminiBrain(api_key="")           # no client -> cannot author
        rows = brain.author_missing_shorts()
        self.assertEqual([r["verdict"] for r in rows], ["failed"])
        data = self.read()
        self.assertEqual(data["status"], "draft")
        self.assertFalse(data["renderer_ready"])
        self.assertIn("authoring failed", data["notes"])

    def test_a_manifest_with_no_source_script_is_not_guessed_at(self):
        self.manifest.write_text(
            "short: short-psalm999\ncompanion_longform_id: '9999'\nstatus: draft\n"
            "renderer_ready: false\nnotes: x\n",
            encoding="utf-8",
        )
        brain = gb.GeminiBrain(api_key="fake")
        rows = brain.author_missing_shorts()
        self.assertEqual([r["verdict"] for r in rows], ["no_source"])
        self.assertIn("cannot author", self.read()["notes"])

    def test_a_renderable_manifest_is_left_alone(self):
        self.manifest.write_text(
            "short: short-psalm91\nstatus: approved\nrenderer_ready: true\n",
            encoding="utf-8",
        )
        brain = gb.GeminiBrain(api_key="fake")
        rows = brain.author_missing_shorts()
        self.assertEqual([r["verdict"] for r in rows], ["renderable"])


class TestReleaseStageSelfHeals(unittest.TestCase):
    """`--next` must not print "nothing to do" while the brain could still author."""

    def test_the_release_path_asks_the_brain_before_giving_up(self):
        from pipeline import short_release as sr

        rows = [{"file": "a.yml", "short": "short-psalm23", "status": "draft",
                 "verdict": "needs_renderer", "reason": "no scene script"}]
        authored = [{"file": "a.yml", "key": "short-psalm23",
                     "verdict": "authored", "reason": "120 narration words"}]
        with mock.patch.object(sr, "queue_report", return_value=rows), \
             mock.patch.object(gb.GeminiBrain, "author_missing_shorts",
                               return_value=authored) as author, \
             mock.patch.object(sr, "select_next_queued_short", return_value=None), \
             mock.patch.object(sr.os, "environ", {}), \
             mock.patch("builtins.print"):
            self.assertEqual(sr.main(["--next", "--dry-run"]), 0)
        author.assert_called_once()

    def test_a_queue_that_can_render_never_calls_the_brain(self):
        from pipeline import short_release as sr

        with mock.patch.object(sr, "queue_report", return_value=[]), \
             mock.patch.object(gb.GeminiBrain, "author_missing_shorts") as author, \
             mock.patch.object(sr, "select_next_queued_short", return_value=None), \
             mock.patch.object(sr.os, "environ", {}), \
             mock.patch("builtins.print"):
            sr.main(["--next", "--dry-run"])
        author.assert_not_called()


class TestRendererPicksThemUp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.patch = mock.patch.object(ss, "SPEC_DIR", Path(self.tmp.name))
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_authored_spec_makes_the_key_renderable(self):
        from pipeline.short_release import _renderer_script_keys
        before = _renderer_script_keys()
        self.assertNotIn("short-psalm121", before)
        ss.save_spec(ss.validate_spec(good_spec()))
        self.assertIn("short-psalm121", _renderer_script_keys())


if __name__ == "__main__":
    unittest.main()
