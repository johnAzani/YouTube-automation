"""The channel page is filled in where it is empty and never changed where it is not."""
from __future__ import annotations

import copy
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from pipeline import channel_page as cp
from pipeline.channel_capabilities import brand_for
from pipeline.channels import scheduled_channels
from scripts import setup_channel_page as cli

REPO = Path(__file__).resolve().parent.parent


def _channel(**page) -> dict:
    settings = {"title": "The Family Altar", "description": "Daily prayers for the home.",
                "country": "NG", "defaultLanguage": "en", **page}
    return {"id": "UC_family", "brandingSettings": {"channel": settings,
                                                    "image": {"bannerExternalUrl": "https://x/banner"}}}


LONGFORMS = [{"video_id": "OLDVIDEO001", "views": 9, "published": "2026-11-01"},
             {"video_id": "NEWVIDEO002", "views": 2, "published": "2026-11-12"}]
PLAYLISTS = [{"id": "PL_one", "items": 4}, {"id": "PL_empty", "items": 0}, {"id": "PL_three", "items": 2}]
KEYWORDS = ("prayer for my family", "family prayer", "prayer for children", "kjv")


def _plan(channel=None, sections=None, **kw):
    return cp.plan(channel or _channel(), sections or [], keywords=kw.get("keywords", KEYWORDS),
                   longforms=kw.get("longforms", LONGFORMS), playlists=kw.get("playlists", PLAYLISTS))


def test_an_empty_page_gets_keywords_a_trailer_and_shelves():
    plan = _plan()
    page = plan.branding["channel"]
    assert page["keywords"] == '"prayer for my family" "family prayer" "prayer for children" kjv'
    assert page["unsubscribedTrailer"] == "OLDVIDEO001", "the most watched long-form"
    assert [(s["snippet"]["type"], s["snippet"]["position"],
             (s.get("contentDetails") or {}).get("playlists")) for s in plan.sections] == [
        ("popularUploads", 0, None), ("singlePlaylist", 1, ["PL_one"]),
        ("singlePlaylist", 2, ["PL_three"])], "an empty playlist gets no shelf"


def test_everything_else_on_the_page_is_sent_back_unchanged():
    channel = _channel()
    before = copy.deepcopy(channel)
    plan = _plan(channel)
    assert channel == before, "the plan does not edit what YouTube returned"
    sent = plan.branding
    for key in ("title", "description", "country", "defaultLanguage"):
        assert sent["channel"][key] == before["brandingSettings"]["channel"][key]
    assert sent["image"] == before["brandingSettings"]["image"]


def test_a_page_someone_set_up_by_hand_is_left_alone():
    sections = [{"snippet": {"type": "popularUploads", "position": 0}},
                {"snippet": {"type": "singlePlaylist", "position": 1},
                 "contentDetails": {"playlists": ["PL_one"]}},
                {"snippet": {"type": "singlePlaylist", "position": 2},
                 "contentDetails": {"playlists": ["PL_three"]}}]
    plan = _plan(_channel(keywords="my own words", unsubscribedTrailer="NEWVIDEO002"), sections)
    assert plan.empty and plan.branding is None and plan.sections == []


def test_a_trailer_the_code_does_not_recognise_is_still_left_alone():
    """It may be a Short or a video with no receipt here: a person chose it."""
    sections = [{"snippet": {"type": "popularUploads", "position": 0}}]
    plan = _plan(_channel(keywords="kept", unsubscribedTrailer="SOMEOTHER00"), sections, playlists=[])
    assert plan.empty


def test_no_long_form_means_no_trailer_and_no_popular_shelf():
    plan = _plan(longforms=[], playlists=[])
    assert "unsubscribedTrailer" not in plan.branding["channel"]
    assert plan.sections == []


def test_new_shelves_go_after_the_existing_ones_and_stop_at_ten():
    existing = [{"snippet": {"type": "multipleChannels", "position": n}} for n in range(9)]
    plan = _plan(sections=existing)
    assert [(s["snippet"]["type"], s["snippet"]["position"]) for s in plan.sections] == [("popularUploads", 9)]
    assert any("limit of ten" in note for note in plan.notes)


def test_keywords_are_quoted_deduplicated_and_bounded():
    assert cp.keyword_string(("night prayer", "Night Prayer", "kjv", 'say "amen"')) == \
        '"night prayer" kjv "say amen"'
    long = cp.keyword_string(tuple(f"prayer phrase number {n}" for n in range(60)))
    assert len(long) <= cp.MAX_KEYWORD_CHARS and long.endswith('"')


