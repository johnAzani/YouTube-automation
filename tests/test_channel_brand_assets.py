"""The third channel's brand assets: the right sizes, the documented palette.

YouTube's crops are the reason this is a test and not a note. A banner whose text
sits outside the centre 1235x338 is cropped on every phone; an avatar drawn to the
edges loses its mark to the circular crop; a "transparent" watermark that ships with
a white background sits as a white square in the corner of every video. None of that
is visible on the machine where the file is made.
"""
from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools import make_channel_brand_assets as assets

ROOT = Path(__file__).resolve().parents[1]
MEDIA = ROOT / "docs" / "media"
DOC = ROOT / "docs" / "MIDDAY_WATCH_BRANDING.md"


class TestTheAssetsAreTheRightShape(unittest.TestCase):
    def test_avatar_is_square_800(self):
        im = Image.open(MEDIA / "midday-watch-avatar.png")
        self.assertEqual(im.size, (800, 800))

    def test_banner_is_2560_by_1440(self):
        im = Image.open(MEDIA / "midday-watch-banner.png")
        self.assertEqual(im.size, (2560, 1440))

    def test_watermark_is_transparent_150(self):
        im = Image.open(MEDIA / "midday-watch-watermark.png")
        self.assertEqual(im.size, (150, 150))
        self.assertEqual(im.mode, "RGBA")
        self.assertEqual(im.getpixel((0, 0))[3], 0,
                         "a watermark with an opaque corner draws a white square on every video")

    def test_thumbnail_template_is_16_9(self):
        im = Image.open(MEDIA / "midday-watch-thumbnail-template.png")
        self.assertEqual(im.size, (1280, 720))

    def test_the_safe_box_is_youtubes_not_ours(self):
        """Mobile shows only the centre 1235 x 338 of a 2560 x 1440 banner."""
        self.assertEqual(assets.BANNER_SAFE, (1235, 338))
        self.assertLess(assets.BANNER_SAFE[0], assets.BANNER[0])
        self.assertLess(assets.BANNER_SAFE[1], assets.BANNER[1])

    def test_a_long_channel_name_still_fits_the_safe_box(self):
        """The title shrinks rather than spilling out of the mobile crop."""
        wide = dict(assets.PALETTES["midday-watch"])
        wide["name"] = "THE MIDDAY WATCH AND EVENING VIGIL"
        image = assets.make_banner(wide)
        self.assertEqual(image.size, assets.BANNER)


