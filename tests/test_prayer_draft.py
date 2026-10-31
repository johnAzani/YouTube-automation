import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
from pipeline.prayer_alignment import align
from pipeline.prayer_draft import build
from pipeline.script_doc import Scene, ScriptDoc


class DraftTests(unittest.TestCase):
    def test_scene_cuts_use_measured_speech(self):
        doc = ScriptDoc(Path('a.md'), {'format': 'longform', 'niche': 'prayer', 'voice': 'Charon'},
                        [Scene(1, 'One', 'first sentence.'), Scene(2, 'Two', 'second sentence.')])
        words = [('first', .1, 10), ('sentence.', 10.1, 110), ('second', 111, 200), ('sentence.', 201, 300)]
        with patch('pipeline.prayer_draft.parse_script', return_value=doc), patch('pipeline.prayer_draft._probe_duration', return_value=301), patch('pipeline.prayer_draft.align', return_value=words), patch('pipeline.prayer_draft.render', return_value=Path('out.mp4')) as renderer:
            build(Path('a.md'), Path('a.wav'), Path('model'), [Path('a.jpg'), Path('b.jpg')], Path('out.mp4'))
        self.assertEqual(renderer.call_args.args[1], [(Path('a.jpg'), 110), (Path('b.jpg'), 191)])

    def test_audio_model_is_offline_and_mismatch_rejected(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp); audio = root/'audio.wav'; audio.write_bytes(b'x')
            model = root/'model'; model.mkdir(); (model/'model.bin').write_bytes(b'x')
            spoken = [SimpleNamespace(word=' Rest', start=.1, end=.4, probability=.9)]
            class Model:
                def __init__(self, path, **kw):
                    assert kw['local_files_only'] is True
                def transcribe(self, *a, **kw):
                    return [SimpleNamespace(words=spoken)], None
            with patch.dict(sys.modules, {'faster_whisper': SimpleNamespace(WhisperModel=Model)}):
                self.assertEqual(align(audio, 'Rest.', model), [('Rest.', .1, .4)])
                with self.assertRaises(ValueError):
                    align(audio, 'Peace.', model)
