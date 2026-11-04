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


# --- The read-aloud contract must reach the model on EVERY transport ---------
# 4 Nov 2026: the Psalm 27 video (7ll7w1hYf7o) opened by speaking the delivery
# instructions aloud. Root cause: the `interactions` transport — the primary
# path — received the bare script and never saw the "read, don't comment"
# instruction, which only existed on the generate_content fallback as an
# unfenced "Text to read:" prefix the model could narrate as stage direction.

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


def test_every_transport_payload_carries_the_contract_and_fenced_script():
    instruction = gemini_tts.read_aloud_instruction()
    client = MagicMock()
    client.interactions = None  # force the generate_content transport
    client.models.generate_content.return_value = _fake_audio_response()
    raw = Path("/tmp/_tts_contract_test.raw")
    gemini_tts._synthesize_single_chunk(client, SCRIPT, "Charon", instruction,
                                        gemini_tts.DEFAULT_MODEL, raw)
    contents = client.models.generate_content.call_args.kwargs["contents"]
    assert "Read the text between the markers aloud" in contents
    assert "must never be spoken" in contents
    assert gemini_tts.SCRIPT_START in contents
    assert gemini_tts.SCRIPT_END in contents
    assert SCRIPT in contents
    assert "Text to read:" not in contents


def test_interactions_payload_is_fenced_too():
    source = Path(gemini_tts.__file__).read_text(encoding="utf-8")
    assert source.count("SCRIPT_START") >= 4, (
        "every interactions.create payload (initial, burst-retry, transient-retry) "
        "plus the generate_content payload must fence the script — a payload that "
        "sends the bare script reproduces the Psalm 27 narration-of-instructions bug"
    )
    assert '"text": text}' not in source.replace(" ", ""), (
        "no TTS payload may send the bare script without the read-aloud contract"
    )
