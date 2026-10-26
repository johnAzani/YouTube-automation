from pathlib import Path
import pytest
from pipeline.short_release import EDITIONS
from pipeline.licences import load_ledger, uncleared_stills, unsafe_stills


def test_short_psalm91_registration():
    assert "short-psalm91" in EDITIONS
    ed = EDITIONS["short-psalm91"]
    assert ed.job_id == "SHORT-0002"
    assert ed.slug == "short-0002-psalm-91-prayer-of-protection"
    assert "Psalm 91" in ed.title
    assert ed.niche == "faith and prayer"
    assert "The Secret Place" in ed.description
    assert any("prayer" in tag.lower() for tag in ed.tags)


def test_psalm91_assets_cleared_in_ledger():
    ledger = load_ledger(use_cache=False)
    psalm91_stills = [
        Path("image-search/short-prayer-scene-01.jpg"),
        Path("image-search/short-prayer-scene-02.jpg"),
        Path("image-search/short-prayer-scene-03.jpg"),
        Path("image-search/short-prayer-scene-04.jpg"),
        Path("image-search/short-prayer-scene-05.jpg"),
        Path("image-search/short-prayer-scene-06.jpg"),
        Path("image-search/short-prayer-cover-poster.jpg"),
    ]
    # Verify all files exist
    for still in psalm91_stills:
        assert still.is_file(), f"Asset missing: {still}"

    # Verify no uncleared or unsafe stills
    bad_unsafe = unsafe_stills(psalm91_stills, ledger)
    bad_uncleared = uncleared_stills(psalm91_stills, ledger)
    assert not bad_unsafe, f"Found unsafe stills: {bad_unsafe}"
    assert not bad_uncleared, f"Found uncleared stills: {bad_uncleared}"


def test_psalm91_kinetic_typography_phrases_and_stream():
    from tools.shorts import SCRIPTS, build_kinetic_stream, load_words, kinetic_typography_layer
    from PIL import Image
    cfg = SCRIPTS["short-psalm91"]
    assert "kinetic_phrases" in cfg
    assert len(cfg["kinetic_phrases"]) >= 20
    words = load_words("short-psalm91")
    stream = build_kinetic_stream("short-psalm91", words)
    assert len(stream) == len(cfg["kinetic_phrases"])
    # Verify stream covers beginning, middle, and end
    assert stream[0]["t0"] == 0.0
    assert stream[-1]["t1"] > 38.0
    # Test rendering a frame
    bg = Image.new("RGB", (720, 1280), (10, 20, 40))
    layer = kinetic_typography_layer(bg, stream, 2.5, is_prayer=True)
    assert layer.size == (720, 1280)
    assert layer.mode == "RGBA"

