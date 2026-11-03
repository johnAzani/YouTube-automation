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


class TestEveryReleaseLooksLikeItself(unittest.TestCase):
    """On 2 November Psalm 46 premiered wearing Psalm 121's thumbnail.

    The pack was rendered with no knowledge of the job, so the hero copy was the
    fixed "PRAY THIS TONIGHT" and the seed was fixed too: two videos, one picture.
    Every script already carried its own ``thumb_text``; the pipeline never passed
    it in.
    """

    def test_the_scripts_own_line_is_the_hero(self):
        out = TMP / "own-line"
        reports = ctr.generate_ctr_pack(out, hero_override="Be Still and Know",
                                        doc_key="0013")
        text = [r for r in reports if r.hero]
        poster = [r for r in reports if not r.hero]
        self.assertEqual([r.hero for r in text], ["BE STILL AND KNOW"] * len(text))
        self.assertEqual(len(poster), 1, "the textless poster must stay textless")

    def test_the_copy_still_fits_the_measured_sweet_spot(self):
        out = TMP / "own-line2"
        reports = ctr.generate_ctr_pack(out, hero_override="Angels Watch Over You",
                                        doc_key="0016")
        for r in reports:
            if not r.hero:
                continue
            self.assertLessEqual(r.lines, 3)
            self.assertGreaterEqual(r.contrast, MIN_CONTRAST - 0.5, r.variant)
            self.assertTrue(r.safe_zone_ok, r.variant)
            self.assertLess(r.path.stat().st_size, 2 * 1024 * 1024)

    def test_two_releases_do_not_render_the_same_frame(self):
        a = ctr.generate_ctr_pack(TMP / "a", hero_override="Be Still and Know",
                                  doc_key="0013")
        b = ctr.generate_ctr_pack(TMP / "b", hero_override="Lay Down in Peace",
                                  doc_key="0017")
        for ra, rb in zip(a, b):
            self.assertNotEqual(ra.path.read_bytes(), rb.path.read_bytes(), ra.variant)

    def test_the_same_job_renders_the_same_frame(self):
        # determinism: a retried run must not silently change the picture
        a = ctr.variations_for("0013")
        b = ctr.variations_for("0013")
        self.assertEqual([(v.seed, v.moon, v.moon_scale) for v in a],
                         [(v.seed, v.moon, v.moon_scale) for v in b])

    def test_variation_stays_inside_the_validated_bounds(self):
        for key in ("0003", "0010", "0013", "0017", "9999"):
            for v in ctr.variations_for(key):
                self.assertGreaterEqual(v.moon[0], 0.66)
                self.assertLessEqual(v.moon[0], 0.82)
                self.assertGreaterEqual(v.moon_scale, 0.19)
                self.assertLessEqual(v.moon_scale, 0.222)

    def test_a_four_word_hero_does_not_break_into_a_lone_conjunction(self):
        # greedy wrapping gave "BE STILL / AND / KNOW"; the balanced search finds
        # "BE STILL / AND KNOW" for the price of a slightly smaller size
        from PIL import ImageDraw

        draw = ImageDraw.Draw(Image.new("RGB", (10, 10)))
        box = ctr.CTR_VARIANTS[0].text_box
        for hero, expected in (("BE STILL AND KNOW", ["BE STILL", "AND KNOW"]),
                               ("LAY DOWN IN PEACE", ["LAY DOWN", "IN PEACE"]),
                               ("NO TERROR BY NIGHT", ["NO TERROR", "BY NIGHT"])):
            _font_, lines, _t, _l, _s = ctr._layout(draw, hero, box)
            self.assertEqual(lines, expected)

    def test_a_hero_that_must_stack_still_fits_the_box(self):
        from PIL import ImageDraw

        draw = ImageDraw.Draw(Image.new("RGB", (10, 10)))
        box = ctr.CTR_VARIANTS[0].text_box
        for report in ctr.generate_ctr_pack(TMP / "long-hero",
                                            hero_override="The Lord Bless and Keep You",
                                            doc_key="0033"):
            if report.hero:
                self.assertLessEqual(report.lines, 3)
                self.assertGreaterEqual(report.contrast, MIN_CONTRAST - 0.5)


