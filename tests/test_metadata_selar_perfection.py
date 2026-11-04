"""End-to-end verification of Metadata Perfection, Selar Integration & Stream Atoms."""
from __future__ import annotations

import re
import subprocess
import tempfile
import wave
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
from PIL import Image

from pipeline.assemble import ffmpeg_bin
from pipeline.captions import build_srt_from_aligned_words, write_srt_file
from pipeline.localize_metadata import build_metadata_localizations
from pipeline.metadata import (
    build_description,
    build_tags,
    chapters_from_scenes,
    fit_youtube_tags,
    is_faith_doc,
    serialized_youtube_tag_cost,
    smart_truncate_title,
    truncate_utf8_bytes,
)
from pipeline.pinned_comments import generate_pastoral_pinned_comment
from pipeline.prayer_visuals import render
from pipeline.script_doc import Scene, ScriptDoc, parse_script
from pipeline.shorts_bridge import (
    DEFAULT_PLAYLIST_FALLBACK,
    enrich_short_description_with_bridge,
    generate_short_bridge_comment,
)
from pipeline.social_pack import (
    PLAYLIST_LINKS,
    PODCAST_URL,
    SELAR_JOURNAL_URL,
    SELAR_STORE_URL,
    build_standardized_description_footer,
    sanitize_persona_integrity,
)
from pipeline.thumbnail_ctr import generate_ctr_pack
from pipeline.upload import update_live_video_metadata

REPO_ROOT = Path(__file__).resolve().parent.parent
QUEUE_DIR = REPO_ROOT / "content" / "queue"


def test_every_queued_faith_script_has_crisp_title_hook_and_both_selar_links():
    faith_docs = []
    for p in sorted(QUEUE_DIR.glob("*.md")):
        if p.stem.lower() == "readme":
            continue
        doc = parse_script(p)
        if not is_faith_doc(doc):
            continue
        faith_docs.append(doc)
        assert 35 <= len(doc.title) <= 70, f"{p.name} title out of optimal viewport: {doc.title!r} ({len(doc.title)}c)"
        hook = str(doc.meta.get("seo_hook", "")).strip()
        assert 60 <= len(hook) <= 155, f"{p.name} missing/oversized seo_hook: {hook!r}"
        assert "<" not in doc.title and ">" not in doc.title

        durs = [65.0] * len(doc.scenes)
        desc = build_description(doc, durs)
        assert len(desc.encode("utf-8")) <= 4900
        assert "<" not in desc and ">" not in desc

        # Both verified live Selar links MUST be present in every faith description
        assert SELAR_JOURNAL_URL in desc, f"{p.name} missing Prayer Journal Selar link"
        assert SELAR_STORE_URL in desc, f"{p.name} missing Show Love Selar link"

        # Line 2 above-the-fold placement check
        lines = desc.splitlines()
        assert lines[0] == hook
        assert SELAR_JOURNAL_URL in lines[1], f"{p.name} missing Line 2 watch-page fold Selar link"

        # Valid 00:00 chapters block
        assert "\nCHAPTERS\n00:00 " in desc
        # Zero dead PL_... fake playlist placeholders
        assert "PL_NIGHT_PRAYERS" not in desc
        assert "PL_BEDTIME_SLEEP" not in desc
        assert "PL_COMPLETE_PSALMS" not in desc
        # Zero personal handle/name leak
        assert "azani" not in desc.lower()

        # Backend tags obey exact quote-aware 500-char API limit
        tags = build_tags(doc)
        assert len(tags) >= 6
        assert serialized_youtube_tag_cost(tags) <= 500
        assert all("432" not in t for t in tags)

        # Pastoral comment includes both clickable Selar links on long-form
        comment = generate_pastoral_pinned_comment(doc)
        assert SELAR_JOURNAL_URL in comment
        assert SELAR_STORE_URL in comment
        assert "AMEN" in comment

    assert len(faith_docs) >= 22


def test_nonfaith_scripts_never_receive_faith_or_selar_links():
    from pipeline.script_doc import ScriptDoc

    nonfaith = ScriptDoc(
        path=Path("business-fixture.md"),
        meta={"id": "fixture-1", "title": "Business fixture", "niche": "business", "format": "longform"},
        scenes=[],
    )
    assert not is_faith_doc(nonfaith)
    desc = build_description(nonfaith, [])
    assert "selar.com" not in desc.lower()
    assert generate_pastoral_pinned_comment(nonfaith) == ""
    assert build_metadata_localizations(nonfaith.title, desc, "business") == {}


