import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from PIL import Image
from pipeline.prayer_visuals import sentence_stream, render


class PrayerVisualTests(unittest.TestCase):
    def test_sentence_transition_and_real_word_timings(self):
        words = [('First.', .1, .8), ('Second.', 1.4, 2), ('No', 3.0, 3.2), ('evil', 3.3, 3.5), ('shall', 3.6, 3.8), ('befall', 3.9, 4.2), ('you.', 4.3, 4.5)]
        cards = sentence_stream(words, timing_source='measured')
        self.assertEqual(cards[2]['disp_t0'], 2)
        self.assertEqual(cards[2]['word_timings'][0], (3.0, 3.2))
        self.assertEqual(cards[-1]['disp_t1'], 4.5)
        with self.assertRaises(ValueError):
            sentence_stream(words, timing_source='estimated')

    def test_widescreen_uses_shorts_layer_without_changing_portrait(self):
        from tools.shorts import kinetic_typography_layer
        words = [('Rest', .1, .5), ('tonight.', .6, 1.0)]
        cards = sentence_stream(words, timing_source='measured')
        bg = Image.new('RGB', (720, 1280))
        a = kinetic_typography_layer(bg, cards, .2, is_prayer=True)
        b = kinetic_typography_layer(bg, cards, .2, is_prayer=True, canvas_size=(720, 1280))
        self.assertEqual(a.tobytes(), b.tobytes())
        wide = kinetic_typography_layer(Image.new('RGB', (1280, 720)), cards, .2, True, (1280, 720))
        self.assertEqual(wide.size, (1280, 720))
        self.assertIsNotNone(wide.getbbox())

    def test_actual_video_encode_with_approved_graphics(self):
        import subprocess
        from pipeline.assemble import ffmpeg_bin
        from pipeline.tts import _probe_duration
        with TemporaryDirectory() as tmp:
            p = Path(tmp)
            Image.new('RGB', (320, 320), (40, 80, 150)).save(p/'plate.png')
            subprocess.run([ffmpeg_bin(), '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=1', str(p/'audio.wav')], check=True)
            out = render(p/'audio.wav', [(p/'plate.png', 1)], [('Rest.', .1, .9)], 1, p/'out.mp4', timing_source='measured', width=640, height=360, fps=4)
            self.assertGreater(out.stat().st_size, 1000)
            self.assertAlmostEqual(_probe_duration(out), 1, delta=.2)

    def test_synthetic_five_minute_video_covers_all_scenes(self):
        import subprocess
        from pipeline.assemble import ffmpeg_bin
        from pipeline.tts import _probe_duration
        with TemporaryDirectory() as tmp:
            p = Path(tmp)
            Image.new('RGB', (160, 160), (40, 80, 150)).save(p/'a.png')
            Image.new('RGB', (160, 160), (50, 100, 160)).save(p/'b.png')
            subprocess.run([ffmpeg_bin(), '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=8000:cl=mono', '-t', '301', str(p/'audio.wav')], check=True)
            out = render(p/'audio.wav', [(p/'a.png', 150.5), (p/'b.png', 150.5)], [('Start.', .1, .9), ('End.', 299, 300)], 301, p/'out.mp4', timing_source='measured', width=160, height=90, fps=1)
            self.assertAlmostEqual(_probe_duration(out), 301, delta=.2)