@pytest.mark.parametrize("channel_id", scheduled_channels())
def test_every_channel_has_keywords_of_its_own(channel_id):
    words = cp.keyword_string(brand_for(channel_id).seo_tag_seeds)
    assert len(words) >= 40
    others = [brand_for(other).display_name.lower() for other in scheduled_channels() if other != channel_id]
    assert not any(name in words.lower() for name in others), "no other channel is named"


def test_apply_writes_the_branding_once_and_each_shelf():
    youtube = MagicMock()
    channel = _channel()
    plan = _plan(channel)
    done = cp.apply(youtube, channel, plan)
    update = youtube.channels.return_value.update.call_args.kwargs
    assert update["part"] == "brandingSettings" and update["body"]["id"] == "UC_family"
    assert update["body"]["brandingSettings"]["channel"]["title"] == "The Family Altar"
    inserts = youtube.channelSections.return_value.insert.call_args_list
    assert [c.kwargs["body"]["snippet"]["type"] for c in inserts] == \
        ["popularUploads", "singlePlaylist", "singlePlaylist"]
    assert done[0] == "branding written" and len(done) == 4


def test_apply_refuses_a_request_that_lost_the_channel_description():
    youtube = MagicMock()
    channel = _channel()
    plan = _plan(channel)
    del plan.branding["channel"]["description"]
    done = cp.apply(youtube, channel, plan)
    youtube.channels.return_value.update.assert_not_called()
    assert done[0].startswith("branding NOT written")


def test_one_refused_shelf_does_not_stop_the_next():
    youtube = MagicMock()
    youtube.channelSections.return_value.insert.return_value.execute.side_effect = [
        RuntimeError("forbidden"), {"id": "s2"}, {"id": "s3"}]
    done = cp.apply(youtube, _channel(), _plan())
    assert [line.split(":")[0].split(" (")[0] for line in done[1:]] == \
        ["shelf refused", "shelf added", "shelf added"]


def test_the_request_fields_exist_in_the_installed_youtube_api_description():
    import json
    import os

    import googleapiclient

    path = os.path.join(os.path.dirname(googleapiclient.__file__), "discovery_cache", "documents",
                        "youtube.v3.json")
    if not os.path.isfile(path):
        pytest.skip("no bundled API description")
    schemas = json.load(open(path, encoding="utf-8"))["schemas"]
    assert {"keywords", "unsubscribedTrailer"} <= set(schemas["ChannelSettings"]["properties"])
    assert {"popularUploads", "singlePlaylist"} <= set(
        schemas["ChannelSectionSnippet"]["properties"]["type"]["enum"])
    assert "playlists" in schemas["ChannelSectionContentDetails"]["properties"]


def test_the_command_reads_plans_and_writes_with_a_fake_client(tmp_path, monkeypatch):
    youtube = MagicMock()
    youtube.channels.return_value.list.return_value.execute.return_value = {"items": [_channel()]}
    youtube.channelSections.return_value.list.return_value.execute.return_value = {"items": []}
    youtube.playlists.return_value.list.return_value.execute.return_value = {"items": []}
    monkeypatch.setattr(cli, "channel_longforms", lambda channel_id, snapshots: LONGFORMS)
    lines = cli.run("prayer5", youtube, snapshots=[])
    assert "branding written" in lines and "shelf added: popularUploads" in lines
    youtube.reset_mock()
    youtube.channels.return_value.list.return_value.execute.return_value = {"items": [_channel()]}
    youtube.channelSections.return_value.list.return_value.execute.return_value = {"items": []}
    youtube.playlists.return_value.list.return_value.execute.return_value = {"items": []}
    lines = cli.run("prayer5", youtube, dry_run=True, snapshots=[])
    assert lines[-1] == "dry run: nothing written"
    youtube.channels.return_value.update.assert_not_called()


def test_the_daily_growth_run_sets_up_the_page():
    workflow = (REPO / ".github" / "workflows" / "growth-autopilot.yml").read_text(encoding="utf-8")
    assert "scripts/setup_channel_page.py --channel" in workflow
    assert workflow.index("scripts/manage_playlists.py") < workflow.index("scripts/setup_channel_page.py"), \
        "playlists exist before they are shelved"
