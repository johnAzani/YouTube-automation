"""Regression tests for scripts.sync_published_thumbnails."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from pipeline.script_doc import parse_script
from scripts import sync_published_thumbnails as spt


class TestIsoDurationParser(unittest.TestCase):
    def test_parses_seconds_minutes_hours(self):
        self.assertEqual(spt.parse_iso8601_duration("PT57S"), 57)
        self.assertEqual(spt.parse_iso8601_duration("PT5M35S"), 335)
        self.assertEqual(spt.parse_iso8601_duration("PT6M"), 360)
        self.assertEqual(spt.parse_iso8601_duration("PT1H2M3S"), 3723)
        self.assertEqual(spt.parse_iso8601_duration(""), 0)


class TestSyncPublishedThumbnails(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.pub_dir = Path(self._tmp.name) / "published"
        self.out_dir = Path(self._tmp.name) / "out"
        self.pub_dir.mkdir(parents=True, exist_ok=True)

        self._write_receipt(
            "0008-psalm-91-prayer-of-divine-protection.md",
            {
                "id": "0008",
                "slug": "psalm-91-prayer-of-divine-protection",
                "title": "Psalm 91: The Complete Prayer of Divine Protection Before You Sleep | The Secret Place",
                "format": "longform",
                "privacy": "public",
                "youtube_video_id": "7RDX0fbIOtQ",
                "thumb_text": "UNDER HIS WINGS",
                "status": "published",
            },
        )
        self._write_receipt(
            "0009-psalm-23-the-lord-is-my-shepherd.md",
            {
                "id": "0009",
                "slug": "psalm-23-the-lord-is-my-shepherd",
                "title": "Psalm 23 | The Lord Is My Shepherd — Evening Sleep Prayer",
                "format": "longform",
                "privacy": "public",
                "youtube_video_id": "JZv67RNPCEI",
                "thumb_text": "THE LORD IS MY SHEPHERD",
                "status": "published",
            },
        )
        self._write_receipt(
            "short-0002-psalm-91-prayer-of-protection.md",
            {
                "id": "short-0002",
                "slug": "psalm-91-prayer-of-protection",
                "title": "Psalm 91 #Shorts",
                "format": "short",
                "youtube_video_id": "SG69BbNlfRw",
                "status": "published",
            },
        )

    def tearDown(self):
        self._tmp.cleanup()

    def _write_receipt(self, filename: str, fm: dict) -> Path:
        p = self.pub_dir / filename
        p.write_text(
            "---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\nBody text.\n",
            encoding="utf-8",
        )
        return p

    def test_skips_cleanly_without_youtube_credentials(self):
        with mock.patch.object(spt, "_has_youtube_credentials", return_value=False):
            rows = spt.sync_published_thumbnails(published_dir=self.pub_dir, out_root=self.out_dir)
        self.assertEqual(rows, [])

    def test_syncs_longform_promotes_0009_clarifies_0008_and_is_idempotent(self):
        fake_items = [
            {
                "id": "7RDX0fbIOtQ",
                "snippet": {
                    "title": "Psalm 91: The Complete Prayer of Divine Protection Before You Sleep | The Secret Place",
                    "description": "Desc",
                    "categoryId": "22",
                },
                "status": {"privacyStatus": "public", "uploadStatus": "processed"},
                "contentDetails": {"duration": "PT40S"},
            },
            {
                "id": "JZv67RNPCEI",
                "snippet": {
                    "title": "Psalm 23 | The Lord Is My Shepherd — Evening Sleep Prayer",
                    "description": "Desc",
                    "categoryId": "22",
                },
                "status": {"privacyStatus": "private", "uploadStatus": "processed"},
                "contentDetails": {"duration": "PT5M21S"},
            },
        ]

        # Per-id fake: the Shorts path asks for processingStatus and then for
        # snippet.thumbnails.shortsAspectRatio, and the whole point is that both
        # questions get the right answer for the right video.
        by_id = {item["id"]: item for item in fake_items}
        by_id["SG69BbNlfRw"] = {
            "id": "SG69BbNlfRw",
            "snippet": {"title": "Psalm 91 #Shorts", "description": "d", "categoryId": "22",
                        "thumbnails": {"default": {"url": "d"},
                                       "shortsAspectRatio": {"url": "s", "width": 1080,
                                                             "height": 1920}}},
            "status": {"privacyStatus": "public", "uploadStatus": "processed"},
            "processingDetails": {"processingStatus": "succeeded"},
            "contentDetails": {"duration": "PT49S"},
        }

        def _fake_list(**kwargs):
            wanted = [v for v in str(kwargs.get("id") or "").split(",") if v]
            rows = [by_id[v] for v in wanted if v in by_id]
            return mock.Mock(execute=mock.Mock(return_value={"items": rows}))

        fake_yt = mock.MagicMock()
        fake_yt.videos.return_value.list.side_effect = _fake_list
        thumb_uploads: list[tuple[str, Path]] = []

        def _fake_set_thumb(vid: str, path: Path) -> str:
            self.assertTrue(path.is_file())
            self.assertLess(path.stat().st_size, 2 * 1024 * 1024)
            thumb_uploads.append((vid, path))
            return "ok"

        rows = spt.sync_published_thumbnails(
            published_dir=self.pub_dir,
            out_root=self.out_dir,
            youtube_client=fake_yt,
            thumb_setter=_fake_set_thumb,
        )
        # Two long-form videos plus the Short that no earlier pass would touch.
        self.assertEqual(len(rows), 3)
        self.assertEqual([v for v, _ in thumb_uploads], ["7RDX0fbIOtQ", "JZv67RNPCEI"])
        self.assertEqual(rows[0]["hero"], "UNDER HIS WINGS")
        self.assertEqual(rows[1]["hero"], "RESTORE MY SOUL")
        short_row = rows[2]
        self.assertEqual(short_row["format"], "short")
        self.assertEqual(short_row["thumbnail_status"], "ok")
        self.assertEqual(short_row["poster"]["width"], 1080)
        self.assertEqual(short_row["poster"]["height"], 1920)
        self.assertGreaterEqual(short_row["poster"]["contrast"], 7.0)
        self.assertTrue(short_row["poster"]["safe_zone_ok"])

        # Verify 0008 (<90s) had its misleading "Complete Prayer" title clarified
        # and 0009 (private, >=180s, processed) was promoted to public.
        update_calls = fake_yt.videos.return_value.update.call_args_list
        self.assertEqual(len(update_calls), 2)
        by_id = {c.kwargs["body"]["id"]: c.kwargs for c in update_calls}

        self.assertEqual(by_id["7RDX0fbIOtQ"]["part"], "snippet")
        self.assertNotIn("Complete Prayer", by_id["7RDX0fbIOtQ"]["body"]["snippet"]["title"])
        self.assertIn("Brief Blessing", by_id["7RDX0fbIOtQ"]["body"]["snippet"]["title"])

        self.assertEqual(by_id["JZv67RNPCEI"]["part"], "status")
        self.assertEqual(by_id["JZv67RNPCEI"]["body"]["status"]["privacyStatus"], "public")

        # Verify YAML receipts were stamped and Short was untouched.
        doc_0008 = parse_script(self.pub_dir / "0008-psalm-91-prayer-of-divine-protection.md")
        doc_0009 = parse_script(self.pub_dir / "0009-psalm-23-the-lord-is-my-shepherd.md")
        doc_short = parse_script(self.pub_dir / "short-0002-psalm-91-prayer-of-protection.md")
        self.assertEqual(doc_0008.meta.get("thumbnail_revision"), spt.THUMBNAIL_REVISION)
        self.assertEqual(doc_0009.meta.get("thumbnail_revision"), spt.THUMBNAIL_REVISION)
        # A Short is now stamped like any other video — and only when YouTube
        # confirmed the 9:16 variant exists (`shortsAspectRatio`).
        self.assertEqual(doc_short.meta.get("thumbnail_revision"), spt.SHORTS_POSTER_REVISION)
        self.assertEqual(doc_short.meta.get("thumbnail_pending"), False)
        self.assertEqual(len(doc_short.meta.get("thumbnail_poster") or []), 4)

        # Second run must be a complete zero-API-call no-op!
        fake_yt.reset_mock()
        thumb_uploads.clear()
        rows2 = spt.sync_published_thumbnails(
            published_dir=self.pub_dir,
            out_root=self.out_dir,
            youtube_client=fake_yt,
            thumb_setter=_fake_set_thumb,
        )
        self.assertEqual(rows2, [])
        fake_yt.videos.assert_not_called()
        self.assertEqual(thumb_uploads, [])

    def test_deleted_remote_video_stamps_receipt_without_wasting_thumbnail_quota(self):
        fake_yt = mock.MagicMock()
        fake_yt.videos.return_value.list.return_value.execute.return_value = {"items": []}
        thumb_setter = mock.MagicMock(return_value="ok")

        rows = spt.sync_published_thumbnails(
            published_dir=self.pub_dir,
            out_root=self.out_dir,
            youtube_client=fake_yt,
            thumb_setter=thumb_setter,
        )
        longform_rows = [r for r in rows if r.get("format") != "short"]
        short_rows = [r for r in rows if r.get("format") == "short"]
        self.assertEqual(len(longform_rows), 2)
        self.assertTrue(all(r["thumbnail_status"] == "video_not_found" for r in longform_rows))
        self.assertEqual(len(short_rows), 1, "the Short is repaired by this pass too")
        self.assertTrue(short_rows[0]["thumbnail_status"].startswith("deferred_processing"))
        thumb_setter.assert_not_called()
        doc_0009 = parse_script(self.pub_dir / "0009-psalm-23-the-lord-is-my-shepherd.md")
        self.assertEqual(doc_0009.meta.get("youtube_status"), "deleted_or_missing")
        self.assertEqual(doc_0009.meta.get("thumbnail_revision"), spt.THUMBNAIL_REVISION)


class TestChannelScopedThumbnailRepair(unittest.TestCase):
    """A token repairs its own channel only, and a refusal must be visible.

    Both channels got a video published with no custom thumbnail while the
    receipt claimed `thumbnail_revision: ctr-v3-cinema`: `upload()` swallowed the
    `thumbnails.set` error, the receipt was stamped anyway, and this repair pass
    then skipped the video forever. These pin the three things that fix it.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.pub_dir = Path(self._tmp.name) / "published"
        self.out_dir = Path(self._tmp.name) / "out"
        self.pub_dir.mkdir(parents=True, exist_ok=True)
        self._write(
            "0036-psalm-5-morning-prayer.md",
            {
                "id": "0036",
                "slug": "psalm-5-morning-prayer",
                "title": "Psalm 5 | Morning Prayer",
                "format": "longform",
                "privacy": "public",
                "channel": "prayer2",
                "youtube_video_id": "_vp27ZYPYaY",
                "status": "published",
                "thumbnail_pending": True,
            },
        )
        self._write(
            "0040-psalm-4-night-prayer.md",
            {
                "id": "0040",
                "slug": "psalm-4-night-prayer",
                "title": "Psalm 4 | Night Prayer",
                "format": "longform",
                "privacy": "public",
                "youtube_video_id": "SPvideoID1",
                "status": "published",
            },
        )

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, filename: str, fm: dict) -> Path:
        p = self.pub_dir / filename
        p.write_text(
            "---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\nBody text.\n",
            encoding="utf-8",
        )
        return p

    def _fake_client(self, ids: list[str]):
        yt = mock.MagicMock()
        yt.videos.return_value.list.return_value.execute.return_value = {
            "items": [
                {
                    "id": vid,
                    "snippet": {"title": f"t {vid}", "description": "d", "categoryId": "22"},
                    "status": {"privacyStatus": "public", "uploadStatus": "processed"},
                    "contentDetails": {"duration": "PT7M18S"},
                }
                for vid in ids
            ]
        }
        return yt

    def test_each_channel_repairs_only_its_own_receipts(self):
        seen: list[str] = []

        def _setter(vid, path):
            seen.append(vid)
            return "ok"

        spt.sync_published_thumbnails(
            published_dir=self.pub_dir,
            out_root=self.out_dir,
            youtube_client=self._fake_client(["_vp27ZYPYaY"]),
            thumb_setter=_setter,
            channel="prayer2",
        )
        self.assertEqual(seen, ["_vp27ZYPYaY"], "must not touch the other channel's video")

        seen.clear()
        spt.sync_published_thumbnails(
            published_dir=self.pub_dir,
            out_root=self.out_dir,
            youtube_client=self._fake_client(["SPvideoID1"]),
            thumb_setter=_setter,
            channel="secret-place",
        )
        self.assertEqual(seen, ["SPvideoID1"])

    def test_a_refused_thumbnail_is_recorded_and_stays_queued(self):
        rows = spt.sync_published_thumbnails(
            published_dir=self.pub_dir,
            out_root=self.out_dir,
            youtube_client=self._fake_client(["_vp27ZYPYaY"]),
            thumb_setter=lambda vid, path: "HttpError 403 insufficientPermissions",
            channel="prayer2",
        )
        self.assertEqual(len(rows), 1)
        doc = parse_script(self.pub_dir / "0036-psalm-5-morning-prayer.md")
        self.assertNotIn("thumbnail_revision", doc.meta)
        self.assertTrue(doc.meta.get("thumbnail_pending"))
        self.assertIn("insufficientPermissions", str(doc.meta.get("thumbnail_error")))
        # Still pending, so the next monitor pass retries it.
        pending = spt.collect_pending_receipts(published_dir=self.pub_dir, channel_id="prayer2")
        self.assertEqual([d.id for _, d in pending], ["0036"])

    def test_a_repaired_thumbnail_is_stamped_and_retires_the_pending_flag(self):
        spt.sync_published_thumbnails(
            published_dir=self.pub_dir,
            out_root=self.out_dir,
            youtube_client=self._fake_client(["_vp27ZYPYaY"]),
            thumb_setter=lambda vid, path: "ok",
            channel="prayer2",
        )
        doc = parse_script(self.pub_dir / "0036-psalm-5-morning-prayer.md")
        self.assertEqual(doc.meta.get("thumbnail_revision"), spt.THUMBNAIL_REVISION)
        self.assertFalse(doc.meta.get("thumbnail_pending"))
        self.assertEqual(
            spt.collect_pending_receipts(published_dir=self.pub_dir, channel_id="prayer2"), []
        )

    def test_all_channels_mode_covers_every_live_channel(self):
        from pipeline.channels import scheduled_channels

        with mock.patch.object(spt, "_has_youtube_credentials", return_value=False):
            results = spt.sync_all_channels(force=True)
        self.assertEqual(sorted(results), sorted(scheduled_channels()))
        self.assertIn("secret-place", results)
        self.assertIn("prayer2", results)

    def test_monitor_workflow_supplies_both_channels_credentials(self):
        text = (Path(__file__).resolve().parent.parent / ".github/workflows/monitor.yml").read_text()
        self.assertIn("sync_published_thumbnails --all-channels", text)
        for key in ("YOUTUBE_CLIENT_ID", "PRAYER2_YOUTUBE_CLIENT_ID",
                    "PRAYER2_YOUTUBE_CLIENT_SECRET", "PRAYER2_YOUTUBE_REFRESH_TOKEN"):
            self.assertIn(key, text)


if __name__ == "__main__":
    unittest.main()
