"""Regression guards for multi-channel supply, quota isolation, rotation, and workflow safety."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import yaml

ROOT = Path(__file__).resolve().parents[1]
UTC = timezone.utc


class _MultiAuthorFakeBrain:
    def __init__(self, queue_dir: Path, channel_id: str = "prayer3", words: int = 900):
        self.queue_dir = queue_dir
        self.channel_id = channel_id
        self.words = words
        self.calls = 0

    def replenish_pipeline(self, min_runway_days: float = 2.0):
        self.calls += 1
        job_id = f"20{self.calls:02d}"
        path = self.queue_dir / f"{job_id}-psalm-91-midday.md"
        filler = " ".join(["steadfast"] * max(0, self.words - 25))
        path.write_text(
            f"---\n"
            f'id: "{job_id}"\n'
            f'title: "Psalm 91: Midday Prayer | The Midday Watch"\n'
            f"channel: {self.channel_id}\n"
            f"status: draft\n"
            f"format: longform\n"
            f"voice: Charon\n"
            f"---\n\n"
            f"## Scene 1 — Refuge (Verse 1)\n"
            f"He that dwelleth in the secret place of the most High shall abide.\n"
            f"{filler}\n",
            encoding="utf-8",
        )
        return SimpleNamespace(
            job_id=job_id,
            longform_path=path,
            word_count=self.words,
            short_manifest_path=None,
        )


class TestSupplyMultiAuthorAndColdStart(unittest.TestCase):
    def test_summary_does_not_crash_when_two_or_more_scripts_authored(self):
        """7 Nov live crash: authoring >=2 scripts turned report.authored into a list."""
        from pipeline import supply as sp

        with tempfile.TemporaryDirectory() as tmp:
            qdir = Path(tmp)
            brain = _MultiAuthorFakeBrain(qdir, channel_id="prayer2")
            with mock.patch("pipeline.supply.expand_backlog", return_value=[]):
                report = sp.ensure_supply(
                    brain, queue_dir=qdir, min_publishable=3, max_authors=2, channel_id="prayer2"
                )
        self.assertEqual(brain.calls, 2)
        self.assertIsInstance(report.authored, list)
        summary = report.summary()
        self.assertIn("authored 2001, 2002", summary)
        self.assertIn("2 publishable after", summary)

    def test_cold_start_channel_spends_empty_queue_author_budget(self):
        """R5: an empty channel (0 publishable) can author up to MAX_AUTHORS_WHEN_EMPTY."""
        from pipeline import supply as sp

        with tempfile.TemporaryDirectory() as tmp:
            qdir = Path(tmp)
            brain = _MultiAuthorFakeBrain(qdir, channel_id="prayer3")
            with mock.patch("pipeline.supply.expand_backlog", return_value=[]):
                report = sp.ensure_supply(
                    brain, queue_dir=qdir, min_publishable=6, channel_id="prayer3"
                )
        self.assertEqual(brain.calls, sp.MAX_AUTHORS_WHEN_EMPTY)
        self.assertEqual(report.publishable_after, sp.MAX_AUTHORS_WHEN_EMPTY)
        self.assertIn("2004", report.summary())

    def test_factcheck_accepts_staged_incoming_file_path(self):
        """verify_and_stage runs in .incoming/ before atomic rename into content/queue/."""
        from scripts import factcheck

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            incoming = root / "queue" / ".incoming"
            out_dir = root / "factcheck"
            incoming.mkdir(parents=True)
            staged = incoming / "2099-psalm-23-test.md"
            staged.write_text(
                '---\nid: "2099"\ntitle: "Psalm 23 Prayer"\nslug: psalm-23-test\n'
                "channel: prayer3\nstatus: draft\nformat: longform\n---\n\n"
                "## Scene 1 — Shepherd\nThe Lord is my shepherd on 12 March 1933.\n",
                encoding="utf-8",
            )
            with mock.patch.object(factcheck, "ROOT", root), \
                 mock.patch.object(factcheck, "QUEUE_DIR", root / "queue"), \
                 mock.patch.object(factcheck, "OUT_DIR", out_dir):
                rc = factcheck.main([str(staged), "--force"])
            self.assertEqual(rc, 0)
            sheet = out_dir / "2099-psalm-23-test.md"
            self.assertTrue(sheet.is_file())
            self.assertIn(factcheck._sha(staged), sheet.read_text(encoding="utf-8"))

    def test_expand_scripts_rejects_off_brand_phrases_and_retired_hardcode(self):
        from tools import expand_scripts as ex

        source = (ROOT / "tools" / "expand_scripts.py").read_text(encoding="utf-8")
        self.assertNotIn('model="gemini-2.5-flash"', source)
        self.assertIn("text_model_candidates()", source)

        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "1038-morning.md"
            p.write_text(
                '---\nid: "1038"\ntitle: "Psalm 5 Morning"\nchannel: prayer2\n'
                "status: approved\nformat: longform\n---\n\n"
                "## Scene 1 — Dawn\nMy voice shalt thou hear in the morning, O Lord.\n",
                encoding="utf-8",
            )
            job = ex.load_job(p)
            leaked = (
                "## Scene 1 — Dawn\nMy voice shalt thou hear in the morning, O Lord.\n"
                "Welcome back to The Secret Place tonight as you drift to sleep.\n"
                + ("Walk steadily in wisdom and grace this hour. " * 140)
            )
            problems = ex.validate(job, leaked)
            self.assertTrue(any("forbidden phrase" in prob for prob in problems), problems)


class TestPerChannelQuotaIsolationAndRotation(unittest.TestCase):
    def test_quota_paused_on_one_channel_never_blocks_another_channel(self):
        """R15: secret-place hitting TTS quota must never block prayer2 or prayer3."""
        from pipeline import run

        reset = (datetime.now(UTC) + timedelta(hours=14)).isoformat()
        with tempfile.TemporaryDirectory() as tmp:
            content = Path(tmp)
            qdir = content / "queue"
            sdir = content / "shorts-queue"
            qdir.mkdir()
            sdir.mkdir()
            (qdir / "0015-sp.md").write_text(
                f'---\nid: "0015"\ntitle: "SP"\nchannel: secret-place\n'
                f'status: quota_paused\nquota_reset_utc: "{reset}"\n---\n\n## Scene 1\nAmen.\n',
                encoding="utf-8",
            )
            (sdir / "0015-short.yml").write_text(
                f'short: short-psalm91v5\nchannel: secret-place\n'
                f'status: quota_paused\nquota_reset_utc: "{reset}"\n',
                encoding="utf-8",
            )
            with mock.patch.object(run, "QUEUE_DIR", qdir):
                self.assertIsNotNone(run.quota_blocked_until(channel_id="secret-place"))
                self.assertIsNone(run.quota_blocked_until(channel_id="prayer2"))
                self.assertIsNone(run.quota_blocked_until(channel_id="prayer3"))

    def test_repo_wide_cooldown_stays_open_while_any_servable_channel_can_publish(self):
        from scripts import automation_monitor as am

        now = datetime(2026, 11, 7, 15, 0, tzinfo=UTC)
        reset_at = datetime(2026, 11, 8, 8, 0, tzinfo=UTC)

        def per_channel(_now, channel_id=None):
            return reset_at if channel_id == "secret-place" else None

        with mock.patch.object(am, "_servable_scheduled_channels",
                               return_value=["secret-place", "prayer2"]), \
             mock.patch("pipeline.run.quota_blocked_until", side_effect=per_channel), \
             mock.patch("scripts.pipeline_watchdog.last_publish",
                        return_value=(Path("x.md"), now - timedelta(hours=2))):
            self.assertEqual(am.active_quota_cooldown(now, channel_id="secret-place"), reset_at)
            self.assertIsNone(am.active_quota_cooldown(now, channel_id="prayer2"))
            self.assertIsNone(
                am.active_quota_cooldown(now),
                "produce.yml as a whole is NOT in cooldown while prayer2 can publish",
            )

    def test_supervisor_skips_quota_blocked_and_empty_channels_and_rotates_attempts(self):
        """R15 + R16 + R27: skip blocked/empty channels and rotate least-recently-attempted."""
        from scripts import scheduler_supervisor as sup

        now = datetime(2026, 11, 7, 15, 0, tzinfo=UTC)
        reset_at = datetime(2026, 11, 8, 8, 0, tzinfo=UTC)

        with mock.patch.object(sup, "_channels",
                               return_value=["secret-place", "prayer2", "prayer3"]), \
             mock.patch.object(sup, "_channel_has_supply",
                               side_effect=lambda c: c in {"secret-place", "prayer2"}), \
             mock.patch("scripts.automation_monitor.active_quota_cooldown",
                        side_effect=lambda _n, channel_id=None: (
                            reset_at if channel_id == "secret-place" else None
                        )):
            ready = sup._unserved_produce_channels(set(), now=now)
            self.assertEqual(ready, ["prayer2"])

        # Rotation when all three channels have supply and none is quota-blocked:
        with mock.patch.object(sup, "_channels",
                               return_value=["secret-place", "prayer2", "prayer3"]), \
             mock.patch.object(sup, "_channel_has_supply", return_value=True), \
             mock.patch("scripts.automation_monitor.active_quota_cooldown", return_value=None):
            order1 = sup._unserved_produce_channels(set(), now=now, attempted=["secret-place"])
            self.assertEqual(order1, ["prayer2", "prayer3", "secret-place"])
            order2 = sup._unserved_produce_channels(
                set(), now=now, attempted=["secret-place", "prayer2"]
            )
            self.assertEqual(order2, ["prayer3", "secret-place", "prayer2"])

    def test_pages_deployment_never_wakes_supervisor_and_health_write_skips_noop(self):
        """R9: break the supervisor -> commit -> pages -> supervisor 60s loop."""
        from scripts import scheduler_supervisor as sup

        wf = yaml.safe_load(
            (ROOT / ".github" / "workflows" / "scheduler-supervisor.yml").read_text(encoding="utf-8")
        )
        triggers = wf.get(True) or wf.get("on") or {}
        woken_by = (triggers.get("workflow_run") or {}).get("workflows") or []
        self.assertNotIn("pages build and deployment", woken_by)

        with tempfile.TemporaryDirectory() as tmp:
            health_path = Path(tmp) / "schedule-health.json"
            h1 = {
                "generated_at": "2026-11-07T14:00:00+00:00",
                "silence_minutes": 4,
                "last_run_at": "2026-11-07T13:56:00+00:00",
                "delivered_late": [],
                "on_time": [{"workflow": "produce.yml", "slot": "s1"}],
                "warn_minutes": 90,
                "alarm_minutes": 240,
            }
            h2 = {**h1, "generated_at": "2026-11-07T14:01:00+00:00", "silence_minutes": 5}
            with mock.patch.object(sup, "SCHEDULE_HEALTH", health_path):
                sup.save_schedule_health(h1)
                first_bytes = health_path.read_text(encoding="utf-8")
                sup.save_schedule_health(h2)
                self.assertEqual(health_path.read_text(encoding="utf-8"), first_bytes)


class TestMultiChannelWorkflowAndVoiceIsolation(unittest.TestCase):
    def test_produce_artifacts_and_chunk_caches_are_channel_scoped(self):
        """R18 + HTTP 409 artifact conflict guard + post-repair queue check."""
        text = (ROOT / ".github" / "workflows" / "produce.yml").read_text(encoding="utf-8")
        self.assertIn("chunks-tts-v5-${{ matrix.channel }}-${{ github.run_id }}", text)
        self.assertIn("release-report-${{ github.run_id }}-${{ matrix.channel }}", text)
        self.assertIn("style-frames-${{ github.run_id }}-${{ matrix.channel }}", text)
        self.assertIn("render-${{ github.run_id }}-${{ matrix.channel }}", text)
        self.assertLess(
            text.index("id: supply"),
            text.index("id: channel_queue"),
            "queue check must run after supply repair so newly authored scripts can publish",
        )

    def test_edge_fallback_uses_slower_rate_and_honest_speaker_label(self):
        """R28: edge-tts fallback slows by -5% and duration errors name the real engine."""
        from pipeline import prayer_pipeline as pp

        doc = SimpleNamespace(full_narration="word " * 900, word_count=900)
        with tempfile.TemporaryDirectory() as tmp:
            audio = Path(tmp) / "narration.mp3"
            with mock.patch.object(pp, "synthesize_gemini_audio", side_effect=RuntimeError("no audio")), \
                 mock.patch.object(pp, "synthesize_edge", return_value=("edge-tts", [])) as edge:
                engine = pp._narrate(doc, audio)
        self.assertEqual(engine, "edge-tts")
        self.assertEqual(edge.call_args.kwargs.get("rate"), "-5%")

        source = (ROOT / "pipeline" / "prayer_pipeline.py").read_text(encoding="utf-8")
        self.assertIn("Actual {speaker} narration is", source)

    def test_release_ticket_deduplicates_already_recorded_video(self):
        """§70: never open duplicate release tickets when a video receipt already exists."""
        from pipeline import run
        from pipeline.script_doc import ScriptDoc

        doc = ScriptDoc(
            path=Path("0099-test.md"),
            meta={"id": "0099", "title": "Psalm 23 Prayer", "format": "longform"},
        )
        with tempfile.TemporaryDirectory() as tmp:
            pdir = Path(tmp)
            (pdir / "0099-test.md").write_text(
                '---\nyoutube_video_id: "xyz123"\nrelease_ticket_opened: true\n---\n',
                encoding="utf-8",
            )
            with mock.patch.object(run, "PUBLISHED_DIR", pdir), \
                 mock.patch.dict(os.environ, {"GITHUB_ACTIONS": "true", "GH_TOKEN": "tok"}), \
                 mock.patch("subprocess.run") as subproc:
                run._open_release_ticket(doc, "https://youtu.be/xyz123", "private", video_id="xyz123")
                run._open_release_ticket(doc, "https://youtu.be/new999", "already_published", video_id="new999")

        subproc.assert_not_called()

    def test_brain_workflow_uses_isolated_staging_not_directory_wide_git_add(self):
        """Multi-channel Brain runs must never run `reset --mixed origin/main` + `git add content/queue/`."""
        wf = ROOT / ".github" / "workflows" / "gemini_brain.yml"
        text = wf.read_text(encoding="utf-8")
        self.assertNotIn("git add content/queue/ content/shorts-queue/", text)
        self.assertIn("START_SHA=", text)
        self.assertIn("/tmp/brain-touched.txt", text)

    def test_normalize_authored_script_strips_double_frontmatter_and_stage_directions(self):
        """Regression: `_repair_envelope` + stage directions must never leak into TTS narration."""
        from pipeline import originality
        from pipeline.gemini_brain import normalize_authored_script_markdown
        from pipeline.script_doc import parse_script

        raw = """---
