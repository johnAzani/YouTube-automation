import hashlib
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
# A TTS model speaks its text payload verbatim. Three owner-reported failures:
#   * Psalm 27 (7ll7w1hYf7o): instruction glued into `contents` ("Text to
#     read:") was narrated as stage direction.
#   * Psalm 5 (oS7f32WDj_Y): the follow-up fix put a fenced read-aloud
#     contract INTO every payload, and the video opened by literally saying
#     "Read the text between the markers aloud, in a calm...".
#   * Psalm 5 replacement (R8mVvedhYVw): PR #253 moved the instruction to
#     GenerateContentConfig.system_instruction — a channel the official
#     Gemini 3.8 TTS migration guide does not document; style belongs in
#     speech_metadata.style. The leak persisted.
# So v4: the ONLY text the model receives is the script chunk; delivery
# style rides in speech_metadata.style (generate_content Part) or a
# speech_metadata annotation (interactions). system_instruction is never
# passed to a TTS model. Cache identity is versioned by DELIVERY_RECIPE.

SCRIPT = "Before you close your eyes tonight, breathe in slowly."
STYLE = "calm, reverent, peaceful devotional tone"


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


def test_generate_content_payload_is_the_script_part_with_style_metadata_only():
    client = MagicMock()
    client.interactions = None  # force the generate_content transport
    client.models.generate_content.return_value = _fake_audio_response()
    raw = Path("/tmp/_tts_contract_test.raw")
    gemini_tts._synthesize_single_chunk(client, SCRIPT, "Charon", STYLE,
                                        gemini_tts.DEFAULT_MODEL, raw)
    call = client.models.generate_content.call_args
    contents = call.kwargs["contents"]
    dumped = contents.model_dump(exclude_none=True)
    assert dumped == {"text": SCRIPT, "speech_metadata": {"style": STYLE}}, (
        "the spoken payload must be the script part with style metadata — "
        "any instruction text in any channel WILL be read aloud "
        "(Psalm 27, Psalm 5 oS7f32WDj_Y, Psalm 5 R8mVvedhYVw)"
    )
    config = call.kwargs["config"]
    assert config.system_instruction is None


def test_interactions_payload_text_is_byte_for_byte_the_script_with_style_annotation():
    client = MagicMock()
    interaction = MagicMock()
    interaction.output_audio.data = b"RIFF"
    interaction.output_audio.mime_type = "audio/wav"
    client.interactions.create.return_value = interaction
    raw = Path("/tmp/_tts_contract_test.raw")
    gemini_tts._synthesize_single_chunk(client, SCRIPT, "Charon", STYLE,
                                        gemini_tts.DEFAULT_MODEL, raw)
    call = client.interactions.create.call_args
    block = call.kwargs["input"][0]["content"][0]
    assert block["text"].encode("utf-8") == SCRIPT.encode("utf-8")
    assert block["type"] == "text"
    (annotation,) = block["annotations"]
    assert annotation == {
        "type": "speech_metadata",
        "start_index": 0,
        "end_index": len(SCRIPT.encode("utf-8")),
        "style": STYLE,
    }
    # No other text channel anywhere in the request.
    assert call.kwargs["response_format"] == {"type": "audio"}
    assert call.kwargs["generation_config"] == {"speech_config": [{"voice": "Charon"}]}


def test_no_transport_payload_carries_instruction_or_markers():
    source = Path(gemini_tts.__file__).read_text(encoding="utf-8")
    assert "SCRIPT_START" not in source and "SCRIPT_END" not in source
    # The old contract's wording may survive only inside comments/docstrings
    # that explain the bug; it must never appear in a payload expression.
    for line in source.splitlines():
        if "Read the text between the markers" in line:
            assert line.lstrip().startswith(("#", "*", '"')), line
    # generate_content must never pass a system instruction to a TTS model.
    assert "system_instruction=" not in source
    # The interactions text block is built by exactly one helper.
    assert "build_interactions_content(text, prompt_style)" in source


def test_style_text_is_short_delivery_adjectives_not_imperatives():
    style = gemini_tts.style_text()
    assert style == STYLE
    lowered = style.lower()
    assert "read" not in lowered and "speak" not in lowered and "only" not in lowered
    assert ":" not in style
    assert len(style.split()) < 12


def test_chunk_cache_key_versions_the_delivery_recipe():
    key = gemini_tts._chunk_cache_key("Charon", gemini_tts.DEFAULT_MODEL, SCRIPT)
    pre_v4_key = hashlib.sha256(
        f"Charon:{gemini_tts.DEFAULT_MODEL}:{SCRIPT}".encode("utf-8")
    ).hexdigest()
    assert key != pre_v4_key
    assert gemini_tts.DELIVERY_RECIPE == "tts-v4-speech-metadata-style"


def test_chunk_cache_key_changes_when_recipe_bumps():
    base = gemini_tts._chunk_cache_key("Charon", gemini_tts.DEFAULT_MODEL, SCRIPT)
    with patch.object(gemini_tts, "DELIVERY_RECIPE", "tts-v999-future"):
        changed = gemini_tts._chunk_cache_key(
            "Charon", gemini_tts.DEFAULT_MODEL, SCRIPT)
    assert base != changed


def test_produce_workflow_chunk_cache_keys_are_recipe_versioned():
    workflow = (
        Path(__file__).resolve().parent.parent
        / ".github" / "workflows" / "produce.yml"
    ).read_text()
    assert "key: chunks-tts-v5-${{ matrix.channel }}-${{ github.run_id }}" in workflow
    assert "key: chunks-${{ github.run_id }}" not in workflow
