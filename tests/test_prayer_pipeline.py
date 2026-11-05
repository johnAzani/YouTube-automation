import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch, MagicMock
from types import SimpleNamespace

from pipeline.prayer_pipeline import produce
from pipeline.script_doc import ScriptDoc, Scene


class RetryEconomyTests(unittest.TestCase):
    """A release that fails at minute 89 must not repay for speech or alignment.

    On 2 November 0017 was rendered three times and published none of them: each
    attempt re-synthesised 888 words of Charon narration and re-ran the alignment
    model before starting the encode it would never finish.
    """

    def _produce(self, root, model):
        (root / 'test' / 'thumbnails').mkdir(parents=True, exist_ok=True)
        doc = ScriptDoc(root/'job.md', {'id': 'test', 'slug': 'test', 'title': 'Test',
                                         'status': 'approved', 'format': 'longform',
                                         'niche': 'prayer', 'voice': 'Charon',
                                         'thumb_text': 'BE STILL'},
                        [Scene(1, 'One', 'hello ' * 900)])
        asset = root/'image.jpg'; asset.write_bytes(b'a')
        output = root/'out.mp4'; output.write_bytes(b'b')
        thumbnail = root/'thumb.jpg'; thumbnail.write_bytes(b'c')
        up = SimpleNamespace(video_id='abc', watch_url='https://youtu.be/abc',
                             privacy_status='public')
        words = [('hello', i * .4, i * .4 + .3) for i in range(900)]
        with patch('pipeline.prayer_pipeline.parse_script', return_value=doc), \
             patch('pipeline.prayer_pipeline.enforce'), \
             patch('pipeline.run._require_production_prerequisites'), \
             patch('pipeline.prayer_pipeline.get_gemini_api_key', return_value='fake'), \
             patch('pipeline.prayer_pipeline.importlib.util.find_spec', return_value=True), \
             patch('pipeline.prayer_pipeline.OUTPUT_DIR', root), \
             patch('pipeline.prayer_pipeline.synthesize_gemini_audio',
                   side_effect=lambda *a, **k: (root / 'test' / 'narration.mp3').write_bytes(b'x')) as tts, \
             patch('pipeline.prayer_pipeline._probe_duration', return_value=301), \
             patch('pipeline.prayer_pipeline.align', return_value=words) as align, \
             patch('pipeline.assets.fetch_scene_assets',
                   return_value=[SimpleNamespace(path=asset)]) as fetch, \
             patch('pipeline.prayer_pipeline.render', return_value=output) as renderer, \
             patch('pipeline.thumbnail_ctr.generate_ctr_pack',
                   return_value=[SimpleNamespace(path=thumbnail, as_dict=lambda: {})]), \
             patch('pipeline.thumbnail_studio.mobile_preview'), \
             patch('pipeline.metadata.write_metadata_pack', return_value={'description': 'prayer'}), \
             patch('pipeline.upload.upload', return_value=up), \
             patch('pipeline.run._mark_job_uploaded'), \
             patch('pipeline.run._open_release_ticket'):
            produce(root/'job.md', False, model)
        return tts, align, fetch, renderer

    def test_a_second_attempt_reuses_speech_and_alignment(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp); model = root / 'model'; model.mkdir()
            (model/'model.bin').write_bytes(b'local')
            tts1, align1, fetch1, render1 = self._produce(root, model)
            tts2, align2, fetch2, render2 = self._produce(root, model)
            self.assertTrue(tts1.called and align1.called)
            self.assertFalse(tts2.called, "speech must not be paid for twice")
            self.assertFalse(align2.called, "alignment must not be recomputed")
            # the render still happens; that is the part that was never finished
            self.assertTrue(render2.called)

    def test_the_renderer_is_handed_a_progress_callback(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp); model = root / 'model'; model.mkdir()
            (model/'model.bin').write_bytes(b'local')
            _, _, _, renderer = self._produce(root, model)
            self.assertTrue(callable(renderer.call_args.kwargs.get("progress")))

    def test_only_one_asset_is_fetched_per_scene(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp); model = root / 'model'; model.mkdir()
            (model/'model.bin').write_bytes(b'local')
            _, _, fetch, _ = self._produce(root, model)
            self.assertEqual(fetch.call_args.kwargs.get("count"), 1,
                             "count=2 downloaded a second clip that was thrown away")

    def test_an_edited_script_speaks_again(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp); model = root / 'model'; model.mkdir()
            (model/'model.bin').write_bytes(b'local')
            self._produce(root, model)
            # change the script text: the fingerprint must no longer match
            doc_words = 'different ' * 900
            tts, align, _, _ = self._produce_with_text(root, model, doc_words)
            self.assertTrue(tts.called)
            self.assertTrue(align.called)

    def _produce_with_text(self, root, model, narration):
        (root / 'test' / 'thumbnails').mkdir(parents=True, exist_ok=True)
        doc = ScriptDoc(root/'job.md', {'id': 'test', 'slug': 'test', 'title': 'Test',
                                         'status': 'approved', 'format': 'longform',
                                         'niche': 'prayer', 'voice': 'Charon'},
                        [Scene(1, 'One', narration)])
        asset = root/'image.jpg'; asset.write_bytes(b'a')
        output = root/'out.mp4'; output.write_bytes(b'b')
        thumbnail = root/'thumb.jpg'; thumbnail.write_bytes(b'c')
        up = SimpleNamespace(video_id='abc', watch_url='https://youtu.be/abc',
                             privacy_status='public')
        words = [(w, i * .4, i * .4 + .3) for i, w in enumerate(narration.split())]
        with patch('pipeline.prayer_pipeline.parse_script', return_value=doc), \
             patch('pipeline.prayer_pipeline.enforce'), \
             patch('pipeline.run._require_production_prerequisites'), \
             patch('pipeline.prayer_pipeline.get_gemini_api_key', return_value='fake'), \
             patch('pipeline.prayer_pipeline.importlib.util.find_spec', return_value=True), \
             patch('pipeline.prayer_pipeline.OUTPUT_DIR', root), \
             patch('pipeline.prayer_pipeline.synthesize_gemini_audio',
                   side_effect=lambda *a, **k: (root / 'test' / 'narration.mp3').write_bytes(b'x')) as tts, \
             patch('pipeline.prayer_pipeline._probe_duration', return_value=301), \
             patch('pipeline.prayer_pipeline.align', return_value=words) as align, \
             patch('pipeline.assets.fetch_scene_assets',
                   return_value=[SimpleNamespace(path=asset)]), \
             patch('pipeline.prayer_pipeline.render', return_value=output), \
             patch('pipeline.thumbnail_ctr.generate_ctr_pack',
                   return_value=[SimpleNamespace(path=thumbnail, as_dict=lambda: {})]), \
             patch('pipeline.thumbnail_studio.mobile_preview'), \
             patch('pipeline.metadata.write_metadata_pack', return_value={'description': 'prayer'}), \
             patch('pipeline.upload.upload', return_value=up), \
             patch('pipeline.run._mark_job_uploaded'), \
             patch('pipeline.run._open_release_ticket'):
            produce(root/'job.md', False, model)
        return tts, align, None, None


