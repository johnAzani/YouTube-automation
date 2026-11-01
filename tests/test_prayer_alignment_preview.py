"""Tests for the tolerant alignment overlay used by the preview dry render.

`.ci/prayer_alignment_preview.py` is not imported by production code; it is copied
over `pipeline/prayer_alignment.py` inside the preview workflow so the owner can
see a full-length master. These tests pin the behaviour that matters: the module
must accept the tokenisations faster-whisper actually produces while still
refusing genuinely wrong or unsafe alignments.
"""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    'prayer_alignment_preview', ROOT / '.ci' / 'prayer_alignment_preview.py')
preview = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(preview)


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
        words = preview.match(['a', 'b', 'c', 'd'],
                              heard(('a', 0.0, 0.3, 0.9), ('bee', 0.3, 0.6, 0.9),
                                    ('see', 0.6, 0.9, 0.9), ('dee', 0.9, 1.2, 0.9)))
        starts = [w[1] for w in words]
        self.assertEqual(starts, sorted(starts))
        for _, start, end in words:
            self.assertLessEqual(start, end)

    def test_low_confidence_is_refused(self):
        with self.assertRaises(ValueError):
            preview.match(['mercy'], heard(('mercy', 0.0, 0.4, 0.05)))

    def test_negative_span_is_refused(self):
        with self.assertRaises(ValueError):
            preview.match(['mercy'], heard(('mercy', 0.5, 0.4, 0.9)))

    def test_no_recognised_words_is_refused(self):
        with self.assertRaises(ValueError):
            preview.match(['mercy'], [])

    def test_completely_different_transcript_does_not_crash(self):
        # Every script word is unmatched; the result is a coherent, monotonic
        # timeline rather than a crash, because the caller still needs durations.
        words = preview.match(['alpha', 'beta', 'gamma'],
                              heard(('one', 0.0, 0.4, 0.9), ('two', 0.4, 0.8, 0.9),
                                    ('three', 0.8, 1.2, 0.9)))
        self.assertEqual(len(words), 3)
        self.assertTrue(all(start <= end for _, start, end in words))


if __name__ == '__main__':
    unittest.main()
