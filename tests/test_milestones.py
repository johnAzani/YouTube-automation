"""Unit tests for Subscriber Milestone Celebration Engine."""
from __future__ import annotations

from pathlib import Path
from PIL import Image

from pipeline.milestones import (
    MILESTONE_TIERS,
    get_current_milestone_status,
    render_milestone_card,
)


def test_milestone_tiers():
    """Verify predefined milestone levels and copy."""
    assert len(MILESTONE_TIERS) >= 4
    targets = [t.subs_target for t in MILESTONE_TIERS]
    assert 1000 in targets
    assert 1250 in targets
    assert 1500 in targets
    assert 2000 in targets


def test_get_current_milestone_status():
    """Verify calculation of achieved and upcoming milestone tiers."""
    achieved, upcoming = get_current_milestone_status(current_subs=1230)
    assert achieved is not None
    assert achieved.subs_target == 1000
    assert upcoming is not None
    assert upcoming.subs_target == 1250


def test_render_milestone_card(tmp_path: Path):
    """Verify rendering of 1080x1080 celebratory Community Tab card."""
    tier = MILESTONE_TIERS[0]
    out_png = tmp_path / "test_milestone_1000.png"
    im = render_milestone_card(tier, out_path=out_png)

    assert isinstance(im, Image.Image)
    assert im.size == (1080, 1080)
    assert out_png.is_file()
    assert out_png.stat().st_size > 15000


def test_celebrate_milestone_cli(monkeypatch, capsys):
    """Verify CLI milestone celebration execution."""
    import scripts.celebrate_milestone as cli

    monkeypatch.setattr("sys.argv", ["celebrate_milestone.py", "--subs", "1250"])
    cli.main()
    captured = capsys.readouterr()
    assert "1,250 BELIEVERS UNITED" in captured.out
    assert "Next Upcoming Milestone: 1,500 STRONG IN FAITH" in captured.out