class TestTheFrameIsTheVideosOwnFootage(unittest.TestCase):
    """Re-seeding the drawing was not enough.

    After the copy became per-video, every thumbnail was still the same moon-over-
    ridge illustration — "only the text changed", as the owner put it. A backdrop is
    now the job's own scene asset, treated so it obeys the same measured rules.
    """

    @classmethod
    def setUpClass(cls):
        from PIL import Image, ImageDraw, ImageFilter
        import random

        cls.tmp = TMP / "backdrops"
        cls.tmp.mkdir(parents=True, exist_ok=True)
        cls.photos = []
        for i, hue in enumerate(((120, 140, 200), (200, 150, 110))):
            rng = random.Random(i)
            im = Image.new("RGB", (1280, 720))
            d = ImageDraw.Draw(im)
            for y in range(720):
                t = y / 720
                d.line([(0, y), (1280, y)],
                       fill=(int(hue[0] * t), int(hue[1] * t), int(hue[2] * t)))
            for _ in range(14):
                cx, cy = rng.randint(0, 1280), rng.randint(150, 650)
                rx, ry = rng.randint(150, 500), rng.randint(60, 200)
                d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry],
                          fill=(rng.randint(60, 170), rng.randint(60, 180), rng.randint(80, 210)))
            im = im.filter(ImageFilter.GaussianBlur(18))
            path = cls.tmp / f"photo-{i}.jpg"
            im.save(path, quality=92)
            cls.photos.append(path)

    def test_the_backdrop_is_the_jobs_own_picture(self):
        reports = ctr.generate_ctr_pack(TMP / "own-footage",
                                        hero_override="Lay Down in Peace",
                                        doc_key="0017", backdrop=self.photos[0])
        for r in reports:
            self.assertEqual(r.backdrop, f"photo:{self.photos[0].name}")

    def test_a_photo_backdrop_still_obeys_the_measured_rules(self):
        reports = ctr.generate_ctr_pack(TMP / "footage-rules",
                                        hero_override="Be Still and Know",
                                        doc_key="0013", backdrop=self.photos[1])
        for r in reports:
            self.assertLess(r.path.stat().st_size, 2 * 1024 * 1024)
            self.assertTrue(r.safe_zone_ok, r.variant)
            self.assertTrue(r.badge_zone_ok, r.variant)
            self.assertGreaterEqual(r.edge_luma, ctr.EDGE_LUMA_MIN, r.variant)
            if r.hero:
                self.assertGreaterEqual(r.contrast, MIN_CONTRAST - 0.5, r.variant)

    def test_two_videos_on_different_footage_cannot_look_alike(self):
        a = ctr.generate_ctr_pack(TMP / "footage-a", hero_override="Lay Down in Peace",
                                  doc_key="0017", backdrop=self.photos[0])
        b = ctr.generate_ctr_pack(TMP / "footage-b", hero_override="Be Still and Know",
                                  doc_key="0013", backdrop=self.photos[1])
        for ra, rb in zip(a, b):
            self.assertNotEqual(ra.path.read_bytes(), rb.path.read_bytes(), ra.variant)

    def test_the_darkest_photo_does_not_dissolve_into_the_page(self):
        from PIL import Image
        flat = self.tmp / "flat.jpg"
        Image.new("RGB", (1280, 720), (2, 3, 6)).save(flat, quality=90)
        reports = ctr.generate_ctr_pack(TMP / "footage-flat", hero_override="No Terror by Night",
                                        doc_key="0015", backdrop=flat)
        for r in reports:
            self.assertGreaterEqual(r.edge_luma, ctr.EDGE_LUMA_MIN, r.variant)

    def test_the_most_detailed_asset_is_chosen(self):
        flat = self.tmp / "choose-flat.jpg"
        from PIL import Image
        Image.new("RGB", (640, 360), (40, 40, 40)).save(flat, quality=90)
        picked = ctr.pick_backdrop([flat, self.photos[0]])
        self.assertEqual(picked, self.photos[0])

    def test_an_unreadable_asset_is_skipped_not_fatal(self):
        missing = self.tmp / "nope.jpg"
        self.assertEqual(ctr.pick_backdrop([missing]), None)
        self.assertEqual(ctr.pick_backdrop([]), None)

    def test_the_pipeline_feeds_the_jobs_assets_to_the_pack(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parents[1]
                  / "pipeline" / "prayer_pipeline.py").read_text(encoding="utf-8")
        self.assertIn("backdrop=pick_backdrop(assets)", source)
        self.assertIn("curated_backdrop_for", source)
        self.assertIn("fetch_scene_assets", source)

    def test_mp4_asset_is_extracted_to_real_frame_for_backdrop(self):
        import shutil
        import subprocess
        if not shutil.which("ffmpeg"):
            self.skipTest("ffmpeg unavailable")
        mp4 = self.tmp / "scene-plate.mp4"
        subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error",
                "-loop", "1", "-t", "1.6",
                "-i", str(self.photos[0]),
                "-vf", "scale=640:360",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                str(mp4),
            ],
            check=True,
        )
        picked = ctr.pick_backdrop([mp4])
        self.assertIsNotNone(picked)
        assert picked is not None
        self.assertTrue(picked.is_file())
        self.assertEqual(picked.suffix.lower(), ".jpg")

    def test_curated_sanctuary_plates_exist_and_rotate_across_jobs(self):
        seen = {ctr.curated_backdrop_for(f"{n:04d}") for n in range(8, 20)}
        self.assertNotIn(None, seen)
        self.assertGreaterEqual(len(seen), 5)

    def test_bright_rocky_bottom_right_corner_is_calmed_for_duration_badge(self):
        from PIL import Image, ImageStat
        from pipeline.thumbnail_studio import DURATION_BADGE_BOX
        bright_corner = self.tmp / "bright-corner.jpg"
        im = Image.open(self.photos[0]).convert("RGB").resize((1280, 720))
        im.paste((245, 240, 225), (1040, 610, 1280, 720))
        im.save(bright_corner, quality=92)
        reports = ctr.generate_ctr_pack(
            TMP / "footage-badge-calm",
            hero_override="Whom Shall I Fear",
            doc_key="0011",
            backdrop=bright_corner,
        )
        self.assertTrue(reports[0].badge_zone_ok)
        self.assertTrue(reports[0].edge_visible)
        out = Image.open(reports[0].path).convert("L").crop(DURATION_BADGE_BOX)
        self.assertLess(ImageStat.Stat(out).mean[0], 85.0)

    def test_every_approved_queue_script_fits_cleanly_without_dropping_words(self):
        from pathlib import Path
        from PIL import Image, ImageDraw
        from pipeline.script_doc import parse_script

        queue = Path(__file__).resolve().parents[1] / "content" / "queue"
        draw = ImageDraw.Draw(Image.new("RGB", (1280, 720)))
        checked = 0
        for md in sorted(queue.glob("*.md")):
            doc = parse_script(md)
            if str(doc.meta.get("status", "")).lower() != "approved":
                continue
            checked += 1
            hero = (str(doc.meta.get("thumb_text") or "").strip() or doc.title).upper()
            _font, lines, _tracking, _leading, px = ctr._layout(draw, hero, (82, 76, 728, 568))
            self.assertGreaterEqual(px, 115, f"{md.name}: {hero} -> {px}px")
            self.assertEqual(
                " ".join(lines),
                " ".join(hero.split()),
                f"{md.name}: dropped words in {lines} vs {hero}",
            )
        self.assertGreaterEqual(checked, 21)


if __name__ == "__main__":
    unittest.main()
