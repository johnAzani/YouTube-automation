"""Safety and rights gates for authored YouTube Shorts releases."""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pipeline.assemble import ffmpeg_bin
from pipeline.licences import load_ledger, uncleared_stills, unsafe_stills
from pipeline.metadata import build_description, write_metadata_pack
from pipeline.script_doc import Scene, ScriptDoc
from pipeline.short_release import (
    EDITIONS,
    run_short_release,
    select_next_queued_short,
    verify_short_render,
)
import tools.deep_dive as deep_dive
import tools.shorts as shorts_tool


def _make_sample_mp4(dest: Path, width: int, height: int, seconds: float = 20.0, audio: bool = True) -> Path:
    cmd = [
        ffmpeg_bin(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=navy:size={width}x{height}:rate=10:duration={seconds}",
    ]
    if audio:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}"]
    cmd += ["-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p"]
    if audio:
        cmd += ["-c:a", "aac", "-shortest"]
    cmd.append(str(dest))
    subprocess.run(cmd, check=True, capture_output=True)
    return dest


class ShortReleaseTests(unittest.TestCase):
    def test_enron_short_and_deep_dive_use_only_cleared_stills(self):
        ledger = load_ledger(use_cache=False)
        for label, scenes in (
            ("short-enron", shorts_tool.SCRIPTS["short-enron"]["scenes"]),
            ("deep-dive-enron", deep_dive.SCRIPTS["enron"]["scenes"]),
        ):
            stills = [sc["img"] for sc in scenes]
            with self.subTest(edition=label):
                self.assertEqual(unsafe_stills(stills, ledger), [])
                self.assertEqual(uncleared_stills(stills, ledger), [])

    def test_short_enron_uses_ten_distinct_plates(self):
        stills = [sc["img"] for sc in shorts_tool.SCRIPTS["short-enron"]["scenes"]]
        self.assertEqual(len(stills), 10)
        self.assertEqual(len(set(stills)), 10)

    def test_verify_short_render_accepts_cleared_vertical_short(self):
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            mp4 = _make_sample_mp4(tdir / "short.mp4", 720, 1280, seconds=20.0, audio=True)
            sources = tdir / "scene-sources.json"
            sources.write_text(
                json.dumps(
                    [
                        {
                            "scene": 1,
                            "fallback": True,
                            "provider": "existing story archive",
                            "file": "houston-skyline-plate-1.png",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            probe = verify_short_render(mp4, sources)
            self.assertEqual((probe.width, probe.height), (720, 1280))
            self.assertTrue(probe.has_audio)

    def test_verify_short_render_rejects_horizontal_or_encumbered_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            horiz = _make_sample_mp4(tdir / "landscape.mp4", 1280, 720, seconds=20.0, audio=True)
            vert = _make_sample_mp4(tdir / "vertical.mp4", 720, 1280, seconds=20.0, audio=True)
            clean_sources = tdir / "clean.json"
            clean_sources.write_text(
                json.dumps([{"scene": 1, "fallback": True, "file": "houston-skyline-plate-1.png"}]),
                encoding="utf-8",
            )
            bad_sources = tdir / "bad.json"
            bad_sources.write_text(
                json.dumps(
                    [
                        {
                            "scene": 1,
                            "fallback": True,
                            "file": "andrew-fastow-enron-cfo-trial-photo-2.jpg",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "vertical"):
                verify_short_render(horiz, clean_sources)
            with self.assertRaisesRegex(RuntimeError, "uncleared fallback"):
                verify_short_render(vert, bad_sources)

    def test_short_metadata_injects_shorts_hashtag_and_skips_chapters(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = ScriptDoc(
                path=Path(tmp) / "s.md",
                meta={
                    "id": "S1",
                    "title": "How Enron Failed #Shorts",
                    "slug": "how-enron-failed",
                    "status": "approved",
                    "format": "short",
                    "niche": "finance",
                    "tags": ["enron", "accounting"],
                    "description": "Primary source summary.",
                },
                scenes=[Scene(index=1, heading="Hook", narration="One two three.")],
            )
            desc = build_description(doc, [30.0])
            self.assertIn("#Shorts", desc)
            self.assertNotIn("CHAPTERS", desc)
            pack = write_metadata_pack(doc, [30.0], Path(tmp))
            self.assertEqual(pack["hashtags"][0], "#Shorts")

    def test_run_short_release_uploads_and_writes_published_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            social_dir = tdir / "social"
            social_dir.mkdir(parents=True)
            mp4 = _make_sample_mp4(social_dir / "short-enron.mp4", 720, 1280, seconds=20.0, audio=True)
            stock_dir = tdir / "output" / "short-stock" / "short-enron"
            stock_dir.mkdir(parents=True)
            (stock_dir / "scene-sources.json").write_text(
                json.dumps([{"scene": 1, "fallback": True, "file": "houston-skyline-plate-1.png"}]),
                encoding="utf-8",
            )
            pub_dir = tdir / "published"
            out_dir = tdir / "output"

            fake_upload = SimpleNamespace(
                video_id="ytShort123",
                privacy_status="private",
                watch_url="https://youtu.be/ytShort123",
                auto_published=False,
            )
            with (
                patch("pipeline.short_release.REPO_ROOT", tdir),
                patch("pipeline.short_release.PUBLISHED_DIR", pub_dir),
                patch("pipeline.short_release.OUTPUT_DIR", out_dir),
                patch("pipeline.short_release.CONFIG.youtube_refresh_token", "rtok"),
                patch("pipeline.short_release.CONFIG.youtube_client_id", "cid"),
                patch("pipeline.short_release.CONFIG.youtube_client_secret", "csec"),
                patch("pipeline.upload.upload", return_value=fake_upload) as upload_mock,
                patch("pipeline.upload.set_video_thumbnail", return_value="ok"),
                patch("pipeline.upload.audit_channel_videos", return_value=[{"id": "ytShort123", "uploadStatus": "processed"}]),
                patch("pipeline.short_release._open_release_ticket") as ticket_mock,
            ):
                res = run_short_release("short-enron", dry_run=False, skip_render=True)

            self.assertTrue(mp4.exists())
            self.assertEqual(res["video_id"], "ytShort123")
            self.assertEqual(res["shorts_url"], "https://www.youtube.com/shorts/ytShort123")
            upload_mock.assert_called_once()
            ticket_mock.assert_called_once()
            receipt = pub_dir / f"{EDITIONS['short-enron'].slug}.md"
            self.assertTrue(receipt.is_file())
            text = receipt.read_text(encoding="utf-8")
            self.assertIn('youtube_video_id: "ytShort123"', text)
            self.assertIn('youtube_shorts_url: "https://www.youtube.com/shorts/ytShort123"', text)

    def test_select_next_queued_short_reads_approved_and_unlinks_after_upload(self):
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            qdir = tdir / "shorts-queue"
            qdir.mkdir(parents=True)
            manifest = qdir / "0001-short-enron.yml"
            manifest.write_text('short: "short-enron"\nstatus: approved\n', encoding="utf-8")
            selected = select_next_queued_short(qdir)
            self.assertEqual(selected, (manifest, "short-enron"))

            social_dir = tdir / "social"
            social_dir.mkdir(parents=True)
            _make_sample_mp4(social_dir / "short-enron.mp4", 720, 1280, seconds=20.0, audio=True)
            stock_dir = tdir / "output" / "short-stock" / "short-enron"
            stock_dir.mkdir(parents=True)
            (stock_dir / "scene-sources.json").write_text(
                json.dumps([{"scene": 1, "fallback": True, "file": "houston-skyline-plate-1.png"}]),
                encoding="utf-8",
            )
            fake_upload = SimpleNamespace(
                video_id="ytShort999",
                privacy_status="private",
                watch_url="https://youtu.be/ytShort999",
                auto_published=False,
            )
            with (
                patch("pipeline.short_release.REPO_ROOT", tdir),
                patch("pipeline.short_release.PUBLISHED_DIR", tdir / "published"),
                patch("pipeline.short_release.OUTPUT_DIR", tdir / "output"),
                patch("pipeline.short_release.CONFIG.youtube_refresh_token", "rtok"),
                patch("pipeline.short_release.CONFIG.youtube_client_id", "cid"),
                patch("pipeline.short_release.CONFIG.youtube_client_secret", "csec"),
                patch("pipeline.upload.upload", return_value=fake_upload),
                patch("pipeline.upload.set_video_thumbnail", return_value="ok"),
                patch("pipeline.upload.audit_channel_videos", return_value=[{"id": "ytShort999", "uploadStatus": "processed"}]),
                patch("pipeline.short_release._open_release_ticket"),
            ):
                run_short_release(
                    "short-enron",
                    dry_run=False,
                    skip_render=True,
                    manifest_path=manifest,
                )
            self.assertFalse(manifest.exists())
            self.assertIsNone(select_next_queued_short(qdir))

    def test_run_short_release_honors_privacy_and_replace_from_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            social_dir = tdir / "social"
            social_dir.mkdir(parents=True)
            _make_sample_mp4(social_dir / "short-psalm91.mp4", 720, 1280, seconds=20.0, audio=True)
            stock_dir = tdir / "output" / "short-stock" / "short-psalm91"
            stock_dir.mkdir(parents=True)
            (stock_dir / "scene-sources.json").write_text(
                json.dumps([{"scene": 1, "fallback": True, "file": "short-prayer-scene-01.jpg"}]),
                encoding="utf-8",
            )
            qdir = tdir / "shorts-queue"
            qdir.mkdir(parents=True)
            manifest = qdir / "short-0002.yml"
            manifest.write_text(
                'short: "short-psalm91"\nstatus: approved\nreplace: true\nprivacy: "public"\n',
                encoding="utf-8",
            )

            fake_upload = SimpleNamespace(
                video_id="ytPsalm123",
                privacy_status="public",
                watch_url="https://youtu.be/ytPsalm123",
                auto_published=True,
            )
            with (
                patch("pipeline.short_release.REPO_ROOT", tdir),
                patch("pipeline.short_release.PUBLISHED_DIR", tdir / "published"),
                patch("pipeline.short_release.OUTPUT_DIR", tdir / "output"),
                patch("pipeline.short_release.CONFIG.youtube_refresh_token", "rtok"),
                patch("pipeline.short_release.CONFIG.youtube_client_id", "cid"),
                patch("pipeline.short_release.CONFIG.youtube_client_secret", "csec"),
                patch("pipeline.upload.upload", return_value=fake_upload) as upload_mock,
                patch("pipeline.upload.set_video_thumbnail", return_value="ok"),
                patch("pipeline.upload.audit_channel_videos", return_value=[{"id": "ytPsalm123", "uploadStatus": "processed"}]),
                patch("pipeline.short_release._open_release_ticket"),
            ):
                res = run_short_release(
                    "short-psalm91",
                    dry_run=False,
                    skip_render=True,
                    manifest_path=manifest,
                )

            self.assertEqual(res["video_id"], "ytPsalm123")
            self.assertEqual(res["privacy_status"], "public")
            # Verify privacy='public' was forwarded to upload()
            _, kwargs = upload_mock.call_args
            self.assertEqual(kwargs.get("privacy"), "public")


    def test_short_plates_fill_vertical_frame_edge_to_edge(self):
        img_name = shorts_tool.SCRIPTS["short-enron"]["scenes"][4]["img"]
        plate = shorts_tool.prep_plate(Path(shorts_tool.IMG) / img_name)
        self.assertEqual(plate.size, (1080, 1920))
        top_band = [plate.getpixel((x, 40)) for x in range(100, 980, 80)]
        bot_band = [plate.getpixel((x, 1880)) for x in range(100, 980, 80)]
        self.assertGreater(max(sum(px) for px in top_band), 90)
        self.assertGreater(max(sum(px) for px in bot_band), 90)

    def test_scroll_stopping_short_thumbnail_dimensions_and_size(self):
        from PIL import Image
        from pipeline.thumbnail import generate_short_scroll_stopper_thumbnail

        with tempfile.TemporaryDirectory() as tmp:
            out_jpg = Path(tmp) / "thumb.jpg"
            hero = Path(__file__).resolve().parent.parent / "image-search" / "short-enron-thumb-hero.jpg"
            res = generate_short_scroll_stopper_thumbnail(hero, out_jpg)
            self.assertTrue(res.is_file())
            self.assertLess(res.stat().st_size, 2 * 1024 * 1024)
            with Image.open(res) as im:
                self.assertEqual(im.size, (1280, 720))



if __name__ == "__main__":
    unittest.main()
