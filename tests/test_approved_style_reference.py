"""Protect the channel owner's approved visual reference from silent replacement."""
import hashlib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / 'docs/media/approved-style-preview.mp4'
APPROVED_SHA256 = '69c55e855ed3a9a8ec1ffa79663489d7370eaaf636158c1ae853fe2c11d9f156'


class ApprovedStyleReferenceTests(unittest.TestCase):
    def test_approved_preview_has_not_changed(self):
        self.assertEqual(hashlib.sha256(REFERENCE.read_bytes()).hexdigest(), APPROVED_SHA256)

    def test_dashboard_exposes_reference_without_a_review_gate(self):
        dashboard = (ROOT / 'docs/index.html').read_text(encoding='utf-8')
        self.assertIn('media/approved-style-preview.mp4', dashboard)
        self.assertIn('id="style-preview"', dashboard)
