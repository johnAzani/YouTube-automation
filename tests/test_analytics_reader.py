"""The daily Analytics read: what may be written into a public repository, and what never is.

Decided by the owner on 14 November 2026: watch hours, traffic sources and
retention may be committed. Revenue never. These tests hold the reader to that,
to "only GET", and to counting watch hours the way the Partner Program does
(time in the Shorts feed does not count).
"""
from __future__ import annotations

import datetime
import json
import re
import urllib.parse
from pathlib import Path

import pytest
import yaml

from pipeline.channels import CHANNELS
from scripts import analytics_reader as reader

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github/workflows/channel-analytics.yml"
TODAY = datetime.date(2026, 11, 15)
VIDEO_A, VIDEO_B = "aaaaaaaaaa1", "bbbbbbbbbb2"


def _table(names, rows):
    return {"columnHeaders": [{"name": name} for name in names], "rows": rows}


def _google(asked, refuse=(), kinds_year=None):
    """A stand-in for `probe.get`: answers by what the question asks for."""
    def get(url, token):
        assert token == "ACCESS"
        asked.append(url)
        query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        if "youtube/v3/channels" in url:
            return 200, {"items": [{"statistics": {"subscriberCount": "1250", "viewCount": "9"}}]}, ""
        dimension = query.get("dimensions", [""])[0]
        days = (datetime.date.fromisoformat(query["endDate"][0])
                - datetime.date.fromisoformat(query["startDate"][0])).days
        if (dimension, days) in refuse:
            return 403, None, "403 PERMISSION_DENIED accessNotConfigured"
        if dimension == "creatorContentType" and days == 365:
            return 200, _table(["creatorContentType", "views", "estimatedMinutesWatched"], kinds_year or [
                ["shorts", 5000, 3876], ["videoOnDemand", 300, 900], ["liveStream", 4, 72]]), ""
        if dimension == "creatorContentType" and days == 90:
            return 200, _table(["creatorContentType", "views"], [["shorts", 4200], ["videoOnDemand", 250]]), ""
        if dimension == "creatorContentType" and days == 28:
            return 200, _table(["creatorContentType", "views", "estimatedMinutesWatched"],
                               [["shorts", 2800, 1200], ["videoOnDemand", 118, 84]]), ""
        if dimension == "insightTrafficSourceType":
            return 200, _table(["insightTrafficSourceType", "views", "estimatedMinutesWatched"],
                               [["SHORTS", 2700, 1150], ["YT_SEARCH", 150, 90], ["BRAND::NEW|x", 68, 44]]), ""
        if dimension == "day":
            return 200, _table(["day", "views", "estimatedMinutesWatched"],
                               [["2026-11-12", 100, 60], ["2026-11-13", 90, 30], ["not a day", 1, 1]]), ""
        if dimension == "video":
            return 200, _table(
                ["video", "estimatedMinutesWatched", "views", "averageViewDuration", "averageViewPercentage"],
                [[VIDEO_A, 600, 200, 180, 45.678], [VIDEO_B, 300, 100, 31, 62.0], ["not-an-id", 9, 9, 9, 9]]), ""
        raise AssertionError("unexpected question: " + url)
    return get


def _report(**kwargs):
    asked = []
    report, why = reader.read_channel("secret-place", "ACCESS", TODAY, get=_google(asked, **kwargs))
    return report, why, asked


# ----------------------------------------------------------------- what it asks

def test_it_only_reads_and_never_asks_about_money():
    source = (ROOT / "scripts/analytics_reader.py").read_text(encoding="utf-8")
    # The token refresh is the only request with a body; nothing is POSTed, PUT or DELETEd to YouTube.
    assert source.count("data=form") == 1
    for verb in ("method='POST'", 'method="POST"', "PUT", "DELETE", "PATCH"):
        assert verb not in source
    _report_, _why, asked = _report()
    assert len(asked) == 7 and all("youtubeanalytics.googleapis.com" in u or "youtube/v3/channels" in u for u in asked)
    for url in asked:
        assert not reader.MONEY.search(url), url
        assert "ids=channel==MINE" in url or "mine=true" in url


@pytest.mark.parametrize("metric", ["estimatedRevenue", "estimatedAdRevenue", "grossRevenue", "cpm",
                                    "playbackBasedCpm", "adImpressions", "monetizedPlaybacks",
                                    "estimatedRedPartnerRevenue"])
def test_a_question_about_money_is_refused_before_it_leaves(metric):
    def get(url, token):
        raise AssertionError("the request must not be sent")
    with pytest.raises(ValueError):
        reader.ask("2026-01-01", "2026-02-01", "metrics=views," + metric, "ACCESS", get)


