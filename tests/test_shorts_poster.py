"""Contract tests for the native 1080x1920 Shorts poster and its upload gate.

These pin the four things that were wrong with the old path, each of which is
measurable rather than a matter of taste:

1. size — a 1280x720 canvas center-cropped to 9:16 keeps 31.6% of its pixels and
   upscales the rest; the poster is authored at 1080x1920 instead;
2. contrast — the old card measured 2.89:1 behind its hero against a 7.0 floor;
3. safe zone — every glyph must sit inside the box YouTube does not overlay;
4. honesty — the receipt may only say the thumbnail landed when YouTube itself
   reports `shortsAspectRatio`.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from pipeline import shorts_poster as sp
from pipeline import upload
from pipeline.thumbnail_studio import MIN_CONTRAST, contrast_ratio

ROOT = Path(__file__).resolve().parent.parent
SPEC_DIR = ROOT / "content" / "shorts-scripts"


def _fake_client(*, processing: str = "succeeded", thumbs: dict | None = None,
                 set_error: Exception | None = None, set_calls: list | None = None):
    """A minimal stand-in for the Data API client, keyed by the fields we read."""
    class _Exec:
        def __init__(self, value=None, error=None):
            self._value, self._error = value, error

        def execute(self):
            if self._error is not None:
                raise self._error
            return self._value

    class _Videos:
        def list(self, part="", id=""):  # noqa: A002 - mirrors the API
            if "processingDetails" in part:
                item = {"status": {"uploadStatus": "processed"}}
                if processing:
                    item["processingDetails"] = {"processingStatus": processing}
                return _Exec({"items": [item]})
            return _Exec({"items": [{"id": id, "snippet": {"thumbnails": thumbs or {}}}]})

    class _Thumbs:
        def set(self, videoId="", media_body=None):  # noqa: N803 - mirrors the API
            if set_calls is not None:
                set_calls.append(videoId)
            return _Exec({"items": [{"default": {"url": "x"}}]}, set_error)

    class _Client:
        def videos(self):
            return _Videos()

        def thumbnails(self):
            return _Thumbs()

    return _Client()


class TestPosterCanvas(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.out = Path(self._tmp.name) / "poster.jpg"

    def tearDown(self):
        self._tmp.cleanup()

    def test_renders_at_native_nine_by_sixteen(self):
        report = sp.render_shorts_poster(
            self.out, lines=("ANGELS STAND WATCH", "AROUND YOUR BED", "PSALM 91", "NIGHT GUARD"),
            kicker="PRAYER BEFORE SLEEP", channel_id="secret-place")
        self.assertEqual((report.width, report.height), (1080, 1920))
        with Image.open(self.out) as im:
            self.assertEqual(im.size, (1080, 1920))
        self.assertEqual(self.out.suffix, ".jpg")
        # thumbnails.set accepts 50 MB; a poster that ever grows past that is a bug
        self.assertLess(self.out.stat().st_size, 50 * 1024 * 1024)
        self.assertEqual(report.revision, sp.POSTER_REVISION)

    def test_contrast_is_measured_and_clears_the_floor(self):
        report = sp.render_shorts_poster(
            self.out, lines=("PSALM 23 PRAYER", "BEFORE YOU SLEEP", "DIVINE PEACE", ""),
            channel_id="secret-place")
        self.assertGreaterEqual(report.contrast, MIN_CONTRAST)
        self.assertGreaterEqual(MIN_CONTRAST, 7.0)
        # and the number is a real measurement of the composite, not the fill colour
        with Image.open(self.out) as im:
            sample = im.convert("RGB").getpixel((120, 700))
        self.assertNotEqual(contrast_ratio((255, 255, 255), sample), report.contrast)

    def test_every_glyph_stays_inside_the_safe_box(self):
        report = sp.render_shorts_poster(
            self.out, lines=("HOW ENRON FAKED $70", "BILLION IN PLAIN SIGHT", "", ""),
            channel_id="secret-place")
        self.assertTrue(report.safe_zone_ok, report.notes)
        left, top, right, bottom = sp.SAFE_BOX
        with Image.open(self.out) as im:
            px = im.convert("L").load()
            for y in range(0, top):
                self.assertTrue(all(px[x, y] < 60 for x in range(0, 1080, 24)),
                                f"pixel outside the safe box at y={y}")
        self.assertGreater(right, left)

    def test_long_copy_is_fitted_not_clipped(self):
        """A line that does not fit at 132 px is stepped down, not trimmed."""
        report = sp.render_shorts_poster(
            self.out, lines=("ANGELS STAND WATCH", "AROUND YOUR BED", "", ""),
            channel_id="secret-place")
        self.assertLess(report.hero_px, 132, "it must shrink to fit 796 px of text width")
        self.assertGreaterEqual(report.hero_px, 64)
        self.assertTrue(report.safe_zone_ok, report.notes)

    def test_unfittable_copy_is_refused_rather_than_shrunk_into_a_smear(self):
        with self.assertRaises(sp.PosterRefused):
            sp.render_shorts_poster(
                self.out, lines=("SUPERCALIFRAGILISTICEXPIALIDOCIOUS" * 3, "", "", ""),
                channel_id="secret-place")
        self.assertFalse(self.out.exists(), "a refused poster must not leave a file behind")


class TestPosterCopy(unittest.TestCase):
    def test_kicker_is_dropped_when_it_repeats_the_hero(self):
        self.assertTrue(sp.kicker_is_redundant(
            "BEGIN YOUR DAY IN PRAYER", ("BEGIN YOUR", "DAY IN QUIET", "", "")))
        self.assertFalse(sp.kicker_is_redundant(
            "PRAYER BEFORE SLEEP", ("ANGELS STAND WATCH", "AROUND YOUR BED", "", "")))

    def test_dangling_connector_folds_into_the_sub_line(self):
        spec = {"poster": ["BEGIN YOUR", "DAY IN QUIET", "PRAYER WITH", "THE MORNING ALTAR"]}
        self.assertEqual(sp.poster_lines(spec),
                         ("BEGIN YOUR", "DAY IN QUIET", "PRAYER WITH THE MORNING ALTAR", ""))

    def test_a_complete_sub_line_keeps_its_pill(self):
        spec = {"poster": ["ANGELS STAND WATCH", "AROUND YOUR BED", "PSALM 91:11-12",
                           "ANGELIC NIGHT GUARD"]}
        self.assertEqual(sp.poster_lines(spec)[2:], ("PSALM 91:11-12", "ANGELIC NIGHT GUARD"))

    def test_short_specs_miss_at_most_one_line(self):
        spec = {"poster": ["ONE", "TWO"]}
        h1, h2, sub, tag = sp.poster_lines(spec)
        self.assertEqual((h1, h2, sub, tag), ("ONE", "TWO", "", ""))

    def test_title_fallback_keeps_numbers_and_currency(self):
        lines = sp.lines_from_title(
            "Say this: How Enron faked $70 billion in plain sight #Shorts", "")
        self.assertIn("$70", " ".join(lines))
        self.assertIn("BILLION", " ".join(lines))
        self.assertNotIn("SAY THIS", " ".join(lines))

    def test_title_fallback_reads_the_scripture(self):
        lines = sp.lines_from_title(
            "Say this: Psalm 91 prayer before you sleep | Divine protection", "")
        self.assertEqual(lines[2], "DIVINE PROTECTION")


class TestChannelVoice(unittest.TestCase):
    def test_each_channel_gets_its_own_daypart(self):
        self.assertEqual(sp.grade_for("secret-place"), "night")
        self.assertEqual(sp.grade_for("prayer2"), "dawn")
        self.assertEqual(sp.grade_for("prayer3"), "noon")
        self.assertEqual(sp.kicker_for("secret-place"), "PRAYER BEFORE SLEEP")
        self.assertEqual(sp.kicker_for("prayer2"), "BEGIN YOUR DAY IN PRAYER")
        self.assertEqual(sp.kicker_for("prayer3"), "PAUSE AND PRAY AT NOON")

    def test_a_specs_channel_wins_over_the_callers_default(self):
        """A Morning Altar Short must never be drawn in the pre-sleep grade."""
        spec = json.loads((SPEC_DIR / "short-morningmark1v35.json").read_text(encoding="utf-8"))
        self.assertEqual(spec.get("channel"), "prayer2")
        with tempfile.TemporaryDirectory() as tmp:
            report = sp.poster_for_spec("short-morningmark1v35", Path(tmp) / "p.jpg")
        self.assertEqual(report.grade, "dawn")


class TestPosterEntryPoints(unittest.TestCase):
    def test_spec_key_path_renders_the_authored_lockup(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = sp.poster_for_spec("short-psalm91v11", Path(tmp) / "p.jpg")
        self.assertEqual(report.lines[:2], ("ANGELS STAND WATCH", "AROUND YOUR BED"))
        self.assertEqual(report.kicker, "PRAYER BEFORE SLEEP")

    def test_slug_without_a_spec_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(sp.poster_for_slug("psalm-91-prayer-of-protection",
                                                 Path(tmp) / "p.jpg"))

    def test_missing_spec_raises_rather_than_rendering_an_empty_card(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                sp.poster_for_spec("short-nope", Path(tmp) / "p.jpg")


class TestUploadGate(unittest.TestCase):
    """`apply_shorts_thumbnail` must be able to say "not yet" and "not proven"."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "poster.jpg"
        Image.new("RGB", (108, 192), (10, 30, 70)).save(self.path, quality=80)

    def tearDown(self):
        self._tmp.cleanup()

    def test_ok_only_when_youtube_reports_the_shorts_variant(self):
        client = _fake_client(thumbs={"default": {}, "shortsAspectRatio": {"width": 1080}})
        status = upload.apply_shorts_thumbnail("vid1", self.path, youtube=client,
                                               sleep=lambda _s: None)
        self.assertEqual(status, "ok")

    def test_unverified_when_the_variant_is_absent(self):
        client = _fake_client(thumbs={"default": {}, "medium": {}})
        status = upload.apply_shorts_thumbnail("vid1", self.path, youtube=client,
                                              sleep=lambda _s: None)
        self.assertTrue(status.startswith("unverified"), status)

    def test_defers_while_youtube_is_still_processing(self):
        calls: list[str] = []
        client = _fake_client(processing="processing", set_calls=calls)
        status = upload.apply_shorts_thumbnail("vid1", self.path, youtube=client,
                                              sleep=lambda _s: None, wait_seconds=0)
        self.assertEqual(status, "deferred_processing_processing")
        self.assertEqual(calls, [], "never spend quota on a video still being processed")

    def test_rate_limit_is_retried_before_giving_up(self):
        class _Rate(Exception):
            pass

        calls: list[str] = []
        client = _fake_client(set_error=_Rate("uploadRateLimitExceeded"), set_calls=calls)
        # 429 twice with backoff, then give up and say why (never silently "ok")
        status = upload.apply_shorts_thumbnail("vid1", self.path, youtube=client,
                                               sleep=lambda _s: None)
        self.assertEqual(len(calls), 3)
        self.assertIn("_Rate", status)

    def test_a_missing_file_is_skipped_without_calling_anything(self):
        status = upload.apply_shorts_thumbnail("vid1", Path(self._tmp.name) / "nope.jpg",
                                              youtube=_fake_client())
        self.assertEqual(status, "skipped")


