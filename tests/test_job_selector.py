"""--job accepts a bare job id, not only a full path.

Produce video #89 died in two minutes: the dispatch form received
"0036", the workflow prefixed it to content/queue/0036, and no such
file exists — the queue file is 0036-psalm-5-....md. An id is how a
human names a job, so the CLI resolves it.
"""
from pathlib import Path

import pytest

import pipeline.run as run_module
from pipeline.run import resolve_job_path, select_jobs


@pytest.fixture
def queue(tmp_path, monkeypatch):
    (tmp_path / "0036-psalm-5-morning-prayer-begin-your-day.md").write_text("x")
    (tmp_path / "0011-psalm-27-the-lord-is-my-light.md").write_text("x")
    monkeypatch.setattr(run_module, "QUEUE_DIR", tmp_path)
    return tmp_path


def test_bare_job_id_resolves_to_queue_file(queue):
    resolved = resolve_job_path("0036")
    assert resolved == queue / "0036-psalm-5-morning-prayer-begin-your-day.md"


def test_bare_filename_still_resolves(queue):
    resolved = resolve_job_path("0036-psalm-5-morning-prayer-begin-your-day.md")
    assert resolved == queue / "0036-psalm-5-morning-prayer-begin-your-day.md"


def test_bare_filename_resolves(queue):
    resolved = resolve_job_path("0011-psalm-27-the-lord-is-my-light.md")
    assert resolved.name.startswith("0011-")


def test_unknown_id_names_the_available_files(queue):
    with pytest.raises(ValueError, match="0036-psalm-5"):
        resolve_job_path("9999")


def test_ambiguous_prefix_lists_matches(queue):
    with pytest.raises(ValueError, match="ambiguous"):
        resolve_job_path("00")


def test_select_jobs_resolves_bare_id(queue):
    (selected,) = select_jobs(all_flag=False, job_path="0036", next_flag=False)
    assert selected.name.startswith("0036-")


def test_duplicate_ids_are_skipped_instead_of_selecting_by_slug(tmp_path, monkeypatch):
    def job(name, job_id):
        (tmp_path / name).write_text(
            f"---\nid: '{job_id}'\nchannel: prayer8\nstatus: approved\nformat: short\n---\n\n## Scene 1 — Prayer\nGrace and peace.\n",
            encoding="utf-8",
        )
    job("0600-a.md", "0600")
    job("0600-b.md", "0600")
    job("0601-good.md", "0601")
    monkeypatch.setattr(run_module, "QUEUE_DIR", tmp_path)
    # Keep the fixture independent of real published IDs, which change as the
    # production queue advances and are now checked even across different slugs.
    monkeypatch.setattr(run_module, "PUBLISHED_DIR", tmp_path / "published")
    monkeypatch.setattr(run_module.CONFIG, "channel_id", "prayer8")
    assert run_module._duplicate_queue_ids(tmp_path) == {"0600"}
    assert select_jobs(False, None, True) == [tmp_path / "0601-good.md"]


def test_explicit_job_cannot_bypass_duplicate_guard(tmp_path, monkeypatch):
    first = tmp_path / "0600-a.md"
    for path in (first, tmp_path / "0600-b.md"):
        path.write_text("---\nid: '0600'\nchannel: prayer8\nstatus: approved\n---\n\n## Scene 1 — Prayer\nGrace and peace.\n", encoding="utf-8")
    monkeypatch.setattr(run_module, "QUEUE_DIR", tmp_path)
    monkeypatch.setattr(run_module.CONFIG, "channel_id", "prayer8")
    with pytest.raises(RuntimeError, match="duplicate queue ID"):
        run_module.process(first, False)
