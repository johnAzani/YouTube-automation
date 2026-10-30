"""Unit tests for 30-Night Scripture Protection Prayer Journal PDF Builder."""
from __future__ import annotations

from pathlib import Path
import pypdfium2 as pdfium

from pipeline.journal_builder import (
    NIGHTS_DATA,
    OUTPUT_PDF_PATH,
    build_prayer_journal_pdf,
)


def test_nights_data_integrity():
    """Verify that all 30 nights are fully authored and meet theological standards."""
    assert len(NIGHTS_DATA) == 30

    for i, night in enumerate(NIGHTS_DATA, 1):
        assert night.night_number == i
        assert len(night.theme) > 3
        assert len(night.scripture_text) > 10
        assert len(night.scripture_ref) > 3
        assert len(night.meditation) > 50
        assert len(night.declaration) > 30
        assert len(night.prayer) > 30

        # Enforce editorial persona invariant (zero mentions of personal creator name)
        full_text = f"{night.theme} {night.meditation} {night.declaration} {night.prayer}".lower()
        assert "john azani" not in full_text
        assert "azani john" not in full_text


def test_build_prayer_journal_pdf(tmp_path: Path):
    """Verify programmatic PDF compilation to exactly 34 pages with valid geometry."""
    test_pdf = tmp_path / "test_journal.pdf"
    result = build_prayer_journal_pdf(test_pdf)

    assert result == test_pdf
    assert test_pdf.is_file()
    assert test_pdf.stat().st_size > 20000

    doc = pdfium.PdfDocument(str(test_pdf))
    assert len(doc) == 34

    # Verify letter geometry (8.5 x 11 inches = 612 x 792 points)
    for page in doc:
        w, h = page.get_size()
        assert w == 612.0
        assert h == 792.0
