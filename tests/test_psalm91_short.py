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
