"""Original illustrations must reproduce their recorded bytes, not borrow clearance."""
import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pipeline.licences import load_ledger
from tools import make_plates

ROOT = Path(__file__).resolve().parents[1]


class OriginalPlateTests(unittest.TestCase):
    def test_generated_pixels_match_recorded_clearance(self):
        ledger = load_ledger(use_cache=False)
        for i, name in enumerate(make_plates.PLATES):
            with self.subTest(plate=name):
                image = make_plates.make_plate(20261023 + i * 977)
                self.assertEqual(image.size, (1280, 720))
                buf = io.BytesIO()
                image.save(buf, 'PNG', optimize=True)
                entry = ledger[name]
                self.assertEqual(hashlib.sha256(buf.getvalue()).hexdigest(), entry['sha256'])
                self.assertEqual(entry['status'], 'cleared')
                self.assertIn('Original procedural artwork', entry['license'])
                self.assertIn('make_plates.py', entry['source_url'])
                self.assertIn('not a photograph', entry['notes'])

    def test_ensure_does_not_hide_existing_file_drift(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(make_plates, 'IMG', tmp):
            make_plates.ensure_plates()
            target = Path(tmp) / make_plates.PLATES[0]
            target.write_bytes(b'changed bytes must be caught by ledger check')
            make_plates.ensure_plates()
            self.assertEqual(target.read_bytes(), b'changed bytes must be caught by ledger check')

    def test_renderers_no_longer_reference_getty_headquarters_photos(self):
        for filename in ('deep_dive.py', 'shorts.py'):
            source = (ROOT / 'tools' / filename).read_text()
            self.assertNotIn('enron-corporation-headquarters-houston-c-', source)
            for plate in make_plates.PLATES:
                self.assertIn(plate, source)
            self.assertIn('ensure_plates()', source)
