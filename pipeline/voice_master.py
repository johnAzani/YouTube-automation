"""Voice mastering and the narration-over-music mix.

Measured on 13 November 2026, before this module existed:

* Narration as it left speech synthesis: about -19.7 LUFS, true peak -7.4 dBFS.
* Finished video (voice + music bed): about -19.1 LUFS, true peak -5.6 dBFS.
* Music bed at the 0.58 mix level: about -29.9 LUFS, so only ~10 LU under the voice.

YouTube plays everything against a -14 LUFS reference and turns loud videos down,
but it never turns a quiet one up. A video at -19 LUFS therefore plays about 5 dB
quieter than whatever the listener heard before it, and that is the whole
"audibility" complaint on a phone speaker: nothing was wrong with the take, it was
simply delivered quiet, with more than 5 dB of unused headroom and a music bed
close enough to mask consonants.

What this does, all inside the final encode (the narration file on disk, its
checksum, its cached chunks and its word alignment are never touched, so no
speech is re-synthesised and no free-tier TTS quota is spent):

1. Tone: remove rumble below the voice, ease the boxy low-mids that sit on top of
   the music pads, lift the consonant band a little so words stay clear on small
   speakers.
2. Dynamics: gentle 2.5:1 compression so quiet phrase endings stay audible without
   the loud words jumping out.
3. Loudness: measured first, then one fixed gain to the target (two-pass,
   "linear" loudnorm). A fixed gain cannot pump or breathe the way a one-pass
   normaliser does on speech with pauses.
4. Mix: the music ducks a few dB while the voice is speaking and comes back in
   the pauses; a final limiter holds the true peak under -1 dBFS.

None of this changes timing. Filters here are sample-for-sample, so captions and
kinetic text stay aligned to the same word boundaries.

Fail-open by design: if the loudness measurement cannot be taken, the mix falls
back to the exact filter graph used before this module, and says so. A mastering
problem must never cost a release.
"""
from __future__ import annotations

import json
import math
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

#: Integrated loudness of the mastered voice. The finished mix lands a fraction
#: of a LU above this once the music is added, i.e. just under YouTube's -14
#: reference: as loud as the platform will play it, with nothing turned down.
VOICE_TARGET_LUFS = -15.0
#: Ceiling for the mastered voice (dBTP). Leaves room for AAC encoding overshoot.
VOICE_TRUE_PEAK_DB = -1.5
#: Loudness range handed to the normaliser. Speech here measures 2-5 LU.
VOICE_LOUDNESS_RANGE = 9.0
#: Final mix ceiling as a linear sample value (0.891 = -1.0 dBFS).
MIX_LIMIT = 0.891

#: Tone and dynamics, applied before loudness is measured so the measurement
#: describes what will actually be normalised.
TONE_CHAIN = (
    "highpass=f=75,"
    "equalizer=f=220:t=q:w=1.0:g=-1.0,"
    "equalizer=f=3400:t=q:w=1.2:g=1.5,"
    "acompressor=threshold=-22dB:ratio=2.5:attack=12:release=180:knee=6"
)

#: Music ducking under speech. The voice is the key; with the voice near
#: -15 LUFS this takes roughly 2.5 dB off the bed while words are spoken and
#: releases over 0.7 s into pauses, so the bed swells in the silences. Measured:
#: bed -29.9 LUFS alone, about -32.5 LUFS under speech, so the voice sits 15 LU
#: over the music in pauses and about 17 LU over it while speaking (it was 10).
DUCK = "sidechaincompress=threshold=0.0316:ratio=1.2:attack=25:release=700:knee=6"

#: Bump when the audible recipe changes, so a receipt can say which one it used.
MASTER_RECIPE = "voice-master-v1"

_LOUDNORM_JSON = re.compile(r"\{[^{}]*\"input_i\"[^{}]*\}", re.S)


@dataclass(frozen=True)
class Loudness:
    """What the normaliser measured for the tone-shaped voice."""

    input_i: float
    input_tp: float
    input_lra: float
    input_thresh: float
    target_offset: float

    @property
    def usable(self) -> bool:
        values = (self.input_i, self.input_tp, self.input_lra, self.input_thresh,
                  self.target_offset)
        # Digital silence measures -inf / -70: there is nothing to normalise and
        # applying 55 dB of gain to noise would be worse than doing nothing.
        return all(math.isfinite(v) for v in values) and self.input_i > -50.0


def _ffmpeg() -> str:
    from .assemble import ffmpeg_bin

    return ffmpeg_bin()