def test_smart_truncate_title_never_chops_mid_word_or_leaves_dangling_ampersand():
    raw_0010 = (
        "Psalm 121: He Who Keeps You Will Neither Slumber Nor Sleep — "
        "Night Prayer for Sleep, Peace & Divine Guard | The Secret Place"
    )
    truncated = smart_truncate_title(raw_0010, 95)
    assert len(truncated) <= 95
    assert not truncated.endswith(("&", "& ", "Di", "and"))
    assert "The Secret Place" not in truncated


def test_chapters_enforce_00_00_start_clean_labels_and_10s_minimum():
    doc = ScriptDoc(
        path=Path("/tmp/ch.md"),
        meta={"title": "Psalm 27 Night Prayer", "niche": "faith and prayer"},
        scenes=[
            Scene(1, "My Light and My Salvation (Verse 1)", "one"),
            Scene(2, "Short Bridge (Verse 2)", "two"),
            Scene(3, "Hidden in His Pavilion Upon a Rock (Verses 5–6)", "three"),
            Scene(4, "Seeing the Goodness of the Lord & Waiting in Courage (Verses 13–14)", "four"),
            Scene(5, "Tiny Tail (Verse 14)", "five"),
        ],
    )
    chaps = chapters_from_scenes(doc, [60.0, 5.0, 55.0, 62.0, 4.0])
    assert chaps[0][0] == "00:00"
    assert all("(Verse" not in name and "(Ver" not in name for _, name in chaps)


def test_quote_aware_tag_budget_never_exceeds_500_chars():
    many_multiword = [f"bedtime scripture prayer phrase number {i}" for i in range(30)]
    packed = fit_youtube_tags(many_multiword, max_chars=490)
    assert 1 <= len(packed) <= 18
    assert serialized_youtube_tag_cost(packed) <= 490


def test_localization_fixes_portuguese_bug_and_preserves_selar_links():
    locs_3 = build_metadata_localizations("Psalm 3:3-5 Night Prayer", "English body")
    locs_34 = build_metadata_localizations("Psalm 34 Night Prayer", "English body")
    assert "Salmo 3:" in locs_3["pt"]["title"]
    assert "Salmo 34" in locs_34["pt"]["title"]
    # Portuguese must be pure Portuguese (not Spanish "Escucha esta...")
    assert "Escucha esta" not in locs_34["pt"]["description"]
    assert "Ouça esta" in locs_34["pt"]["description"]
    assert SELAR_JOURNAL_URL in locs_34["es"]["description"]
    assert SELAR_STORE_URL in locs_34["pt"]["description"]

    # Emoji & multi-byte UTF-8 byte safety
    huge = "🕊️ oración de paz — " * 500
    assert len(truncate_utf8_bytes(huge, max_bytes=4900).encode("utf-8")) <= 4900


def test_social_pack_and_shorts_bridge_have_zero_dead_playlists_or_personal_handles():
    footer = build_standardized_description_footer(include_store_links=True)
    assert SELAR_JOURNAL_URL in footer
    assert SELAR_STORE_URL in footer
    assert "PL_NIGHT_PRAYERS" not in footer
    legacy_domain = "https://" + "john" + "azani.github.io/YouTube-automation/podcast.xml"
    assert "azani" not in sanitize_persona_integrity(legacy_domain).lower()
    assert "azani" not in PODCAST_URL.lower()
    assert all("PL_" not in url for url in PLAYLIST_LINKS.values())
    assert "PL_" not in DEFAULT_PLAYLIST_FALLBACK

    short_desc = enrich_short_description_with_bridge("Short scripture body.\n\n#Shorts #Psalm91", "short-psalm91")
    assert SELAR_JOURNAL_URL in short_desc
    assert SELAR_STORE_URL in short_desc
    assert short_desc.rstrip().endswith("#Shorts #Psalm91")

    short_comment = generate_short_bridge_comment("short-psalm91")
    assert "@TheSecretPlace" in short_comment
    assert "7RDX0fbIOtQ" in short_comment


