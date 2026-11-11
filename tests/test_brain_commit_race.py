"""The brain must not clobber newer authored content or reuse a job ID."""
from pathlib import Path
import subprocess

from scripts.guard_brain_commit import check_conflicts


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, check=True).stdout.strip()


def repo_with_base(tmp_path: Path):
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.email", "test@example.com")
    git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "content/queue").mkdir(parents=True)
    (tmp_path / "content/queue/0602-approved.md").write_text("approved")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "base")
    return git(tmp_path, "rev-parse", "HEAD")


def commit(repo, path, content):
    file = repo / path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(content)
    git(repo, "add", path)
    git(repo, "commit", "-qm", "concurrent commit")


def test_rejects_overwriting_a_concurrently_modified_file(tmp_path):
    base = repo_with_base(tmp_path)
    path = "content/queue/0602-approved.md"
    commit(tmp_path, path, "reviewed changes")
    assert any("changed since authoring began" in s for s in check_conflicts(tmp_path, base, [path], []))
    assert any("changed since authoring began" in s for s in check_conflicts(tmp_path, base, [], [path]))


def test_rejects_different_slug_with_concurrent_queued_or_published_id(tmp_path):
    base = repo_with_base(tmp_path)
    commit(tmp_path, "content/queue/0600-reviewed.md", "reviewed")
    commit(tmp_path, "content/published/0601-published.md", "published")
    conflicts = check_conflicts(tmp_path, base, ["content/queue/0600-generated.md", "content/queue/0601-generated.md"], [])
    assert any("job ID 0600 already used" in s for s in conflicts)
    assert any("job ID 0601 already used" in s for s in conflicts)


def test_rejects_duplicate_ids_in_one_new_batch_and_allows_unrelated_changes(tmp_path):
    base = repo_with_base(tmp_path)
    commit(tmp_path, "unrelated.txt", "fine")
    assert check_conflicts(tmp_path, base, ["content/queue/0603-first.md"], []) == []
    errors = check_conflicts(tmp_path, base, ["content/queue/0603-first.md", "content/queue/0603-second.md"], [])
    assert any("job ID 0603 already used" in s for s in errors)


def test_rejects_concurrent_creation_of_same_path(tmp_path):
    base = repo_with_base(tmp_path)
    path = "content/shorts-scripts/short-shield.json"
    commit(tmp_path, path, "reviewed")
    assert any("changed since authoring began" in s for s in check_conflicts(tmp_path, base, [path], []))
