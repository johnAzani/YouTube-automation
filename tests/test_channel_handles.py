"""A channel's @handle is a link, and a link nobody opened is a guess.

The Secret Place was planned as `@TheSecretPlace`. On YouTube it is
`@SecretPlaceSanctuary`. For 44 uploads every subscribe link in its descriptions,
and the "pray the complete prayer" fallback link at the top of its Shorts, opened
a "404 Not Found" page (found 14 November 2026). These tests keep the dead name
out of anything that is uploaded, and prove the repair of the videos already
live changes the link and nothing else.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from pipeline.channels import CHANNELS, RETIRED_HANDLES, get_channel
from scripts import repair_live_handles as repair

ROOT = Path(__file__).resolve().parent.parent
OLD = "@TheSecretPlace"
NEW = "@SecretPlaceSanctuary"
#: Everything that ends up in a description, a comment, a feed or a public page.
SHIPPED = ("pipeline", "scripts", "tools", ".github/workflows")
TEXT_SUFFIXES = {".py", ".yml", ".yaml", ".md", ".json", ".txt", ".html", ".xml"}


def _shipped_files():
    for folder in SHIPPED:
        for path in sorted((ROOT / folder).rglob("*")):
            if path.is_file() and path.suffix in TEXT_SUFFIXES and "__pycache__" not in path.parts:
                yield path


# ---------------------------------------------------------------- the registry

def test_the_secret_place_links_to_the_handle_it_has_on_youtube():
    assert get_channel("secret-place").handle == NEW
    assert RETIRED_HANDLES == {"secret-place": (OLD,)}


def test_a_retired_handle_is_never_a_live_one():
    live = {profile.handle.lower() for profile in CHANNELS.values()}
    for channel, names in RETIRED_HANDLES.items():
        assert channel in CHANNELS
        for name in names:
            assert name.startswith("@") and name.lower() not in live


def test_nothing_that_is_uploaded_still_names_a_retired_handle():
    allowed = {ROOT / "pipeline/channels.py"}  # where the retired names are listed
    offenders = []
    for path in _shipped_files():
        if path in allowed:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for names in RETIRED_HANDLES.values():
            for name in names:
                if repair.swap(text, name, "") != text:
                    offenders.append(f"{path.relative_to(ROOT)} names {name}")
    assert not offenders, offenders


def test_every_youtube_handle_link_in_the_code_is_a_registered_channel():
    known = {profile.handle.lower() for profile in CHANNELS.values()}
    link = re.compile(r"youtube\.com/(@[A-Za-z0-9_][A-Za-z0-9_.-]*[A-Za-z0-9_])")
    strangers = sorted({f"{path.relative_to(ROOT)}: {match}"
                        for path in _shipped_files()
                        for match in link.findall(path.read_text(encoding="utf-8", errors="ignore"))
                        if match.lower() not in known})
    assert not strangers, strangers


def test_the_produce_workflow_hands_each_channel_its_registered_handle():
    line = next(line for line in (ROOT / ".github/workflows/produce.yml").read_text(encoding="utf-8").splitlines()
                if line.strip().startswith("CHANNEL_HANDLE:"))
    assert sorted(re.findall(r"'(@[A-Za-z0-9_.-]+)'", line)) == sorted(p.handle for p in CHANNELS.values())
    # The last, unconditional value is channel 1's.
    assert line.rstrip().rstrip("}").rstrip().rstrip(")").endswith(f"'{NEW}'")


def test_what_gets_uploaded_for_the_secret_place_carries_the_working_links():
    from pipeline.shorts_bridge import (
        enrich_short_description_with_bridge, generate_short_bridge_comment, playlist_fallback_for_channel)
    from pipeline.social_pack import SUBSCRIBE_URL

    assert playlist_fallback_for_channel("secret-place") == f"https://www.youtube.com/{NEW}/playlists"
    assert SUBSCRIBE_URL == f"https://www.youtube.com/{NEW}?sub_confirmation=1"
    description = enrich_short_description_with_bridge(
        "A short prayer.\n\n#Shorts #Psalm999", "short-psalm999v1", channel_id="secret-place")
    comment = generate_short_bridge_comment("short-psalm999v1", channel_id="secret-place")
    for text in (description, comment):
        assert OLD not in text.replace(NEW, "")
    assert f"https://www.youtube.com/{NEW}/playlists" in description


# ------------------------------------------------------------------ the repair

@pytest.mark.parametrize("before, after", [
    (f"https://www.youtube.com/{OLD}?sub_confirmation=1", f"https://www.youtube.com/{NEW}?sub_confirmation=1"),
    (f"👉 https://www.youtube.com/{OLD}/playlists\n━━", f"👉 https://www.youtube.com/{NEW}/playlists\n━━"),
    (f"(Also in {OLD} bio):", f"(Also in {NEW} bio):"),
    (f"visit youtube.com/{OLD}.", f"visit youtube.com/{NEW}."),
    ("youtube.com/@thesecretplace", f"youtube.com/{NEW}"),
    # Not the handle: a hashtag, a longer name, a shop address, the channel's name.
    ("#TheSecretPlace #NightPrayer", "#TheSecretPlace #NightPrayer"),
    ("@TheSecretPlacePrayer", "@TheSecretPlacePrayer"),
    ("https://selar.com/showlove/thesecretplace", "https://selar.com/showlove/thesecretplace"),
    ("Subscribe to The Secret Place", "Subscribe to The Secret Place"),
    ("write to prayer@thesecretplace.media.", "write to prayer@thesecretplace.media."),
    ("@thesecretplace.daily", "@thesecretplace.daily"),
    (f"already {NEW}", f"already {NEW}"),
])
def test_only_the_handle_itself_is_swapped(before, after):
    assert repair.swap(before, OLD, NEW) == after
    assert repair.swap(after, OLD, NEW) == after  # running it twice changes nothing more


def _video(video_id, description, localizations=None):
    video = {"id": video_id, "snippet": {
        "title": "A Title", "description": description, "tags": ["psalm 91", "night prayer"],
        "categoryId": "22", "defaultLanguage": "en", "defaultAudioLanguage": "en",
        # Read-only fields YouTube returns and refuses or ignores on the way back.
        "channelId": "UCsomething", "publishedAt": "2026-11-01T00:00:00Z", "channelTitle": "The Secret Place",
        "thumbnails": {"default": {"url": "x"}}, "liveBroadcastContent": "none",
        "localized": {"title": "A Title", "description": description}}}
    if localizations is not None:
        video["localizations"] = localizations
    return video


def test_the_body_sent_back_changes_the_description_and_nothing_else():
    video = _video("vid00000001", f"Pray.\n• Subscribe: https://www.youtube.com/{OLD}?sub_confirmation=1\n#TheSecretPlace",
                   {"en": {"title": "A Title", "description": f"x youtube.com/{OLD}/playlists"},
                    "fr": {"title": "Un Titre", "description": f"Priez. https://www.youtube.com/{OLD}?sub_confirmation=1"},
                    "es": {"title": "Un Título", "description": "sin enlace"}})
    body = repair.corrected_body(video, (OLD,), NEW)
    assert body["id"] == "vid00000001"
    assert set(body["snippet"]) == set(repair.WRITABLE)  # no read-only field goes back
    for key in ("title", "tags", "categoryId", "defaultLanguage", "defaultAudioLanguage"):
        assert body["snippet"][key] == video["snippet"][key]
    assert body["snippet"]["description"] == (
        f"Pray.\n• Subscribe: https://www.youtube.com/{NEW}?sub_confirmation=1\n#TheSecretPlace")
    assert body["localizations"]["fr"] == {
        "title": "Un Titre", "description": f"Priez. https://www.youtube.com/{NEW}?sub_confirmation=1"}
    assert body["localizations"]["en"]["description"] == f"x youtube.com/{NEW}/playlists"
    assert body["localizations"]["es"] == {"title": "Un Título", "description": "sin enlace"}
    assert not repair.still_broken(body, (OLD,)) and repair.still_broken(video, (OLD,))


def test_a_video_that_is_already_right_gets_no_write_at_all():
    assert repair.corrected_body(_video("vid00000002", f"https://www.youtube.com/{NEW}"), (OLD,), NEW) is None
    assert repair.corrected_body(_video("vid00000003", "no link", {"fr": {"title": "t", "description": "d"}}),
                                 (OLD,), NEW) is None


def test_a_video_without_tags_or_languages_does_not_get_empty_ones_invented():
    video = _video("vid00000004", f"youtube.com/{OLD}")
    for key in ("tags", "defaultLanguage", "defaultAudioLanguage"):
        del video["snippet"][key]
    body = repair.corrected_body(video, (OLD,), NEW)
    assert set(body["snippet"]) == {"title", "description", "categoryId"} and "localizations" not in body


class _Call:
    def __init__(self, result=None, error=None):
        self.result, self.error = result, error

    def execute(self):
        if self.error:
            raise self.error
        return self.result


class _YouTube:
    """Just enough of the API client: it holds videos and records every call."""

    def __init__(self, videos, refuse=None, ignore_writes=False):
        self.videos_by_id = {video["id"]: video for video in videos}
        self.lists, self.updates = [], []
        self.refuse, self.ignore_writes = refuse or {}, ignore_writes

    def videos(self):
        return self

    def list(self, part, id, maxResults=None):  # noqa: A002 - the API's own parameter name
        self.lists.append((part, id))
        return _Call({"items": [self.videos_by_id[v] for v in id.split(",") if v in self.videos_by_id]})

    def update(self, part, body):
        self.updates.append((part, body))
        if body["id"] in self.refuse:
            return _Call(error=self.refuse[body["id"]])
        if self.ignore_writes:
            return _Call(self.videos_by_id[body["id"]])
        return _Call({"id": body["id"], "snippet": body["snippet"], "localizations": body.get("localizations", {})})


def _receipt(folder, name, video_id, channel=None, extra=""):
    lines = ["---", f"id: '{name}'", f"title: \"{name}\"", f"slug: {name}", "status: published",
             "format: short", "niche: faith and prayer"]
    if channel:
        lines.append(f"channel: {channel}")
    lines.append(f'youtube_video_id: "{video_id}"')
    if extra:
        lines.append(extra)
    lines += ["---", "", "Body.", ""]
    path = folder / f"{name}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _stamps():
    made = []
    return made, lambda path, key, value: made.append((path.name, key, value))


BROKEN = f"• Subscribe: https://www.youtube.com/{OLD}?sub_confirmation=1"


def test_only_the_channel_with_a_retired_handle_is_looked_at(tmp_path):
    _receipt(tmp_path, "0001-a", "aaaaaaaaaa1")
    _receipt(tmp_path, "0201-b", "bbbbbbbbbb1", channel="prayer2")
    _receipt(tmp_path, "0002-c", "cccccccccc1", extra=f'live_handle: "{NEW}"')
    _receipt(tmp_path, "0003-d", "dddddddddd1", extra='youtube_status: "deleted_or_missing"')
    (tmp_path / "0004-no-video.md").write_text("---\nid: '0004'\ntitle: t\n---\nBody\n", encoding="utf-8")
    found = repair.pending(tmp_path)
    assert list(found) == ["secret-place"]
    assert [(path.name, video) for path, video in found["secret-place"]] == [("0001-a.md", "aaaaaaaaaa1")]


def test_a_dry_run_reads_and_writes_nothing(tmp_path):
    _receipt(tmp_path, "0001-a", "aaaaaaaaaa1")
    _receipt(tmp_path, "0002-b", "bbbbbbbbbb1")
    youtube = _YouTube([_video("aaaaaaaaaa1", BROKEN), _video("bbbbbbbbbb1", "fine")])
    made, stamp = _stamps()
    report = repair.repair(apply=False, published_dir=tmp_path, client_for=lambda c: youtube, stamp=stamp)
    assert youtube.updates == [] and made == []
    assert report["secret-place"]["would_correct"] == 1 and report["secret-place"]["already_right"] == 1
    assert "1 descriptions would be corrected" in repair.sentence("secret-place", report["secret-place"], False)


def test_applying_rewrites_the_broken_ones_stamps_the_good_ones_and_reads_in_one_call(tmp_path):
    _receipt(tmp_path, "0001-a", "aaaaaaaaaa1")
    _receipt(tmp_path, "0002-b", "bbbbbbbbbb1")
    _receipt(tmp_path, "0003-c", "cccccccccc1")
    _receipt(tmp_path, "0301-other", "zzzzzzzzzz1", channel="prayer3")
    youtube = _YouTube([_video("aaaaaaaaaa1", BROKEN, {"fr": {"title": "t", "description": BROKEN}}),
                        _video("bbbbbbbbbb1", "fine")])  # cccccccccc1 is gone from the channel
    made, stamp = _stamps()
    asked = []
    report = repair.repair(apply=True, published_dir=tmp_path, stamp=stamp,
                           client_for=lambda channel: asked.append(channel) or youtube)
    assert asked == ["secret-place"]  # no other channel's sign-in is even built
    assert youtube.lists == [("snippet,localizations", "aaaaaaaaaa1,bbbbbbbbbb1,cccccccccc1")]
    assert [(part, body["id"]) for part, body in youtube.updates] == [("snippet,localizations", "aaaaaaaaaa1")]
    assert OLD not in youtube.updates[0][1]["snippet"]["description"]
    assert made == [("0001-a.md", "live_handle", NEW), ("0002-b.md", "live_handle", NEW)]
    counts = report["secret-place"]
    assert (counts["corrected"], counts["already_right"], counts["not_found"], counts["failed"]) == (1, 1, 1, 0)
    assert repair.sentence("secret-place", counts, True) == (
        f"1 descriptions now link to {NEW}; 1 already right; 1 not found on the channel")


def test_a_run_writes_no_more_than_its_allowance_and_the_rest_waits(tmp_path):
    for n in range(5):
        _receipt(tmp_path, f"000{n}-x", f"vvvvvvvvvv{n}")
    youtube = _YouTube([_video(f"vvvvvvvvvv{n}", BROKEN) for n in range(5)])
    made, stamp = _stamps()
    report = repair.repair(apply=True, published_dir=tmp_path, client_for=lambda c: youtube, stamp=stamp,
                           max_updates=2)
    assert len(youtube.updates) == 2 and len(made) == 2
    assert report["secret-place"]["corrected"] == 2 and report["secret-place"]["left"] == 3


def test_when_the_quota_runs_out_it_stops_asking_and_fails_nothing(tmp_path):
    for n in range(3):
        _receipt(tmp_path, f"000{n}-x", f"vvvvvvvvvv{n}")
    youtube = _YouTube([_video(f"vvvvvvvvvv{n}", BROKEN) for n in range(3)],
                       refuse={"vvvvvvvvvv1": RuntimeError("HttpError 403 quotaExceeded")})
    made, stamp = _stamps()
    report = repair.repair(apply=True, published_dir=tmp_path, client_for=lambda c: youtube, stamp=stamp)
    assert [body["id"] for _part, body in youtube.updates] == ["vvvvvvvvvv0", "vvvvvvvvvv1"]
    assert [name for name, _k, _v in made] == ["0000-x.md"]
    counts = report["secret-place"]
    assert (counts["corrected"], counts["left"], counts["failed"]) == (1, 2, 0)


def test_a_refused_or_ineffective_write_is_not_stamped_so_it_is_tried_again(tmp_path):
    _receipt(tmp_path, "0001-a", "aaaaaaaaaa1")
    _receipt(tmp_path, "0002-b", "bbbbbbbbbb1")
    made, stamp = _stamps()
    refused = _YouTube([_video("aaaaaaaaaa1", BROKEN), _video("bbbbbbbbbb1", BROKEN)],
                       refuse={"aaaaaaaaaa1": RuntimeError("HttpError 400 invalidDescription")})
    report = repair.repair(apply=True, published_dir=tmp_path, client_for=lambda c: refused, stamp=stamp)
    assert [name for name, _k, _v in made] == ["0002-b.md"]
    assert report["secret-place"]["failed"] == 1 and report["secret-place"]["corrected"] == 1

    made.clear()
    deaf = _YouTube([_video("aaaaaaaaaa1", BROKEN), _video("bbbbbbbbbb1", BROKEN)], ignore_writes=True)
    report = repair.repair(apply=True, published_dir=tmp_path, client_for=lambda c: deaf, stamp=stamp)
    assert made == [] and report["secret-place"]["failed"] == 2


def test_without_a_sign_in_nothing_is_touched_and_the_run_says_so(tmp_path, capsys, monkeypatch):
    _receipt(tmp_path, "0001-a", "aaaaaaaaaa1")
    made, stamp = _stamps()
    report = repair.repair(apply=True, published_dir=tmp_path, client_for=lambda c: None, stamp=stamp)
    assert made == [] and report["secret-place"]["no_credentials"] == 1
    assert "no sign-in" in repair.sentence("secret-place", report["secret-place"], True)

    def boom(channel):
        raise RuntimeError("invalid_grant")
    assert repair.repair(apply=True, published_dir=tmp_path, client_for=boom,
                         stamp=stamp)["secret-place"]["left"] == 1

    # The command line never fails the step that runs it, whatever happens inside.
    monkeypatch.setattr(repair, "repair", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("anything")))
    assert repair.main(["--apply"]) == 0
    assert "::warning title=Live handle repair::stopped early (RuntimeError)" in capsys.readouterr().out


def test_the_real_stamp_writes_the_handle_into_the_receipt_and_ends_the_work(tmp_path):
    path = _receipt(tmp_path, "0001-a", "aaaaaaaaaa1")
    youtube = _YouTube([_video("aaaaaaaaaa1", BROKEN)])
    repair.repair(apply=True, published_dir=tmp_path, client_for=lambda c: youtube)
    assert f'live_handle: "{NEW}"' in path.read_text(encoding="utf-8")
    assert repair.pending(tmp_path) == {}  # nothing left: the next run makes no API call


def test_the_monitor_runs_the_repair_after_the_metadata_sync_and_cannot_be_failed_by_it():
    text = (ROOT / ".github/workflows/monitor.yml").read_text(encoding="utf-8")
    sync = text.index("python -m scripts.retrofit_published_metadata --sync-pending")
    fix = text.index("python -m scripts.repair_live_handles --apply")
    assert sync < fix < text.index("python -m scripts.release_report --sweep-stale")
    assert text[fix:].split("\n", 2)[1].strip().startswith("|| echo")