def test_a_report_that_names_money_cannot_be_written(tmp_path):
    report, _why, _asked = _report()
    report["last_28_days"]["estimatedRevenue"] = 1.23
    report["videos_365d"][0]["cpm"] = 4
    assert reader.money_keys(report) == ["last_28_days.estimatedRevenue", "videos_365d[0].cpm"]
    with pytest.raises(ValueError):
        reader.write_report(report, tmp_path)
    assert list(tmp_path.iterdir()) == []
    with pytest.raises(ValueError):
        reader.write_report({"channel": "somebody-else"}, tmp_path)


# ------------------------------------------------------------ what it works out

def test_watch_hours_are_counted_the_way_the_partner_program_counts_them():
    report, why, _asked = _report()
    assert why == ""
    program = report["partner_program"]
    # 900 minutes long-form + 72 live = 16.2 hours counted; 3,876 Shorts minutes = 64.6 hours, kept apart.
    assert program["watch_hours_365d"] == {"long_form_and_live": 16.2, "shorts": 64.6, "other": 0.0, "total": 80.8}
    assert program["watch_hours_counted"] == 16.2
    assert program["shorts_views_90d"] == 4200
    assert program["subscribers"] == 1250
    assert program["needs"] == {"subscribers": 1000, "watch_hours": 4000, "shorts_views_90d": 10_000_000}
    assert program["long_form_hours_a_day_needed"] == 11.0
    assert program["long_form_hours_a_day_last_28_days"] == 0.05  # 84 minutes over 28 days
    assert report["windows"] == {"year": ["2025-11-15", "2026-11-15"], "quarter": ["2026-08-17", "2026-11-15"],
                                 "month": ["2026-10-18", "2026-11-15"]}


def test_a_kind_of_video_it_does_not_know_is_counted_as_neither_and_said_out_loud():
    report, _why, _asked = _report(kinds_year=[["shorts", 10, 60], ["videoOnDemand", 10, 120], ["story", 3, 30]])
    hours = report["partner_program"]["watch_hours_365d"]
    assert hours == {"long_form_and_live": 2.0, "shorts": 1.0, "other": 0.5, "total": 3.5}
    assert "also seen and counted as neither: story (0.5 h)" in reader.headline(report)
    plain, _why, _asked = _report()
    assert "also seen" not in reader.headline(plain)


def test_the_threshold_doubles_for_a_channel_applying_from_february_2027():
    assert reader.needs(datetime.date(2027, 1, 31))["watch_hours"] == 4000
    assert reader.needs(datetime.date(2027, 2, 1)) == {
        "subscribers": 1000, "watch_hours": 8000, "shorts_views_90d": 20_000_000}


def test_the_last_28_days_carry_sources_days_and_videos_with_nothing_unsafe_in_them():
    report, _why, _asked = _report()
    month = report["last_28_days"]
    assert month["views"] == 2918 and month["views_by_kind"] == {"shorts": 2800, "videoondemand": 118}
    assert month["watch_hours"]["long_form_and_live"] == 1.4 and month["watch_hours"]["shorts"] == 20.0
    assert month["traffic_sources"] == [
        {"source": "SHORTS", "views": 2700, "watch_hours": 19.17},
        {"source": "YT_SEARCH", "views": 150, "watch_hours": 1.5},
        {"source": "BRANDNEWx", "views": 68, "watch_hours": 0.73}]  # only safe characters survive
    assert month["by_day"] == [{"day": "2026-11-12", "views": 100, "watch_hours": 1.0},
                               {"day": "2026-11-13", "views": 90, "watch_hours": 0.5}]
    assert report["videos_365d"] == [
        {"video_id": VIDEO_A, "watch_hours": 10.0, "views": 200, "average_view_seconds": 180,
         "average_view_percent": 45.7},
        {"video_id": VIDEO_B, "watch_hours": 5.0, "views": 100, "average_view_seconds": 31,
         "average_view_percent": 62.0}]
    assert reader.money_keys(report) == []
    assert "thumbnail impressions" in report["not_included"][0]


def test_a_channel_that_is_not_granted_gets_no_report():
    report, why, asked = _report(refuse={("creatorContentType", 365)})
    assert report is None and why == "403 PERMISSION_DENIED accessNotConfigured"
    assert len(asked) == 1  # it stops at the first refusal instead of asking seven more times


def test_one_refused_question_is_recorded_and_the_rest_is_still_written():
    report, _why, _asked = _report(refuse={("video", 365)})
    assert report["videos_365d"] == []
    assert report["coverage"]["videos by watch time, 365 days"] == "refused 403 PERMISSION_DENIED accessNotConfigured"
    assert report["coverage"]["where viewers came from, 28 days"] == "3 rows"


