"""Titles, openings and retention rules shared by every channel.

Measured on 13 November 2026: 78 long-forms published, none with 25 views after
three days. Every title was "<reference> <daypart> Prayer | <channel>" and ten of
the twelve most recent scripts opened with the same welcome to the channel.
"""
from __future__ import annotations

import unittest

from pipeline.brain_equipment.equipment_registry import (
    compile_full_brain_prompt, front_matter_skeleton, get_viewer_first_standard)
from pipeline.channel_capabilities import brand_for
from pipeline.gemini_brain import (normalize_authored_script_markdown,
                                   strip_channel_greeting)
from pipeline.script_doc import MIN_LONGFORM_WORDS

CHANNELS = ("secret-place", "prayer2", "prayer3", "prayer4", "prayer5",
            "prayer6", "prayer7", "prayer8", "prayer9", "prayer10")

HEADING = "## VIEWER-FIRST STANDARD: TITLE, OPENING AND RETENTION (ALL CHANNELS)"


class EveryChannelGetsTheSameStandard(unittest.TestCase):
    def test_standard_is_in_every_channel_prompt_and_comes_last(self):
        standard = get_viewer_first_standard()
        self.assertTrue(standard)
        for channel in CHANNELS:
            with self.subTest(channel=channel):
                prompt = compile_full_brain_prompt(channel)
                self.assertIn(HEADING, prompt)
                self.assertTrue(prompt.rstrip().endswith(standard))
                self.assertGreater(prompt.index(HEADING), prompt.index("DOCOGA REELS v2"))

    def test_standard_names_no_channel(self):
        standard = get_viewer_first_standard()
        for channel in CHANNELS:
            self.assertNotIn(brand_for(channel).display_name, standard)

    def test_old_title_template_is_gone_from_the_skeleton(self):
        for channel in CHANNELS:
            skeleton = front_matter_skeleton(channel)
            self.assertNotIn("<Morning/Midday/Night> Prayer", skeleton)
            self.assertIn("the listener's need", skeleton)
            self.assertIn("35-70 chars", skeleton)

    def test_the_rules_that_matter_are_stated(self):
        standard = get_viewer_first_standard()
        for rule in (
            "The first 45 characters",
            "35 to 70 characters",
            "Never open with a greeting or a welcome",
            "The channel name is not spoken in the first three sentences",
            "read aloud within the first 45 seconds",
            "Never promise an outcome God has not promised",
            "King James Version",
        ):
            self.assertIn(rule, standard)

    def test_the_standard_forbids_bait_rather_than_teaching_it(self):
        standard = get_viewer_first_standard().lower()
        self.assertIn('no "instant miracle"', standard)
        self.assertIn('never "stay to the end"', standard)


