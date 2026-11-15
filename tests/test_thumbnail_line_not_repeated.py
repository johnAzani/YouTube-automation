"""A new script does not take a thumbnail line a queued script already has.

15 November 2026: The Provision Table (0514) and The Guided Path (0808) both
wrote "ORDERED STEPS", because their roadmaps give the same hook to Psalm 37:23.
Nothing compared a new line with the queue. The commit carried `[skip ci]`, so
the test that reads the queue failed on the next pull request, not on the commit
that caused it. It was the third time in three days (13 and 14 November:
"PERFECT PEACE").
"""
from __future__ import annotations

from pipeline import gemini_brain
from pipeline.gemini_brain import _clamp_thumb_text_for_ctr as clamp
from pipeline.gemini_brain import normalize_authored_script_markdown, queued_thumb_lines

TITLE = "Steps Ordered by the Lord: Psalm 37:23-25 | The Provision Table"


def _queued(directory, job_id, line, quote="'"):
    (directory / f"{job_id}-x.md").write_text(
        f"---\nid: {quote}{job_id}{quote}\ntitle: T\nthumb_text: {line}\n---\n\n## Scene 1 — One\n\nAmen.\n",
        encoding="utf-8")


def test_the_lines_already_waiting_are_read_from_the_queue(tmp_path):
    _queued(tmp_path, "0808", "ORDERED STEPS", quote="")
    _queued(tmp_path, "0514", '"Ordered By The Lord"')
    (tmp_path / "README.md").write_text("no front matter", encoding="utf-8")
    assert queued_thumb_lines(queue_dir=tmp_path) == {"ORDERED STEPS", "ORDERED BY THE LORD"}
    assert queued_thumb_lines(own_id="0514", queue_dir=tmp_path) == {"ORDERED STEPS"}  # not its own line
    assert queued_thumb_lines(queue_dir=tmp_path / "missing") == set()


def test_a_taken_line_gives_way_to_the_next_cut_that_fits():
    assert clamp("ORDERED STEPS", "daily", TITLE) == "ORDERED STEPS"
    assert clamp("ORDERED STEPS", "daily", TITLE, taken={"ORDERED STEPS"}) == "STEPS ORDERED"
    assert clamp("ORDERED STEPS", "daily", TITLE,
                 taken={"ORDERED STEPS", "STEPS ORDERED"}) == "ORDERED BY THE LORD"


def test_a_repeated_line_is_kept_before_one_bare_word_or_a_fixed_line():
    assert clamp("ORDERED STEPS", "daily", "", taken={"ORDERED STEPS"}) == "ORDERED STEPS"
    everything = {"ORDERED STEPS", "STEPS ORDERED", "ORDERED BY THE LORD", "THE LORD"}
    assert clamp("ORDERED STEPS", "daily", TITLE, taken=everything) == "ORDERED STEPS"


def test_a_newly_authored_script_is_compared_with_the_queue(tmp_path, monkeypatch):
    _queued(tmp_path, "0808", "ORDERED STEPS")
    monkeypatch.setattr(gemini_brain, "QUEUE_DIR", tmp_path)
    raw = "\n".join([
        "---", 'id: "0514"', "slug: steps-ordered-by-the-lord", f'title: "{TITLE}"', "status: approved",
        "format: longform", "niche: faith", 'thumb_text: "ORDERED STEPS"', "channel: prayer7", "---", "",
        "## Scene 1 — Ordered", "", "The steps of a good man are ordered by the LORD.", ""])
    meta = gemini_brain.job_front_matter(normalize_authored_script_markdown(raw, channel_id="prayer7"))
    assert meta["thumb_text"] == "STEPS ORDERED"
    # Its own file in the queue (a script being rewritten) is not a clash with itself.
    (tmp_path / "0808-x.md").unlink()
    _queued(tmp_path, "0514", "ORDERED STEPS")
    meta = gemini_brain.job_front_matter(normalize_authored_script_markdown(raw, channel_id="prayer7"))
    assert meta["thumb_text"] == "ORDERED STEPS"