@pytest.mark.parametrize("value, expected", [(7, 7), ("12", 12), ("3.5", 3.5), (2.0, 2), (None, 0), ("x", 0),
                                             (True, 0), (float("nan"), 0), (float("inf"), 0), ([1], 0)])
def test_whatever_the_api_sends_becomes_a_plain_number(value, expected):
    assert reader.number(value) == expected


# ------------------------------------------------------------ files and wording

def test_the_file_is_written_whole_and_read_back(tmp_path):
    report, _why, _asked = _report()
    path = reader.write_report(report, tmp_path)
    assert path == tmp_path / "secret-place.json" and not (tmp_path / "secret-place.json.tmp").exists()
    assert json.loads(path.read_text(encoding="utf-8")) == report
    (tmp_path / "prayer2.json").write_text("{not json", encoding="utf-8")
    (tmp_path / "prayer3.json").write_text(json.dumps({"schema": 99, "channel": "prayer3"}), encoding="utf-8")
    (tmp_path / "prayer4.json").write_text(json.dumps({**report, "channel": "prayer5"}), encoding="utf-8")
    assert list(reader.load_reports(tmp_path)) == ["secret-place"]  # broken or mislabelled files are ignored


def test_the_summary_is_plain_markdown_the_owner_can_read(tmp_path):
    report, _why, _asked = _report()
    receipts = tmp_path / "published"
    receipts.mkdir()
    (receipts / "0001-a.md").write_text(
        '---\nid: \'0001\'\ntitle: "Psalm 91 | Night Prayer"\nyoutube_video_id: "%s"\n---\nBody\n' % VIDEO_A,
        encoding="utf-8")
    text = reader.summary({"secret-place": report}, receipts)
    assert "| The Secret Place | 1,250 | 16.2 | 4,200 | 0.05 | " in text
    assert "need 1,000" in text and "need 4,000" in text and "need 10,000,000" in text and "(need 11)" in text
    assert "| Shorts feed | 2,700 | 19.2 |" in text and "| YouTube search | 150 | 1.5 |" in text
    # A title cannot break the table, and a video without a receipt shows its id.
    assert "| [Psalm 91 / Night Prayer](https://youtu.be/%s) | 10 | 200 | 3:00 (45.7%%) |" % VIDEO_A in text
    assert "| [%s](https://youtu.be/%s) | 5 | 100 | 0:31 (62%%) |" % (VIDEO_B, VIDEO_B) in text
    assert "Not granted Analytics access yet: The Morning Altar, " in text
    assert "Revenue is never written here." in text and not reader.MONEY.search(text.replace("Revenue is never", ""))
    assert reader.summary({}).rstrip().endswith("No channel has been granted Analytics access yet.")


@pytest.mark.parametrize("value, text", [(0, "0"), (0.05, "0.05"), (0.5, "0.5"), (1.44, "1.4"), (16.2, "16.2"),
                                         (99.96, "100"), (1204.4, "1,204")])
def test_hours_are_shown_without_false_precision(value, text):
    assert reader.amount(value) == text


def test_the_daily_issue_gets_three_lines_only_for_a_channel_with_a_report(tmp_path):
    report, _why, _asked = _report()
    reader.write_report(report, tmp_path)
    lines = reader.issue_lines("secret-place", tmp_path)
    assert lines[0] == "### Toward the Partner Program (YouTube Analytics, read %s)" % report["generated_at"][:10]
    assert "**16.2 of 4,000**" in lines[2] and "64.6 h, does not count" in lines[2]
    assert "**0.05**" in lines[3] and "**4,200 of 10,000,000**" in lines[4]
    assert reader.issue_lines("prayer2", tmp_path) == []

    from scripts.metrics_snapshot import _partner_program_lines
    assert _partner_program_lines("prayer2") in ([], reader.issue_lines("prayer2"))


# ------------------------------------------------------------------- a whole run

def _run(monkeypatch, capsys, tmp_path, argv, granted=("secret-place",), refuse=()):
    asked = []
    monkeypatch.setattr(reader, "access_token", lambda cid, secret, refresh: (
        ("ACCESS", "") if cid else ("", "credentials not present in this run")))
    monkeypatch.setattr(reader.probe, "get", _google(asked, refuse=refuse))
    for channel, profile in CHANNELS.items():
        for name in profile.secret_names().values():
            monkeypatch.delenv(name, raising=False)
    for channel in granted:
        names = CHANNELS[channel].secret_names()
        for key in ("client_id", "client_secret", "refresh_token"):
            monkeypatch.setenv(names[key], "SECRET-" + key)
    assert reader.main(argv + ["--out", str(tmp_path)]) == 0
    return capsys.readouterr().out, asked


