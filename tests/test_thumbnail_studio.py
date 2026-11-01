"""The thumbnail constraints are numeric, so they are testable.

Every threshold below comes from the research in docs/THUMBNAIL_RESEARCH.md:
thumbnail is the highest-leverage CTR decision on the platform, 70-75% of views
are mobile, and a thumbnail renders as small as 168x94 px in the feed. These
tests fail if a future edit makes the hero smaller than mobile-legible, pushes
text into the duration badge, or ships an image YouTube would reject.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline import thumbnail_studio as ts  # noqa: E402
from pipeline.script_doc import parse_script  # noqa: E402

HERO = "THE LORD IS YOUR KEEPER"


class TestMeasuredConstraints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path("/tmp/thumb_studio_tests")
        cls.tmp.mkdir(parents=True, exist_ok=True)
        cls.reports = ts.generate_style_pack(HERO, cls.tmp)

    def test_three_variants_for_test_and_compare(self):
        # YouTube's Test & Compare takes up to three thumbnails.
        self.assertEqual(len(self.reports), 3)
        self.assertEqual([r.variant for r in self.reports], ["main", "b", "c"])
        for report in self.reports:
            self.assertTrue(report.path.is_file())

    def test_youtube_specs(self):
        for report in self.reports:
            img = Image.open(report.path)
            self.assertEqual(img.size, (1280, 720), "16:9 at 1280x720")
            self.assertEqual(img.mode, "RGB")
            self.assertLess(report.file_kb, 2048, "YouTube rejects thumbnails over 2 MB")

    def test_hero_is_mobile_legible(self):
        for report in self.reports:
            self.assertGreaterEqual(report.hero_px, ts.MIN_HERO_PX,
                                    f"{report.variant}: hero below the legibility floor")
            self.assertLessEqual(report.words, ts.MAX_HERO_WORDS,
                                 f"{report.variant}: more words than the feed can read")
            self.assertLessEqual(report.lines, ts.MAX_LINES)

    def test_contrast_meets_the_a_b_tested_threshold(self):
        for report in self.reports:
            self.assertGreaterEqual(report.contrast, ts.MIN_CONTRAST,
                                    f"{report.variant}: contrast {report.contrast:.1f}")

    def test_text_stays_out_of_the_duration_badge_and_safe_area(self):
        for report in self.reports:
            self.assertTrue(report.badge_zone_ok, f"{report.variant}: detail under the badge")
            self.assertTrue(report.safe_zone_ok, f"{report.variant}: text outside safe area")

    def test_frame_is_occupied_not_empty_card_chrome(self):
        """The old card left ~40% of the frame empty and its type was 82 px.

        'Legible ink' = bright/gold pixels, i.e. type and focal art that survives the
        downscale to 168 px. The old design measured 5.6% of the frame; anything that
        regresses toward that is a scroll-past.
        """
        from pipeline.thumbnail import generate_thumbnail_variants
        queue_like = parse_script(ROOT / "content" / "published" /
                                  "0010-psalm-121-he-who-keeps-you-will-neither-slumber-no.md")
        legacy = generate_thumbnail_variants(queue_like, None, self.tmp)[0]
        legacy_ink = _legible_ink_share(legacy)
        new_ink = _legible_ink_share(self.reports[0].path)
        self.assertGreater(new_ink, 0.10, f"new thumbnail only {new_ink:.1%} legible ink")
        self.assertGreater(new_ink, legacy_ink * 2,
                           f"new {new_ink:.1%} vs old {legacy_ink:.1%} legible ink")

    def test_hero_type_is_taller_than_the_old_generator(self):
        # The old render_studio_thumbnail used an 82 px hero, which is below the
        # mobile-legibility floor at 1280x720 (research: >= ~70 px cap height).
        for report in self.reports:
            self.assertGreater(report.hero_px, 82)
            self.assertGreaterEqual(report.hero_px / ts.CANVAS[1], 0.13)


class TestHeroSelection(unittest.TestCase):
    def test_hero_never_exceeds_the_word_budget(self):
        hero = ts.choose_hero(text="Psalm 121: He Who Keeps You Will Neither Slumber Nor Sleep")
        self.assertLessEqual(len(hero.split()), ts.MAX_HERO_WORDS)
        self.assertEqual(hero, hero.upper())

    def test_hero_prefers_the_script_thumb_text(self):
        doc = parse_script(ROOT / "content" / "published" /
                           "0010-psalm-121-he-who-keeps-you-will-neither-slumber-no.md")
        self.assertEqual(ts.choose_hero(doc), "THE LORD IS YOUR KEEPER")

    def test_hero_falls_back_when_nothing_is_set(self):
        self.assertTrue(ts.choose_hero(text="").strip())

    def test_long_words_still_fit_three_lines(self):
        img = Image.new("RGB", ts.CANVAS)
        draw = ImageDraw.Draw(img)
        font, lines, _ = ts.layout_hero(draw, "PROTECTION", ts.SAFE_BOX)
        self.assertEqual(font.size >= ts.MIN_HERO_PX, True)
        self.assertLessEqual(len(lines), ts.MAX_LINES)


class TestColourMaths(unittest.TestCase):
    def test_contrast_ratio_is_wcag_correct(self):
        self.assertAlmostEqual(ts.contrast_ratio((255, 255, 255), (0, 0, 0)), 21.0, places=1)
        self.assertAlmostEqual(ts.contrast_ratio((0, 0, 0), (0, 0, 0)), 1.0, places=2)
        white_on_gold = ts.contrast_ratio((255, 255, 255), (255, 214, 64))
        self.assertLess(white_on_gold, 1.6, "white on gold is not a legible pairing")

    def test_relative_luminance_ordering(self):
        self.assertGreater(ts.relative_luminance((255, 255, 255)),
                           ts.relative_luminance((255, 214, 64)))
        self.assertGreater(ts.relative_luminance((255, 214, 64)),
                           ts.relative_luminance((10, 22, 48)))


def _legible_ink_share(path: Path) -> float:
    """Share of the frame that is bright white type or gold accent or focal art.

    Cheap proxy for "this frame has something to look at at 168 px", evaluated on a
    half-scale render so the metric matches what a phone actually shows.
    """
    img = Image.open(path).convert("RGB").resize((640, 360))
    total = 0
    for r, g, b in img.getdata():
        lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
        if lum > 170 or (r > 190 and g > 150 and b < 130):
            total += 1
    return total / (640 * 360)


if __name__ == "__main__":
    unittest.main()
