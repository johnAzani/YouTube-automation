import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch, MagicMock
from types import SimpleNamespace

from pipeline.prayer_pipeline import produce
from pipeline.script_doc import ScriptDoc, Scene


class PrayerPipelineTests(unittest.TestCase):
    def test_full_path_uses_approved_renderer_and_marks_confirmed_upload(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp); model = root / 'model'; model.mkdir(); (model/'model.bin').write_bytes(b'local')
            doc = ScriptDoc(root/'job.md', {'id': 'test', 'slug': 'test', 'title': 'Test', 'status': 'approved', 'format': 'longform', 'niche': 'prayer', 'voice': 'Charon'}, [Scene(1, 'One', 'hello ' * 700)])
            asset = root/'image.jpg'; asset.write_bytes(b'a')
            output = root/'out.mp4'; output.write_bytes(b'b')
            thumbnail = root/'thumb.jpg'; thumbnail.write_bytes(b'c')
            upload = SimpleNamespace(video_id='abc', watch_url='https://youtu.be/abc', privacy_status='public')
            words = [('hello', i * .4, i * .4 + .3) for i in range(700)]
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
