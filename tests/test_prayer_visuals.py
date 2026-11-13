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

    def test_a_long_prayer_sentence_becomes_several_cards(self):
        """The expansion writes real prayer sentences; the renderer must draw them.

        A 40-word sentence needs about eight 30-character lines, which used to raise
        'Sentence is too long for the widescreen layout' and kill the upload.
        """
        sentence = ("Father when the day has left us feeling small remind us that "
                    "the hills are not higher than Your compassion and that we do "
                    "not have to find strength in ourselves before we come to You.")
        tokens = sentence.split()
        words = [(t, 0.4 * i, 0.4 * i + 0.35) for i, t in enumerate(tokens)]
        words[-1] = (tokens[-1] + '.', words[-1][1], words[-1][2])
        cards = sentence_stream(words, timing_source='measured')
        self.assertGreater(len(cards), 1, "a long sentence must paginate, not raise")
        self.assertTrue(all(len(card['lines']) <= 6 for card in cards))
        # every word is spoken exactly once across the cards, in order
        timings = [t for card in cards for t in card['word_timings']]
        self.assertEqual(timings, [(a, b) for _, a, b in words])
        self.assertEqual(cards[0]['disp_t0'], 0.0)
        for before, after in zip(cards, cards[1:]):
            # spoken time never overlaps and never goes backwards
            self.assertGreaterEqual(after['t0'], before['t1'])
            self.assertEqual(before['disp_t1'], before['t1'])

    def test_every_card_still_fits_the_layout(self):
        words = [(f"word{i}", 0.2 * i, 0.2 * i + 0.15) for i in range(60)]
        words[-1] = ("end.", words[-1][1], words[-1][2])
        for card in sentence_stream(words, timing_source='measured'):
            self.assertLessEqual(len(card['lines']), 6)
            self.assertTrue(all(len(line) <= 30 for line in card['lines']))

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

    def test_longform_render_mixes_shorts_background_music(self):
        """A silent narration input must still output the stereo Shorts score bed."""
        import subprocess
        import wave
        import numpy as np
        from pipeline.assemble import ffmpeg_bin

        with TemporaryDirectory() as tmp:
            p = Path(tmp)
            Image.new('RGB', (320, 180), (20, 45, 95)).save(p / 'plate.png')
            silent_nar = p / 'silent.wav'
            decoded_pcm = p / 'decoded.wav'
            subprocess.run(
                [ffmpeg_bin(), '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=mono', '-t', '6', str(silent_nar)],
                check=True,
            )
            out = render(
                silent_nar,
                [(p / 'plate.png', 3.0), (p / 'plate.png', 3.0)],
                [('Peace', 0.4, 1.2), ('tonight.', 1.3, 2.2), ('Amen.', 4.6, 5.4)],
                6.0,
                p / 'with_music.mp4',
                timing_source='measured',
                width=320,
                height=180,
                fps=4,
            )
            subprocess.run(
                [ffmpeg_bin(), '-loglevel', 'error', '-y', '-i', str(out), '-vn', '-ac', '2', '-ar', '44100', str(decoded_pcm)],
                check=True,
            )
            with wave.open(str(decoded_pcm), 'rb') as wf:
                self.assertEqual(wf.getnchannels(), 2)
                samples = np.frombuffer(wf.readframes(wf.getnframes()), dtype='<i2').astype(np.float64) / 32768.0
            stereo = samples.reshape(-1, 2)
            rms = float(np.sqrt(np.mean(stereo ** 2)))
            peak = float(np.max(np.abs(stereo)))
            stereo_diff = float(np.max(np.abs(stereo[:, 0] - stereo[:, 1])))
            self.assertGreater(rms, 0.005, "Long-form output MP4 is missing the Shorts background music bed")
            self.assertGreater(peak, 0.03)
            self.assertGreater(stereo_diff, 0.001, "Expected true stereo-detuned Shorts pad bed")

    def test_brain_authored_short_cards_paginate_to_three_lines_max(self):
        from tools.shorts import SCRIPTS, build_kinetic_stream

        for key in ('short-psalm121', 'short-psalm27', 'short-psalm46', 'short-psalm34'):
            if key not in SCRIPTS:
                continue
            from pipeline.short_release import _clean_word_token
            spoken = [w for cap in SCRIPTS[key]['captions'] for w in cap[2].split()
                      if _clean_word_token(w)]
            fake_words = [(i * 0.45, i * 0.45 + 0.38, _clean_word_token(w))
                          for i, w in enumerate(spoken)]
            stream = build_kinetic_stream(key, fake_words, adur=len(spoken) * 0.45 + 1)
            self.assertGreater(len(stream), 0, key)
            for card in stream:
                self.assertLessEqual(len(card['lines']), 3, f"{key}: {card['lines']}")