id: '0049'
slug: psalm-55-17-midday-pause
title: "Psalm 55:17 — At Noon Will I Pray | The Midday Watch"
status: approved
channel: prayer3
niche: daily-devotional
thumb_text: "PAUSE AT NOON"
originality: "Original devotional exposition on Psalm 55:17 KJV."
---

---
title: "Psalm 55:17 — At Noon Will I Pray | The Midday Watch"
description: "Pause at noonday with Psalm 55:17."
tags: ["midday prayer", "psalm 55"]
---

### Scene 1: The Noonday Hook & The Pause (Movement 1)
- Visual Asset Query: "Sunbeams piercing through quiet cathedral windows high resolution public domain"
- Kinetic Visual: "PAUSE AT NOON"
- Narration:
Evening, and morning, and at noon, will I pray, and cry aloud: and he shall hear my voice.
Step out of the noise of *this hour* and breathe before the throne of grace, laying down every burden,
every unfinished task, every anxious calculation of the morning, and receiving the steady peace of God
that keeps heart and mind anchored in Christ Jesus throughout the heat of this day.

### Scene 2: Sent Back Into the Day
[Visual Asset 2: Calm river under afternoon sun]
[Narration:]
Commit thy works unto the Lord, and thy thoughts shall be established as you walk back into the afternoon
in quietness, diligence, integrity, and unshaken confidence that the Father who heard your voice at noon
goes before you until evening falls and brings your labor to peaceful completion. Amen.
"""
        cleaned = normalize_authored_script_markdown(raw, channel_id="prayer3")
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "0049-psalm-55-17-midday-pause.md"
            out.write_text(cleaned, encoding="utf-8")
            doc = parse_script(out)

        self.assertEqual(doc.channel, "prayer3")
        self.assertEqual(doc.meta["niche"], "faith and prayer")
        self.assertEqual(len(doc.scenes), 2)
        self.assertEqual(doc.scenes[0].heading, "The Noonday Hook & The Pause")
        self.assertEqual(originality.check(doc), [])
        self.assertEqual(len(doc.meta.get("asset_queries") or []), 6)
        self.assertIsInstance(doc.meta.get("asset_query_verification"), dict)
        joined = "\n".join(s.narration for s in doc.scenes)
        for forbidden in ("Visual Asset", "Kinetic Visual", "Typography:", "Narration:", "---", "*", "["):
            self.assertNotIn(forbidden, joined)

    def test_thumbnail_workflows_wire_every_registered_channel(self):
        """Every registered channel must receive its YouTube credentials in monitor.yml & set-thumbnail.yml."""
        from pipeline.channels import CHANNELS

        monitor_text = (ROOT / ".github" / "workflows" / "monitor.yml").read_text(encoding="utf-8")
        set_thumb_text = (ROOT / ".github" / "workflows" / "set-thumbnail.yml").read_text(encoding="utf-8")
        for cid, profile in CHANNELS.items():
            self.assertIn(cid, set_thumb_text, f"set-thumbnail.yml missing channel option {cid}")
            prefix = (profile.secret_prefix or "").strip().rstrip("_")
            token_var = f"{prefix}_YOUTUBE_REFRESH_TOKEN" if prefix else "YOUTUBE_REFRESH_TOKEN"
            self.assertIn(token_var, monitor_text, f"monitor.yml missing {token_var} for {cid}")
            self.assertIn(token_var, set_thumb_text, f"set-thumbnail.yml missing {token_var} for {cid}")

    def test_growth_community_and_supervisor_workflows_are_multi_channel_and_push_safe(self):
        """Pin #1 (3-channel growth-autopilot) and #2 (isolated push & fresh-main supervisor)."""
        from pipeline.channels import CHANNELS

        growth_path = ROOT / ".github" / "workflows" / "growth-autopilot.yml"
        growth_text = growth_path.read_text(encoding="utf-8")
        growth = yaml.safe_load(growth_text)
        self.assertIn("plan", growth["jobs"])
        self.assertEqual(growth["jobs"]["growth"]["strategy"]["max-parallel"], 1)
        for cid, profile in CHANNELS.items():
            prefix = (profile.secret_prefix or "").strip().rstrip("_")
            token_var = f"{prefix}_YOUTUBE_REFRESH_TOKEN" if prefix else "YOUTUBE_REFRESH_TOKEN"
            self.assertIn(token_var, growth_text, f"growth-autopilot.yml missing {token_var} for {cid}")

        community_text = (ROOT / ".github" / "workflows" / "community.yml").read_text(encoding="utf-8")
        self.assertIn("git fetch --quiet origin main", community_text)
        self.assertNotIn("git add content/community/\n", community_text)
        self.assertNotIn("\n          git push\n", community_text)

        sup_text = (ROOT / ".github" / "workflows" / "scheduler-supervisor.yml").read_text(encoding="utf-8")
        self.assertIn("git pull --ff-only origin main || true", sup_text)
        self.assertIn("/tmp/supervisor-ledger", sup_text)

    def test_tts_content_blocked_splits_and_run_quarantines_head_of_line(self):
        """#1: A content_blocked script must split sub-chunks first and quarantine+advance if still blocked."""
        from pipeline import gemini_tts, run as prun

        self.assertTrue(gemini_tts.is_content_blocked_error("Error code: 400 - {'code': 'content_blocked'}"))
        self.assertTrue(
            gemini_tts.is_content_blocked_error(
                "Gemini API returned no audio content for model gemini-3.8-flash-tts"
            )
        )
        long_text = ("Paragraph one of prayer. " * 20) + "\n\n" + ("Paragraph two of prayer. " * 20)
        halves = gemini_tts._split_chunk_in_half(long_text)
        self.assertEqual(len(halves), 2)

        with tempfile.TemporaryDirectory() as tmp:
            qdir = Path(tmp) / "queue"
            qdir.mkdir()
            bad = qdir / "0015-blocked.md"
            good = qdir / "0016-clean.md"
            for p, jid in ((bad, "0015"), (good, "0016")):
                p.write_text(
                    f'---\nid: "{jid}"\ntitle: "Psalm {jid} Prayer"\nstatus: approved\n'
                    f'format: longform\nniche: faith and prayer\n---\n\n## Scene 1\n'
                    + ("steadfast " * 860)
                    + "\n",
                    encoding="utf-8",
                )

            def fake_process(path: Path, dry: bool):
                if path == bad:
                    raise gemini_tts.GeminiContentBlockedError("content_blocked on chunk 1/2")
                return {
                    "uploaded": True,
                    "video_id": "clean_vid_16",
                    "watch_url": "https://youtu.be/clean_vid_16",
                    "privacy_status": "public",
                    "duration_seconds": 365,
                }

            with mock.patch.dict(os.environ, {"DRY_RUN": "0"}), \
                 mock.patch.object(prun.CONFIG, "dry_run", False), \
                 mock.patch.object(prun, "QUEUE_DIR", qdir), \
                 mock.patch.object(prun, "quota_blocked_until", return_value=None), \
                 mock.patch.object(prun, "select_jobs", side_effect=[[bad], [good]]), \
                 mock.patch.object(prun, "process", side_effect=fake_process):
                rc = prun.main(["--next"])

            self.assertEqual(rc, 0)
            bad_after = bad.read_text(encoding="utf-8")
            self.assertIn("status: tts_blocked", bad_after)
            self.assertIn("tts_blocked_reason:", bad_after)

    def test_produce_workflow_plan_skips_quota_cooldown_and_guards_bash_errexit(self):
        produce_text = (ROOT / ".github" / "workflows" / "produce.yml").read_text(encoding="utf-8")
        self.assertIn("active_quota_cooldown(now, channel_id=cid)", produce_text)
        self.assertIn("last_publish_for_channel", produce_text)
        # Ensure `set +e` precedes `set -o pipefail` so rc=3 reaches the cooldown handler
        self.assertIn("set +e\n          set -o pipefail", produce_text)

    def test_monitor_status_material_guard_and_release_report_quota_hygiene(self):
        """#2: Clock-only diffs in status.json are suppressed; quota-pause & public tickets auto-close."""
        from scripts import automation_monitor as am
        from scripts import release_report as rr

        with tempfile.TemporaryDirectory() as tmp:
            st_path = Path(tmp) / "status.json"
            v1 = {
                "generated_at": "2026-11-07T19:43:00+00:00",
                "healthy": True,
                "automations": [{"workflow": "comments.yml", "verdict": "OK", "detail": "last success 0.3h ago"}],
                "outcomes": [{"outcome": "last upload", "verdict": "OK", "detail": "uploaded 0h ago"}],
            }
            v2 = {
                "generated_at": "2026-11-07T19:51:00+00:00",
                "healthy": True,
                "automations": [{"workflow": "comments.yml", "verdict": "OK", "detail": "last success 0.4h ago"}],
                "outcomes": [{"outcome": "last upload", "verdict": "OK", "detail": "uploaded 1h ago"}],
            }
            v3 = {
                **v2,
                "healthy": False,
                "automations": [{"workflow": "comments.yml", "verdict": "FAILING", "detail": "failed 5m ago"}],
            }
            self.assertTrue(am.save_monitor_state(v1, st_path))
            self.assertFalse(am.save_monitor_state(v2, st_path), "clock-only age drift must not rewrite status.json")
            self.assertTrue(am.save_monitor_state(v3, st_path), "verdict change must rewrite status.json")

            # Quota pause vs real stage failure in release_report
            quota_log = "::error title=Release did not publish::Gemini's free-tier TTS allowance (10 requests/day) is spent until 2026-11-08T08:00:00+00:00 UTC."
            self.assertTrue(rr.is_quota_cooldown_only({"open": [], "failure": None}, quota_log))
            self.assertFalse(
                rr.is_quota_cooldown_only(
                    {"open": [], "failure": {"stage": "speech synthesis"}},
                    quota_log,
                )
            )

            # Sweep stale issues (#311 quota pause + #255/#250 public release tickets)
            pub_dir = Path(tmp) / "published"
            pub_dir.mkdir()
            (pub_dir / "0036-psalm-5.md").write_text(
                '---\nid: "0036"\ntitle: "Psalm 5 Morning Prayer | Begin Your Day in God\'s Presence"\n'
                'status: published\nprivacy: public\nyoutube_video_id: _vp27ZYPYaY\n---\nAmen.\n',
                encoding="utf-8",
            )
            fake_open = [
                {"number": 311, "title": "Release failed (run 42231785039)", "body": quota_log},
                {"number": 326, "title": "Release failed in speech synthesis (run 42355558122)", "body": "content_blocked"},
                {"number": 255, "title": "Release ticket: Psalm 5 Morning Prayer | Begin Your Day in God's Presence", "body": " checklist"},
            ]
            closed_nums: list[str] = []

            def fake_run(cmd, **kwargs):
                if cmd[:3] == ["gh", "issue", "list"]:
                    return SimpleNamespace(returncode=0, stdout=json.dumps(fake_open), stderr="")
                if cmd[:3] == ["gh", "issue", "close"]:
                    closed_nums.append(cmd[3])
                    return SimpleNamespace(returncode=0, stdout="", stderr="")
                return SimpleNamespace(returncode=1, stdout="", stderr="")

            with mock.patch("shutil.which", return_value="/usr/bin/gh"), \
                 mock.patch("subprocess.run", side_effect=fake_run):
                swept = rr.sweep_stale_release_issues("johnAzani/YouTube-automation", published_dir=pub_dir)
            self.assertEqual(swept, [311, 255])
            self.assertNotIn("326", closed_nums)

    def test_community_and_metrics_workflows_cover_all_three_channels(self):
        """#3: community.yml & metrics.yml cover secret-place, prayer2, and prayer3."""
        from pipeline.channels import CHANNELS
        from pipeline.community_posts import community_schedule_for, publish_community_post

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch("pipeline.community_posts.COMMUNITY_DIR", Path(tmp)):
                seen_ids = set()
                for cid in CHANNELS:
                    sched = community_schedule_for(cid)
                    self.assertEqual(len(sched), 4)
                    res = publish_community_post(sched[0], dry_run=True, channel_id=cid)
                    self.assertEqual(res["status"], "ready_for_manual_post")
                    self.assertTrue(Path(res["ready_pack"]).is_file())
                    self.assertTrue(Path(res["card_path"]).is_file())
                    seen_ids.add(sched[0].post_id)
                self.assertEqual(len(seen_ids), 3)

        comm_text = (ROOT / ".github" / "workflows" / "community.yml").read_text(encoding="utf-8")
        metrics_text = (ROOT / ".github" / "workflows" / "metrics.yml").read_text(encoding="utf-8")
        self.assertIn("--all-channels", comm_text)
        for cid, profile in CHANNELS.items():
            prefix = (profile.secret_prefix or "").strip().rstrip("_")
            token_var = f"{prefix}_YOUTUBE_REFRESH_TOKEN" if prefix else "YOUTUBE_REFRESH_TOKEN"
            self.assertIn(token_var, comm_text, f"community.yml missing {token_var}")
            self.assertIn(token_var, metrics_text, f"metrics.yml missing {token_var}")

    def test_normalize_authored_script_spaces_alphabetic_em_dashes(self):
        """#333 prevention: Brain normalizer spaces word—word compounds while keeping numeric 5–6 ranges."""
        from pipeline.gemini_brain import normalize_authored_script_markdown

        raw = (
            "---\nid: '0098'\ntitle: 'Proverbs 16:3 Prayer'\nstatus: approved\nchannel: prayer3\n---\n\n"
            "## Scene 1 — Commit Thy Works (Psalm 91:5–6)\n\n"
            "Every project, every labor—lift all of it into His hands from Psalm 91:5–6.\n"
        )
        cleaned = normalize_authored_script_markdown(raw, channel_id="prayer3")
        self.assertIn("labor — lift", cleaned)
        self.assertIn("Psalm 91:5–6", cleaned)

    def test_sweep_stale_release_issues_closes_superseded_private_drafts(self):
        """#250/#255 cleanup: close superseded private draft tickets while keeping canonical private ticket open."""
        from scripts import release_report as rr

        with tempfile.TemporaryDirectory() as tmp:
            pub_dir = Path(tmp)
            (pub_dir / "0036-psalm-5.md").write_text(
                "---\n"
                'title: "Psalm 5 Morning Prayer | Begin Your Day in God\'s Presence"\n'
                "status: published\n"
                "privacy: private\n"
                'youtube_video_id: "_vp27ZYPYaY"\n'
                "---\nBody\n",
                encoding="utf-8",
            )
            fake_open = [
                {
                    "number": 250,
                    "title": "Release ticket: Psalm 5 Morning Prayer | Begin Your Day in God's Presence",
                    "body": "- Watch link: https://youtu.be/oS7f32WDj_Y\n",
                },
                {
                    "number": 255,
                    "title": "Release ticket: Psalm 5 Morning Prayer | Begin Your Day in God's Presence",
                    "body": "- Watch link: https://youtu.be/R8mVvedhYVw\n",
                },
                {
                    "number": 260,
                    "title": "Release ticket: Psalm 5 Morning Prayer | Begin Your Day in God's Presence",
                    "body": "- Watch link: https://youtu.be/_vp27ZYPYaY\n",
                },
            ]
            with mock.patch("shutil.which", return_value="/usr/bin/gh"), \
                 mock.patch(
                     "subprocess.run",
                     side_effect=lambda cmd, **kw: SimpleNamespace(
                         returncode=0,
                         stdout=json.dumps(fake_open) if cmd[:3] == ["gh", "issue", "list"] else "",
                         stderr="",
                     ),
                 ):
                swept = rr.sweep_stale_release_issues("johnAzani/YouTube-automation", published_dir=pub_dir)
            self.assertEqual(swept, [250, 255])

    def test_build_dashboard_data_covers_all_channels_with_material_change_guard(self):
        """Item #4: network-state.json covers all 3 channels and ignores volatile age/timestamp drift."""
        import copy
        from pipeline.channels import CHANNELS
        from scripts.build_dashboard_data import (
            build_network_state,
            material_fingerprint,
            write_network_state,
        )

        state = build_network_state(ROOT)
        self.assertEqual({c["id"] for c in state["channels"]}, set(CHANNELS))
        self.assertGreaterEqual(state["totals"]["published_total"], 29)
        self.assertEqual(state["cost_lock"]["monthly_cost_usd"], 0.0)

        drifted = copy.deepcopy(state)
        drifted["generated_at"] = "2099-01-01T00:00:00Z"
        if drifted["automations"]:
            drifted["automations"][0]["detail"] = "last success 9.4h ago"
            state["automations"][0]["detail"] = "last success 0.2h ago"
        self.assertEqual(material_fingerprint(state), material_fingerprint(drifted))

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "network-state.json"
            self.assertTrue(write_network_state(out, repo_root=ROOT))
            self.assertFalse(write_network_state(out, repo_root=ROOT))

        dashboard_html = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
        self.assertIn("./network-state.json", dashboard_html)
        self.assertIn("channel-command-grid", dashboard_html)
        self.assertIn("live-catalog-grid", dashboard_html)

    def test_apply_channel_env_preserves_workflow_mapped_credentials_and_blocks_cross_channel_leak(self):
        """Run 42430375723 regression: workflow-scoped YOUTUBE_* vars survive apply_channel_env(same_ch)."""
        from pipeline.channels import apply_channel_env

        # Case 1: workflow job env already mapped PRAYER2 -> YOUTUBE_* and set CHANNEL_ID=prayer2
        scoped_env = {
            "CHANNEL_ID": "prayer2",
            "YOUTUBE_CLIENT_ID": "p2-id",
            "YOUTUBE_CLIENT_SECRET": "p2-sec",
            "YOUTUBE_REFRESH_TOKEN": "p2-tok",
        }
        with mock.patch.dict(os.environ, scoped_env, clear=True):
            cid = apply_channel_env("prayer2")
            self.assertEqual(cid, "prayer2")
            self.assertEqual(os.environ.get("YOUTUBE_CLIENT_ID"), "p2-id")
            self.assertEqual(os.environ.get("YOUTUBE_REFRESH_TOKEN"), "p2-tok")

        # Case 2: switching from secret-place to prayer2 without PRAYER2_* clears inherited creds
        inherited_env = {
            "CHANNEL_ID": "secret-place",
            "YOUTUBE_CLIENT_ID": "sp-id",
            "YOUTUBE_REFRESH_TOKEN": "sp-tok",
        }
        with mock.patch.dict(os.environ, inherited_env, clear=True):
            apply_channel_env("prayer2")
            self.assertIsNone(os.environ.get("YOUTUBE_CLIENT_ID"))
            self.assertIsNone(os.environ.get("YOUTUBE_REFRESH_TOKEN"))

    def test_every_scheduled_channel_has_ready_shorts_runway(self):
        """shorts:<channel> must never start at 0 across provisioned channels."""
        from pipeline.channels import scheduled_channels
        from pipeline.short_release import count_ready_shorts

        for cid in scheduled_channels():
            self.assertGreaterEqual(
                count_ready_shorts(channel_id=cid),
                2,
                f"channel {cid} has fewer than 2 ready Shorts in content/shorts-queue/",
            )

    def test_thumbnail_rate_limit_stamps_cooldown_and_skips_until_expiry(self):
        """PIPx_odfiag uploadRateLimitExceeded regression: back off 6h instead of burning 50 units/pass."""
        from scripts import sync_published_thumbnails as spt

        with tempfile.TemporaryDirectory() as tmp:
            pdir = Path(tmp) / "published"
            out_dir = Path(tmp) / "out"
            pdir.mkdir(parents=True, exist_ok=True)
            rec = pdir / "0040-proverbs-3-5-6.md"
            rec.write_text(
                "---\n"
                "id: '0040'\n"
                "title: 'Proverbs 3:5-6 Morning Prayer | The Morning Altar'\n"
                "slug: proverbs-3-5-6-trust-in-the-lord\n"
                "status: published\n"
                "channel: prayer2\n"
                "format: longform\n"
                "privacy: public\n"
                "thumb_text: TRUST IN THE LORD\n"
                "youtube_video_id: PIPx_odfiag\n"
                "---\nBody\n",
                encoding="utf-8",
            )
            fake_yt = mock.MagicMock()
            fake_yt.videos.return_value.list.return_value.execute.return_value = {
                "items": [{
                    "id": "PIPx_odfiag",
                    "snippet": {"title": "Proverbs 3:5-6 Morning Prayer | The Morning Altar"},
                    "status": {"privacyStatus": "public", "uploadStatus": "processed"},
                    "contentDetails": {"duration": "PT10M54S"},
                }]
            }
            rate_err = "HttpError: The user has uploaded too many thumbnails recently. [uploadRateLimitExceeded]"
            rows = spt.sync_published_thumbnails(
                published_dir=pdir,
                out_root=out_dir,
                youtube_client=fake_yt,
                thumb_setter=lambda vid, p: rate_err,
                channel="prayer2",
            )
            self.assertEqual(len(rows), 1)
            text = rec.read_text(encoding="utf-8")
            self.assertIn("thumbnail_retry_after:", text)
            # Immediate subsequent pass skips during active cooldown window
            self.assertEqual(spt.collect_pending_receipts(published_dir=pdir, channel_id="prayer2"), [])
            # `--force` overrides cooldown when requested explicitly
            self.assertEqual(len(spt.collect_pending_receipts(published_dir=pdir, force=True, channel_id="prayer2")), 1)

    def test_sweep_stale_release_issues_keeps_newest_analytics_snapshot_only(self):
        """#78/#248/#320 cleanup: keep newest snapshot per channel prefix, close older ones."""
        from scripts import release_report as rr

        with tempfile.TemporaryDirectory() as tmp:
            fake_snaps = [
                {"number": 320, "title": "📊 Channel Analytics Snapshot: 2026-11-06"},
                {"number": 248, "title": "📊 Channel Analytics Snapshot: 2026-11-04"},
                {"number": 78, "title": "📊 Channel Analytics Snapshot: 2026-10-29"},
            ]

            def fake_run(cmd, **kw):
                if cmd[:3] == ["gh", "issue", "list"]:
                    q = " ".join(cmd)
                    if "Channel Analytics Snapshot" in q:
                        return SimpleNamespace(returncode=0, stdout=json.dumps(fake_snaps), stderr="")
                    return SimpleNamespace(returncode=0, stdout="[]", stderr="")
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            with mock.patch("shutil.which", return_value="/usr/bin/gh"), \
                 mock.patch("subprocess.run", side_effect=fake_run):
                closed = rr.sweep_stale_release_issues("johnAzani/YouTube-automation", published_dir=Path(tmp))
            self.assertEqual(closed, [248, 78])

    def test_every_scheduled_channel_maintains_deep_roadmap_headroom(self):
        """Every live channel must keep >=15 unqueued/unpublished scriptures and unique Short keys."""
        from pipeline.channel_capabilities import brand_for
        from pipeline.channels import scheduled_channels
        from pipeline.gemini_brain import GeminiBrain, extract_scripture_reference, short_key_for_doc
        from scripts.continuous_research import roadmap_for_channel

        existing_ids = {p.name[:4] for p in (ROOT / "content" / "queue").glob("[0-9]*.md")} | {
            p.name[:4] for p in (ROOT / "content" / "published").glob("[0-9]*.md")
        }
        seen_global_ids: set[str] = set()
        for cid in scheduled_channels():
            rm = roadmap_for_channel(cid)
            brand = brand_for(cid)
            eligible = [row for row in rm if row["id"] not in existing_ids]
            self.assertGreaterEqual(
                len(eligible),
                15,
                f"{cid} has only {len(eligible)} unqueued scriptures left in its roadmap",
            )
            brain = GeminiBrain(api_key="", channel_id=cid)
            cand = brain.select_next_scripture()
            self.assertIn(cand, eligible)

            seen_channel_keys: set[str] = set()
            for row in rm:
                rid = row["id"]
                self.assertNotIn(rid, seen_global_ids, f"duplicate roadmap id {rid}")
                seen_global_ids.add(rid)
                fake_doc = SimpleNamespace(
                    id=rid,
                    channel=cid,
                    title=f"{row['scripture']} Prayer {brand.title_suffix}",
                    slug=f"{rid}-test",
                )
                ref = extract_scripture_reference(fake_doc)
                self.assertTrue(ref)
                skey = short_key_for_doc(fake_doc)
                self.assertRegex(skey, r"^short-[a-z0-9]+$")
                self.assertNotIn(skey, seen_channel_keys, f"Short key collision {skey} in {cid}")
                seen_channel_keys.add(skey)

    def test_author_short_spec_advances_on_per_model_429_quota(self):
        """A 429 on one model (e.g. 20/day 3.6-flash) skips remaining attempts on it and tries the next."""
        from pipeline import gemini_brain as gb
        from pipeline.script_doc import parse_script

        valid_spec_json = (ROOT / "content" / "shorts-scripts" / "short-middaypsalm37v5.json").read_text(encoding="utf-8")
        doc = parse_script(ROOT / "content" / "queue" / "0051-psalm-37-5-midday-prayer.md")

        brain = gb.GeminiBrain(api_key="", channel_id="prayer3")
        calls: list[str] = []

        def fake_generate(model: str, contents: str, config=None):
            calls.append(model)
            if model == calls[0] and calls.count(model) == 1:
                raise RuntimeError("429 RESOURCE_EXHAUSTED: limit 20 for model")
            return SimpleNamespace(text=valid_spec_json)

        brain._client = SimpleNamespace(models=SimpleNamespace(generate_content=fake_generate))
        with mock.patch.object(gb, "_TRANSIENT_BACKOFF", ()), mock.patch("builtins.print"):
            spec = brain.author_short_spec(doc, key="short-middaypsalm37v5")

        self.assertEqual(spec.key, "short-middaypsalm37v5")
        self.assertEqual(calls.count(calls[0]), 1, "must not burn a second attempt on a 429 model")
        self.assertEqual(len(calls), 2, "must escalate to the next model in the chain")

    def test_require_renderable_defers_manifest_instead_of_polluting_shorts_queue(self):
        """Autonomous staging never writes broken `needs_renderer` manifests into shorts-queue."""
        from pipeline import gemini_brain as gb
        from pipeline import short_release as sr
        from pipeline.script_doc import parse_script

        doc = parse_script(ROOT / "content" / "queue" / "0051-psalm-37-5-midday-prayer.md")
        with tempfile.TemporaryDirectory() as tmp:
            qdir = Path(tmp) / "shorts-queue"
            brain = gb.GeminiBrain(api_key="", channel_id="prayer3")
            with mock.patch.object(gb, "SHORTS_QUEUE_DIR", qdir), \
                 mock.patch.object(sr, "_renderer_script_keys", return_value=set()), \
                 mock.patch("builtins.print"):
                mpath, mkey = brain.generate_companion_short(doc, require_renderable=True)
                self.assertIsNone(mpath)
                self.assertEqual(mkey, "short-middaypsalm37v5")
                self.assertEqual(list(qdir.glob("*.yml")), [])

    def test_expanded_book_regex_parses_epistles_and_prophets_cleanly(self):
        """Expanded `_BOOK_RE` extracts clean references and Short keys across OT/NT books."""
        from pipeline.gemini_brain import extract_scripture_reference, short_key_for_doc

        samples = [
            ("2 Samuel 23:4 Morning Prayer | The Morning Altar", "prayer2", "2 Samuel 23:4", "short-morning2samuel23v4"),
            ("2 Chronicles 20:12 Midday Prayer | The Midday Watch", "prayer3", "2 Chronicles 20:12", "short-midday2chronicles20v12"),
            ("1 Thessalonians 5:16-18 Midday Prayer | The Midday Watch", "prayer3", "1 Thessalonians 5:16-18", "short-midday1thessalonians5v16"),
            ("Zephaniah 3:17 Night Prayer | The Secret Place", "secret-place", "Zephaniah 3:17", "short-zephaniah3v17"),
            ("1 John 4:18 Night Prayer | The Secret Place", "secret-place", "1 John 4:18", "short-1john4v18"),
        ]
        for title, cid, expected_ref, expected_key in samples:
            doc = SimpleNamespace(id="9999", channel=cid, title=title, slug="test")
            self.assertEqual(extract_scripture_reference(doc), expected_ref)
            self.assertEqual(short_key_for_doc(doc), expected_key)

    def test_shorts_bridge_never_leaks_cross_channel_handles_or_videos(self):
        """Shorts-to-longform bridge stays strictly inside the Short's own channel."""
        from pipeline.channel_capabilities import brand_for, known_channels
        from pipeline.shorts_bridge import (
            enrich_short_description_with_bridge,
            generate_short_bridge_comment,
            resolve_longform_counterpart,
        )

        # Published Morning Altar Short -> Morning Altar's own Psalm 5 video (never @TheSecretPlace)
        cp_m5 = resolve_longform_counterpart("short-morningpsalm5")
        self.assertEqual(cp_m5["channel"], "prayer2")
        self.assertTrue(cp_m5["is_live_video"])
        self.assertNotIn("@TheSecretPlace", cp_m5["url"])
        self.assertNotIn("nighttime", cp_m5["theme"])

        # Future / unpublished Morning Altar & Midday Watch Shorts -> each channel's own playlists tab
        cp_m_unpub = resolve_longform_counterpart("short-morningpsalm150v6")
        self.assertEqual(cp_m_unpub["channel"], "prayer2")
        self.assertEqual(cp_m_unpub["url"], "https://www.youtube.com/@TheMorningAltarDaily/playlists")

        cp_mid_unpub = resolve_longform_counterpart("short-middaypsalm150v6")
        self.assertEqual(cp_mid_unpub["channel"], "prayer3")
        self.assertEqual(cp_mid_unpub["url"], "https://www.youtube.com/@TheMiddayWatch/playlists")

        # Midday Psalm 91:6 must link prayer3's 0046, never secret-place's 0008 (7RDX0fbIOtQ)
        cp_mid91 = resolve_longform_counterpart("short-middaypsalm91v6")
        self.assertEqual(cp_mid91["channel"], "prayer3")
        self.assertNotEqual(cp_mid91["video_id"], "7RDX0fbIOtQ")

        for short_key, cid in (
            ("short-psalm91", "secret-place"),
            ("short-morningpsalm90v17", "prayer2"),
            ("short-middaypsalm37v5", "prayer3"),
        ):
            comment = generate_short_bridge_comment(short_key)
            desc = enrich_short_description_with_bridge("Prayer body.\n\n#Shorts", short_key)
            for other in known_channels():
                if other == cid:
                    continue
                self.assertNotIn(brand_for(other).handle, comment)
                self.assertNotIn(brand_for(other).handle, desc)
            for bad in brand_for(cid).forbidden_phrases:
                self.assertNotIn(bad.lower(), comment.lower())

    def test_performance_feedback_classifies_sunrise_and_midday_catalog_cleanly(self):
        """Every published long-form prayer classifies into a specific theme and extracts scripture."""
        from pipeline.performance_feedback import extract_scripture, load_published_index

        for cid in ("secret-place", "prayer2", "prayer3"):
            idx = load_published_index(channel_id=cid)
            longform = [v for v in idx.values() if v["format"] != "short"]
            self.assertGreaterEqual(len(longform), 3)
            for v in longform:
                self.assertNotEqual(
                    v["theme"],
                    "general_prayer",
                    f"{cid} video {v['title']!r} fell into unranked general_prayer",
                )
                self.assertTrue(v["scripture"], f"{cid} video {v['title']!r} extracted blank scripture")

        self.assertEqual(extract_scripture("Lamentations 3:22-23 Morning Prayer"), "Lamentations 3")
        self.assertEqual(extract_scripture("2 Chronicles 20:12 Midday Prayer"), "2 Chronicles 20")
        self.assertEqual(extract_scripture("Zephaniah 3:17 Night Prayer"), "Zephaniah 3")
        self.assertEqual(extract_scripture("1 Thessalonians 5:16-18 Midday Prayer"), "1 Thessalonians 5")

    def test_milestone_tiers_for_every_channel_are_free_of_forbidden_phrases(self):
        """Subscriber milestone copy uses each channel's own ministry identity and daypart."""
        from pipeline.channel_capabilities import brand_for, known_channels
        from pipeline.milestones import get_current_milestone_status, milestone_tiers_for_channel

        for cid in known_channels():
            brand = brand_for(cid)
            tiers = milestone_tiers_for_channel(cid)
            self.assertEqual(len(tiers), 4)
            achieved, upcoming = get_current_milestone_status(1260, channel_id=cid)
            self.assertIsNotNone(achieved)
            self.assertEqual(achieved.subs_target, 1250)
            self.assertEqual(upcoming.subs_target, 1500)
            for tier in tiers:
                blob = f"{tier.headline} {tier.subheading} {tier.pastoral_message}".lower()
                for bad in brand.forbidden_phrases:
                    self.assertNotIn(
                        bad.lower(),
                        blob,
                        f"{cid} milestone {tier.subs_target} contains forbidden {bad!r}",
                    )

    def test_metadata_localizations_never_leak_night_copy_or_selar_onto_sunrise_or_midday(self):
        """Spanish/Portuguese localizations on prayer2 & prayer3 stay strictly daypart-pure."""
        from pipeline.localize_metadata import build_metadata_localizations

        locs_p2 = build_metadata_localizations(
            "Proverbs 3:5-6 Morning Prayer | The Morning Altar",
            "Begin this sunrise in prayer.",
            channel_id="prayer2",
        )
        self.assertIn("Proverbios 3:5-6", locs_p2["es"]["title"])
        self.assertIn("Provérbios 3:5-6", locs_p2["pt"]["title"])
        self.assertNotIn("3:24", locs_p2["es"]["title"])

        locs_p3 = build_metadata_localizations(
            "Psalm 91:6 Midday Prayer | The Midday Watch",
            "Pause at noonday in prayer.",
            channel_id="prayer3",
        )
        self.assertIn("Salmo 91:6", locs_p3["es"]["title"])
        self.assertIn("Mediodía", locs_p3["es"]["title"])
        self.assertIn("Meio-Dia", locs_p3["pt"]["title"])

        for locs in (locs_p2, locs_p3):
            for lang in ("es", "pt"):
                blob = f"{locs[lang]['title']}\n{locs[lang]['description']}".lower()
                self.assertNotIn("selar.com", blob)
                self.assertNotIn("the secret place", blob)
                for night_word in ("dormir", "noche", "nocturna", "noite"):
                    self.assertNotIn(night_word, blob)

    def test_metadata_tags_hashtags_and_seo_hooks_are_daypart_scoped(self):
        """Sunrise and midday scripts never inherit bedtime hashtags or sleep backend tags."""
        from pipeline.metadata import build_description, build_tags, write_metadata_pack
        from pipeline.script_doc import parse_script

        p2_doc = parse_script(ROOT / "content" / "published" / "0038-lamentations-3-22-23-new-mercies-every-morning.md")
        p3_doc = parse_script(ROOT / "content" / "published" / "0046-psalm-91-6-the-destruction-that-wasteth-at-noonday.md")

        for doc in (p2_doc, p3_doc):
            desc = build_description(doc, [65.0] * len(doc.scenes))
            tags = build_tags(doc)
            for bad_ht in ("#NightPrayer", "#PrayerBeforeSleep", "#BedtimePrayer", "#TheSecretPlace"):
                self.assertNotIn(bad_ht, desc)
            for bad_tag_word in ("sleep", "night", "bedtime", "secret place"):
                self.assertTrue(
                    all(bad_tag_word not in t for t in tags),
                    f"{doc.path.name} leaked {bad_tag_word!r} into tags: {tags}",
                )
            with tempfile.TemporaryDirectory() as tmp:
                pack = write_metadata_pack(doc, [65.0] * len(doc.scenes), Path(tmp))
                self.assertEqual(pack["selar_journal_url"], "")
                self.assertEqual(pack["selar_store_url"], "")

    def test_retrofit_published_metadata_strips_audit_json_and_links_published_shorts(self):
        """Live retrofit strips receipt audit JSON and links paired Shorts directly to YouTube watch URLs."""
        from pipeline.channel_capabilities import brand_for
        from scripts.retrofit_published_metadata import collect_published_faith_targets

        targets = collect_published_faith_targets(only_pending=False)
        by_file = {t["file"]: t for t in targets}

        expected_live_links = {
            "short-middaypsalm55v17-midday-prayer.md": "https://youtu.be/xjiV3SHKsR4",
            "short-middaypsalm91v6-midday-prayer.md": "https://youtu.be/GeZ3liNIxag",
            "short-morninglamentations3v22-sunrise-prayer.md": "https://youtu.be/3tm3_lNvoGM",
            "short-morningmark1v35-sunrise-prayer.md": "https://youtu.be/Nq7a1yC4Rzw",
            "short-morningproverbs3v5-sunrise-prayer.md": "https://youtu.be/PIPx_odfiag",
        }
        for fname, watch_url in expected_live_links.items():
            self.assertIn(watch_url, by_file[fname]["description"])

        for t in targets:
            desc = t["description"]
            self.assertNotIn("## Custom Thumbnail", desc)
            self.assertNotIn("## Channel Video Status", desc)
            self.assertNotIn("```json", desc)
            cid = t["channel"]
            if cid != "secret-place":
                self.assertNotIn("selar.com", desc.lower())
                self.assertNotIn("selar.com", t["localizations"]["es"]["description"].lower())
                self.assertNotIn("selar.com", t["localizations"]["pt"]["description"].lower())
                for bad in brand_for(cid).forbidden_phrases:
                    self.assertNotIn(bad.lower(), desc.lower())

    def test_pastoral_pinned_comments_are_daypart_clean_across_all_published_and_queued_docs(self):
        """Long-form pinned comments on prayer2 & prayer3 never emit bedtime verses or sleep themes."""
        from pipeline.channel_capabilities import brand_for
        from pipeline.metadata import is_faith_doc
        from pipeline.pinned_comments import generate_pastoral_pinned_comment
        from pipeline.script_doc import parse_script

        paths = sorted((ROOT / "content" / "published").glob("*.md")) + sorted(
            (ROOT / "content" / "queue").glob("*.md")
        )
        checked = 0
        for p in paths:
            if p.stem.lower() == "readme":
                continue
            doc = parse_script(p)
            if not is_faith_doc(doc) or doc.channel == "secret-place":
                continue
            checked += 1
            comment = generate_pastoral_pinned_comment(doc)
            low = comment.lower()
            for night_word in ("sleep", "slumber", "tonight", "liest down"):
                self.assertNotIn(night_word, low, f"{p.name} leaked {night_word!r} in comment")
            for bad in brand_for(doc.channel).forbidden_phrases:
                self.assertNotIn(bad.lower(), low, f"{p.name} leaked {bad!r} in comment")
        self.assertGreaterEqual(checked, 20)

    def test_watchdog_and_monitor_alert_when_one_channel_stalls_behind_active_sibling(self):
        """A recent upload on secret-place never masks a >26h/>48h stall on prayer2 or prayer3."""
        from scripts import automation_monitor as am
        from scripts import pipeline_watchdog as pw

        now = datetime(2026, 11, 8, 20, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            pub = Path(tmp) / "published"
            pub.mkdir()
            qdir = Path(tmp) / "content" / "queue"
            qdir.mkdir(parents=True)
            (qdir / "0099-ok.md").write_text(
                "---\nid: '0099'\nstatus: approved\nformat: longform\n---\n\n## Scene 1\n"
                + ("word " * 900),
                encoding="utf-8",
            )

            # secret-place uploaded 2h ago (fresh), prayer2 32h ago (>26h), prayer3 52h ago (>48h)
            (pub / "0020-sp.md").write_text(
                f"---\nchannel: secret-place\nyoutube_video_id: sp1\n"
                f"published_at: '{(now - timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M:%SZ')}'\n---\n",
                encoding="utf-8",
            )
            (pub / "0040-p2.md").write_text(
                f"---\nchannel: prayer2\nyoutube_video_id: p21\n"
                f"published_at: '{(now - timedelta(hours=32)).strftime('%Y-%m-%dT%H:%M:%SZ')}'\n---\n",
                encoding="utf-8",
            )
            (pub / "0045-p3.md").write_text(
                f"---\nchannel: prayer3\nyoutube_video_id: p31\n"
                f"published_at: '{(now - timedelta(hours=52)).strftime('%Y-%m-%dT%H:%M:%SZ')}'\n---\n",
                encoding="utf-8",
            )

            wd_rep = pw.Report()
            with mock.patch("scripts.automation_health.queue_health", return_value=[
                {"queue": "longform:secret-place", "channel": "secret-place", "ready": 5, "note": "ok"},
                {"queue": "longform:prayer2", "channel": "prayer2", "ready": 4, "note": "ok"},
                {"queue": "longform:prayer3", "channel": "prayer3", "ready": 4, "note": "ok"},
            ]):
                pw.check_queues(wd_rep, published_dir=pub, now=now)

            self.assertFalse(wd_rep.healthy)
            pub_findings = [f.detail for f in wd_rep.findings if f.area == "publishing"]
            self.assertEqual(len(pub_findings), 2)
            self.assertTrue(any("The Morning Altar (prayer2)" in d for d in pub_findings))
            self.assertTrue(any("The Midday Watch (prayer3)" in d for d in pub_findings))

            mon_rep = am.MonitorReport()
            with mock.patch.object(am, "ROOT", Path(tmp)):
                am.check_outcomes(mon_rep, now=now, published_dir=pub, log_path=Path(tmp) / "none.json")
            by_name = {o["outcome"]: o for o in mon_rep.outcomes}
            self.assertEqual(by_name["last upload"]["severity"], "ok")
            self.assertEqual(by_name["last upload (secret-place)"]["severity"], "ok")
            self.assertEqual(by_name["last upload (prayer2)"]["severity"], "warning")
            self.assertEqual(by_name["last upload (prayer3)"]["severity"], "blocking")

    def test_poisoned_speech_alignment_purges_chunks_and_falls_back_to_edge_tts(self):
        """Alignment rejection purges narration + _gemini_chunks_* and falls back cleanly to edge-tts."""
        from types import SimpleNamespace
        from pipeline import prayer_pipeline as pp
        from pipeline.script_doc import Scene, ScriptDoc

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model = root / "model"
            model.mkdir()
            (model / "model.bin").write_bytes(b"local")
            slug_out = root / "0015-psalm-91-5-6"
            (slug_out / "thumbnails").mkdir(parents=True)
            chunk_dir = slug_out / "_gemini_chunks_deadbeef1234"
            chunk_dir.mkdir(parents=True)
            (chunk_dir / "part_000.wav").write_bytes(b"POISONED")

            doc = ScriptDoc(
                root / "0015.md",
                {
                    "id": "0015",
                    "slug": "0015-psalm-91-5-6",
                    "title": "Psalm 91:5-6 | Night Peace",
                    "status": "approved",
                    "format": "longform",
                    "niche": "prayer",
                    "voice": "Charon",
                    "thumb_text": "NIGHT PEACE",
                    "channel": "secret-place",
                },
                [Scene(1, "One", "hello " * 900)],
            )
            asset = root / "image.jpg"
            asset.write_bytes(b"a")
            output = root / "out.mp4"
            output.write_bytes(b"b")
            thumbnail = root / "thumb.jpg"
            thumbnail.write_bytes(b"c")
            words = [("hello", i * 0.4, i * 0.4 + 0.3) for i in range(900)]

            align_calls: list[int] = []

            def fake_align(audio_path, text, model_dir):
                align_calls.append(1)
                if len(align_calls) == 1:
                    raise ValueError("Narration does not match the script (only 2% of words aligned).")
                return words

            def fake_edge(text, out_mp3, voice, rate="-5%"):
                out_mp3.write_bytes(b"CLEAN_EDGE_MP3")
                return ("edge-tts", "en-US-AndrewMultilingualNeural")

            with mock.patch.object(pp, "parse_script", return_value=doc), \
                 mock.patch.object(pp, "enforce"), \
                 mock.patch("pipeline.run._require_production_prerequisites"), \
                 mock.patch.object(pp, "get_gemini_api_key", return_value="fake"), \
                 mock.patch.object(pp.importlib.util, "find_spec", return_value=True), \
                 mock.patch.object(pp, "OUTPUT_DIR", root), \
                 mock.patch.object(pp, "synthesize_gemini_audio",
                                   side_effect=lambda *a, **k: (slug_out / "narration.mp3").write_bytes(b"BAD")), \
                 mock.patch.object(pp, "_probe_duration", return_value=360.0), \
                 mock.patch.object(pp, "align", side_effect=fake_align), \
                 mock.patch.object(pp, "synthesize_edge", side_effect=fake_edge), \
                 mock.patch("pipeline.assets.fetch_scene_assets", return_value=[SimpleNamespace(path=asset)]), \
                 mock.patch.object(pp, "render", return_value=output), \
                 mock.patch("pipeline.thumbnail_ctr.generate_ctr_pack",
                            return_value=[SimpleNamespace(path=thumbnail, as_dict=lambda: {})]), \
                 mock.patch("pipeline.thumbnail_studio.mobile_preview"), \
                 mock.patch("pipeline.metadata.write_metadata_pack", return_value={"description": "prayer"}):
                pp.produce(root / "0015.md", True, model)

            self.assertEqual(len(align_calls), 2)
            self.assertFalse(chunk_dir.exists(), "Poisoned _gemini_chunks_* must be purged immediately")
            saved_meta = json.loads((slug_out / "narration.json").read_text(encoding="utf-8"))
            self.assertEqual(saved_meta["engine"], "edge-tts")

        produce_wf = (ROOT / ".github" / "workflows" / "produce.yml").read_text(encoding="utf-8")
        self.assertIn("chunks-tts-v5-${{ matrix.channel }}-", produce_wf)
        self.assertNotIn("chunks-tts-v4-", produce_wf)
        self.assertNotIn("\n            chunks-\n", produce_wf)

    def test_thumbnail_rate_limit_halts_channel_loop_without_burning_quota(self):
        """First uploadRateLimitExceeded backs off remaining channel items with 0 extra API calls."""
        from types import SimpleNamespace
        from scripts import sync_published_thumbnails as spt

        with tempfile.TemporaryDirectory() as tmp:
            pub = Path(tmp) / "published"
            out = Path(tmp) / "out"
            pub.mkdir()
            out.mkdir()
            fake_jpg = Path(tmp) / "thumb.jpg"
            fake_jpg.write_bytes(b"JPG")
            vids = []
            for idx in range(36, 40):
                vid = f"vid00{idx}AAAA"
                vids.append(vid)
                (pub / f"00{idx}-morning-prayer.md").write_text(
                    f'---\nid: "00{idx}"\ntitle: "Psalm {idx} Morning Prayer"\n'
                    f'scripture: "Psalm {idx}:1"\nchannel: prayer2\nstatus: published\n'
                    f'privacy: public\nyoutube_video_id: {vid}\nthumbnail_pending: true\n---\nAmen.\n',
                    encoding="utf-8",
                )
            (pub / "short-morningpsalm36.md").write_text(
                '---\nid: "short-36"\nslug: "short-morningpsalm36"\ntitle: "Morning Short #Shorts"\n'
                'format: short\nchannel: prayer2\nstatus: published\nprivacy: public\n'
                'youtube_video_id: shrt36AAAAA\nthumbnail_pending: true\n---\nAmen.\n',
                encoding="utf-8",
            )

            fake_yt = mock.MagicMock()
            fake_yt.videos().list().execute.return_value = {
                "items": [
                    {
                        "id": v,
                        "snippet": {"title": "T", "description": "D", "categoryId": "22"},
                        "status": {"privacyStatus": "public"},
                        "contentDetails": {"duration": "PT8M"},
                    }
                    for v in vids
                ]
            }

            setter_calls: list[str] = []

            def fake_setter(vid, thumb_path):
                setter_calls.append(vid)
                return "HttpError 429 uploadRateLimitExceeded: The user has uploaded too many thumbnails recently."

            fake_rep = SimpleNamespace(
                path=fake_jpg,
                hero="MORNING PEACE",
                hero_px=132,
                contrast=12.5,
                backdrop="dawn_sanctuary",
                passes=True,
                as_dict=lambda: {"passes": True},
            )

            with mock.patch.object(spt, "generate_ctr_pack", return_value=[fake_rep]), \
                 mock.patch.object(spt, "apply_shorts_thumbnail", side_effect=AssertionError("Shorts API must be skipped once channel is rate-limited")):
                rows = spt.sync_published_thumbnails(
                    published_dir=pub,
                    out_root=out,
                    youtube_client=fake_yt,
                    thumb_setter=fake_setter,
                    channel="prayer2",
                )

            self.assertEqual(setter_calls, ["vid0036AAAA"], "Must stop calling thumbnails.set after first rate-limit hit")
            self.assertEqual(len(rows), 5)
            self.assertTrue(all("rate_limit" in r["thumbnail_status"] or "uploadRateLimitExceeded" in r["thumbnail_status"] for r in rows))
            for md in pub.glob("*.md"):
                self.assertIn("thumbnail_retry_after:", md.read_text(encoding="utf-8"))
            self.assertEqual(spt.DEFAULT_CHANNEL_PASS_LIMIT, 4)

    def test_release_report_channel_scoping_and_longform_only_publish_recency(self):
        """A green sibling channel never closes another channel's failure ticket; Shorts don't mask long-form stalls."""
        from scripts import pipeline_watchdog as pw
        from scripts import release_report as rr

        summary = rr.summarise(rr.parse_trail(
            "19:16:00Z ▶ speech alignment — 469s of audio\n"
            "19:18:17Z ✗ speech alignment — failed after 137s: ValueError: only 2% aligned\n"
        ))
        _, body = rr.render(summary, run_id="42465258075", channel_id="secret-place")
        self.assertIn("- **Channel:** `secret-place`", body)

        open_issues = [
            {"number": 339, "title": "Release failed in speech alignment (run 42465258075)", "body": body},
            {"number": 340, "title": "Release failed in encode (run 42465299999)", "body": "- **Channel:** `prayer2`"},
            {"number": 301, "title": "Release died inside encode (run 41900000000)", "body": "Legacy untagged ticket"},
        ]
        closed_by_prayer2: list[int] = []

        def fake_gh_p2(cmd, **kwargs):
            res = mock.MagicMock(returncode=0, stdout="[]", stderr="")
            if cmd[:3] == ["gh", "issue", "list"]:
                res.stdout = json.dumps(open_issues)
            elif cmd[:3] == ["gh", "issue", "close"]:
                closed_by_prayer2.append(int(cmd[3]))
            return res

        with mock.patch("shutil.which", return_value="/usr/bin/gh"), \
             mock.patch.object(rr, "sweep_stale_release_issues", return_value=[]), \
             mock.patch("subprocess.run", side_effect=fake_gh_p2):
            rr.close_resolved_issues("johnAzani/YouTube-automation", run_id="42471579273", channel_id="prayer2")

        self.assertEqual(closed_by_prayer2, [340], "prayer2 must only close prayer2 issues, never secret-place (#339) or legacy (#301)")

        closed_by_sp: list[int] = []

        def fake_gh_sp(cmd, **kwargs):
            res = mock.MagicMock(returncode=0, stdout="[]", stderr="")
            if cmd[:3] == ["gh", "issue", "list"]:
                res.stdout = json.dumps(open_issues)
            elif cmd[:3] == ["gh", "issue", "close"]:
                closed_by_sp.append(int(cmd[3]))
            return res

        with mock.patch("shutil.which", return_value="/usr/bin/gh"), \
             mock.patch.object(rr, "sweep_stale_release_issues", return_value=[]), \
             mock.patch("subprocess.run", side_effect=fake_gh_sp):
            rr.close_resolved_issues("johnAzani/YouTube-automation", run_id="42500000001", channel_id="secret-place")

        self.assertEqual(sorted(closed_by_sp), [301, 339])

        with tempfile.TemporaryDirectory() as tmp:
            pub = Path(tmp)
            now = datetime(2026, 11, 8, 20, 0, tzinfo=timezone.utc)
            (pub / "0014-longform.md").write_text(
                f"---\nchannel: secret-place\nyoutube_video_id: lf0014AAAAA\n"
                f"published_at: '{(now - timedelta(hours=36)).strftime('%Y-%m-%dT%H:%M:%SZ')}'\n---\n",
                encoding="utf-8",
            )
            (pub / "short-psalm91v5.md").write_text(
                f"---\nchannel: secret-place\nformat: short\nyoutube_video_id: sh91v5AAAAA\n"
                f"published_at: '{(now - timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M:%SZ')}'\n---\n",
                encoding="utf-8",
            )
            any_lp = pw.last_publish_for_channel("secret-place", published_dir=pub)
            lf_lp = pw.last_publish_for_channel("secret-place", published_dir=pub, longform_only=True)
            self.assertEqual(any_lp[0].name, "short-psalm91v5.md")
            self.assertEqual(lf_lp[0].name, "0014-longform.md")

        produce_wf = (ROOT / ".github" / "workflows" / "produce.yml").read_text(encoding="utf-8")
        self.assertIn("longform_only=True", produce_wf)
        self.assertIn("env.LONGFORM_UPLOADED == 'true'", produce_wf)


if __name__ == "__main__":
    unittest.main()
