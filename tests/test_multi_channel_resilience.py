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
        self.assertIn("chunks-tts-v4-${{ matrix.channel }}-${{ github.run_id }}", text)
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

            with mock.patch.object(prun, "QUEUE_DIR", qdir), \
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




if __name__ == "__main__":
    unittest.main()
