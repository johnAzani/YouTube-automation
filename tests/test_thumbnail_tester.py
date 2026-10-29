"""Unit tests for Multi-Variant Thumbnail A/B Test Generator & Mobile Contrast Scorer."""
from __future__ import annotations

import json
from pathlib import Path
from PIL import Image

from pipeline.thumbnail_tester import (
    ThumbnailVariantSpec,
    evaluate_thumbnail_legibility,
    generate_thumbnail_test_suite,
    get_default_variants_for_script,
    render_variant_image,
)


def test_get_default_variants():
    """Verify that 3 psychological testing variants are defined."""
    variants = get_default_variants_for_script("Psalm 91 Prayer", scripture_ref="Psalm 91")
    assert len(variants) == 3
    ids = [v.variant_id for v in variants]
    assert ids == ["A", "B", "C"]
    for v in variants:
        assert len(v.primary_headline) > 0
        assert len(v.secondary_kicker) > 0
        assert len(v.badge_label) > 0


def test_render_variant_image(tmp_path: Path):
    """Verify rendering of a 1280x720 thumbnail variant."""
    variants = get_default_variants_for_script("Psalm 91 Prayer", scripture_ref="Psalm 91")
    spec = variants[0]
    out_jpg = tmp_path / "test_thumb_var_a.jpg"
    img = render_variant_image(spec, out_path=out_jpg)

    assert isinstance(img, Image.Image)
    assert img.size == (1280, 720)
    assert out_jpg.is_file()
    assert out_jpg.stat().st_size > 15000


def test_evaluate_thumbnail_legibility():
    """Verify mobile contrast ratio and edge sharpness calculation."""
    variants = get_default_variants_for_script("Psalm 91 Prayer", scripture_ref="Psalm 91")
    spec = variants[0]
    img = render_variant_image(spec)
    score = evaluate_thumbnail_legibility(img, "A")

    assert score.variant_id == "A"
    assert score.contrast_ratio > 3.0
    assert score.mobile_edge_acuity > 0.0
    assert isinstance(score.timestamp_safe, bool)
    assert 0.0 <= score.composite_ctr_score <= 100.0


def test_generate_thumbnail_test_suite(tmp_path: Path):
    """Verify end-to-end A/B/C pack generation with report."""
    report = generate_thumbnail_test_suite(
        title="Psalm 23: The Lord Is My Shepherd",
        scripture_ref="Psalm 23",
        out_dir=tmp_path,
    )

    assert "variants" in report
    assert len(report["variants"]) == 3
    assert "winner_recommendation" in report
    assert (tmp_path / "thumbnail_ab_test_report.json").is_file()
    assert (tmp_path / "thumbnail_variant_a.jpg").is_file()
    assert (tmp_path / "thumbnail_variant_b.jpg").is_file()
    assert (tmp_path / "thumbnail_variant_c.jpg").is_file()