class TestTheBannerSurvivesTheCropAPhoneShows(unittest.TestCase):
    """The band a phone shows is taller than the box the spec calls mobile-safe.

    Photographed on a 1080x2400 Android phone (2026-11-06, the live channel): the
    banner card renders 1005x295 px = 3.41:1, which is the centre 2560x753 of the
    file — 139 px taller than the 1546x423 TV band and 415 px taller than the
    1235x338 safe box. The first upload placed the sun at y=0.255h and the horizon
    at y=0.802h, so on the phone the disc was sliced by the top edge (a gold sliver
    in the rounded corner) and the tower rose out of nothing as a black notch. All
    of the type was inside the safe box; none of it was the problem.
    """

    RATIOS = (assets.PHONE_CROP_RATIO, 3.65)   # the phone, and YouTube's TV band

    @classmethod
    def setUpClass(cls):
        cls.banner = Image.open(MEDIA / "midday-watch-banner.png").convert("RGB")
        cls.palette = assets.PALETTES["midday-watch"]

    def band(self, ratio):
        return self.banner.crop(assets.phone_crop_box(self.banner.size, ratio))

    def test_the_phone_band_is_taller_than_the_safe_box(self):
        """Two different boxes: the type fits the safe box, the scenery the band."""
        band = self.band(assets.PHONE_CROP_RATIO)
        self.assertEqual(band.width, assets.BANNER[0])
        self.assertGreater(band.height, assets.BANNER_SAFE[1],
                           "a phone shows a taller band than the 1235x338 safe box")

    def test_the_sun_disc_is_whole_inside_the_band(self):
        """A disc touching an edge is the sliver that made the first upload look broken."""
        sun_rgb = self.palette["sun"]
        for ratio in self.RATIOS:
            with self.subTest(ratio=ratio):
                band = self.band(ratio)
                w, h = band.size
                # Only the right-hand third: the gold rule and the verse sit left of it.
                region = band.crop((int(w * 0.70), 0, w, h)).load()
                xs, ys = [], []
                for y in range(0, h, 2):
                    for x in range(0, w - int(w * 0.70), 2):
                        if region[x, y] == sun_rgb:
                            xs.append(x)
                            ys.append(y)
                self.assertTrue(xs, "no sun disc in the right-hand third of the banner")
                left, right = min(xs), max(xs)
                top, bottom = min(ys), max(ys)
                self.assertGreater(left, 24, "sun disc touches the left of the band")
                self.assertLess(right, w - int(w * 0.70) - 24, "sun disc is cut on the right")
                self.assertGreater(top, 24, "sun disc is sliced by the top edge of the band")
                self.assertLess(bottom, h - 24, "sun disc is sliced by the bottom edge")
                aspect = (right - left) / max(1, bottom - top)
                self.assertGreater(aspect, 0.85, "the clipped sun is not a disc any more")
                self.assertLess(aspect, 1.15, "the clipped sun is not a disc any more")

    def test_the_ground_is_visible_at_the_foot_of_the_band(self):
        """A tower on a featureless field reads as a floating black notch."""
        for ratio in self.RATIOS:
            with self.subTest(ratio=ratio):
                band = self.band(ratio)
                w, h = band.size
                px = band.load()
                warm = total = 0
                for y in range(h - 12, h):
                    for x in range(0, w, 6):
                        r, g, b = px[x, y]
                        total += 1
                        warm += r > b + 40        # sky is blue; ground is warm
                self.assertGreater(warm / total, 0.95,
                                   "the bottom of the band is sky, not ground")

    def test_the_tower_stands_on_that_ground(self):
        """Its foot must be inside the band, not sawn off by the bottom edge."""
        shadow = self.palette["shadow"]
        for ratio in self.RATIOS:
            with self.subTest(ratio=ratio):
                band = self.band(ratio)
                w, h = band.size
                px = band.load()
                col = int(w * 0.842)
                rows = [y for y in range(h) if px[col, y] == shadow]
                self.assertTrue(rows, "no tower in the band")
                self.assertLess(max(rows), h - 16,
                                "the tower's foot is cut by the bottom edge of the band")


class TestThePaletteIsTheDocumentedOne(unittest.TestCase):
    def test_every_palette_colour_appears_in_the_branding_doc(self):
        palette = assets.PALETTES["midday-watch"]
        doc = DOC.read_text(encoding="utf-8").lower()
        for name, value in palette.items():
            if not isinstance(value, tuple):
                continue
            hex_code = "#{:02x}{:02x}{:02x}".format(*value)
            with self.subTest(colour=name):
                self.assertIn(hex_code, doc,
                              f"{name} is {hex_code} in the generator but not in the doc; "
                              f"the palette must be one documented set")

    def test_the_palette_does_not_collide_with_the_other_channels(self):
        midday = assets.PALETTES["midday-watch"]
        # The Secret Place's midnight set and the Morning Altar's pre-dawn navy.
        others = {(4, 18, 43), (8, 28, 63), (255, 201, 60)}
        for name in ("sky", "panel", "sun"):
            self.assertNotIn(midday[name], others,
                             f"{name} repeats a colour the other channels already own")


class TestTheAboutTextFits(unittest.TestCase):
    def test_about_description_is_under_youtubes_limit(self):
        doc = DOC.read_text(encoding="utf-8")
        about = doc.split("```text")[1].split("```")[0].strip()
        self.assertTrue(about)
        self.assertLessEqual(len(about), 1000,
                             "YouTube truncates the channel description at 1,000 characters")
        self.assertIn("Psalm 55:17", about)

    def test_keywords_are_present_and_within_budget(self):
        doc = DOC.read_text(encoding="utf-8")
        keywords = doc.split("```text")[2].split("```")[0].strip()
        self.assertIn("Midday Prayer", keywords)
        self.assertLess(len(keywords), 500, "YouTube's keyword field is 500 characters")


