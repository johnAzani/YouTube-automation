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
    """A phone crops the banner to its centre 1546 x 423 and scales that up.

    Measured from two screenshots of the live channel (2026-11-06, 1080 x 2400
    Android). The card is 3.63 : 1, but it does not show the whole 2560 width: the
    wordmark is 1091 px wide in the file and 699 px wide in a 984 px card, so the
    card is showing 984 * 1091 / 699 = 1535 px of the middle. Fitting candidate
    crops to the screenshot agreed (MAE 7.6 at 1526 x 443; 11+ at 2560 x 705).

    The first fix read the card's ratio alone, assumed the full width, and left the
    sun straddling the edge of the real window — on the phone, a gold crescent in
    the rounded corner. Type inside the box is not enough; *nothing hard* may cross
    its edge.
    """

    #: The measured window, plus two plausible neighbouring ones, so a slightly
    #: different card size on another device cannot reintroduce a sliced shape.
    WINDOWS = ((1546, 423), (1520, 400), (1600, 450))

    @classmethod
    def setUpClass(cls):
        cls.banner = Image.open(MEDIA / "midday-watch-banner.png").convert("RGB")
        cls.palette = assets.PALETTES["midday-watch"]

    def window(self, size):
        return self.banner.crop(assets.phone_crop_box(self.banner.size, size))

    def test_the_window_is_the_safe_area_not_the_aspect_ratio(self):
        self.assertEqual(assets.PHONE_CROP, (1546, 423))
        safe_w, safe_h = assets.BANNER_SAFE
        self.assertLess(safe_w, assets.PHONE_CROP[0])
        self.assertLess(safe_h, assets.PHONE_CROP[1])

    def test_the_type_sits_wholly_inside_the_window(self):
        """Everything a viewer must read is inside the crop, with room to spare."""
        w, h = self.banner.size
        box = assets.phone_crop_box(self.banner.size)
        left, top = box[0], box[1]
        px = self.banner.load()
        xs, ys = [], []
        for y in range(top, top + assets.PHONE_CROP[1]):
            for x in range(left, left + assets.PHONE_CROP[0]):
                r, g, b = px[x, y]
                if r > 235 and g > 235 and b > 225:      # the wordmark, in Ivory
                    xs.append(x - left)
                    ys.append(y - top)
        self.assertTrue(xs, "no wordmark inside the phone window")
        self.assertGreater(min(xs), 40)
        self.assertLess(max(xs), assets.PHONE_CROP[0] - 40)
        self.assertGreater(min(ys), 40)
        self.assertLess(max(ys), assets.PHONE_CROP[1] - 40)

    def test_no_sun_or_tower_is_visible_in_the_window(self):
        """They live outside it on purpose — a shape cut by the edge is the bug."""
        sun_rgb = self.palette["sun"]
        shadow = self.palette["shadow"]
        for size in self.WINDOWS:
            with self.subTest(window=size):
                win = self.window(size)
                px = win.load()
                # Look only right of the type block: the gold rule and the verse are
                # drawn in the sun colour too, and they are meant to be in the window.
                start_x = (size[0] + assets.BANNER_SAFE[0]) // 2 + 8
                sun = shadow_hits = 0
                for y in range(0, win.height, 2):
                    for x in range(start_x, win.width, 2):
                        p = px[x, y]
                        if p == shadow:
                            shadow_hits += 1
                        elif p == sun_rgb:
                            sun += 1
                self.assertEqual(sun, 0, "the sun is cut by the phone window's edge")
                self.assertEqual(shadow_hits, 0, "the tower is cut by the window's edge")

    def test_the_window_edges_are_clean_sky(self):
        """No hard shape may touch the crop: the corner of the card must be sky."""
        w, h = self.banner.size
        left, top, right, bottom = assets.phone_crop_box(self.banner.size)
        win = self.banner.crop((left, top, right, bottom))
        px = win.load()
        ring = 6
        for y in range(win.height):
            for x in range(win.width):
                if ring <= x < win.width - ring and ring <= y < win.height - ring:
                    continue
                p = px[x, y]
                bright = sum(p) / 3
                # Warm haze at the foot of the card is deliberate; a disc, a tower or
                # a letterform touching the edge is not.
                self.assertLess(bright, 150, f"something hard at the window edge ({x},{y})")
                self.assertNotEqual(p, self.palette["sun"], f"sun at the edge ({x},{y})")
                self.assertNotEqual(p, self.palette["shadow"], f"tower at the edge ({x},{y})")

    def test_the_scenery_survives_the_16_9_frame(self):
        """Outside the window the artwork must still be a scene, not a void."""
        px = self.banner.load()
        sun = self.palette["sun"]
        shadow = self.palette["shadow"]
        cx = int(self.banner.width * 0.838)
        cy = int(self.banner.height * 0.140)
        r = int(self.banner.width * 0.051)
        # sample the sun's ring, not its brass centre
        self.assertEqual(px[cx + int(r * 0.8), cy], sun,
                         "no sun in the sky the TV shows")
        tower_x = int(self.banner.width * 0.852)
        tower_y = int(self.banner.height * 0.640)   # the shaft, above its foot
        self.assertEqual(px[tower_x, tower_y], shadow,
                         "no tower on the ground the TV shows")


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
