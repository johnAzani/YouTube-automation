"""Unit tests for Selar Digital Store & Products Engine."""
from __future__ import annotations

import json
from pathlib import Path
from PIL import Image

from pipeline.selar_store import (
    CANONICAL_SELAR_PRODUCTS,
    export_selar_product_manifests,
    render_selar_product_cover,
)
from pipeline.social_pack import build_standardized_description_footer


def test_canonical_selar_products():
    """Verify canonical product definitions and pricing parameters."""
    assert len(CANONICAL_SELAR_PRODUCTS) >= 3
    p1 = CANONICAL_SELAR_PRODUCTS[0]
    assert "432 Hz Offline" in p1.title
    assert p1.is_pay_what_you_want is True
    assert p1.suggested_usd >= 3.0

    p2 = CANONICAL_SELAR_PRODUCTS[1]
    assert "Prayer Journal" in p2.title
    assert p2.is_pay_what_you_want is True


def test_render_selar_product_cover(tmp_path: Path):
    """Verify rendering of 1080x1080 product cover."""
    prod = CANONICAL_SELAR_PRODUCTS[0]
    out_cover = tmp_path / "test_cover.png"
    im = render_selar_product_cover(prod, out_path=out_cover)

    assert isinstance(im, Image.Image)
    assert im.size == (1080, 1080)
    assert out_cover.is_file()
    assert out_cover.stat().st_size > 15000


def test_export_selar_product_manifests(tmp_path: Path):
    """Verify export of JSON listing manifests and cover cards."""
    files = export_selar_product_manifests(out_dir=tmp_path)
    assert len(files) >= 6

    json_files = [f for f in files if f.suffix == ".json"]
    assert len(json_files) == len(CANONICAL_SELAR_PRODUCTS)
    for jf in json_files:
        data = json.loads(jf.read_text(encoding="utf-8"))
        assert "product_id" in data
        assert "First Bank of Nigeria" in data["selar_payout_target"]


def test_social_pack_includes_selar_store():
    """Verify standardized description footer includes Selar store link."""
    footer = build_standardized_description_footer(include_store_links=True)
    assert "selar.co" in footer
    assert "OFFLINE BEDTIME PRAYER SANCTUARY" in footer
