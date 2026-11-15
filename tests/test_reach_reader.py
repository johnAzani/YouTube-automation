"""Reading YouTube's daily reach files: thumbnail impressions and click rate.

Held fixed: only GET requests; the access token goes to Google's reporting host
and nowhere else; four named columns are read and nothing that is money can be
written; the click rate's unit is settled from the file or left out; a channel
with nothing to read keeps the file it has and does not fail the run; a session
branch writes nothing.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

from pipeline.channels import CHANNELS
from scripts import analytics_reader as reader
from scripts import reach_reader as reach

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github/workflows/channel-analytics.yml"
NOW = "2026-11-15T16:30:00Z"
VIDEO_A, VIDEO_B, VIDEO_C = "aaaaaaaaaa1", "bbbbbbbbbb2", "cccccccccc3"
HEADER = "date,channel_id,video_id,subscribed_status,country_code," \
         "video_thumbnail_impressions,video_thumbnail_impressions_ctr\n"
URL = "https://youtubereporting.googleapis.com/v1/media/%s?alt=media"


def _csv(*rows):
    return (HEADER + "".join("%s,UCxxxx,%s,%s,%s,%s,%s\n" % row for row in rows)).encode()


#: 12 November as YouTube might write it: a fraction of 1, split by country and subscription.
DAY_12 = _csv(("20261112", VIDEO_A, "subscribed", "NG", 40, 0.05),      # 2 clicks
              ("20261112", VIDEO_A, "unsubscribed", "US", 160, 0.0125),  # 2 clicks
              ("20261112", VIDEO_B, "unsubscribed", "NG", 7, 0.142857),  # 1 click
              ("20261112", VIDEO_C, "unsubscribed", "GB", 9, 0.0))
DAY_13 = _csv(("20261113", VIDEO_A, "unsubscribed", "NG", 100, 0.03),    # 3 clicks
              ("20261113", "not-an-id", "unsubscribed", "NG", 5, 0.2),
              ("notaday", VIDEO_B, "unsubscribed", "NG", 5, 0.2))


def _file(name, day, created):
    return {"id": name, "jobId": "job-1", "startTime": "%sT08:00:00Z" % day, "endTime": "%sT08:00:00Z" % day,
            "createTime": created, "downloadUrl": URL % name}


def _google(asked, jobs=None, files=(), refuse=None, pages=None):
    """A stand-in for `probe.get`."""
    def get(url, token):
        assert token == "ACCESS"
        asked.append(url)
        if refuse:
            return 403, None, refuse
        if url.endswith("/jobs"):
            return 200, {"jobs": jobs if jobs is not None else [
                {"id": "job-1", "reportTypeId": reach.REPORT_TYPE, "createTime": "2026-11-14T16:30:13Z"},
                {"id": "job-yt", "reportTypeId": reach.REPORT_TYPE, "systemManaged": True},
                {"id": "job-other", "reportTypeId": "channel_basic_a3"}]}, ""
        assert "/jobs/job-1/reports?pageSize=100" in url, url
        if pages:
            token_asked = re.search(r"pageToken=(\w+)", url)
            return 200, pages[token_asked.group(1) if token_asked else ""], ""
        return 200, {"reports": list(files)}, ""
    return get


def _fetch(store, fetched=None):
    def fetch(url, token):
        assert token == "ACCESS"
        if fetched is not None:
            fetched.append(url)
        answer = store[url.split("/media/")[1].split("?")[0]]
        return (None, answer) if isinstance(answer, str) else (answer, "")
    return fetch


def _read(files, store, **kwargs):
    asked = []
    return reach.read_channel("secret-place", "ACCESS", NOW, kwargs.pop("previous", None),
                              get=_google(asked, files=files, **kwargs), fetch=_fetch(store)) + (asked,)


TWO_DAYS = [_file("f12", "2026-11-12", "2026-11-14T20:00:00Z"), _file("f13", "2026-11-13", "2026-11-15T20:00:00Z")]
STORE = {"f12": DAY_12, "f13": DAY_13}


# ------------------------------------------------------------------ what it reads

def test_impressions_and_clicks_are_summed_per_video_and_per_day():
    report, why, failed, asked = _read(TWO_DAYS, STORE)
    assert why == "" and failed == []
    assert report["window"] == {"first_day": "2026-11-12", "last_day": "2026-11-13", "days": 2,
                                "impressions": 316, "clicks": 8, "click_rate_percent": 2.53, "videos": 3}
    assert report["by_day"] == [{"day": "2026-11-12", "impressions": 216, "clicks": 5},
                                {"day": "2026-11-13", "impressions": 100, "clicks": 3}]
    assert report["videos"] == [
        {"video_id": VIDEO_A, "impressions": 300, "clicks": 7, "click_rate_percent": 2.33,
         "first_day": "2026-11-12", "last_day": "2026-11-13"},
        {"video_id": VIDEO_C, "impressions": 9, "clicks": 0, "click_rate_percent": 0.0,
         "first_day": "2026-11-12", "last_day": "2026-11-12"},
        {"video_id": VIDEO_B, "impressions": 7, "clicks": 1, "click_rate_percent": 14.29,
         "first_day": "2026-11-12", "last_day": "2026-11-12"}]
    assert report["files_read"] == 2 and report["job_since"] == "2026-11-14"
    assert report["click_rate_unit_in_file"] == "fraction" and report["generated_at"] == NOW
    assert report["click_rate_samples_as_written"] == []
    # The channel's id is in the file and is not carried into the report.
    assert "UCxxxx" not in json.dumps(report) and "channel_id" in report["columns_seen"]
    # Only the studio's own job is read: not YouTube's, not another report's.
    assert all("job-yt" not in url and "job-other" not in url for url in asked)


def test_a_file_written_in_percent_gives_the_same_answer():
    as_percent = _csv(("20261112", VIDEO_A, "subscribed", "NG", 40, 5.0),
                      ("20261112", VIDEO_A, "unsubscribed", "US", 160, 1.25),
                      ("20261112", VIDEO_B, "unsubscribed", "NG", 7, 14.2857),
                      ("20261112", VIDEO_C, "unsubscribed", "GB", 9, 0))
    report, _why, _failed, _asked = _read(TWO_DAYS[:1], {"f12": as_percent})
    assert report["click_rate_unit_in_file"] == "percent"
    assert report["window"]["impressions"] == 216 and report["window"]["clicks"] == 5


@pytest.mark.parametrize("rows, unit", [
    ([("d", "v", 40.0, 0.05)], "fraction"),          # 2 clicks; as a percentage it would be 0.02 of a click
    ([("d", "v", 40.0, 5.0)], "percent"),            # above 1 cannot be a fraction
    ([("d", "v", 40.0, 0.0)], "none seen"),
    ([], "none seen"),
    ([("d", "v", 10000.0, 0.9)], "undetermined"),    # 9,000 clicks or 90: both possible
    ([("d", "v", 3.0, 0.01)], "undetermined"),       # neither reading gives a whole click
    ([("d", "v", 10000.0, 0.9), ("d", "w", 40.0, 0.05)], "fraction"),  # one clear row settles it
])
def test_the_unit_of_the_click_rate_is_settled_from_the_rows(rows, unit):
    assert reach.rate_unit(rows) == unit


def test_an_unsettled_click_rate_is_left_out_and_impressions_are_still_written(tmp_path):
    odd = _csv(("20261112", VIDEO_A, "subscribed", "NG", 10000, 0.9))
    report, why, _failed, _asked = _read(TWO_DAYS[:1], {"f12": odd})
    assert why == "" and report["window"]["impressions"] == 10000
    assert report["window"]["clicks"] is None and report["window"]["click_rate_percent"] is None
    assert report["videos"][0]["clicks"] is None and report["by_day"][0]["clicks"] is None
    assert "click rate not determined" in reach.headline(report)
    assert report["click_rate_samples_as_written"] == [[10000, 0.9]]  # enough to correct the rule from the file
    reach.write_reach(report, tmp_path)
    assert "the click rate could not be settled" in "\n".join(reader.reach_lines(report, {}))


def test_a_day_written_twice_is_read_once_from_the_later_file():
    older = _file("f12-old", "2026-11-12", "2026-11-14T09:00:00Z")
    fetched = []
    report, _why, _failed = reach.read_channel(
        "secret-place", "ACCESS", NOW, None, get=_google([], files=[older] + TWO_DAYS),
        fetch=_fetch({**STORE, "f12-old": _csv(("20261112", VIDEO_A, "x", "NG", 999, 0.5))}, fetched))
    assert report["window"]["impressions"] == 316 and report["files_read"] == 2
    assert not any("f12-old" in url for url in fetched)


def test_every_page_of_the_file_list_is_followed():
    pages = {"": {"reports": TWO_DAYS[:1], "nextPageToken": "next"}, "next": {"reports": TWO_DAYS[1:]}}
    report, _why, _failed = reach.read_channel("secret-place", "ACCESS", NOW, None,
                                               get=_google([], pages=pages), fetch=_fetch(STORE))
    assert report["files_read"] == 2


def test_days_youtube_no_longer_holds_stay_in_the_daily_list():
    previous = {"by_day": [{"day": "2026-09-01", "impressions": 50, "clicks": 4},
                           {"day": "2026-11-12", "impressions": 1, "clicks": 1},   # read again: replaced
                           {"day": "nonsense", "impressions": 9, "clicks": 9}]}
    report, _why, _failed, _asked = _read(TWO_DAYS, STORE, previous=previous)
    assert [row["day"] for row in report["by_day"]] == ["2026-09-01", "2026-11-12", "2026-11-13"]
    assert report["by_day"][0] == {"day": "2026-09-01", "impressions": 50, "clicks": 4}
    assert report["by_day"][1]["impressions"] == 216
    assert report["window"]["days"] == 2 and report["window"]["impressions"] == 316  # the window is this read only


# ------------------------------------------------------------- when there is nothing

@pytest.mark.parametrize("kwargs, expected", [
    ({"refuse": "403 PERMISSION_DENIED ACCESS_TOKEN_SCOPE_INSUFFICIENT"},
     "not granted yet (403 PERMISSION_DENIED ACCESS_TOKEN_SCOPE_INSUFFICIENT)"),
    ({"jobs": [{"id": "job-yt", "reportTypeId": reach.REPORT_TYPE, "systemManaged": True}]},
     "no reach job yet (the reporting-jobs run starts one)"),
    ({}, "reach job running since 2026-11-14, no daily file yet"),
])
def test_a_channel_with_nothing_to_read_gets_no_report_and_a_reason(kwargs, expected):
    report, why, _failed, _asked = _read([], {}, **kwargs)
    assert report is None and why == expected


def test_a_file_that_cannot_be_read_is_said_and_the_others_still_count():
    store = {"f12": DAY_12, "f13": "503 UNAVAILABLE"}
    report, why, failed, _asked = _read(TWO_DAYS, store)
    assert why == "" and report["files_read"] == 1 and failed == ["503 UNAVAILABLE"]
    assert report["window"]["impressions"] == 216


def test_a_file_without_the_expected_columns_is_refused_with_the_columns_it_has():
    store = {"f12": b"date,video_id,views\n20261112,%s,5\n" % VIDEO_A.encode()}
    report, why, _failed, _asked = _read(TWO_DAYS[:1], store)
    assert report is None
    assert "column missing: video_thumbnail_impressions, video_thumbnail_impressions_ctr" in why
    assert "columns: date, video_id, views" in why


def test_an_empty_file_is_a_day_with_nothing_in_it():
    report, why, failed, _asked = _read(TWO_DAYS[:1], {"f12": b""})
    assert why == "" and failed == [] and report["window"]["days"] == 0
    assert reach.headline(report) == "1 daily file read, no row in it yet"
    assert reader.reach_lines(report, {}) == []


# ---------------------------------------------------------------- what it may send

@pytest.mark.parametrize("url", [
    "http://youtubereporting.googleapis.com/v1/media/x",
    "https://youtubereporting.googleapis.com.evil.example/v1/media/x",
    "https://evil.example/?https://youtubereporting.googleapis.com/",
    "", None,
])
def test_the_token_is_never_sent_anywhere_but_googles_reporting_host(url, monkeypatch):
    def refuse_all(*_args, **_kwargs):
        raise AssertionError("a request left for " + str(url))
    monkeypatch.setattr(reach.urllib.request, "build_opener", refuse_all)
    assert reach.download(url, "ACCESS") == (None, "download address is not on youtubereporting.googleapis.com")


def test_a_redirect_is_not_followed():
    assert reach._NoRedirect().redirect_request(None, None, 302, "Found", {}, "https://elsewhere.example/") is None


def test_it_only_reads():
    source = (ROOT / "scripts/reach_reader.py").read_text(encoding="utf-8")
    assert "method=" not in source and "data=" not in source  # no POST, PUT or DELETE is built here
    assert "create_job" not in source and "reporting_jobs" not in source.split('"""', 2)[2]