def test_a_run_writes_the_granted_channel_and_names_the_rest_in_one_line(monkeypatch, capsys, tmp_path):
    out, _asked = _run(monkeypatch, capsys, tmp_path, [])
    annotations = [line for line in out.splitlines() if line.startswith("::")]
    assert len(annotations) == 2  # ten channels must fit under GitHub's ten-annotation limit
    assert annotations[0].startswith(
        "::notice title=Analytics secret-place::16.2 of 4,000 watch hours counted over 365 days "
        "(long-form and live; Shorts 64.6 h not counted); 1,250 of 1,000 subscribers; "
        "last 28 days: 1.4 long-form hours, 2,918 views; file written")
    assert annotations[1] == ("::notice title=Analytics prayer2, prayer3, prayer4, prayer5, prayer6, prayer7, "
                              "prayer8, prayer9, prayer10::credentials not present in this run; no file written")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["README.md", "secret-place.json"]
    assert "SECRET-" not in out and "ACCESS" not in out


def test_a_dry_run_on_a_session_branch_writes_nothing(monkeypatch, capsys, tmp_path):
    out, asked = _run(monkeypatch, capsys, tmp_path, ["--no-write"])
    assert "not written (dry run)" in out and asked
    assert list(tmp_path.iterdir()) == []


def test_a_channel_not_granted_keeps_the_file_it_already_has(monkeypatch, capsys, tmp_path):
    old = {"schema": 1, "channel": "prayer2", "kept": True}
    (tmp_path / "prayer2.json").write_text(json.dumps(old), encoding="utf-8")
    out, _asked = _run(monkeypatch, capsys, tmp_path, ["--channel", "prayer2"], granted=("prayer2",),
                       refuse={("creatorContentType", 365)})
    assert "::notice title=Analytics prayer2::not granted yet (403 PERMISSION_DENIED accessNotConfigured); " \
           "no file written" in out
    assert json.loads((tmp_path / "prayer2.json").read_text(encoding="utf-8")) == old


def test_one_channel_blowing_up_does_not_cost_the_others_or_the_job(monkeypatch, capsys, tmp_path):
    real = reader.read_channel

    def flaky(channel, token, today, get=None):
        if channel == "prayer2":
            raise RuntimeError("anything")
        return real(channel, token, today, get)
    monkeypatch.setattr(reader, "read_channel", flaky)
    out, _asked = _run(monkeypatch, capsys, tmp_path, [], granted=("secret-place", "prayer2"))
    assert "::warning title=Analytics prayer2::stopped early (RuntimeError); no file written" in out
    assert (tmp_path / "secret-place.json").exists() and not (tmp_path / "prayer2.json").exists()


# ------------------------------------------------------------------ the workflow

def _workflow():
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_the_job_with_youtube_credentials_cannot_write_and_the_job_that_writes_has_none():
    workflow = _workflow()
    assert workflow["permissions"] == {"contents": "read"}
    read, publish = workflow["jobs"]["read"], workflow["jobs"]["publish"]
    assert "permissions" not in read
    assert read["steps"][0]["with"] == {"persist-credentials": False}
    assert publish["permissions"] == {"contents": "write"}
    assert publish["if"] == "${{ github.ref == 'refs/heads/main' }}" and publish["needs"] == "read"
    assert "secrets." not in json.dumps(publish)
    env = read["steps"][1]["env"]
    wanted = {name for profile in CHANNELS.values() for key, name in profile.secret_names().items()
              if key in ("client_id", "client_secret", "refresh_token")}
    assert set(env) == wanted and len(env) == 30
    for name, value in env.items():
        assert value == "${{ secrets.%s }}" % name  # each channel's own secret, under its own name


def test_a_session_branch_reads_and_reports_but_commits_nothing():
    workflow = _workflow()
    triggers = workflow[True]
    assert triggers["push"] == {"branches": ["arena/**"], "paths": [
        ".github/workflows/channel-analytics.yml", "scripts/analytics_reader.py"]}
    assert "schedule" in triggers and "workflow_dispatch" in triggers
    run = workflow["jobs"]["read"]["steps"][1]["run"]
    assert 'if [ "$GITHUB_REF" = "refs/heads/main" ]' in run and "--no-write" in run
    upload = workflow["jobs"]["read"]["steps"][2]
    assert upload["if"] == "${{ github.ref == 'refs/heads/main' }}" and upload["with"]["path"] == "content/analytics/"
    commit = workflow["jobs"]["publish"]["steps"][-1]["run"]
    assert "git add content/analytics\n" in commit and "[skip ci]" in commit and "git push --quiet origin HEAD:main" in commit
    assert "rebase" not in commit and "--force" not in commit
    assert re.search(r"for attempt in 1 2 3", commit)
