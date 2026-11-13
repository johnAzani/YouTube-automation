"""Real-Git simulations of concurrent production state commits (no remote calls)."""
from pathlib import Path
import subprocess

import pytest
import yaml

from scripts.guard_produce_commit import check_conflicts


def git(repo, *args):
    return subprocess.run(['git', *args], cwd=repo, text=True, capture_output=True, check=True).stdout.strip()


def init(tmp_path):
    git(tmp_path, 'init', '-q')
    git(tmp_path, 'config', 'user.email', 'test@example.com')
    git(tmp_path, 'config', 'user.name', 'Test')
    queue = tmp_path / 'content/queue/0100-first.md'
    queue.parent.mkdir(parents=True)
    queue.write_text('approved')
    git(tmp_path, 'add', '.')
    git(tmp_path, 'commit', '-qm', 'base')
    return git(tmp_path, 'rev-parse', 'HEAD')


def commit(repo, path, value):
    file = repo / path
    file.parent.mkdir(parents=True, exist_ok=True)
    if value is None:
        file.unlink()
        git(repo, 'rm', '-q', path)
    else:
        file.write_text(value)
        git(repo, 'add', path)
    git(repo, 'commit', '-qm', 'concurrent')


def test_unrelated_channel_changes_do_not_block_a_commit(tmp_path):
    base = init(tmp_path)
    queue = 'content/queue/0100-first.md'
    commit(tmp_path, 'content/published/0200-other.md', 'other receipt')
    (tmp_path / queue).write_text('our edited queue')
    assert check_conflicts(tmp_path, base, 'HEAD', [queue], []) == []


def test_concurrent_queue_edits_cannot_be_overwritten_or_deleted(tmp_path):
    base = init(tmp_path)
    path = 'content/queue/0100-first.md'
    commit(tmp_path, path, 'reviewed upstream')
    (tmp_path / path).write_text('old producer state')
    assert check_conflicts(tmp_path, base, 'HEAD', [path], []) == [path]
    (tmp_path / path).unlink()
    assert check_conflicts(tmp_path, base, 'HEAD', [], [path]) == [path]


def test_identical_concurrent_receipt_and_deletion_are_safe(tmp_path):
    base = init(tmp_path)
    path = 'content/queue/0100-first.md'
    receipt = 'content/published/0100-first.md'
    commit(tmp_path, receipt, 'same receipt')
    commit(tmp_path, path, None)
    assert check_conflicts(tmp_path, base, 'HEAD', [receipt], [path]) == []


def test_different_concurrent_receipt_is_never_overwritten(tmp_path):
    base = init(tmp_path)
    path = 'content/published/0100-first.md'
    commit(tmp_path, path, 'other video id')
    (tmp_path / path).write_text('our video id')
    assert check_conflicts(tmp_path, base, 'HEAD', [path], []) == [path]


def test_guard_rechecks_new_tip_after_rejected_push(tmp_path):
    base = init(tmp_path)
    path = 'content/queue/0100-first.md'
    (tmp_path / path).write_text('our change')
    assert check_conflicts(tmp_path, base, 'HEAD', [path], []) == []
    commit(tmp_path, path, 'a competing writer')
    (tmp_path / path).write_text('our change')
    assert check_conflicts(tmp_path, base, 'HEAD', [path], []) == [path]


def test_invalid_refs_unsafe_paths_or_missing_touched_files_fail_closed(tmp_path):
    base = init(tmp_path)
    with pytest.raises(RuntimeError):
        check_conflicts(tmp_path, 'bad-ref', 'HEAD', [], [])
    with pytest.raises(ValueError):
        check_conflicts(tmp_path, base, 'HEAD', ['content/../elsewhere'], [])
    with pytest.raises(OSError):
        check_conflicts(tmp_path, base, 'HEAD', ['content/queue/missing.md'], [])
    with pytest.raises(ValueError):
        check_conflicts(tmp_path, base, 'HEAD', [], ['content/queue/0100-first.md'])


def test_workflow_runs_guard_each_attempt_before_reset_and_stages_no_parallelism():
    root = Path(__file__).resolve().parents[1]
    data = yaml.safe_load((root / '.github/workflows/produce.yml').read_text())
    job = data['jobs']['produce']
    assert job['strategy']['max-parallel'] == 1
    step = next(s for s in job['steps'] if s.get('name') == 'Commit queue state (job moved to published/)')
    command = step['run']
    assert command.index('for attempt in') < command.index('guard_produce_commit.py') < command.index('git reset --mixed origin/main')
    assert '--target origin/main' in command
    assert 'output/report/content-conflict' in command
