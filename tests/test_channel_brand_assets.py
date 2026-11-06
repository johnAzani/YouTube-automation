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
