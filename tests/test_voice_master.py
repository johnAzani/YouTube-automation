"""Voice mastering: louder, clearer narration without touching the take.

The numbers asserted here are the reason the module exists. Before it, a finished
video measured about -19 LUFS against YouTube's -14 reference, and YouTube never
turns a quiet video up.
"""
from __future__ import annotations

import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from pipeline import voice_master as vm
from pipeline.assemble import ffmpeg_bin


def _summary(path: Path, prefilter: str = "") -> tuple[float, float]:
    """(integrated LUFS, true peak dBFS) of a file."""
    chain = f"{prefilter},ebur128=peak=true" if prefilter else "ebur128=peak=true"
    proc = subprocess.run(
        [ffmpeg_bin(), "-hide_banner", "-nostats", "-i", str(path), "-af", chain,
         "-f", "null", "-"], capture_output=True, text=True, check=True)
    tail = proc.stderr[proc.stderr.rindex("Summary:"):]
    loud = float(re.search(r"I:\s+(-?[\d.]+) LUFS", tail).group(1))
    peak = float(re.search(r"Peak:\s+(-?[\d.]+) dBFS", tail).group(1))
    return loud, peak


def _duration(path: Path) -> float:
    proc = subprocess.run([ffmpeg_bin(), "-hide_banner", "-i", str(path)],
                          capture_output=True, text=True)
    h, m, s = re.search(r"Duration: (\d+):(\d+):([\d.]+)", proc.stderr).groups()
    return int(h) * 3600 + int(m) * 60 + float(s)


def _make(path: Path, source: str, seconds: float, extra: str = "") -> Path:
    subprocess.run(
        [ffmpeg_bin(), "-y", "-loglevel", "error", "-f", "lavfi", "-i", source,
         "-t", str(seconds), *(["-af", extra] if extra else []), str(path)],
        check=True)
    return path


class ReportParsing(unittest.TestCase):
    REPORT = """
[Parsed_loudnorm_4 @ 0x1]
{
\t"input_i" : "-24.04",
\t"input_tp" : "-11.10",
\t"input_lra" : "1.40",
\t"input_thresh" : "-34.34",
\t"output_i" : "-15.01",
\t"normalization_type" : "dynamic",
\t"target_offset" : "-0.03"
}
"""

    def test_reads_the_measurement(self):
        measured = vm.parse_loudnorm_report(self.REPORT)
        self.assertEqual(measured.input_i, -24.04)
        self.assertEqual(measured.input_tp, -11.10)
        self.assertEqual(measured.target_offset, -0.03)

    def test_silence_is_not_normalised(self):
        silent = self.REPORT.replace("-24.04", "-inf").replace("-11.10", "-inf")
        self.assertIsNone(vm.parse_loudnorm_report(silent))
        self.assertIsNone(vm.parse_loudnorm_report(self.REPORT.replace("-24.04", "-70.00")))

    def test_garbage_is_not_a_measurement(self):
        self.assertIsNone(vm.parse_loudnorm_report(""))
        self.assertIsNone(vm.parse_loudnorm_report('{"input_i": "abc"}'))


class FilterShape(unittest.TestCase):
    MEASURED = vm.Loudness(-24.04, -11.1, 1.4, -34.34, -0.03)

    def test_missing_narration_keeps_the_old_mix(self):
        said = []
        graph = vm.mix_filter(Path("/nonexistent/narration.mp3"), "volume=0.58",
                              log=said.append)
        self.assertEqual(graph, vm.legacy_mix_filter("volume=0.58"))
        self.assertIn("unmastered", said[0])

    def test_legacy_mix_is_the_graph_used_before_mastering(self):
        self.assertEqual(
            vm.legacy_mix_filter("volume=0.58"),
            "[2:a]volume=0.58[m];[1:a]aformat=channel_layouts=stereo,volume=1.0[v];"
            "[m][v]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.95[a]")

    def test_mastered_graph_uses_a_fixed_gain_not_a_riding_normaliser(self):
        graph = vm.mastered_mix_filter(self.MEASURED, "volume=0.58")
        self.assertIn("linear=true", graph)
        self.assertIn("measured_I=-24.04", graph)
        self.assertIn(f"I={vm.VOICE_TARGET_LUFS}", graph)
        self.assertNotIn("dynaudnorm", graph)
        self.assertNotIn("\n", graph)

    def test_the_bed_cannot_be_cut_short_and_the_limiter_does_not_relevel(self):
        graph = vm.mastered_mix_filter(self.MEASURED, "volume=0.58")
        self.assertIn("[k]apad[key]", graph)
        self.assertIn("level=disabled", graph)

    def test_nothing_in_the_chain_can_change_timing(self):
        for stretch in ("atempo", "silenceremove", "rubberband", "asetrate", "atrim"):
            self.assertNotIn(stretch, vm.mastered_mix_filter(self.MEASURED, "volume=0.58"))


