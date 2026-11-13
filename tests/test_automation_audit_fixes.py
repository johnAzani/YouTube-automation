"""Regression coverage for the all-channel automation audit."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from pipeline import short_release as sr
from pipeline.gemini_tts import DEFAULT_MODEL
from scripts import build_dashboard_data as dashboard


class ShortVoiceProvenance(unittest.TestCase):
    def test_unlabelled_cache_is_replaced_and_verified_cache_reused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio = root / 'assets' / 'deepdive' / 'short-test.mp3'
            audio.parent.mkdir(parents=True)
            audio.write_bytes(b'unknown-voice')
            words = audio.parent / 'words-short-test.json'
            words.write_text('stale timings')
            spec = SimpleNamespace(narration_text='A fresh prayer', words=3)
            spec_file = root / 'spec.json'
            spec_file.write_text('{}')

            def synth(text, path):
                self.assertFalse(words.exists())
                path.write_bytes(b'charon-audio')
                return DEFAULT_MODEL

            with mock.patch.object(sr, 'REPO_ROOT', root), \
                 mock.patch('pipeline.short_script.spec_path', return_value=spec_file), \
                 mock.patch('pipeline.short_script.load_spec', return_value=spec), \
                 mock.patch.object(sr, '_synthesise_narration', side_effect=synth) as narrator, \
                 mock.patch.object(sr, '_ensure_word_timings'):
                sr._ensure_narration('short-test')
                sr._ensure_narration('short-test')
                self.assertEqual(narrator.call_count, 1)
                self.assertEqual(json.loads(audio.with_suffix('.voice.json').read_text())['voice'], 'Charon')
                audio.write_bytes(b'tampered')
                sr._ensure_narration('short-test')
                self.assertEqual(narrator.call_count, 2)

    def test_missing_legacy_provenance_blocks_production(self):
        with mock.patch('pipeline.short_script.spec_path', return_value=Path('/no-such-spec')):
            with self.assertRaisesRegex(RuntimeError, 'no verified Charon provenance'):
                sr._ensure_narration('short-legacy')

    def test_failure_cleans_partial_audio_and_propagates_quota(self):
        from pipeline.quota_handler import GeminiQuotaExceededError
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_file = root / 'spec.json'
            spec_file.write_text('{}')
            def failed(text, path):
                path.write_bytes(b'partial')
                raise GeminiQuotaExceededError('quota')
            with mock.patch.object(sr, 'REPO_ROOT', root), \
                 mock.patch('pipeline.short_script.spec_path', return_value=spec_file), \
                 mock.patch('pipeline.short_script.load_spec', return_value=SimpleNamespace(narration_text='text', words=1)), \
                 mock.patch.object(sr, '_synthesise_narration', side_effect=failed):
                with self.assertRaises(GeminiQuotaExceededError):
                    sr._ensure_narration('short-test')
            self.assertFalse((root / 'assets/deepdive/short-test.mp3').exists())


class SupervisorJobAPI(unittest.TestCase):
    def test_job_pages_are_combined(self):
        from scripts import scheduler_supervisor as sup
        result = SimpleNamespace(returncode=0, stdout=json.dumps([
            {'jobs': [{'status': 'completed'}]}, {'jobs': [{'status': 'in_progress'}]}]), stderr='')
        with mock.patch('scripts.automation_monitor.repo_slug', return_value='owner/repo'), \
             mock.patch.object(sup.subprocess, 'run', return_value=result) as call:
            self.assertEqual(len(sup._run_jobs(123)), 2)
            self.assertIn('--paginate', call.call_args.args[0])
            self.assertIn('--slurp', call.call_args.args[0])

    def test_failed_or_invalid_job_response_is_unknown(self):
        from scripts import scheduler_supervisor as sup
        with mock.patch('scripts.automation_monitor.repo_slug', return_value='owner/repo'):
            for result in (SimpleNamespace(returncode=1, stderr='error', stdout=''),
                           SimpleNamespace(returncode=0, stderr='', stdout='invalid'),
                           SimpleNamespace(returncode=0, stderr='', stdout='[{}]'),
                           SimpleNamespace(returncode=0, stderr='', stdout='[{"jobs":[null]}]')):
                with mock.patch.object(sup.subprocess, 'run', return_value=result):
                    self.assertIsNone(sup._run_jobs(123))


class DashboardAccuracy(unittest.TestCase):
    def test_target_time_is_only_displayed_if_valid_string(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue = root / 'content/shorts-queue'
            queue.mkdir(parents=True)
            (queue / 'a.yml').write_text('short: short-a\ntarget_window_utc: 18:44\n')
            (queue / 'b.yml').write_text("short: short-b\ntarget_window_utc: '18:44'\n")
            (queue / 'c.yml').write_text("short: short-c\ntarget_window_utc: '25:00'\n")
            rows = dashboard._load_shorts_queue(root)
            self.assertEqual([r['target_window_utc'] for r in rows], ['', '18:44', ''])

    def test_thumbnail_pending_is_receipt_based(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pub = root / 'content/published'
            pub.mkdir(parents=True)
            (pub / 'one.md').write_text('---\nid: 1\nchannel: prayer8\nthumbnail_pending: true\n---\ntext')
            state = dashboard.build_network_state(root)
            channel = next(c for c in state['channels'] if c['id'] == 'prayer8')
            self.assertEqual(channel['counts']['thumbnail_pending'], 1)

    def test_missing_monitor_snapshot_is_not_healthy(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = dashboard.build_network_state(Path(tmp))
            self.assertFalse(state['totals']['network_healthy'])
            self.assertEqual(state['monitor_generated_at'], '')

    def test_failed_metrics_snapshot_does_not_overwrite_feedback(self):
        source = (Path(__file__).resolve().parents[1] / '.github/workflows/growth-autopilot.yml').read_text()
        self.assertIn("if: ${{ steps.metrics.outcome == 'success' }}", source)
        self.assertIn('the previous feedback artifact was preserved', source)
        import yaml
        steps = yaml.safe_load(source)['jobs']['growth']['steps']
        feedback = next(s for s in steps if s.get('id') == 'feedback')
        commit = next(s for s in steps if s.get('name', '').startswith('Commit the derived feedback'))
        self.assertTrue(feedback['continue-on-error'])
        self.assertIn("steps.metrics.outcome == 'success'", commit['if'])
        self.assertIn("steps.feedback.outcome == 'success'", commit['if'])


if __name__ == '__main__':
    unittest.main()
