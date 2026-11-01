"""Guards the long-form runway audit used before production is unpaused.

`scripts/audit_runway.py` exists because a queue of 250-word scripts looks like a
month of scheduled uploads while actually failing closed on the renderer's
650-word full-length gate. These tests keep the audit's arithmetic and its
machine-readable output honest.
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_runway import MIN_WORDS, WORDS_PER_SECOND, audit  # noqa: E402

QUEUE = ROOT / 'content' / 'queue'


class TestRunwayAudit(unittest.TestCase):
    def test_every_script_is_measured(self):
        rows = audit(QUEUE)
        self.assertTrue(rows, 'queue should not be empty')
        for row in rows:
            self.assertNotIn('error', row, f'{row["file"]} failed to parse')
            self.assertGreater(row['words'], 0, row['file'])
            self.assertGreater(row['scenes'], 0, row['file'])
            self.assertEqual(row['minutes'],
                             round(row['words'] / WORDS_PER_SECOND / 60, 1),
                             row['file'])

    def test_full_length_flag_matches_the_renderer_gate(self):
        for row in audit(QUEUE):
            self.assertEqual(row['full_length_ok'], row['words'] >= MIN_WORDS,
                             row['file'])

    def test_json_output_is_machine_readable(self):
        completed = subprocess.run(
            [sys.executable, str(ROOT / 'scripts' / 'audit_runway.py'), '--json'],
            capture_output=True, text=True, cwd=str(ROOT))
        rows = json.loads(completed.stdout)
        self.assertEqual(len(rows), len(audit(QUEUE)))
        self.assertEqual(completed.returncode, 1,
                         'a queue containing below-floor scripts must exit non-zero')

    def test_short_queue_exits_zero(self):
        # A queue with nothing below the floor is not an error.
        for row in audit(QUEUE):
            if not row['full_length_ok']:
                self.assertLess(row['words'], MIN_WORDS)
        self.assertGreater(MIN_WORDS, 0)


if __name__ == '__main__':
    unittest.main()