class TestRedrawingIsDeliberate(unittest.TestCase):
    def test_existing_files_are_not_overwritten_without_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(assets.main(["--channel", "midday-watch", "--out", tmp]), 0)
            target = Path(tmp) / "midday-watch-avatar.png"
            before = target.read_bytes()
            target.write_bytes(b"approved-by-eye")

            assets.main(["--channel", "midday-watch", "--out", tmp])
            self.assertEqual(target.read_bytes(), b"approved-by-eye",
                             "a re-run must not silently replace approved art")

            assets.main(["--channel", "midday-watch", "--out", tmp, "--force"])
            self.assertNotEqual(target.read_bytes(), b"approved-by-eye")
            self.assertEqual(Image.open(target).size, (800, 800))
            del before

    def test_the_doc_names_the_generator(self):
        self.assertIn("tools/make_channel_brand_assets.py", DOC.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()


class TestTheKitCanBeHandedOver(unittest.TestCase):
    """The download has to be the same art as the repo, or it ships the wrong banner.

    A brand kit is a hand-off: it leaves this repository and lands in YouTube
    Studio. A stale archive is worse than no archive — the file that gets uploaded
    is the one in the zip.
    """

    ZIP = MEDIA / "midday-watch-brand-assets.zip"
    KIT = "midday-watch-brand-kit/"

    def _names(self):
        import zipfile

        with zipfile.ZipFile(self.ZIP) as zf:
            return zf.namelist()

    def test_the_archive_exists_and_carries_every_upload(self):
        for name in ("midday-watch-avatar.png", "midday-watch-banner.png",
                     "midday-watch-watermark.png", "midday-watch-thumbnail-template.png",
                     "midday-watch-brand-sheet.png", "MIDDAY_WATCH_BRANDING.md",
                     "THIRD_CHANNEL_SETUP.md", "START_HERE.txt"):
            with self.subTest(item=name):
                self.assertIn(self.KIT + name, self._names())

    def test_the_archive_is_the_art_on_disk(self):
        import zipfile

        with zipfile.ZipFile(self.ZIP) as zf:
            for name in ("avatar", "banner", "watermark", "thumbnail-template", "brand-sheet"):
                filename = f"midday-watch-{name}.png"
                with self.subTest(asset=filename):
                    self.assertEqual(
                        zf.read(self.KIT + filename),
                        (MEDIA / filename).read_bytes(),
                        f"{filename} in the zip is not the file in docs/media — "
                        f"rebuild the kit")

    def test_the_archive_images_are_the_right_sizes(self):
        import io
        import zipfile

        expected = {
            "midday-watch-avatar.png": (800, 800),
            "midday-watch-banner.png": (2560, 1440),
            "midday-watch-watermark.png": (150, 150),
            "midday-watch-thumbnail-template.png": (1280, 720),
        }
        with zipfile.ZipFile(self.ZIP) as zf:
            for name, size in expected.items():
                with self.subTest(asset=name):
                    image = Image.open(io.BytesIO(zf.read(self.KIT + name)))
                    self.assertEqual(image.size, size)

    def test_the_brand_sheet_renders(self):
        sheet = Image.open(MEDIA / "midday-watch-brand-sheet.png")
        self.assertEqual(sheet.size, assets.SHEET)

    def test_the_kit_rebuilds_from_the_generator(self):
        """Every asset in the archive must be reproducible, not hand-staged."""
        import zipfile

        with tempfile.TemporaryDirectory() as tmp:
            built = assets.build_kit(Path(tmp) / "kit.zip", MEDIA, ROOT / "docs")
            with zipfile.ZipFile(built) as zf:
                names = set(zf.namelist())
                self.assertIn(TestTheKitCanBeHandedOver.KIT + "START_HERE.txt", names)
                for name in ("avatar", "banner", "watermark", "thumbnail-template"):
                    filename = f"midday-watch-{name}.png"
                    with self.subTest(asset=filename):
                        self.assertEqual(zf.read(TestTheKitCanBeHandedOver.KIT + filename),
                                         (MEDIA / filename).read_bytes())

    def test_the_doc_points_at_the_download(self):
        doc = DOC.read_text(encoding="utf-8")
        self.assertIn("midday-watch-brand-assets.zip", doc)
        self.assertIn("midday-watch-brand-sheet.png", doc)