class RendersLouderAndCleaner(unittest.TestCase):
    """End to end through ffmpeg, on a quiet speech-shaped signal over a bed."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        # Pink noise gated four times a second: wide-band and bursty like speech,
        # and quiet (about -27 LUFS), like narration straight out of synthesis.
        cls.voice = _make(root / "voice.wav", "anoisesrc=color=pink:amplitude=0.12:seed=7",
                          12, "tremolo=f=4:d=0.9,aformat=sample_rates=24000:channel_layouts=mono")
        cls.music = _make(root / "music.wav", "sine=frequency=220:sample_rate=44100", 16,
                          "volume=0.25,aformat=channel_layouts=stereo")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _mix(self, graph: str, name: str) -> Path:
        out = Path(self.tmp.name) / name
        subprocess.run(
            [ffmpeg_bin(), "-y", "-loglevel", "error", "-i", str(self.voice),
             "-i", str(self.music), "-filter_complex", graph, "-map", "[a]",
             "-ar", "48000", str(out)], check=True, timeout=120)
        return out

    def test_voice_alone_lands_on_target_under_the_ceiling(self):
        measured = vm.measure_voice(self.voice)
        self.assertIsNotNone(measured)
        self.assertLess(measured.input_i, -20.0, "fixture should start quiet")
        loud, peak = _summary(self.voice, vm.voice_chain(measured))
        self.assertAlmostEqual(loud, vm.VOICE_TARGET_LUFS, delta=1.0)
        self.assertLessEqual(peak, -1.0)

    def test_mix_is_louder_than_before_and_never_clips(self):
        args = dict(voice_input="0:a", music_input="1:a")
        before = self._mix(vm.legacy_mix_filter("volume=0.58", **args), "before.wav")
        after = self._mix(vm.mix_filter(self.voice, "volume=0.58", log=None, **args),
                          "after.wav")
        loud_before, _ = _summary(before)
        loud_after, peak_after = _summary(after)
        self.assertGreater(loud_after, loud_before + 3.0)
        self.assertLessEqual(peak_after, -0.9)
        self.assertGreater(loud_after, -17.0)
        self.assertLess(loud_after, -13.0)

    def test_music_plays_on_after_the_voice_ends(self):
        args = dict(voice_input="0:a", music_input="1:a")
        after = self._mix(vm.mix_filter(self.voice, "volume=0.58", log=None, **args),
                          "tail.wav")
        self.assertAlmostEqual(_duration(after), 16.0, delta=0.1)
        self.assertAlmostEqual(_duration(self.voice), 12.0, delta=0.1)

    def test_music_is_lower_under_speech_than_in_the_pause_after_it(self):
        args = dict(voice_input="0:a", music_input="1:a")
        measured = vm.measure_voice(self.voice)
        graph = vm.mastered_mix_filter(measured, "volume=0.58", **args)
        # Same graph, but listen to the ducked bed alone instead of the mix.
        bed_only = graph[:graph.index("[md][v]amix")] + "[v]anullsink;[md]anull[a]"
        bed = self._mix(bed_only, "bed.wav")
        under_speech, _ = _summary(bed, "atrim=start=2:end=10")
        in_the_clear, _ = _summary(bed, "atrim=start=13.5:end=16")
        self.assertLess(under_speech, in_the_clear - 1.0)


if __name__ == "__main__":
    unittest.main()