class PrayerPipelineTests(unittest.TestCase):
    def test_full_path_uses_approved_renderer_and_marks_confirmed_upload(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp); model = root / 'model'; model.mkdir(); (model/'model.bin').write_bytes(b'local')
            doc = ScriptDoc(root/'job.md', {'id': 'test', 'slug': 'test', 'title': 'Test', 'status': 'approved', 'format': 'longform', 'niche': 'prayer', 'voice': 'Charon'}, [Scene(1, 'One', 'hello ' * 900)])
            asset = root/'image.jpg'; asset.write_bytes(b'a')
            output = root/'out.mp4'; output.write_bytes(b'b')
            thumbnail = root/'thumb.jpg'; thumbnail.write_bytes(b'c')
            upload = SimpleNamespace(video_id='abc', watch_url='https://youtu.be/abc', privacy_status='public')
            words = [('hello', i * .4, i * .4 + .3) for i in range(900)]
            with patch('pipeline.prayer_pipeline.parse_script', return_value=doc), patch('pipeline.prayer_pipeline.enforce'), \
                 patch('pipeline.run._require_production_prerequisites'), patch('pipeline.prayer_pipeline.get_gemini_api_key', return_value='fake'), \
                 patch('pipeline.prayer_pipeline.importlib.util.find_spec', return_value=True), patch('pipeline.prayer_pipeline.OUTPUT_DIR', root), \
                 patch('pipeline.prayer_pipeline.synthesize_gemini_audio') as tts, patch('pipeline.prayer_pipeline._probe_duration', return_value=301), \
                 patch('pipeline.prayer_pipeline.align', return_value=words), patch('pipeline.assets.fetch_scene_assets', return_value=[SimpleNamespace(path=asset)]), \
                 patch('pipeline.prayer_pipeline.render', return_value=output) as renderer, patch('pipeline.thumbnail.generate_thumbnail_variants', return_value=[thumbnail]), \
                 patch('pipeline.metadata.write_metadata_pack', return_value={'description':'prayer'}), patch('pipeline.upload.upload', return_value=upload), \
                 patch('pipeline.run._mark_job_uploaded') as mark, patch('pipeline.run._open_release_ticket'):
                result = produce(root/'job.md', False, model)
            self.assertTrue(result['uploaded'])
            self.assertEqual(tts.call_args.kwargs['voice'], 'Charon')
            self.assertEqual(tts.call_args.kwargs['model'], 'gemini-3.8-flash-tts')
            self.assertEqual(renderer.call_args.kwargs['timing_source'], 'measured')
            mark.assert_called_once()

    def test_short_script_fails_before_tts(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp); model = root/'model'; model.mkdir(); (model/'model.bin').write_bytes(b'x')
            doc = ScriptDoc(root/'job.md', {'status':'approved','format':'longform','niche':'prayer','voice':'Charon'}, [Scene(1,'One','hello')])
            with patch('pipeline.prayer_pipeline.parse_script', return_value=doc), patch('pipeline.prayer_pipeline.enforce'), \
                 patch('pipeline.run._require_production_prerequisites'), patch('pipeline.prayer_pipeline.get_gemini_api_key', return_value='fake'), \
                 patch('pipeline.prayer_pipeline.importlib.util.find_spec', return_value=True), patch('pipeline.prayer_pipeline.synthesize_gemini_audio') as tts:
                with self.assertRaisesRegex(RuntimeError, 'expand it'):
                    produce(root/'job.md', False, model)
                tts.assert_not_called()

    def test_missing_alignment_never_calls_tts(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc = ScriptDoc(root/'job.md', {'status':'approved','format':'longform','niche':'prayer','voice':'Charon'}, [Scene(1,'One','hello ' * 900)])
            with patch('pipeline.prayer_pipeline.parse_script', return_value=doc), patch('pipeline.prayer_pipeline.enforce'), \
                 patch('pipeline.run._require_production_prerequisites'), patch('pipeline.prayer_pipeline.get_gemini_api_key', return_value='fake'), \
                 patch('pipeline.prayer_pipeline.synthesize_gemini_audio') as tts:
                with self.assertRaisesRegex(RuntimeError, 'alignment model'):
                    produce(root/'job.md', False, root/'missing-model')
                tts.assert_not_called()

    def test_existing_published_record_fails_before_tts(self):
        """A published record for the same job file must stop the run before
        any synthesis: on 5 November 2026 job 0036 rendered 52 minutes and
        uploaded, then failed when the receipt move refused to overwrite a
        stale record resurrected by a monitor snapshot."""
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc = ScriptDoc(root/'job.md', {'id': 'test', 'status': 'approved', 'format': 'longform', 'niche': 'prayer', 'voice': 'Charon'}, [Scene(1, 'One', 'hello ' * 900)])
            published_dir = root / 'published'
            published_dir.mkdir()
            (published_dir / 'job.md').write_text('status: published')
            with patch('pipeline.prayer_pipeline.parse_script', return_value=doc), \
                 patch('pipeline.prayer_pipeline.enforce'), \
                 patch('pipeline.run._require_production_prerequisites'), \
                 patch('pipeline.prayer_pipeline.PUBLISHED_DIR', published_dir), \
                 patch('pipeline.prayer_pipeline.get_gemini_api_key', return_value='fake'), \
                 patch('pipeline.prayer_pipeline.synthesize_gemini_audio') as tts:
                with self.assertRaisesRegex(RuntimeError, 'already exists'):
                    produce(root/'job.md', False, root/'model')
            tts.assert_not_called()

    def test_wrong_voice_is_rejected_before_tts(self):
        doc = ScriptDoc(Path('job.md'), {'status':'approved','format':'longform','niche':'prayer','voice':'Other'}, [Scene(1,'One','hello')])
        with patch('pipeline.prayer_pipeline.parse_script', return_value=doc), \
             patch('pipeline.prayer_pipeline.synthesize_gemini_audio') as tts:
            with self.assertRaisesRegex(RuntimeError, 'Charon'):
                produce(Path('job.md'), False, Path('model'))
            tts.assert_not_called()
