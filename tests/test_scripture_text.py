"""The words of the passage are bundled, shown to the writer, and checked.

Before 14 November 2026 the writer quoted from memory. One Short in sixteen came
back garbled and was caught by a person, not by code.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from pipeline import evergreen_shorts as ev
from pipeline import gemini_brain as gb
from pipeline import scripture_text as st
from pipeline import short_release as sr
from pipeline import short_script as ss

REPO = Path(__file__).resolve().parent.parent
KJV_5522 = ("Cast thy burden upon the LORD, and he shall sustain thee: "
            "he shall never suffer the righteous to be moved.")


def test_the_whole_bible_is_bundled():
    bible = st._bible()
    assert len(bible) == 66
    assert sum(len(verses) for book in bible.values() for verses in book.values()) == 31102
    assert st.passage("John 11:35")[0].text == "Jesus wept."
    assert st.passage("Psalm 55:22")[0].text == KJV_5522


def test_references_are_read_as_ranges_lists_and_whole_chapters():
    assert [v.number for v in st.passage("Psalm 121:1-2, 5")] == [1, 2, 5]
    assert [v.number for v in st.passage("Psalm 91:4–7")] == [4, 5, 6, 7]
    assert len(st.passage("Psalm 23")) == 6
    assert st.passage("Psalms 23:1")[0].label == "Psalm 23:1"
    assert st.passage("1 John 4:4")[0].book == "1 john"
    assert st.passage("A prayer on 2 Corinthians 5:17 | The Morning Altar")[0].number == 17


@pytest.mark.parametrize("reference", ["Psalm 151:1", "John 3:99", "Hezekiah 4:2", ""])
def test_a_reference_the_text_does_not_have_is_refused(reference):
    assert not st.exists(reference)
    assert "not found" in st.quote_problems("Any narration at all.", reference)[0]


def test_every_passage_a_channel_can_be_asked_to_write_exists():
    """A roadmap row or evergreen passage that is not in the Bible can never be authored."""
    from scripts.continuous_research import ROADMAPS

    references = [ref for refs in ev.EVERGREEN.values() for ref in refs]
    references += [row["scripture"] for rows in ROADMAPS.values() for row in rows]
    missing = [ref for ref in references if not st.exists(ref)]
    assert not missing, f"not in the bundled text: {missing[:10]}"


def test_the_garbled_short_that_started_this_is_refused():
    garbled = ("If the weight will not lift tonight, hear this. Cast your cares on the Lord. "
               "He will never permit. He will sustain the righteous to be moved. Father, hold them.")
    problems = st.quote_problems(garbled, "Psalm 55:22")
    assert problems and "does not quote any whole verse" in problems[0]
    assert KJV_5522 in problems[0], "the refusal carries the words to copy"


def test_a_verse_quoted_as_written_passes():
    narration = f"If the weight will not lift tonight, hear this. {KJV_5522} Father, hold them."
    check = st.check_quote(narration, "Psalm 55:22")
    assert check.ok and check.quoted == ["Psalm 55:22"]


def test_punctuation_capitals_and_spelling_are_not_misquotation():
    assert not st.quote_problems("show me thy ways o lord teach me thy paths", "Psalm 25:4")
    assert not st.quote_problems(
        "Who is this King of glory? The LORD of hosts, he is the King of glory.", "Psalm 24:10"), \
        "Selah is a marker, not a word of the sentence"
    assert "Show me thy ways" in st.prompt_block("Psalm 25:4-5")
    assert "Selah" not in st.prompt_block("Psalm 24:10")


def test_the_joining_word_a_verse_opens_with_may_be_left_off():
    spoken = ("God so loved the world, that he gave his only begotten Son, that whosoever "
              "believeth in him should not perish, but have everlasting life.")
    assert not st.quote_problems(spoken, "John 3:16")


def test_one_changed_word_is_a_misquotation():
    changed = KJV_5522.replace("sustain", "support")
    problems = st.quote_problems(f"Hear this. {changed} Amen.", "Psalm 55:22")
    assert problems


def test_a_verse_right_beside_a_faithful_one_with_words_added_is_caught():
    narration = ("He giveth power to the faint; and to them that have no might he increaseth "
                 "strength. But they that wait upon the LORD shall renew their strength; they "
                 "shall mount up with wings as eagles; they shall run, and not be weary; and "
                 "they shall walk step by step, and not faint.")
    check = st.check_quote(narration, "Isaiah 40:29-31")
    assert check.quoted == ["Isaiah 40:29"]
    assert any("Isaiah 40:31 is quoted in part and then with words changed" in p
               for p in check.problems)
    stops_cleanly = narration.split(" and they shall walk")[0]
    clean = st.check_quote(stops_cleanly, "Isaiah 40:29-31")
    assert clean.ok and clean.in_part == ["Isaiah 40:31"], "stopping at the punctuation is faithful"


def test_prayer_in_the_writers_own_words_after_the_verse_is_not_a_misquotation():
    narration = (f"{KJV_5522} Father, I give You the burden I have carried all day. Sustain "
                 "me tonight, and let nothing move the ground You have set under my feet.")
    assert not st.quote_problems(narration, "Psalm 55:22")


def test_a_long_verse_may_be_quoted_by_whole_clauses():
    assert len(st._words(st.passage("Joshua 24:15")[0].text)) > st.LONG_VERSE_WORDS
    check = st.check_quote("Hear it. As for me and my house, we will serve the LORD. Amen.",
                           "Joshua 24:15")
    assert check.ok and check.in_part == ["Joshua 24:15"]
    assert st.quote_problems("As for me and my home, we will serve the LORD.", "Joshua 24:15")
    assert "may be quoted in part" in st.prompt_block("Joshua 24:15")
    assert "may be quoted in part" not in st.prompt_block("Psalm 23:1")


def test_the_writer_is_shown_the_words_not_only_the_reference():
    prompt = ss.build_prompt("Psalm 55:22", key="short-psalm55v22", channel_id="secret-place",
                             avoid_openings=[])
    assert KJV_5522 in prompt
    assert "exactly as written" in prompt
    whole_psalm = st.prompt_block("Psalm 119")
    assert len(whole_psalm.split()) < st.PROMPT_MAX_WORDS + 220, "a whole psalm is not pasted in"


# --------------------------------------------------------------------------- #
# The brain refuses a misquoting spec and asks again
# --------------------------------------------------------------------------- #
def _spec(key: str, scripture: str, channel: str, verse_line: str) -> dict:
    lines = [
        "When the weight you carried all day will not lift, this word is for you tonight.",
        verse_line,
        "Father, I bring You the thing I have carried all day and could not put down.",
        "I thank You that nothing in it is hidden from You, and nothing in it is too heavy.",
        "Teach my heart to rest in what You have said and not in what I can see.",
        "Keep me and the ones I love until morning, and wake us in Your peace. Amen.",
    ]
    captions, phrases, scenes, start = [], [], [], 0
    for index, line in enumerate(lines):
        stop = start + 6
        captions.append([start, stop, line])
        phrases.append([start, stop, [" ".join(line.split()[:3]).upper()], ["WORD"], scripture.upper()])
        scenes.append({"a": " ".join(line.split()[:4]), "img": f"{key}-scene-{index + 1:02d}.jpg",
                       "kicker": "A WORD FOR TONIGHT", "sub": "REST IN WHAT HE SAID",
                       "cam": "push_in", "focus": [0.5, 0.5]})
        start = stop + 1
    return {
        "key": key, "channel": channel, "scripture": scripture,
        "title": ["A WORD", "FOR TONIGHT"],
        "poster": ["REST TONIGHT", "IN HIS WORD", "A PRAYER FOR", "A QUIET MIND"],
        "end": ["SUBSCRIBE", "A prayer every night"],
        "stock_queries": [f"calm night sky {i}" for i in range(len(lines))],
        "scenes": scenes, "captions": captions, "kinetic_phrases": phrases, "beats": [],
    }


GARBLED_LINE = "He will never permit. He will sustain the righteous to be moved, the psalm says."


def _brain(monkeypatch, answers: list[dict]):
    monkeypatch.setenv("CHANNEL_ID", "secret-place")
    monkeypatch.setattr(gb.GeminiBrain, "is_api_available", lambda self: True)
    monkeypatch.setattr(gb, "text_model_candidates", lambda primary=None: ["model-a", "model-b"])
    brain = gb.GeminiBrain(api_key="fake", channel_id="secret-place")
    prompts: list[str] = []

    def generate(model=None, contents=None):
        prompts.append(contents)
        return SimpleNamespace(text=json.dumps(answers[min(len(prompts), len(answers)) - 1]))

    brain._client = SimpleNamespace(models=SimpleNamespace(generate_content=generate))
    brain.prompts = prompts
    return brain


def test_the_brain_rejects_a_misquoting_spec_and_asks_again_with_the_words(monkeypatch):
    key = "short-psalm55v22"
    bad = _spec(key, "Psalm 55:22", "secret-place", GARBLED_LINE)
    good = _spec(key, "Psalm 55:22", "secret-place", KJV_5522)
    brain = _brain(monkeypatch, [bad, good])
    spec = brain.author_short_spec(None, key=key, scripture="Psalm 55:22")
    assert KJV_5522 in spec.narration_text
    assert len(brain.prompts) == 2
    assert "Previous output was rejected" in brain.prompts[1]
    assert "does not quote any whole verse" in brain.prompts[1]


def test_the_brain_never_returns_a_spec_that_misquotes(monkeypatch):
    key = "short-psalm55v22"
    brain = _brain(monkeypatch, [_spec(key, "Psalm 55:22", "secret-place", GARBLED_LINE)])
    with pytest.raises(gb.BrainAuthoringError):
        brain.author_short_spec(None, key=key, scripture="Psalm 55:22")
    assert len(brain.prompts) == 4, "two attempts on each of two models, then it stops"


# --------------------------------------------------------------------------- #
# Waiting Shorts written before the check are rewritten, and verified ones go first
# --------------------------------------------------------------------------- #
@pytest.fixture
def queue(tmp_path, monkeypatch):
    queue_dir, specs, published = tmp_path / "queue", tmp_path / "specs", tmp_path / "published"
    for directory in (queue_dir, specs, published):
        directory.mkdir()
    monkeypatch.setattr(gb, "SHORTS_QUEUE_DIR", queue_dir)
    monkeypatch.setattr(sr, "SHORTS_QUEUE_DIR", queue_dir)
    monkeypatch.setattr(ss, "SPEC_DIR", specs)
    monkeypatch.setattr(gb, "PUBLISHED_DIR", published)
    monkeypatch.setattr(sr, "_renderer_script_keys", lambda: set(ss.authored_keys()))
    monkeypatch.setattr(sr, "resolve_edition", lambda key, channel_id=None: SimpleNamespace(slug=key))
    monkeypatch.setenv("CHANNEL_ID", "secret-place")
    monkeypatch.setattr(gb.GeminiBrain, "is_api_available", lambda self: True)

    def add(name: str, key: str, scripture: str, line: str, **manifest):
        spec = ss.require_valid(ss.validate_spec(_spec(key, scripture, "secret-place", line),
                                                 key=key, channel_id="secret-place"))
        ss.save_spec(spec)
        data = {"short": key, "channel": "secret-place", "scripture": scripture,
                "status": "approved", "standalone": True, **manifest}
        (queue_dir / name).write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        return queue_dir / name

    return SimpleNamespace(dir=queue_dir, specs=specs, published=published, add=add)


def test_a_verified_short_goes_out_ahead_of_an_unverified_one(queue):
    queue.add("0000-short-psalm55v22.yml", "short-psalm55v22", "Psalm 55:22", GARBLED_LINE)
    verified = queue.add("0000-short-psalm56v3.yml", "short-psalm56v3", "Psalm 56:3",
                         "What time I am afraid, I will trust in thee.")
    picked = sr.select_next_queued_short(queue_dir=queue.dir, published_dir=queue.published,
                                         channel_id="secret-place")
    assert picked == (verified, "short-psalm56v3")
    assert sr.scripture_status("short-psalm55v22") == "unverified"
    assert sr.scripture_status("short-psalm56v3") == "verified"
    assert sr.scripture_status("short-handwritten") == "unknown"


def test_a_channel_with_only_unverified_shorts_still_publishes_and_says_so(queue, capsys):
    legacy = queue.add("0000-short-psalm55v22.yml", "short-psalm55v22", "Psalm 55:22", GARBLED_LINE)
    picked = sr.select_next_queued_short(queue_dir=queue.dir, published_dir=queue.published,
                                         channel_id="secret-place")
    assert picked == (legacy, "short-psalm55v22")
    assert "not yet scripture-verified" in capsys.readouterr().out


def test_each_pass_rewrites_a_bounded_number_of_misquoting_shorts(queue, monkeypatch):
    names = []
    for verse in (1, 2, 3, 4, 5):
        key = f"short-psalm23v{verse}"
        names.append(queue.add(f"0000-{key}.yml", key, f"Psalm 23:{verse}", GARBLED_LINE,
                               alignment_failures=2))
    faithful = queue.add("0000-short-psalm56v3.yml", "short-psalm56v3", "Psalm 56:3",
                         "What time I am afraid, I will trust in thee.")
    held = queue.add("0000-short-psalm55v22.yml", "short-psalm55v22", "Psalm 55:22", GARBLED_LINE,
                     status="draft", requote=True, pause_reason="misquotes the verse")
    brain = gb.GeminiBrain(api_key="fake", channel_id="secret-place")
    asked: list[str] = []

    def author(_doc, key=None, *, scripture=None):
        asked.append(scripture)
        text = " ".join(v.text for v in st.passage(scripture))
        return ss.require_valid(ss.validate_spec(_spec(key, scripture, "secret-place", text),
                                                 key=key, channel_id="secret-place"))

    monkeypatch.setattr(brain, "author_short_spec", author)
    rows = brain.author_missing_shorts()
    requoted = [row for row in rows if row["verdict"] == "requoted"]
    assert len(requoted) == gb.MAX_REQUOTES_PER_PASS == len(asked)
    assert "Psalm 56:3" not in asked, "a faithful Short is left alone"
    first = yaml.safe_load(names[0].read_text(encoding="utf-8"))
    assert first["status"] == "approved" and "alignment_failures" not in first
    assert sr.scripture_status("short-psalm23v1") == "verified"
    assert yaml.safe_load(faithful.read_text(encoding="utf-8"))["status"] == "approved"

    # Later passes finish the rest, including the one held as a draft for this.
    brain.author_missing_shorts()
    brain.author_missing_shorts()
    data = yaml.safe_load(held.read_text(encoding="utf-8"))
    assert data["status"] == "approved"
    assert "requote" not in data and "pause_reason" not in data
    assert all(sr.scripture_status(f"short-psalm23v{v}") == "verified" for v in (1, 2, 3, 4, 5))


def test_a_failed_rewrite_leaves_the_old_short_in_place(queue, monkeypatch):
    path = queue.add("0000-short-psalm55v22.yml", "short-psalm55v22", "Psalm 55:22", GARBLED_LINE)
    before = (queue.specs / "short-psalm55v22.json").read_text(encoding="utf-8")
    brain = gb.GeminiBrain(api_key="fake", channel_id="secret-place")

    def refuse(_doc, key=None, *, scripture=None):
        raise gb.BrainAuthoringError("rejected on every candidate model")

    monkeypatch.setattr(brain, "author_short_spec", refuse)
    rows = brain.author_missing_shorts()
    assert [row["verdict"] for row in rows] == ["requote_failed"]
    assert (queue.specs / "short-psalm55v22.json").read_text(encoding="utf-8") == before
    assert yaml.safe_load(path.read_text(encoding="utf-8"))["status"] == "approved"


def test_the_held_psalm_55_short_is_marked_for_rewriting():
    data = yaml.safe_load((REPO / "content" / "shorts-queue" / "0000-short-psalm55v22.yml")
                          .read_text(encoding="utf-8"))
    if data.get("status") == "draft":
        assert data.get("requote") is True
    else:  # the brain has rewritten it since
        assert sr.scripture_status("short-psalm55v22", data) == "verified"
