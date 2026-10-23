"""ffmpeg must resolve on any machine — including one where apt never delivered.

On 2026-10-23 the required `Unit tests + doctor` CI job hung inside
`sudo apt-get install ffmpeg` for its entire 10-minute budget and was cancelled —
three runs in a row — without executing a single test. GitHub reports a job
timeout as `cancelled` rather than `failure`, so it did not read as a failure.

The apt ffmpeg was also redundant: `requirements.txt` pins `imageio-ffmpeg`, whose
static build `pipeline.assemble.ffmpeg_bin()` already knows how to find — but CI
ran apt *before* pip, so the fallback was never in place when apt hung. And
`tools/deep_dive.py` / `tools/shorts.py` did not use that resolver at all: they
defaulted to the literal string `'ffmpeg'`, so they broke on any machine without
system ffmpeg even though a static build was installed.

These tests pin the precedence, and keep the workflows from re-inlining an
unbounded apt install.
"""
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

from pipeline.assemble import ffmpeg_bin

ROOT = Path(__file__).resolve().parent.parent


def _code_lines(text: str) -> str:
    """Text without comment lines, so a prose explanation cannot satisfy an assertion."""
    return "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))
WORKFLOWS = ROOT / ".github" / "workflows"
SETUP_ACTION = ROOT / ".github" / "actions" / "setup-render-deps" / "action.yml"


class FFmpegPrecedence(unittest.TestCase):
    """FFMPEG_BINARY (when real) > PATH > the imageio-ffmpeg static build."""

    def test_explicit_binary_wins(self):
        with tempfile.NamedTemporaryFile(suffix="-ffmpeg") as fh:
            with mock.patch.dict(os.environ, {"FFMPEG_BINARY": fh.name}, clear=False):
                self.assertEqual(ffmpeg_bin(), fh.name)

    def test_path_is_used_when_no_override(self):
        with tempfile.TemporaryDirectory() as d:
            fake = Path(d) / "ffmpeg"
            fake.write_text("#!/bin/sh\nexit 0\n")
            fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
            env = {"FFMPEG_BINARY": "", "PATH": d}
            with mock.patch.dict(os.environ, env, clear=False):
                os.environ.pop("FFMPEG_BINARY", None)
                self.assertEqual(ffmpeg_bin(), str(fake))

    def test_falls_back_to_the_pinned_static_build(self):
        """No env, nothing on PATH: the dependency in requirements.txt must save us."""
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"PATH": d}, clear=False):
                os.environ.pop("FFMPEG_BINARY", None)
                resolved = ffmpeg_bin()
        import imageio_ffmpeg  # noqa: WPS433  (only needed for this assertion)

        self.assertEqual(resolved, imageio_ffmpeg.get_ffmpeg_exe())
        self.assertTrue(Path(resolved).exists(), f"{resolved} does not exist")
        self.assertTrue(os.access(resolved, os.X_OK), f"{resolved} is not executable")

    def test_a_bare_ffmpeg_binary_that_resolves_to_nothing_is_ignored(self):
        """Regression: remaster.yml pinned `FFMPEG_BINARY: ffmpeg`, which is not a path.

        `Path('ffmpeg').exists()` is False relative to the working directory, so
        honouring it would hand callers a command that cannot be found — exactly
        what the renderers used to do. The resolver must move on to the next
        candidate instead.
        """
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"FFMPEG_BINARY": "ffmpeg", "PATH": d}, clear=False):
                self.assertNotEqual(ffmpeg_bin(), "ffmpeg")
                self.assertTrue(Path(ffmpeg_bin()).exists())

    def test_missing_everything_raises_with_instructions(self):
        with mock.patch.dict(os.environ, {"FFMPEG_BINARY": "", "PATH": ""}, clear=False):
            os.environ.pop("FFMPEG_BINARY", None)
            with mock.patch.dict(sys.modules, {"imageio_ffmpeg": None}):
                with self.assertRaises(RuntimeError) as ctx:
                    ffmpeg_bin()
        self.assertIn("imageio-ffmpeg", str(ctx.exception))


class RendererClisUseTheSharedResolver(unittest.TestCase):
    """The two CLIs CI renders with must not re-implement (and break) resolution."""

    def test_both_delegate_to_ffmpeg_bin(self):
        for rel in ("tools/deep_dive.py", "tools/shorts.py", "tools/motionstudio.py"):
            src = _code_lines((ROOT / rel).read_text())
            self.assertNotIn(
                "os.environ.get('FFMPEG_BINARY', 'ffmpeg')", src,
                f"{rel} fell back to the literal 'ffmpeg' — it breaks with no system ffmpeg",
            )
            self.assertIn("from pipeline.assemble import ffmpeg_bin", src,
                          f"{rel} does not use the shared resolver")
            self.assertIn("FFMPEG = _resolve_ffmpeg()", [ln.strip() for ln in src.splitlines()],
                          f"{rel} does not resolve FFMPEG through the resolver")


