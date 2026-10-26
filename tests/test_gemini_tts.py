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