if __name__ == "__main__":
    unittest.main()


class TestAnOverWideHeroIsFoldedNotDropped(unittest.TestCase):
    """Forty-one Shorts could not make a poster on 26 November 2026.

    `_fit` stops shrinking at a 64px floor, so a hero line wider than the safe box
    stayed wider than the safe box and the poster refused: correct behaviour (a
    muddy poster is worse than none) with the wrong cause — the authoring step had
    no width limit. The fold must re-wrap the words and keep every one of them.
    """

    def test_a_too_wide_line_is_split_at_word_boundaries(self):
        from pipeline.shorts_poster import fold_hero

        self.assertEqual(fold_hero("IS FROM EVERLASTING TO EVERLASTING"),
                         ["IS FROM EVERLASTING", "TO EVERLASTING"])

    def test_a_fitting_line_is_left_alone(self):
        from pipeline.shorts_poster import fold_hero

        self.assertEqual(fold_hero("EVERLASTING"), ["EVERLASTING"])

    def test_the_budget_is_measured_not_counted(self):
        """Eleven capital W's are as wide as twenty-one letters of a real hero.

        Any single character budget is therefore wrong in one direction or the
        other: `HERO_MAX_CHARS = 22` still let an 845px line into a 796px box.
        The honest rule is the one the renderer enforces — measure the pixels.
        """
        from pipeline.shorts_poster import _measure_width, fold_hero

        wide, narrow = "W" * 12, "THE MERCY OF THE LORD"
        self.assertGreater(_measure_width(wide, 64), _measure_width(narrow, 64))
        # The shorter string is NOT the one that has to wrap.
        self.assertEqual(len(fold_hero(wide)), 1)
        self.assertEqual(len(fold_hero(narrow)), 2)

    def test_folding_never_loses_a_word(self):
        """The first version of the fold kept two lines and dropped the rest.

        `IS FROM EVERLASTING TO EVERLASTING` was painted as
        `IS FROM EVERLASTING TO` — a poster that reads fine and says the wrong
        thing, which is worse than one that refuses.
        """
        from pipeline.shorts_poster import fold_hero

        source = "THE MERCY OF THE LORD IS FROM EVERLASTING TO EVERLASTING"
        folded = fold_hero(source)
        self.assertEqual(" ".join(folded).split(), source.split())

    def test_every_spec_in_the_repository_can_make_a_poster(self):
        import json
        from pathlib import Path

        from pipeline.shorts_poster import PosterRefused, poster_for_spec

        root = Path(__file__).resolve().parents[1]
        refused = []
        with tempfile.TemporaryDirectory() as tmp:
            for path in sorted((root / "content" / "shorts-scripts").glob("*.json")):
                try:
                    report = poster_for_spec(path, Path(tmp) / f"{path.stem}.jpg")
                except PosterRefused as exc:
                    refused.append((path.stem, str(exc)[:70]))
                    continue
                self.assertTrue(all(report.lines), f"{path.stem} lost a poster line")
        self.assertEqual(refused, [], f"{len(refused)} Shorts cannot make a poster")

    def test_the_widest_hero_line_fits_the_safe_zone(self):
        from PIL import Image, ImageDraw

        from pipeline.shorts_poster import SAFE_BOX, _font, fold_hero

        measure = ImageDraw.Draw(Image.new("RGB", (1080, 1920)))
        inner = (SAFE_BOX[2] - SAFE_BOX[0]) - 140
        for source in ("IS FROM EVERLASTING TO EVERLASTING",
                       "THE SHADOW OF THE ALMIGHTY",
                       "GOD MULTIPLIES YOUR EFFORT"):
            for line in fold_hero(source):
                width = measure.textlength(line, font=_font(64))
                self.assertLessEqual(width, inner, f"{line!r} is {width:.0f}px, > {inner}px")


class TestTheFoldIsTheOnlyWayWordsMove(unittest.TestCase):
    def test_a_word_wider_than_the_box_is_left_whole(self):
        """Better a line that shrinks than a word broken in half."""
        from pipeline.shorts_poster import fold_hero

        self.assertEqual(fold_hero("EXTRAORDINARILY EXTRAORDINARILY"),
                         ["EXTRAORDINARILY", "EXTRAORDINARILY"])