class WorkflowsDoNotReintroduceUnboundedApt(unittest.TestCase):
    def test_no_workflow_installs_render_deps_inline(self):
        offenders = [
            p.name for p in sorted(WORKFLOWS.glob("*.yml"))
            if "apt-get install" in _code_lines(p.read_text())
        ]
        self.assertEqual(
            offenders, [],
            f"{offenders} install render deps inline. Use "
            f".github/actions/setup-render-deps so apt stays bounded and "
            f"non-fatal — an unbounded apt install cost three CI runs.",
        )

    def test_render_jobs_use_the_shared_setup_action(self):
        for name in ("dry-run.yml", "produce.yml", "remaster.yml"):
            self.assertIn("./.github/actions/setup-render-deps",
                          (WORKFLOWS / name).read_text(),
                          f"{name} does not use the shared setup action")

    def test_setup_action_timeboxes_apt(self):
        text = _code_lines(SETUP_ACTION.read_text())
        for cmd in ("apt-get update", "apt-get install"):
            line = next((ln for ln in text.splitlines() if cmd in ln), None)
            self.assertIsNotNone(line, f"{cmd} missing from the setup action")
            self.assertIn("timeout", line, f"{cmd} is not timeboxed: {line.strip()}")
        self.assertIn(">> \"$GITHUB_ENV\"", text,
                      "the static-build fallback must be exported for later steps")

    def test_media_probe_does_not_assume_ffprobe(self):
        """imageio-ffmpeg ships ffmpeg only, so the fallback build has no ffprobe."""
        text = (WORKFLOWS / "dry-run.yml").read_text()
        self.assertIn("command -v ffprobe", text,
                      "the media check calls ffprobe without guarding for its absence")
        self.assertIn("-hide_banner -i", text,
                      "no ffmpeg-banner fallback for probing streams")


class WorkflowMediaProbeActuallyRuns(unittest.TestCase):
    """Run the YAML's own shell function against real media, with no ffprobe.

    Asserting that the string `command -v ffprobe` appears proves nothing: the
    first version of this fallback grep'd for `Stream #0:0: Video`, and the real
    banner is `Stream #0:0[0x1](und): Video:` — it matched nothing, so every
    render would have been reported as having no video stream. Only executing it
    catches that.
    """

    @classmethod
    def setUpClass(cls):
        import imageio_ffmpeg  # noqa: WPS433

        cls.ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        cls.bash = shutil.which("bash")
        cls.tmp = tempfile.mkdtemp(prefix="probe-test-")
        # A PATH with the tools the function needs and deliberately no ffprobe.
        cls.bin_dir = os.path.join(cls.tmp, "bin")
        os.makedirs(cls.bin_dir)
        for tool in ("grep", "sed", "tr"):
            src = shutil.which(tool)
            if src:
                os.symlink(src, os.path.join(cls.bin_dir, tool))
        cls.media = os.path.join(cls.tmp, "tiny.mp4")
        subprocess.run(
            [cls.ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
             "-f", "lavfi", "-i", "testsrc=duration=0.2:size=64x64:rate=10",
             "-f", "lavfi", "-i", "sine=frequency=440:duration=0.2",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
             "-shortest", cls.media],
            check=True, capture_output=True,
        )

    @staticmethod
    def _probe_function_from_yaml() -> str:
        text = (WORKFLOWS / "dry-run.yml").read_text()
        start = text.index("probe_streams() {")
        end = text.index("\n          }\n", start) + len("\n          }\n")
        return textwrap.dedent(text[start:end])

    def test_probe_reports_video_and_audio(self):
        if not self.bash:
            self.skipTest("no bash available")
        script = os.path.join(self.tmp, "probe.sh")
        with open(script, "w", encoding="utf-8") as fh:
            fh.write(self._probe_function_from_yaml() + '\nprobe_streams "$1"\n')
        env = {"PATH": self.bin_dir, "FFMPEG_BINARY": self.ffmpeg}
        proc = subprocess.run([self.bash, script, self.media],
                              env=env, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, f"probe failed: {proc.stderr}")
        streams = proc.stdout.split()
        self.assertIn("video", streams, f"video stream not detected: {proc.stdout!r}")
        self.assertIn("audio", streams, f"audio stream not detected: {proc.stdout!r}")


if __name__ == "__main__":
    unittest.main()