def _script(opening: str, words: int, channel: str = "prayer10") -> str:
    brand = brand_for(channel)
    filler = " ".join(["Lord, teach us to walk in Your wisdom today."] * (words // 9 + 1))
    return (
        "---\n"
        "id: '0999'\n"
        f"title: \"When You Don't Know What to Do: James 1:5 {brand.title_suffix}\"\n"
        "slug: when-you-dont-know-what-to-do-james-1-5\n"
        "status: approved\n"
        f"channel: {channel}\n"
        "format: longform\n"
        "niche: faith and prayer\n"
        "thumb_text: ASK HE GIVES\n"
        "---\n\n"
        "## Scene 1 — If Any of You Lack Wisdom\n\n"
        f"{opening} There are days when the honest prayer is simply this: Lord, I do "
        "not know what to do.\n\n"
        f"{filler}\n\n"
        "## Scene 2 — A God Who Gives\n\n"
        "He giveth to all men liberally, and upbraideth not.\n"
    )


class GreetingIsRemovedAtAuthoring(unittest.TestCase):
    NAME = "The Guided Path"
    BODY = ("## Scene 1 — If Any of You Lack Wisdom\n\n"
            "{opening} There are days when the honest prayer is simply this: Lord, "
            "I do not know what to do.\n\nJames was writing to believers.\n\n"
            "## Scene 2 — A God Who Gives\n\nHe giveth liberally.\n")

    def _body(self, opening: str) -> str:
        return self.BODY.format(opening=opening)

    def test_plain_welcome_is_dropped_and_the_next_sentence_opens(self):
        for opening in (
            "Grace and peace to you, and welcome to The Guided Path.",
            "Grace, courage, and unshakable peace be unto you, and welcome to The Guided Path.",
            "Beloved in Christ, welcome to The Guided Path.",
            "Welcome to The Guided Path.",
        ):
            with self.subTest(opening=opening):
                out = strip_channel_greeting(self._body(opening), self.NAME)
                self.assertNotIn("welcome to", out.lower())
                self.assertIn("## Scene 1 — If Any of You Lack Wisdom\n\nThere are days", out)
                self.assertIn("## Scene 2 — A God Who Gives", out)

    def test_an_opening_about_the_listener_is_untouched(self):
        body = self._body("Perhaps you have come with a decision in front of you.")
        self.assertEqual(strip_channel_greeting(body, self.NAME), body)

    def test_another_channels_name_is_not_this_functions_business(self):
        body = self._body("Grace and peace to you, and welcome to The Guided Path.")
        self.assertEqual(strip_channel_greeting(body, "The Morning Altar"), body)

    def test_a_long_greeting_that_carries_the_situation_is_kept(self):
        opening = ("Grace and peace to you who have lain awake since two in the morning "
                   "turning one decision over and over and over again in the dark, and "
                   "welcome to The Guided Path.")
        body = self._body(opening)
        self.assertEqual(strip_channel_greeting(body, self.NAME), body)

    def test_a_later_welcome_is_not_touched(self):
        body = self._body("Lord, I do not know what to do.").replace(
            "James was writing to believers.",
            "Grace and peace to you, and welcome to The Guided Path.")
        self.assertEqual(strip_channel_greeting(body, self.NAME), body)

    def test_never_cuts_a_script_below_the_production_floor(self):
        body = self._body("Grace and peace to you, and welcome to The Guided Path.")
        self.assertEqual(strip_channel_greeting(body, self.NAME, min_words=10_000), body)

    def test_authoring_normaliser_applies_it_on_a_full_length_script(self):
        text = _script("Grace and peace to you, and welcome to The Guided Path.",
                       MIN_LONGFORM_WORDS + 150)
        out = normalize_authored_script_markdown(text, channel_id="prayer10")
        self.assertNotIn("welcome to The Guided Path", out)
        self.assertIn("\n\nThere are days when the honest prayer", out)

    def test_authoring_normaliser_keeps_it_when_the_script_is_at_the_floor(self):
        text = _script("Grace and peace to you, and welcome to The Guided Path.", 200)
        out = normalize_authored_script_markdown(text, channel_id="prayer10")
        self.assertIn("welcome to The Guided Path", out)


if __name__ == "__main__":
    unittest.main()


class ThumbnailLineStaysTheModelsOwnWords(unittest.TestCase):
    """On 13 November two jobs authored in one pass both got "PERFECT PEACE"."""

    def _clamp(self, text: str) -> str:
        from pipeline.gemini_brain import _clamp_thumb_text_for_ctr
        return _clamp_thumb_text_for_ctr(text, "Family Prayer")

    def test_a_line_that_fits_is_kept_whole_including_four_words(self):
        for line in ("ASK FOR WISDOM", "A BLESSED HOME", "A HEDGE AROUND US",
                     "WORK UNTO THE LORD", "NO WEAPON SHALL PROSPER"):
            self.assertEqual(self._clamp(line), line)

    def test_a_line_too_wide_is_cut_to_its_own_words_not_replaced(self):
        for line in ("GOD GUARDS OUR HOME", "HE BLESSES THE HABITATION OF THE JUST",
                     "HEDGE OF PROTECTION AROUND MY HOUSEHOLD"):
            with self.subTest(line=line):
                out = self._clamp(line)
                self.assertNotEqual(out, "PERFECT PEACE")
                self.assertIn(out, line, "the cut must be a contiguous part of the line")

    def test_a_cut_never_ends_on_a_dangling_word(self):
        for line in ("GOD GUARDS OUR HOME", "HE BLESSES THE HABITATION OF THE JUST",
                     "TRUST IN THE EVERLASTING", "REST UNDER HIS FEATHERS TONIGHT"):
            with self.subTest(line=line):
                out = self._clamp(line)
                if out != line:
                    self.assertNotIn(out.split()[-1],
                                     {"THE", "OF", "OUR", "MY", "HIS", "UNTO", "IN", "A"})

    def test_two_different_lines_do_not_collapse_into_one(self):
        self.assertNotEqual(self._clamp("HEDGE OF PROTECTION AROUND MY HOUSEHOLD"),
                            self._clamp("HE BLESSES THE HABITATION OF THE JUST"))

    def test_empty_input_still_yields_a_line(self):
        self.assertTrue(self._clamp(""))