def _loudnorm_target() -> str:
    return (f"loudnorm=I={VOICE_TARGET_LUFS}:TP={VOICE_TRUE_PEAK_DB}"
            f":LRA={VOICE_LOUDNESS_RANGE}")


def parse_loudnorm_report(stderr: str) -> Loudness | None:
    """Read the JSON block loudnorm prints at the end of an analysis pass."""
    matches = _LOUDNORM_JSON.findall(stderr or "")
    if not matches:
        return None
    try:
        data = json.loads(matches[-1])
        measured = Loudness(
            input_i=float(data["input_i"]),
            input_tp=float(data["input_tp"]),
            input_lra=float(data["input_lra"]),
            input_thresh=float(data["input_thresh"]),
            target_offset=float(data["target_offset"]),
        )
    except (KeyError, TypeError, ValueError):
        return None
    return measured if measured.usable else None


def measure_voice(narration: Path, *, timeout: float = 300.0) -> Loudness | None:
    """Analysis pass: loudness of the narration after tone and dynamics.

    Audio only, no encode: a seven-minute prayer takes a few seconds. Returns
    None on any failure; the caller then keeps the legacy mix.
    """
    narration = Path(narration)
    if not narration.is_file():
        return None
    cmd = [
        _ffmpeg(), "-hide_banner", "-nostats", "-i", str(narration), "-vn",
        "-af", f"{TONE_CHAIN},{_loudnorm_target()}:print_format=json",
        "-f", "null", "-",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return parse_loudnorm_report(proc.stderr)


def voice_chain(measured: Loudness) -> str:
    """Tone, dynamics and a fixed gain to the loudness target (48 kHz out)."""
    return (
        f"{TONE_CHAIN},{_loudnorm_target()}"
        f":measured_I={measured.input_i:.2f}:measured_TP={measured.input_tp:.2f}"
        f":measured_LRA={measured.input_lra:.2f}:measured_thresh={measured.input_thresh:.2f}"
        f":offset={measured.target_offset:.2f}:linear=true,"
        # loudnorm works at 192 kHz internally and hands that rate on.
        "aresample=48000"
    )


def legacy_mix_filter(music_stage: str, *, voice_input: str = "1:a",
                      music_input: str = "2:a", out_label: str = "a") -> str:
    """The mix exactly as it was before mastering: the fail-open fallback."""
    return (
        f"[{music_input}]{music_stage}[m];"
        f"[{voice_input}]aformat=channel_layouts=stereo,volume=1.0[v];"
        f"[m][v]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.95[{out_label}]"
    )


def mastered_mix_filter(measured: Loudness, music_stage: str, *,
                        voice_input: str = "1:a", music_input: str = "2:a",
                        out_label: str = "a") -> str:
    """Mastered voice over a ducked music bed, limited to -1 dBFS."""
    return (
        f"[{music_input}]{music_stage},aresample=48000,"
        f"aformat=channel_layouts=stereo[m];"
        f"[{voice_input}]{voice_chain(measured)},aformat=channel_layouts=stereo,"
        f"asplit=2[v][k];"
        # The key is padded with silence so the bed is never cut short when the
        # music outlasts the voice (a Short's end card plays music alone).
        f"[k]apad[key];"
        f"[m][key]{DUCK}[md];"
        f"[md][v]amix=inputs=2:duration=longest:normalize=0,"
        f"alimiter=limit={MIX_LIMIT}:level=disabled[{out_label}]"
    )


def mix_filter(narration: Path, music_stage: str, *, voice_input: str = "1:a",
               music_input: str = "2:a", out_label: str = "a",
               log=print) -> str:
    """The `-filter_complex` for narration over music, mastered when possible.

    `music_stage` is the filter chain applied to the music input before the mix
    (its level and fades), for example ``"volume=0.58"``.
    """
    measured = measure_voice(narration)
    if measured is None:
        if log:
            log("[voice-master] loudness could not be measured; "
                "keeping the unmastered mix for this render")
        return legacy_mix_filter(music_stage, voice_input=voice_input,
                                 music_input=music_input, out_label=out_label)
    if log:
        gain = VOICE_TARGET_LUFS - measured.input_i
        log(f"[voice-master] {MASTER_RECIPE}: narration {measured.input_i:.1f} LUFS, "
            f"peak {measured.input_tp:.1f} dBTP -> {VOICE_TARGET_LUFS:.0f} LUFS "
            f"({gain:+.1f} dB), music ducked under speech")
    return mastered_mix_filter(measured, music_stage, voice_input=voice_input,
                               music_input=music_input, out_label=out_label)
