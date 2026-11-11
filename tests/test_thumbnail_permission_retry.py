"""Safe retries after thumbnail permission/eligibility changes."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest
import yaml

from pipeline.script_doc import parse_script
from scripts import sync_published_thumbnails as sync


@pytest.fixture
def receipts(tmp_path):
    directory = tmp_path / "published"
    directory.mkdir()

    def write(name, **meta):
        path = directory / name
        data = {
            "id": name.split("-")[0], "slug": name.removesuffix(".md"),
            "title": "Protection Prayer", "status": "published", "channel": "prayer8",
            "youtube_video_id": "video8", "privacy": "public", **meta,
        }
        path.write_text("---\n" + yaml.safe_dump(data, sort_keys=False) + "---\nPrayer.\n")
        return path

    return directory, write


def test_permission_failure_recovers_even_after_old_short_attempt_limit(receipts):
    directory, write = receipts
    path = write("short-shield.md", format="short", thumbnail_pending=True,
                 thumbnail_error="HttpError 403 [forbidden]", thumbnail_attempts=8,
                 thumbnail_retry_after="2099-01-01T00:00:00Z", thumbnail_retry_reason="permission")
    assert sync.collect_pending_short_receipts(directory, channel_id="prayer8") == []
    eligible = sync.collect_pending_short_receipts(directory, channel_id="prayer8", retry_permission=True)
    assert [p for p, _ in eligible] == [path]
    assert sync.collect_pending_short_receipts(directory, channel_id="prayer7", retry_permission=True) == []
    sync.stamp_frontmatter_field(path, "thumbnail_retry_after", "2000-01-01T00:00:00Z")
    assert [p for p, _ in sync.collect_pending_short_receipts(directory, channel_id="prayer8")] == [path]


def test_retry_does_not_override_rate_limit_or_reapply_success(receipts):
    directory, write = receipts
    write("0600-pending.md", format="longform", thumbnail_pending=True,
          thumbnail_error="HttpError 403 [forbidden]", thumbnail_retry_after="2099-01-01T00:00:00Z",
          thumbnail_retry_reason="rate_limit")
    write("0601-done.md", format="longform", thumbnail_pending=False,
          thumbnail_error="HttpError 403 [forbidden]", thumbnail_revision=sync.THUMBNAIL_REVISION)
    assert sync.collect_pending_receipts(directory, channel_id="prayer8", retry_permission=True) == []
    assert not sync._is_permission_refusal("HTTP 403 uploadRateLimitExceeded")
    assert not sync._is_permission_refusal("HTTP 403 quotaExceeded")


def test_rate_limited_short_remains_retryable_after_attempt_cap(receipts):
    directory, write = receipts
    path = write("short-rate.md", format="short", thumbnail_pending=True,
                 thumbnail_error="HttpError 403 uploadRateLimitExceeded", thumbnail_attempts=8,
                 thumbnail_retry_after="2000-01-01T00:00:00Z", thumbnail_retry_reason="rate_limit")
    assert [p for p, _ in sync.collect_pending_short_receipts(directory, channel_id="prayer8")] == [path]
    assert sync.collect_pending_short_receipts(directory, channel_id="prayer8", retry_permission=True) == []


def test_pending_wins_over_old_revision_stamp(receipts):
    directory, write = receipts
    path = write("0600-pending.md", format="longform", thumbnail_pending=True,
                 thumbnail_error="403 forbidden", thumbnail_revision=sync.THUMBNAIL_REVISION)
    assert [p for p, _ in sync.collect_pending_receipts(directory, channel_id="prayer8")] == [path]


def test_targeted_success_clears_pending_and_never_changes_privacy(receipts, tmp_path):
    directory, write = receipts
    path = write("0600-pending.md", format="longform", thumbnail_pending=True,
                 thumbnail_error="HttpError 403 [forbidden]", thumbnail_retry_after="2099-01-01T00:00:00Z",
                 thumbnail_retry_reason="permission")
    write("0500-other.md", format="longform", channel="prayer7", youtube_video_id="other",
          thumbnail_pending=True, thumbnail_error="403 forbidden")
    youtube = mock.MagicMock()
    youtube.videos.return_value.list.return_value.execute.return_value = {"items": [{
        "id": "video8", "snippet": {"title": "Test", "categoryId": "22"},
        "status": {"privacyStatus": "private", "uploadStatus": "processed"},
        "contentDetails": {"duration": "PT7M"},
    }]}
    setter = mock.Mock(return_value="ok")
    rows = sync.sync_published_thumbnails(
        published_dir=directory, out_root=tmp_path / "out", youtube_client=youtube,
        thumb_setter=setter, channel="prayer8", retry_permission=True, thumbnails_only=True,
    )
    assert len(rows) == 1 and rows[0]["thumbnail_status"] == "ok"
    assert setter.call_args.args[0] == "video8"
    youtube.videos.return_value.update.assert_not_called()
    meta = parse_script(path).meta
    assert meta["thumbnail_pending"] is False
    assert meta["thumbnail_revision"] == sync.THUMBNAIL_REVISION
    assert "thumbnail_error" not in meta and "thumbnail_retry_after" not in meta
    assert "thumbnail_retry_reason" not in meta
    assert sync.collect_pending_receipts(directory, channel_id="prayer8", retry_permission=True) == []


def test_short_403_gets_cooldown_and_keeps_retrying(receipts, tmp_path, monkeypatch):
    directory, write = receipts
    path = write("short-shield.md", format="short", thumbnail_pending=True,
                 thumbnail_error="HttpError 403 [forbidden]", thumbnail_attempts=5)
    poster = SimpleNamespace(path=tmp_path / "poster.jpg", contrast=10.0, hero_px=80,
                             lines=["one", "two", "three", "four"], kicker="SCRIPTURE", plate="plate",
                             as_dict=lambda: {"width": 1080})
    monkeypatch.setattr(sync, "_shorts_poster_for", lambda *args: poster)
    monkeypatch.setattr(sync, "apply_shorts_thumbnail", lambda *args, **kwargs: "HttpError 403 [forbidden]")
    rows = sync.sync_published_thumbnails(published_dir=directory, out_root=tmp_path / "out",
                                        youtube_client=mock.MagicMock(), channel="prayer8")
    assert rows[0]["thumbnail_status"] == "HttpError 403 [forbidden]"
    meta = parse_script(path).meta
    assert meta["thumbnail_pending"] is True and meta["thumbnail_attempts"] == 6
    assert meta["thumbnail_retry_reason"] == "permission" and meta["thumbnail_retry_after"]
    retry_at = datetime.fromisoformat(str(meta["thumbnail_retry_after"]).replace("Z", "+00:00"))
    remaining = retry_at - datetime.now(timezone.utc)
    assert timedelta(days=7, minutes=-2) < remaining <= timedelta(days=7)
    assert sync.collect_pending_short_receipts(directory, channel_id="prayer8") == []


def test_short_success_clears_failed_receipt(receipts, tmp_path, monkeypatch):
    directory, write = receipts
    path = write("short-shield.md", format="short", thumbnail_pending=True,
                 thumbnail_error="HttpError 403 [forbidden]", thumbnail_attempts=8,
                 thumbnail_retry_reason="permission", thumbnail_retry_after="2099-01-01T00:00:00Z")
    poster = SimpleNamespace(path=tmp_path / "poster.jpg", contrast=10.0, hero_px=80,
                             lines=["one", "two", "three", "four"], kicker="SCRIPTURE", plate="plate",
                             as_dict=lambda: {"width": 1080})
    monkeypatch.setattr(sync, "_shorts_poster_for", lambda *args: poster)
    monkeypatch.setattr(sync, "apply_shorts_thumbnail", lambda *args, **kwargs: "ok")
    rows = sync.sync_published_thumbnails(published_dir=directory, out_root=tmp_path / "out",
                                        youtube_client=mock.MagicMock(), channel="prayer8",
                                        retry_permission=True, thumbnails_only=True)
    assert rows[0]["thumbnail_status"] == "ok"
    meta = parse_script(path).meta
    assert meta["thumbnail_pending"] is False and meta["thumbnail_attempts"] == 0
    assert not any(key in meta for key in ("thumbnail_error", "thumbnail_retry_after", "thumbnail_retry_reason"))


def test_retry_permission_cli_requires_exact_channel_and_no_force(monkeypatch):
    for args in (["--retry-permission"], ["--retry-permission", "--channel", "unknown"],
                 ["--retry-permission", "--channel", "prayer8", "--force"],
                 ["--retry-permission", "--channel", "prayer8", "--all-channels"]):
        with pytest.raises(SystemExit):
            sync.main(args)
    monkeypatch.setattr(sync, "_has_youtube_credentials", lambda profile: False)
    assert sync.main(["--retry-permission", "--channel", "prayer8"]) == 1


def test_monitor_accepts_safe_targeted_dispatch():
    path = Path(__file__).resolve().parents[1] / ".github/workflows/monitor.yml"
    data = yaml.safe_load(path.read_text())
    assert data[True]["repository_dispatch"]["types"] == ["thumbnail-permission-verified"]
    step = next(s for s in data["jobs"]["monitor"]["steps"] if s.get("name") == "Sync live channel thumbnails")
    assert '--channel "$THUMBNAIL_RETRY_CHANNEL" --retry-permission' in step["run"]
    assert "--force" not in step["run"]
