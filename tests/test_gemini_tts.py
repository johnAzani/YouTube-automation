import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from pipeline import gemini_tts


def test_gemini_voice_profile_mapping():
    assert gemini_tts.GEMINI_VOICES["Charon"] == "Charon"
    assert "Fenrir" in gemini_tts.GEMINI_VOICES
    assert "Aoede" in gemini_tts.GEMINI_VOICES
    assert gemini_tts.FALLBACK_EDGE_VOICE == "en-US-DavisNeural"


def test_gemini_tts_retry_on_429(tmp_path: Path):
    with patch("pipeline.gemini_tts.get_gemini_api_key", return_value="fake-test-key"), \
         patch("google.genai.Client") as mock_client_cls, \
         patch("time.sleep") as mock_sleep:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        
        # First call raises ResourceExhausted (429), second call succeeds
        class FakeResponse:
            class FakeCandidate:
                class FakeContent:
                    class FakePart:
                        inline_data = MagicMock(data=b"RIFF_FAKE_AUDIO_DATA", mime_type="audio/wav")
                        text = None
                    parts = [FakePart()]
                content = FakeContent()
            candidates = [FakeCandidate()]

        mock_client.models.generate_content.side_effect = [
            RuntimeError("429 ResourceExhausted: rate limit reached"),
            FakeResponse(),
        ]

        with patch("pipeline.assemble.ffmpeg_bin", return_value="ffmpeg"), patch("subprocess.run") as mock_sp:
            mock_sp.return_value = MagicMock(returncode=0)
            target = tmp_path / "test_out.mp3"
            # create mock destination after ffmpeg
            target.write_bytes(b"dummy mp3 data")
            res = gemini_tts.synthesize_gemini_audio(
                text="The Lord is my refuge and my fortress.",
                out_path=target,
                voice="Charon",
            )
            assert res == target

        assert mock_client.models.generate_content.call_count == 2
        assert mock_sleep.call_count == 1


# --- The spoken payload must be the script, byte for byte, and NOTHING else --
# A TTS model speaks its text payload verbatim. Two owner-reported failures:
#   * Psalm 27 (7ll7w1hYf7o): instruction glued into `contents` ("Text to
#     read:") was narrated as stage direction.
#   * Psalm 5 (oS7f32WDj_Y): the follow-up fix put a fenced read-aloud
#     contract INTO every payload, and the video opened by literally saying
#     "Read the text between the markers aloud, in a calm...".
# So style guidance now travels ONLY via GenerateContentConfig's
# system_instruction channel; every text payload equals the script exactly.

SCRIPT = "Before you close your eyes tonight, breathe in slowly."


def _fake_audio_response():
    class FakeResponse:
        class FakeCandidate:
            class FakeContent:
                class FakePart:
                    inline_data = MagicMock(data=b"RIFF_FAKE_AUDIO_DATA", mime_type="audio/wav")
                    text = None
                parts = [FakePart()]
            content = FakeContent()
        candidates = [FakeCandidate()]
    return FakeResponse()


def test_generate_content_payload_is_bare_script_and_instruction_is_system():
    instruction = gemini_tts.read_aloud_instruction()
    client = MagicMock()
    client.interactions = None  # force the generate_content transport
    client.models.generate_content.return_value = _fake_audio_response()
    raw = Path("/tmp/_tts_contract_test.raw")
    gemini_tts._synthesize_single_chunk(client, SCRIPT, "Charon", instruction,
                                        gemini_tts.DEFAULT_MODEL, raw)
    call = client.models.generate_content.call_args
    assert call.kwargs["contents"] == SCRIPT, (
        "the spoken payload must be the script itself — any instruction, "
        "fence, or marker inside it WILL be read aloud (Psalm 5, oS7f32WDj_Y)"
    )
    config = call.kwargs["config"]
    assert config.system_instruction == instruction
    assert "markers" not in config.system_instruction


def test_no_transport_payload_carries_instruction_or_markers():
    source = Path(gemini_tts.__file__).read_text(encoding="utf-8")
    assert "SCRIPT_START" not in source and "SCRIPT_END" not in source
    # the old contract's wording may survive only inside comments/docstrings
    # that explain the bug; it must never appear in a payload expression
    for line in source.splitlines():
        if "Read the text between the markers" in line:
            assert line.lstrip().startswith(("#", "*", "\"")), line
    # every interactions payload is the bare chunk text
    assert source.count('"text": text}') >= 3
    assert 'f"{system_instruction}' not in source
