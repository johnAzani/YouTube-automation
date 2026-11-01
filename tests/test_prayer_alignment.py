"""Local speech alignment must accept the tokenisation a recogniser really emits.

Every case below is a real failure from a run of job 0010 on GitHub Actions: a
zero-length word, "for evermore" recognised as "forevermore", and a correctly
transcribed word with a low recogniser probability. The alignment must survive
all three while still refusing timings that are non-monotonic, negative,
non-finite or inferred from text that does not match the script.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline import prayer_alignment as preview  # noqa: E402


def heard(*triples):
    return [preview._Span(word, start, end, prob) for word, start, end, prob in triples]


class TestTolerantMatch(unittest.TestCase):
    def test_exact_word_for_word(self):
        words = preview.match(['The', 'Lord', 'is', 'my', 'keeper'],
                              heard(('The', 0.0, 0.3, 0.9), ('Lord', 0.3, 0.7, 0.9),
                                    ('is', 0.7, 0.9, 0.9), ('my', 0.9, 1.1, 0.9),
                                    ('keeper', 1.1, 1.6, 0.9)))
        self.assertEqual([w[0] for w in words], ['The', 'Lord', 'is', 'my', 'keeper'])
        self.assertAlmostEqual(words[-1][2], 1.6, places=3)

    def test_two_script_words_heard_as_one(self):
        # The exact failure observed on job 0010: "for evermore" -> "forevermore".
        words = preview.match(['glory', 'for', 'evermore'],
                              heard(('glory', 0.0, 0.6, 0.9), ('forevermore', 0.6, 1.4, 0.8)))
        self.assertEqual(len(words), 3)
        self.assertEqual(words[1][:1] + words[2][:1], ('for', 'evermore'))
        self.assertAlmostEqual(words[1][1], 0.6, places=3)
        self.assertAlmostEqual(words[2][2], 1.4, places=2)
        self.assertEqual([w[1] for w in words], sorted(w[1] for w in words))

    def test_one_script_word_heard_as_several(self):
        words = preview.match(['Psalm', '121'],
                              heard(('Psalm', 0.0, 0.4, 0.9), ('one', 0.4, 0.6, 0.9),
                                    ('twenty', 0.6, 0.9, 0.9), ('one', 0.9, 1.2, 0.9)))
        self.assertEqual(len(words), 2)
        self.assertAlmostEqual(words[1][1], 0.4, places=3)
        self.assertAlmostEqual(words[1][2], 1.2, places=3)

    def test_extra_recognised_word_is_skipped(self):
        words = preview.match(['peace', 'be', 'with', 'you'],
                              heard(('peace', 0.0, 0.4, 0.9), ('be', 0.4, 0.6, 0.9),
                                    ('with', 0.6, 0.9, 0.9), ('you', 0.9, 1.1, 0.9),
                                    ('all', 1.1, 1.3, 0.9)))
        self.assertEqual([w[0] for w in words], ['peace', 'be', 'with', 'you'])

    def test_missing_script_word_gets_zero_length_span(self):
        words = preview.match(['the', 'lord', 'is', 'my', 'keeper'],
                              heard(('the', 0.0, 0.3, 0.9), ('lord', 0.3, 0.7, 0.9),
                                    ('my', 0.7, 0.9, 0.9), ('keeper', 0.9, 1.4, 0.9)))
        self.assertEqual(len(words), 5)
        is_word = words[2]
        self.assertEqual(is_word[0], 'is')
        self.assertAlmostEqual(is_word[1], is_word[2], places=3)

    def test_timings_never_go_backwards(self):
        words = preview.match(['peace', 'be', 'with', 'you'],
                              heard(('peace', 0.0, 0.3, 0.9), ('be', 0.3, 0.6, 0.9),
                                    ('with', 0.6, 0.9, 0.9), ('you', 0.9, 1.2, 0.9)))
        starts = [w[1] for w in words]
        self.assertEqual(starts, sorted(starts))
        for _, start, end in words:
            self.assertLessEqual(start, end)

    def test_low_confidence_is_refused_when_the_text_differs(self):
        # Uncertain recognition of something that is not the script word.
        with self.assertRaises(ValueError):
            preview.match(['evermore'], heard(('whatever', 0.0, 0.4, 0.05)))

    def test_low_confidence_exact_match_is_accepted(self):
        # Observed on job 0010: word 314 transcribed correctly with p=0.117.
        # The text matched the script, so the timing is usable.
        words = preview.match(['mercy'], heard(('mercy', 0.0, 0.4, 0.117)))
        self.assertEqual(words, [('mercy', 0.0, 0.4)])

    def test_negative_span_is_refused(self):
        with self.assertRaises(ValueError):
            preview.match(['mercy'], heard(('mercy', 0.5, 0.4, 0.9)))

    def test_no_recognised_words_is_refused(self):
        with self.assertRaises(ValueError):
            preview.match(['mercy'], [])

    def test_narration_that_says_something_else_is_refused(self):
        # The whole point of alignment: audio that is not the script must fail
        # closed, not silently produce a video with the wrong words.
        with self.assertRaises(ValueError):
            preview.match(['Peace.'], heard(('Rest.', 0.1, 0.4, 0.9)))
        with self.assertRaises(ValueError):
            preview.match(['alpha', 'beta', 'gamma'],
                          heard(('one', 0.0, 0.4, 0.9), ('two', 0.4, 0.8, 0.9),
                                ('three', 0.8, 1.2, 0.9)))

    def test_numerals_may_be_spelled_differently(self):
        # Scripts write "121"; narrators say "one twenty one".
        words = preview.match(['Psalm', '121'],
                              heard(('Psalm', 0.0, 0.4, 0.9), ('one', 0.4, 0.6, 0.9),
                                    ('twenty', 0.6, 0.9, 0.9), ('one', 0.9, 1.2, 0.9)))
        self.assertEqual(len(words), 2)
        self.assertAlmostEqual(words[1][2], 1.2, places=3)


if __name__ == '__main__':
    unittest.main()
