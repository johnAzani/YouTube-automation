"""Receipts overwritten by a stale production leg are found and restored.

Built on a real git history: a receipt is committed, a later
``chore(content): publish job`` commit overwrites it the way the stale-checkout
fault did, and the repair has to find it from history alone.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import repair_clobbered_receipts as repair  # noqa: E402

LONG = "content/published/0207-midnight.md"
SHORT = "content/published/short-midnightx-prayer.md"
NEW = "content/published/0208-next.md"


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout


def write(repo: Path, rel: str, text: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def commit(repo: Path, message: str) -> str:
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)
    return git(repo, "rev-parse", "HEAD").strip()


def longform(published_at: str, extra: str = "") -> str:
    return ("---\nid: \"0207\"\ntitle: \"Midnight Prayer\"\nstatus: published\nformat: longform\n"
            "channel: prayer4\npublished_on: \"" + published_at[:10] + "\"\n"
            f"published_at: \"{published_at}\"\nyoutube_video_id: \"LONGVIDEO01\"\n{extra}"
            "---\n\nThe script body.\n")


FULL_SHORT = ("---\nid: \"SHORT-X\"\ntitle: \"A Short\"\nstatus: published\nformat: short\n"
              "channel: prayer4\npublished_at: \"2026-11-12T23:58:17Z\"\n"
              "youtube_video_id: \"SHORTVIDEO1\"\nmetadata_revision: \"selar-seo-v1\"\n"
              "duration_seconds: 62.28\nthumbnail_pending: true\nthumbnail_attempts: 1\n"
              "---\n\nThe real Short script.\n")
STUB_SHORT = ("---\nid: SHORT-X\ntitle: 'A Short'\nstatus: published\nformat: short\n"
              "channel: prayer4\npublished_at: '2026-11-12T23:58:00Z'\n"
              "youtube_video_id: SHORTVIDEO1\nreceipt_recovered_from_youtube: true\n"
              "metadata_retrofit_approved: false\nthumbnail_pending: true\n---\n\n"
              "This receipt was recovered from an existing YouTube video.\n")


def build(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.name", "t")
    git(repo, "config", "user.email", "t@example.com")
    write(repo, LONG, longform("2026-11-13T00:40:37Z", "thumbnail_pending: false\n"))
    write(repo, SHORT, FULL_SHORT)
    commit(repo, "chore(content): publish job [skip ci]")
    # The stale leg: re-stamps the long-form, stubs the Short, and adds its real upload.
    write(repo, LONG, longform("2026-11-13T07:27:44Z", "thumbnail_pending: true\n"))
    write(repo, SHORT, STUB_SHORT)
    write(repo, NEW, longform("2026-11-13T07:20:00Z").replace("LONGVIDEO01", "LONGVIDEO02")
          .replace("0207", "0208"))
    commit(repo, "chore(content): publish job [skip ci]")
    # The monitor has touched both since, as it does in production.
    write(repo, LONG, (repo / LONG).read_text().replace(
        "thumbnail_pending: true\n", "thumbnail_pending: true\nthumbnail_attempts: 2\n"))
    write(repo, SHORT, (repo / SHORT).read_text().replace(
        "thumbnail_pending: true\n", "thumbnail_pending: false\nthumbnail_revision: \"shorts-poster-v1\"\n"))
    commit(repo, "chore(monitor): automation status snapshot [skip ci]")
    return repo


def test_both_shapes_of_damage_are_found(tmp_path):
    repo = build(tmp_path)
    found = {item.path: item for item in repair.find_damage(repo)}
    assert set(found) == {LONG, SHORT}
    assert found[LONG].kind == "restamp"
    assert (found[LONG].was, found[LONG].became) == ("2026-11-13T00:40:37Z", "2026-11-13T07:27:44Z")
    assert found[SHORT].kind == "stub"
    assert repair.main(["--repo", str(repo), "--check"]) == 1


def test_repair_restores_the_true_time_and_keeps_newer_state(tmp_path):
    repo = build(tmp_path)
    assert repair.main(["--repo", str(repo), "--apply"]) == 0
    long_now = repair.fields((repo / LONG).read_text())
    assert long_now["published_at"] == "2026-11-13T00:40:37Z"
    assert long_now["thumbnail_attempts"] == "2"            # the monitor's later work survives
    short_text = (repo / SHORT).read_text()
    short_now = repair.fields(short_text)
    assert "The real Short script." in short_text
    assert "recovered from an existing YouTube video" not in short_text
    assert "receipt_recovered_from_youtube" not in short_now
    assert "metadata_retrofit_approved" not in short_now
    assert short_now["metadata_revision"] == "selar-seo-v1"  # so metadata is not pushed again
    assert short_now["published_at"] == "2026-11-12T23:58:17Z"
    assert short_now["thumbnail_pending"] == "false"         # current thumbnail state carried over
    assert short_now["thumbnail_revision"] == "shorts-poster-v1"
    # The leg's genuine new upload was never a candidate.
    assert git(repo, "status", "--porcelain").split() == ["M", LONG, "M", SHORT]
    # Idempotent: nothing left to do, and a second run changes nothing.
    assert repair.find_damage(repo) == []
    assert repair.main(["--repo", str(repo), "--check"]) == 0


def test_a_replacement_upload_is_not_treated_as_damage(tmp_path):
    """A deliberate re-upload changes the video id; that is not this fault."""
    repo = build(tmp_path)
    git(repo, "checkout", "-q", "--", ".")
    write(repo, NEW, (repo / NEW).read_text().replace("LONGVIDEO02", "REPLACEMENT")
          .replace("07:20:00Z", "09:00:00Z"))
    commit(repo, "chore(content): publish job [skip ci]")
    assert NEW not in {item.path for item in repair.find_damage(repo)}