def test_srt_caption_generator_utf8_no_bom_and_monotonic_non_overlapping(tmp_path: Path):
    narration = (
        "The Lord is my light and my salvation; whom shall I fear? "
        "Rest in deep peace tonight beneath His watchful care. Amen."
    )
    tokens = narration.split()
    words = [(re.sub(r"[^A-Za-z']", "", w).lower(), i * 0.42, i * 0.42 + 0.34) for i, w in enumerate(tokens)]
    srt_file = write_srt_file(tmp_path / "captions.en.srt", words, narration, duration=12.0)
    assert srt_file is not None and srt_file.is_file()

    raw_bytes = srt_file.read_bytes()
    assert not raw_bytes.startswith(b"\xef\xbb\xbf"), "SRT must be UTF-8 strictly without BOM"
    text = raw_bytes.decode("utf-8")
    assert "-->" in text and "," in text
    assert "<" not in text and ">" not in text.replace("-->", "")

    # Verify non-overlapping monotonic cue timestamps and <=2 lines per cue
    blocks = [b for b in text.strip().split("\n\n") if b.strip()]
    prev_end_ms = 0
    for idx, blk in enumerate(blocks, start=1):
        lines = blk.splitlines()
        assert int(lines[0]) == idx
        m = re.match(
            r"^(\d{2}):(\d{2}):(\d{2}),(\d{3}) --> (\d{2}):(\d{2}):(\d{2}),(\d{3})$",
            lines[1],
        )
        assert m, f"Invalid SRT timestamp line: {lines[1]}"
        g = [int(x) for x in m.groups()]
        start_ms = ((g[0] * 3600 + g[1] * 60 + g[2]) * 1000) + g[3]
        end_ms = ((g[4] * 3600 + g[5] * 60 + g[6]) * 1000) + g[7]
        assert start_ms >= prev_end_ms
        assert end_ms > start_ms
        assert end_ms <= 12_000
        assert 1 <= len(lines[2:]) <= 2
        prev_end_ms = end_ms


def test_update_live_video_metadata_preserves_existing_snippet_fields():
    mock_yt = MagicMock()
    mock_yt.videos().list().execute.return_value = {
        "items": [
            {
                "id": "6M6oV8MxD9s",
                "snippet": {
                    "title": "Old Truncated & Di",
                    "description": "Old desc",
                    "categoryId": "22",
                    "tags": ["psalm 121", "night prayer"],
                    "defaultLanguage": "en",
                    "defaultAudioLanguage": "en",
                },
                "localizations": {"es": {"title": "Salmo 121", "description": "Desc"}},
            }
        ]
    }
    mock_yt.videos().update().execute.return_value = {"id": "6M6oV8MxD9s"}

    update_live_video_metadata(
        "6M6oV8MxD9s",
        new_title="Psalm 121 Night Prayer for Sleep & Peace | He Never Slumbers",
        new_description=f"Updated description with {SELAR_JOURNAL_URL}",
        youtube=mock_yt,
    )
    call_kwargs = mock_yt.videos().update.call_args.kwargs
    sent_snippet = call_kwargs["body"]["snippet"]
    assert sent_snippet["categoryId"] == "22"
    assert sent_snippet["tags"] == ["psalm 121", "night prayer"]
    assert sent_snippet["defaultAudioLanguage"] == "en"
    assert "He Never Slumbers" in sent_snippet["title"]


def test_mp4_stream_atoms_bt709_48khz_eng_and_thumbnail_icc(tmp_path: Path):
    img_path = tmp_path / "plate.png"
    Image.new("RGB", (640, 360), (14, 30, 68)).save(img_path)

    sr = 44100
    t = np.linspace(0, 4.0, int(sr * 4.0), endpoint=False)
    pcm = (np.sin(2 * np.pi * 220 * t) * 4000).astype("<i2")
    nar_path = tmp_path / "nar.wav"
    with wave.open(str(nar_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())

    mp4 = render(
        nar_path,
        [(img_path, 2.0), (img_path, 2.0)],
        [("Peace", 0.3, 1.1), ("tonight.", 2.1, 3.2)],
        4.0,
        tmp_path / "out.mp4",
        timing_source="measured",
        width=320,
        height=180,
        fps=8,
    )
    probe = subprocess.run([ffmpeg_bin(), "-hide_banner", "-i", str(mp4)], capture_output=True, text=True)
    stderr = probe.stderr
    assert "(eng): Video: h264 (High)" in stderr
    assert "bt709" in stderr
    assert "(eng): Audio: aac (LC)" in stderr
    assert "48000 Hz, stereo" in stderr

    raw = mp4.read_bytes()
    assert 0 < raw.find(b"moov") < raw.find(b"mdat"), "+faststart must place moov before mdat"

    reports = generate_ctr_pack(tmp_path / "thumbs", hero_override="FEAR NO EVIL", doc_key="0011")
    assert reports[0].path.stat().st_size < 2_000_000
    with Image.open(reports[0].path) as th:
        assert th.info.get("icc_profile"), "Thumbnail JPEG must embed sRGB ICC profile"
