import unittest

from pipeline.prayer_pacing import pacing_notes


class PrayerPacingTests(unittest.TestCase):
    def test_short_prayer_is_not_flagged(self):
        self.assertEqual(pacing_notes("Lord, help me listen. Give me patience. Amen. Amen."), [])

    def test_flags_long_sentences_repeated_prose_and_teasers_without_echoing_text(self):
        phrase = "Give me the patience to answer with care and kindness today."
        notes = pacing_notes(" ".join([phrase, phrase.upper(), "word " * 41 + ".", "Don’t scroll."]))
        self.assertEqual(len(notes), 3)
        self.assertIn("1 sentence(s) over 40 words", notes[0])
        self.assertIn("1 repeated sentence(s)", notes[1])
        self.assertNotIn(phrase, " ".join(notes))
