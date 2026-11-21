"""A Short's title says something of its own, and a Short speaks in its channel's words.

Two things measured on 16 November 2026.

The title. A Short's title is the channel's fixed wording around the reference,
a bar, and a few words after it. Those few words are all that can differ from one
Short to the next on a channel. They were always the last poster line, and on 187
of the 260 Shorts written by then that line was the channel's own name, the
reference a second time, the kind of prayer the title had already named, one
word, or the tail of a longer poster line ("Of Light", "Upon The Bed"). YouTube's
monetisation policy names videos that look made from a template; a row of titles
that differ only by their reference is that, and it gives a viewer no reason to
tap one of them.

The wording. Each channel may not use the others' wording, and long-form prayers
were checked for it. Shorts were not. The Family Altar published one that prayed
"every bedtime prayer", The Secret Place's wording, and `main` failed its tests.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from pipeline import gemini_brain as gb
from pipeline import short_release as sr
from pipeline import short_script as ss
from pipeline.channel_capabilities import brand_for, known_channels

REPO = Path(__file__).resolve().parents[1]
KJV_5522 = ("Cast thy burden upon the LORD, and he shall sustain thee: "
            "he shall never suffer the righteous to be moved.")


def _spec(channel: str = "secret-place", *, poster_last: str = "A QUIET MIND",
          subs: tuple[str, ...] = ("REST IN WHAT HE SAID",), line: str = "") -> dict:
    key, scripture = "short-psalm55v22", "Psalm 55:22"
    lines = [
        "When the weight you carried all day will not lift, this word is for you.",
        KJV_5522,
        line or "Father, I bring You the thing I have carried all day and could not put down.",
        "I thank You that nothing in it is hidden from You, and nothing in it is too heavy.",
        "Teach my heart to rest in what You have said and not in what I can see.",
        "Keep me and the ones I love through this day, and hold us in Your peace. Amen.",
    ]
    captions, phrases, scenes, start = [], [], [], 0
    for index, text in enumerate(lines):
        stop = start + 6
        captions.append([start, stop, text])
        phrases.append([start, stop, [" ".join(text.split()[:3]).upper()], ["WORD"], scripture.upper()])
        scenes.append({"a": " ".join(text.split()[:4]), "img": f"{key}-scene-{index + 1:02d}.jpg",
                       "kicker": "PSALM 55:22", "sub": subs[min(index, len(subs) - 1)],
                       "cam": "push_in", "focus": [0.5, 0.5]})
        start = stop + 1
    return {
        "key": key, "channel": channel, "scripture": scripture,
        "title": ["A WORD", "FOR TODAY"],
        "poster": ["REST TODAY", "IN HIS WORD", "A PRAYER FOR", poster_last],
        "end": ["SUBSCRIBE", "A prayer every day"],
        "stock_queries": [f"calm sky {i}" for i in range(len(lines))],
        "scenes": scenes, "captions": captions, "kinetic_phrases": phrases, "beats": [],
    }


def _hook(channel: str, **spec) -> str:
    built = ss.validate_spec(_spec(channel, **spec))
    assert built.problems == []
    return sr.title_hook(built, brand_for(channel), "Psalm 55:22")


# --------------------------------------------------------------------------- #
# The words after the bar
# --------------------------------------------------------------------------- #
def test_a_poster_line_that_says_something_is_kept():
    assert _hook("secret-place", poster_last="A QUIET MIND") == "A Quiet Mind"


@pytest.mark.parametrize("channel", list(known_channels()))
def test_the_channels_own_name_is_never_the_hook(channel):
    name = brand_for(channel).display_name
    hook = _hook(channel, poster_last=name.upper(), subs=("CAST YOUR BURDEN ON HIM",))
    assert hook == "Cast Your Burden On Him"


@pytest.mark.parametrize("poster_last, reason", [
    ("PSALM 55:22", "the reference again"),
    ("1 PETER 5:7", "the reference again"),
    ("PEACE", "fewer than two words"),
    ("OF LIGHT", "the tail of a longer line"),
    ("UPON THE BED", "the tail of a longer line"),
    ("THEE WHOLE", "the tail of a longer line"),
])
def test_a_line_that_adds_nothing_is_passed_over(poster_last, reason):
    brand = brand_for("prayer3")
    assert sr.hook_adds_nothing(poster_last, brand, "Psalm 55:22") == reason
    assert _hook("prayer3", poster_last=poster_last,
                 subs=("HE CARRIES WHAT YOU CANNOT",)) == "He Carries What You Cannot"


@pytest.mark.parametrize("channel, repeated", [
    ("prayer4", "MIDNIGHT PRAYER"),
    ("prayer5", "FAMILY PRAYER"),
    ("prayer6", "HEALING PRAYER"),
    ("prayer8", "PROTECTION PRAYER"),
    ("prayer9", "THANKSGIVING PRAYER"),
    ("prayer10", "GUIDANCE PRAYER"),
    ("prayer2", "SUNRISE PRAYER"),
])
def test_the_kind_of_prayer_the_title_already_names_is_not_repeated(channel, repeated):
    brand = brand_for(channel)
    assert sr.hook_adds_nothing(repeated, brand, "Psalm 55:22") == "nothing the title has not said"
    title = brand.short_title_template.format(
        label="Psalm 55:22", hook=_hook(channel, poster_last=repeated, subs=("HE HOLDS YOU UP",)))
    assert title.endswith("| He Holds You Up")


def test_the_first_scene_line_that_says_something_is_the_one_used():
    hook = _hook("prayer3", poster_last="THE MIDDAY WATCH",
                 subs=("PSALM 55:22", "PRAYER", "LAY THE WEIGHT DOWN", "HE WILL HOLD YOU"))
    assert hook == "Lay The Weight Down"


def test_when_no_line_is_better_the_old_answer_stands():
    """Never an empty title, and never a refusal to publish over a title."""
    hook = _hook("prayer3", poster_last="THE MIDDAY WATCH", subs=("PRAYER",))
    assert hook == "The Midday Watch"
    bare = SimpleNamespace(poster=[], scenes=[])
    assert sr.title_hook(bare, brand_for("secret-place"), "Psalm 23") == "Divine Peace"


def test_another_channels_wording_is_not_lifted_into_a_title():
    assert sr.hook_adds_nothing("A BEDTIME PRAYER", brand_for("prayer5"), "Psalm 55:22") \
        == "another channel's wording"


def test_an_apostrophe_does_not_capitalise_the_letter_after_it():
    """`str.title()` put "Receive God'S Peace" on a live Short."""
    assert _hook("prayer6", poster_last="RECEIVE GOD'S PEACE") == "Receive God's Peace"
    assert sr._headline("KJV WISDOM FOR TODAY") == "KJV Wisdom For Today"


def test_two_shorts_on_one_channel_get_different_titles():
    brand = brand_for("prayer2")
    first = _hook("prayer2", poster_last="THE MORNING ALTAR", subs=("AWAKEN THE DAWN",))
    second = _hook("prayer2", poster_last="THE MORNING ALTAR", subs=("A CLEAN HEART",))
    titles = {brand.short_title_template.format(label="Psalm 55:22", hook=h) for h in (first, second)}
    assert len(titles) == 2


def test_most_written_shorts_now_carry_a_hook_of_their_own():
    """On the Shorts in the repository, not on a made-up one."""
    checked = weak = 0
    for path in sorted((REPO / "content" / "shorts-scripts").glob("*.json")):
        spec = ss.load_spec(path)
        if spec.problems:
            continue
        brand = brand_for(spec.channel)
        label = spec.scripture.strip() or (f"Psalm {spec.psalm}" if spec.psalm else spec.key)
        checked += 1
        weak += bool(sr.hook_adds_nothing(sr.title_hook(spec, brand, label), brand, label))
    if checked < 20:
        pytest.skip("too few written Shorts in this checkout to measure")
    assert weak / checked < 0.1, f"{weak} of {checked} Shorts still have a hook that adds nothing"


# --------------------------------------------------------------------------- #
# A Short speaks in its own channel's words
# --------------------------------------------------------------------------- #
BEDTIME = "Give us grace in every shared walk, every bedtime prayer, and every morning greeting."


def test_spoken_wording_of_another_channel_is_found():
    spec = ss.validate_spec(_spec("prayer5", line=BEDTIME))
    assert spec.problems == [], "the schema is unchanged: a published Short must keep loading"
    assert ss.foreign_wording(spec) == "bedtime prayer"
    assert ss.foreign_wording(ss.validate_spec(_spec("secret-place", line=BEDTIME))) is None


def test_a_verse_set_in_capitals_on_screen_is_not_a_channels_name():
    """Psalm 91:1 on The Covenant Shield: the mistake that stopped it for days."""
    spec = ss.validate_spec(_spec("prayer8", subs=("DWELL IN THE SECRET PLACE",)))
    assert ss.foreign_wording(spec) is None


def test_on_screen_wording_of_another_channel_is_found():
    spec = ss.validate_spec(_spec("prayer5", subs=("A BEDTIME PRAYER FOR HOME",)))
    assert ss.foreign_wording(spec) == "bedtime prayer"


def test_the_writer_is_told_which_words_are_not_this_channels():
    prompt = ss.build_prompt("Psalm 55:22", key="short-psalm55v22", channel_id="prayer5",
                             avoid_openings=[])
    assert "These words belong to other channels" in prompt
    assert '"bedtime prayer"' in prompt
    own = ss.build_prompt("Psalm 55:22", key="short-psalm55v22", channel_id="secret-place",
                          avoid_openings=[])
    assert '"bedtime prayer"' not in own, "The Secret Place may say its own words"


def _brain(monkeypatch, channel: str, answers: list[dict]):
    monkeypatch.setenv("CHANNEL_ID", channel)
    monkeypatch.setattr(gb.GeminiBrain, "is_api_available", lambda self: True)
    monkeypatch.setattr(gb, "text_model_candidates", lambda primary=None: ["model-a", "model-b"])
    brain = gb.GeminiBrain(api_key="fake", channel_id=channel)
    prompts: list[str] = []

    def generate(model=None, contents=None):
        prompts.append(contents)
        return SimpleNamespace(text=json.dumps(answers[min(len(prompts), len(answers)) - 1]))

    brain._client = SimpleNamespace(models=SimpleNamespace(generate_content=generate))
    brain.prompts = prompts
    return brain


def test_the_brain_refuses_the_short_and_asks_again(monkeypatch):
    brain = _brain(monkeypatch, "prayer5", [_spec("prayer5", line=BEDTIME), _spec("prayer5")])
    spec = brain.author_short_spec(None, key="short-psalm55v22", scripture="Psalm 55:22")
    assert "bedtime prayer" not in spec.narration_text
    assert len(brain.prompts) == 2
    assert "another channel's wording" in brain.prompts[1]


def test_the_brain_never_returns_a_short_in_another_channels_words(monkeypatch):
    brain = _brain(monkeypatch, "prayer5", [_spec("prayer5", line=BEDTIME)])
    with pytest.raises(gb.BrainAuthoringError, match="another channel's wording"):
        brain.author_short_spec(None, key="short-psalm55v22", scripture="Psalm 55:22")


def test_a_line_that_fits_is_preferred_to_one_that_gets_the_title_cut_at_the_bar():
    """A title over the limit is cut at the bar and loses the hook altogether."""
    brand = brand_for("prayer6")
    label = "1 Thessalonians 5:16-18"
    spec = ss.validate_spec(_spec("prayer6", poster_last="THE HEALING BALM",
                                  subs=("HE IS WITH YOU IN THE SILENCE", "HE IS NEAR")))
    assert sr.title_hook(spec, brand, label) == "He Is With You In The Silence"
    fitted = sr.title_hook(spec, brand, label, limit=sr.SHORT_TITLE_LIMIT)
    assert fitted == "He Is Near"
    assert len(brand.short_title_template.format(label=label, hook=fitted)) <= sr.SHORT_TITLE_LIMIT


def test_every_written_short_keeps_its_hook_in_the_title_that_is_uploaded():
    checked = 0
    for path in sorted((REPO / "content" / "shorts-scripts").glob("*.json")):
        spec = ss.load_spec(path)
        if spec.problems:
            continue
        edition = sr.resolve_edition(spec.key)
        if edition is None:
            continue
        checked += 1
        assert " | " in edition.title, edition.title
        assert edition.title.endswith(" #Shorts") and len(edition.title) <= 100, edition.title
        assert "'S " not in edition.title, edition.title
    if not checked:
        pytest.skip("no written Shorts in this checkout")


# --------------------------------------------------------------------------- #
# The upload's duplicate check finds a video by its title, so it must still
# find a Short that was uploaded under the title the old rule gave it.
# --------------------------------------------------------------------------- #
def _saved(monkeypatch, tmp_path, **spec):
    monkeypatch.setattr(ss, "SPEC_DIR", tmp_path)
    data = _spec("prayer2", **spec)
    (tmp_path / f"{data['key']}.json").write_text(json.dumps(data), encoding="utf-8")
    return sr.resolve_edition(data["key"])


def test_a_short_whose_title_changed_remembers_the_title_it_had(monkeypatch, tmp_path):
    edition = _saved(monkeypatch, tmp_path, poster_last="THE MORNING ALTAR",
                     subs=("AWAKEN THE DAWN",))
    assert edition.title == "Say This Psalm 55:22 Prayer at Sunrise | Awaken The Dawn #Shorts"
    assert edition.earlier_titles == (
        "Say This Psalm 55:22 Prayer at Sunrise | The Morning Altar #Shorts",)
    assert sr._build_script_doc(edition).meta["earlier_titles"] == list(edition.earlier_titles)


def test_a_short_whose_title_did_not_change_has_no_earlier_title(monkeypatch, tmp_path):
    edition = _saved(monkeypatch, tmp_path, poster_last="A QUIET MIND")
    assert edition.title.endswith("| A Quiet Mind #Shorts")
    assert edition.earlier_titles == ()


def test_overflow_keeps_hook_and_remembers_the_previously_truncated_title(monkeypatch, tmp_path):
    from pipeline.metadata import smart_truncate_title

    monkeypatch.setattr(sr, "SHORT_TITLE_LIMIT", 45)
    edition = _saved(monkeypatch, tmp_path, poster_last="A QUIET MIND")
    previous = smart_truncate_title(
        "Say This Psalm 55:22 Prayer at Sunrise | A Quiet Mind", 45) + " #Shorts"
    assert edition.title == "Psalm 55:22 | A Quiet Mind #Shorts"
    assert previous in edition.earlier_titles


def test_the_upload_looks_for_the_earlier_title_too(monkeypatch):
    from unittest.mock import MagicMock

    from pipeline import upload as up
    from pipeline.script_doc import ScriptDoc

    asked = {}

    def check(youtube, title, slug=None, *, additional_titles=()):
        asked["title"], asked["also"] = title, additional_titles
        return {"id": "abc123", "title": additional_titles[0], "match": "exact"}

    monkeypatch.setattr(up, "_credentials", lambda: MagicMock())
    monkeypatch.setattr("googleapiclient.discovery.build", lambda *a, **k: MagicMock())
    monkeypatch.setattr(up, "check_existing_channel_duplicate", check)
    old = "Say This Psalm 55:22 Prayer at Sunrise | The Morning Altar #Shorts"
    doc = ScriptDoc(path=Path("/tmp/x.md"), scenes=[], meta={
        "title": "Say This Psalm 55:22 Prayer at Sunrise | Awaken The Dawn #Shorts",
        "earlier_titles": [old], "privacy": "public", "slug": "short-psalm55v22-sunrise-prayer",
        "format": "short"})
    result = up.upload(doc, Path("/tmp/fake.mp4"))
    assert asked["also"] == (old,)
    assert (result.video_id, result.privacy_status) == ("abc123", "duplicate_prevented")
