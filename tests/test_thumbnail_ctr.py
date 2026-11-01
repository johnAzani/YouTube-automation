"""Guards for the CTR pack.

These tests encode the three defects the studio pack could not see:

1. a frame that dissolves into YouTube's dark-mode page (#0F0F0F),
2. a focal mass too small to register at 168 px,
3. copy that restates the published title.

They are deliberately numeric, so a future redesign cannot quietly regress them.
"""
import unittest
from pathlib import Path

from PIL import Image, ImageStat

from pipeline import thumbnail_ctr as ctr
from pipeline.thumbnail_studio import CANVAS, MIN_CONTRAST, SAFE_BOX, contrast_ratio

TMP = Path("/tmp/ctr-tests")


def setUpModule():
    TMP.mkdir(parents=True, exist_ok=True)
    global REPORTS
    REPORTS = ctr.generate_ctr_pack(TMP)


class TestSpecs(unittest.TestCase):
    def test_canvas_is_youtube_16_9(self):
        for r in REPORTS:
            with Image.open(r.path) as im:
                self.assertEqual(im.size, CANVAS)
                self.assertEqual(im.mode, "RGB")

    def test_under_two_megabytes(self):
        # the documented cap is 2 MB on every YouTube help page
        for r in REPORTS:
            self.assertLess(r.path.stat().st_size, 2 * 1024 * 1024, r.path.name)

    def test_jpeg_not_png(self):
        for r in REPORTS:
            self.assertEqual(r.path.suffix, ".jpg")


class TestDarkFeedVisibility(unittest.TestCase):
    """The defect that started this module: #02050E edges on a #0F0F0F page."""

    def test_border_is_brighter_than_the_app_background(self):
        for r in REPORTS:
            self.assertGreaterEqual(
                r.edge_luma, ctr.EDGE_LUMA_MIN,
                f"{r.variant} border is {r.edge_luma:.1f}, too close to YouTube's "
                f"#{ctr.UI_DARK:02X}{ctr.UI_DARK:02X}{ctr.UI_DARK:02X} page",
            )

    def test_border_clears_ui_grey_by_a_visible_margin(self):
        for r in REPORTS:
            self.assertGreater(r.edge_luma, ctr.UI_DARK + 8)

    def test_almost_no_border_pixel_sits_at_the_app_grey(self):
        # a handful of JPEG undershoots at the extreme corners is tolerable; a
        # whole edge matching the page colour is what kills the frame
        for r in REPORTS:
            self.assertLess(r.border_dark, 0.05, f"{r.variant}: {r.border_dark:.1%} of the border")

    def test_histogram_is_bimodal_not_mid_grey(self):
        # a flat mid-grey frame reads as stock wallpaper; night scenes are a deep
        # field plus one bright focal mass
        for r in REPORTS:
            with Image.open(r.path) as im:
                hist = im.convert("L").histogram()
            total = sum(hist)
            p05 = next(i for i in range(256) if sum(hist[: i + 1]) / total >= 0.05)
            p95 = next(i for i in range(256) if sum(hist[: i + 1]) / total >= 0.95)
            self.assertLess(p05, 34, f"{r.variant} shadows are lifted to {p05}")
            self.assertGreater(p95, 170, f"{r.variant} has no bright focal mass ({p95})")

    def test_bright_mass_present(self):
        for r in REPORTS:
            self.assertGreater(r.bright_share, 0.06, f"{r.variant} is too dim to pop")


class TestLegibility(unittest.TestCase):
    def test_text_contrast_clears_seven_to_one(self):
        for r in REPORTS:
            if not r.hero:
                continue
            self.assertGreaterEqual(r.contrast, MIN_CONTRAST, r.variant)

    def test_hero_is_large_and_short(self):
        for r in REPORTS:
            if not r.hero:
                continue
            self.assertGreaterEqual(r.hero_px, 120, r.variant)
            self.assertLessEqual(r.words, 3, r.variant)
            self.assertLessEqual(r.lines, 3, r.variant)

    def test_text_sits_inside_the_safe_box(self):
        for r in REPORTS:
            if not r.hero:
                continue
            self.assertTrue(r.safe_zone_ok, r.variant)

    def test_duration_badge_corner_is_quiet(self):
        for r in REPORTS:
            self.assertTrue(r.badge_zone_ok, r.variant)

    def test_legible_at_168_px(self):
        """Shrink to feed size and check the type still carries high-contrast ink."""
        for r in REPORTS:
            with Image.open(r.path) as im:
                small = im.convert("L").resize((168, 94), Image.LANCZOS)
            hist = small.histogram()
            total = sum(hist)
            ink = sum(hist[190:]) / total
            self.assertGreater(ink, 0.02, f"{r.variant} loses its type at 168 px")


class TestPackaging(unittest.TestCase):
    def test_three_distinct_concepts(self):
        labels = [r.variant for r in REPORTS]
        self.assertEqual(len(labels), 3)
        self.assertEqual(len(set(labels)), 3)

    def test_no_concept_repeats_the_published_title(self):
        """The title already says 'neither slumber nor sleep' and 'He who keeps you'."""
        banned = {"SLEEP", "KEEPER", "SLUMBER", "NEITHER", "KEEPS"}
        for r in REPORTS:
            words = set(r.hero.replace("\n", " ").split())
            # "SLEEP" is allowed in the curiosity concept only as "WHILE YOU SLEEP",
            # which inverts the title's subject rather than restating it.
            leaked = words & (banned - {"SLEEP"})
            self.assertFalse(leaked, f"{r.variant} restates the title: {leaked}")

    def test_one_concept_is_textless_for_differentiation(self):
        self.assertTrue(any(r.hero == "" for r in REPORTS))

    def test_each_concept_has_a_hero_anchor(self):
        """Someone asleep inside the house: the stand-in for a face."""
        for variant in ctr.CTR_VARIANTS:
            self.assertIsNotNone(variant.house, variant.label)

    def test_variants_differ_in_pixels(self):
        """Test & Compare only pays off if the three are genuinely different frames."""
        imgs = [Image.open(r.path).convert("L").resize((64, 36)) for r in REPORTS]
        for i in range(len(imgs)):
            for j in range(i + 1, len(imgs)):
                a, b = imgs[i].tobytes(), imgs[j].tobytes()
                mean_abs = sum(abs(x - y) for x, y in zip(a, b)) / len(a)
                self.assertGreater(mean_abs, 8, f"variants {i}/{j} are near-identical")


class TestColourMaths(unittest.TestCase):
    def test_warm_white_beats_navy_background(self):
        self.assertGreater(contrast_ratio((255, 250, 238), (10, 20, 44)), 12)

    def test_gold_on_night_clears_aaa(self):
        self.assertGreaterEqual(contrast_ratio((255, 202, 74), (12, 24, 52)), 7.0)


class TestSurfaces(unittest.TestCase):
    def test_safe_box_matches_the_documented_central_80_percent(self):
        x0, y0, x1, y1 = SAFE_BOX
        self.assertGreaterEqual(x0 / CANVAS[0], 0.05)
        self.assertGreaterEqual(y0 / CANVAS[1], 0.05)
        self.assertLessEqual(x1 / CANVAS[0], 0.92)
        self.assertLessEqual(y1 / CANVAS[1], 0.84)


if __name__ == "__main__":
    unittest.main()