def test_a_report_that_names_money_cannot_be_written(tmp_path):
    report, _why, _failed, _asked = _read(TWO_DAYS, STORE)
    for bad in ({**report, "estimated_revenue": 1}, {**report, "columns_seen": ["date", "estimated_partner_revenue"]},
                {**report, "videos": [{**report["videos"][0], "cpm": 2}]}):
        with pytest.raises(ValueError, match="money"):
            reach.write_reach(bad, tmp_path)
    with pytest.raises(ValueError, match="unknown channel"):
        reach.write_reach({**report, "channel": "someone-else"}, tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_a_money_column_in_the_file_is_never_carried_into_the_figures():
    header = HEADER.strip() + ",estimated_partner_revenue\n"
    data = (header + "20261112,UCxxxx,%s,subscribed,NG,40,0.05,12.34\n" % VIDEO_A).encode()
    rows, columns, why = reach.parse(data)
    assert why == "" and rows == [("2026-11-12", VIDEO_A, 40.0, 0.05)]
    report = reach.build("secret-place", rows, 1, NOW, columns=columns)
    assert "12.34" not in json.dumps({k: v for k, v in report.items() if k != "columns_seen"})


# ------------------------------------------------------------------- a whole run

def _run(monkeypatch, capsys, tmp_path, argv, granted=("secret-place",), files=TWO_DAYS, store=STORE, **kwargs):
    asked = []
    monkeypatch.setattr(reach.base, "access_token",
                        lambda cid, secret, refresh: ("ACCESS", "") if refresh else ("", "credentials not present in this run"))
    monkeypatch.setattr(reach.probe, "get", _google(asked, files=files, **kwargs))
    monkeypatch.setattr(reach, "download", _fetch(store))
    for profile in CHANNELS.values():
        for name in profile.secret_names().values():
            monkeypatch.delenv(name, raising=False)
    for channel in granted:
        names = CHANNELS[channel].secret_names()
        for key in ("client_id", "client_secret", "refresh_token"):
            monkeypatch.setenv(names[key], "SECRET-" + key)
    assert reach.main(argv + ["--out", str(tmp_path)]) == 0
    return capsys.readouterr().out


def test_a_run_writes_the_channel_with_files_and_names_the_rest_in_one_line(monkeypatch, capsys, tmp_path):
    out = _run(monkeypatch, capsys, tmp_path, [])
    annotations = [line for line in out.splitlines() if line.startswith("::")]
    assert annotations == [
        "::notice title=Reach secret-place::2 daily files (2026-11-12 to 2026-11-13): 316 thumbnail impressions "
        "on 3 videos, 8 clicks, 2.5% click rate; file written",
        "::notice title=Reach skipped::prayer2, prayer3, prayer4, prayer5, prayer6, prayer7, prayer8, prayer9, "
        "prayer10: credentials not present in this run; no file written"]
    assert all("," not in line.split("::", 2)[1] for line in annotations)  # a comma ends a title on GitHub
    assert sorted(p.name for p in tmp_path.iterdir()) == ["secret-place.reach.json"]
    assert list(reach.load(tmp_path)) == ["secret-place"]
    assert "SECRET-" not in out and "ACCESS" not in out and "UCxxxx" not in out


def test_a_dry_run_on_a_session_branch_writes_nothing(monkeypatch, capsys, tmp_path):
    out = _run(monkeypatch, capsys, tmp_path, ["--no-write"])
    assert "not written (dry run)" in out and "316 thumbnail impressions" in out
    assert list(tmp_path.iterdir()) == []


def test_a_channel_with_no_file_yet_keeps_the_file_it_has(monkeypatch, capsys, tmp_path):
    kept = {"schema": 1, "channel": "secret-place", "window": {"days": 1}, "videos": [], "kept": True}
    (tmp_path / "secret-place.reach.json").write_text(json.dumps(kept), encoding="utf-8")
    out = _run(monkeypatch, capsys, tmp_path, [], files=[])
    assert "::notice title=Reach skipped::secret-place: reach job running since 2026-11-14, no daily file yet; " \
           "no file written" in out
    assert json.loads((tmp_path / "secret-place.reach.json").read_text(encoding="utf-8")) == kept


def test_files_that_cannot_be_read_are_a_warning_not_a_failure(monkeypatch, capsys, tmp_path):
    out = _run(monkeypatch, capsys, tmp_path, [], store={"f12": "503 UNAVAILABLE", "f13": "503 UNAVAILABLE"})
    assert "::warning title=Reach skipped::secret-place: no daily file could be read (503 UNAVAILABLE); " \
           "no file written" in out
    out = _run(monkeypatch, capsys, tmp_path, [], store={"f12": DAY_12, "f13": "503 UNAVAILABLE"})
    assert out.startswith("::warning title=Reach secret-place::1 daily file (2026-11-12 to 2026-11-12): ")
    assert "; file written; 1 file not read (503 UNAVAILABLE)" in out


def test_one_channel_blowing_up_does_not_cost_the_others_or_the_job(monkeypatch, capsys, tmp_path):
    real = reach.read_channel

    def flaky(channel, *args, **kwargs):
        if channel == "prayer2":
            raise RuntimeError("anything")
        return real(channel, *args, **kwargs)
    monkeypatch.setattr(reach, "read_channel", flaky)
    out = _run(monkeypatch, capsys, tmp_path, [], granted=("secret-place", "prayer2"))
    assert "::warning title=Reach skipped::prayer2: stopped early (RuntimeError); no file written" in out
    assert (tmp_path / "secret-place.reach.json").exists()


# ------------------------------------------------------------- what the owner reads

def test_the_summary_shows_thumbnails_under_the_channel(tmp_path):
    report, _why, _failed, _asked = _read(TWO_DAYS, STORE)
    lines = "\n".join(reader.reach_lines(report, {VIDEO_A: "Psalm 91 | Night Prayer"}))
    assert "Thumbnails, 2026-11-12 to 2026-11-13 (2 days of YouTube's daily reach files): shown 316 times, " \
           "clicked 8 times, a click rate of 2.5%." in lines
    assert "| [Psalm 91 / Night Prayer](https://youtu.be/%s) | 300 | 7 | 2.3%% |" % VIDEO_A in lines
    assert "| [%s](https://youtu.be/%s) | 9 | 0 | 0%% |" % (VIDEO_C, VIDEO_C) in lines
    assert "The Shorts feed shows none" in lines
    assert not reader.MONEY.search(lines)


def test_the_analytics_summary_carries_the_reach_section_only_when_a_file_exists(tmp_path):
    from tests.test_analytics_reader import _report
    analytics, _why, _asked = _report()
    report, _why, _failed, _asked = _read(TWO_DAYS, STORE)
    reach.write_reach(report, tmp_path)
    (tmp_path / "prayer2.reach.json").write_text("{not json", encoding="utf-8")
    loaded = reader.load_reach(tmp_path)
    assert list(loaded) == ["secret-place"]
    with_reach = reader.summary({"secret-place": analytics}, tmp_path, reach=loaded)
    without = reader.summary({"secret-place": analytics}, tmp_path)
    assert "Videos by times shown" in with_reach and "Videos by times shown" not in without
    assert with_reach.index("Videos by watch time") < with_reach.index("Thumbnails, 2026-11-12")
    assert list(reader.load_reports(tmp_path)) == []  # a reach file is never mistaken for an analytics report


# ------------------------------------------------------------------ the workflow

def test_the_reach_files_are_read_by_the_job_that_cannot_write():
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    read, publish = workflow["jobs"]["read"], workflow["jobs"]["publish"]
    run = read["steps"][1]["run"]
    main_branch, session = run.split("else")
    assert main_branch.index("scripts/reach_reader.py") < main_branch.index("scripts/analytics_reader.py")
    assert "--no-write" not in main_branch
    assert session.count("--no-write") == 2 and "scripts/reach_reader.py --no-write" in session
    assert "reach_reader" not in json.dumps(publish) and "secrets." not in json.dumps(publish)
    assert "scripts/reach_reader.py" in workflow[True]["push"]["paths"]
    # The publishing job copies every JSON file the reading job wrote, the reach files with them.
    assert "cp -f /tmp/channel-analytics/*.json content/analytics/" in publish["steps"][-1]["run"]
