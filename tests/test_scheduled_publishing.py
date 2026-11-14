"""A long-form can be uploaded early and go public on its slot minute.

Rendering at the slot cannot land on the slot (GitHub starts scheduled runs
hours late; a render takes most of an hour). The alternative is to upload
private with a publish time and let YouTube publish. These tests pin the rules
that make that safe:

* it is OFF until a lead is configured, and off means byte-for-byte the old
  receipt and the old upload body;
* any doubt publishes now, never later and never not at all;
* a receipt for a scheduled video is dated with the public time and says it is
  not public yet, until the monitor has seen YouTube publish it;
* the lead can never reach the next slot, which would mark that slot served.
"""
from __future__ import annotations

import re
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline import publish_schedule  # noqa: E402
from scripts import confirm_scheduled_publish as confirm  # noqa: E402
from scripts import produce_plan  # noqa: E402

UTC = timezone.utc


def at(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 11, day, hour, minute, tzinfo=UTC)


# ---------------------------------------------------------------- the switch

def test_scheduled_publishing_is_off_by_default():
    assert produce_plan.PUBLISH_LEAD_MINUTES == 0
    assert produce_plan.publish_target(at(14, 6, 20)) is None
    assert publish_schedule.resolve_longform_publish_at(at(14, 6, 20), environ={}) is None


def test_the_repository_variable_overrides_the_lead_and_zero_switches_it_off():
    assert produce_plan.lead_minutes(None) == produce_plan.PUBLISH_LEAD_MINUTES
    assert produce_plan.lead_minutes("") == produce_plan.PUBLISH_LEAD_MINUTES
    assert produce_plan.lead_minutes("240") == 240
    assert produce_plan.lead_minutes("0") == 0
    assert produce_plan.lead_minutes("-5") == 0
    assert produce_plan.lead_minutes("soon") == produce_plan.PUBLISH_LEAD_MINUTES


# ---------------------------------------------------------------- the target

def test_the_public_time_is_the_slot_plus_the_lead():
    # Slots today: 06:14, 10:14, 14:14, 19:14, 23:14 UTC.
    assert produce_plan.publish_target(at(14, 6, 20), lead=180) == at(14, 9, 14)
    assert produce_plan.publish_target(at(14, 15, 0), lead=180) == at(14, 17, 14)
    # After midnight the slot is still yesterday's 23:14.
    assert produce_plan.publish_target(at(14, 0, 30), lead=180) == at(14, 2, 14)


def test_a_leg_that_finishes_too_close_to_the_time_publishes_now():
    assert produce_plan.publish_target(at(14, 8, 58), lead=180) == at(14, 9, 14)   # 16 min
    assert produce_plan.publish_target(at(14, 9, 0), lead=180) is None             # 14 min
    assert produce_plan.publish_target(at(14, 9, 30), lead=180) is None            # past


def test_a_lead_that_reaches_the_next_slot_is_refused():
    """14:14 -> 19:14 is five hours. A receipt dated 19:14 would serve BOTH slots."""
    assert produce_plan.next_slot(at(14, 14, 30)) == at(14, 19, 14)
    assert produce_plan.publish_target(at(14, 14, 30), lead=299) == at(14, 19, 13)
    assert produce_plan.publish_target(at(14, 14, 30), lead=300) is None
    assert produce_plan.publish_target(at(14, 14, 30), lead=600) is None
    # The smallest gap is four hours since the 10:14 and 23:14 slots were added
    # (14 November 2026): a lead of 240 or more is refused in the morning.
    assert produce_plan.publish_target(at(14, 6, 20), lead=239) == at(14, 10, 13)
    assert produce_plan.publish_target(at(14, 6, 20), lead=240) is None


def test_next_slot_crosses_midnight():
    assert produce_plan.next_slot(at(14, 19, 14)) == at(14, 23, 14)
    assert produce_plan.next_slot(at(14, 23, 14)) == at(15, 6, 14)
    assert produce_plan.next_slot(at(14, 2, 0)) == at(14, 6, 14)


# ---------------------------------------------------------------- resolver

def test_an_explicit_time_from_a_dispatch_wins():
    got = publish_schedule.resolve_longform_publish_at(
        at(14, 6, 20), environ={"PUBLISH_AT": "2026-11-14T10:14:00Z"})
    assert got == "2026-11-14T10:14:00Z"
    # Any timezone is accepted and sent to YouTube as UTC.
    got = publish_schedule.resolve_longform_publish_at(
        at(14, 6, 20), environ={"PUBLISH_AT": "2026-11-14T11:14:00+01:00"})
    assert got == "2026-11-14T10:14:00Z"


@pytest.mark.parametrize("raw", [
    "2026-11-14T06:30:00Z",        # ten minutes away
    "2026-11-13T14:14:00Z",        # yesterday
    "2026-11-14T10:14:00",         # no timezone: whose 10:14?
    "tomorrow afternoon",
    "2026-11-20T14:14:00Z",        # six days out: a typo, not a plan
    "2026-11-14T14:14:00Z",        # beyond the next slot (10:14): would cancel that slot
    "2026-11-14T10:15:00Z",        # one minute beyond it
])
def test_an_explicit_time_that_cannot_be_trusted_publishes_now(raw):
    assert publish_schedule.resolve_longform_publish_at(
        at(14, 6, 20), environ={"PUBLISH_AT": raw}) is None


def test_the_lead_from_the_environment_schedules_the_slot():
    got = publish_schedule.resolve_longform_publish_at(
        at(14, 6, 20), environ={"PUBLISH_LEAD_MINUTES": "180"})
    assert got == "2026-11-14T09:14:00Z"
    assert publish_schedule.resolve_longform_publish_at(
        at(14, 6, 20), environ={"PUBLISH_LEAD_MINUTES": "0"}) is None


def test_a_broken_schedule_lookup_never_blocks_the_release(monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("cannot read workflows")

    monkeypatch.setattr(produce_plan, "publish_target", boom)
    assert publish_schedule.resolve_longform_publish_at(
        at(14, 6, 20), environ={"PUBLISH_LEAD_MINUTES": "240"}) is None


# ---------------------------------------------------------------- the receipt

JOB = """---
id: "0901"
title: "Psalm 23 Morning Prayer"
slug: "psalm-23-morning-prayer"
channel: prayer2
format: longform
status: approved
privacy: public
---

## Narration

The Lord is my shepherd.
"""


@pytest.fixture()
def queue(tmp_path, monkeypatch):
    from pipeline import run

    published = tmp_path / "published"
    monkeypatch.setattr(run, "PUBLISHED_DIR", published)
    job = tmp_path / "queue" / "0901-psalm-23-morning-prayer.md"
    job.parent.mkdir()
    job.write_text(JOB, encoding="utf-8")
    return run, job, published


def frontmatter(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8").split("---", 2)[1])


def doc_for(job: Path):
    from pipeline.script_doc import parse_script

    return parse_script(job)


def test_an_immediate_upload_writes_the_receipt_it_always_wrote(queue):
    run, job, published = queue
    dest = run._mark_job_uploaded(job, doc_for(job), "abcdefghijk", "ok",
                                  scheduled_for=None, pinned_comment="failed")
    meta = frontmatter(dest)
    for key in ("scheduled_publish", "uploaded_at", "privacy_status", "pinned_comment_pending"):
        assert key not in meta, key
    stamp = datetime.fromisoformat(meta["published_at"].replace("Z", "+00:00"))
    assert abs((datetime.now(UTC) - stamp).total_seconds()) < 60


def test_a_scheduled_upload_is_dated_with_its_public_time_and_says_it_is_private(queue):
    run, job, published = queue
    public_at = (datetime.now(UTC) + timedelta(hours=3)).replace(microsecond=0)
    stamp = public_at.strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = doc_for(job)
    dest = run._mark_job_uploaded(job, doc, "abcdefghijk", "ok",
                                  scheduled_for=stamp, pinned_comment="failed")
    meta = frontmatter(dest)
    assert meta["status"] == "published"
    assert meta["published_at"] == stamp
    assert meta["published_on"] == stamp[:10]
    assert meta["scheduled_publish"] is True
    assert meta["privacy_status"] == "private"
    assert meta["pinned_comment_pending"] is True
    uploaded = datetime.fromisoformat(meta["uploaded_at"].replace("Z", "+00:00"))
    assert abs((datetime.now(UTC) - uploaded).total_seconds()) < 60
    assert doc.meta["scheduled_publish"] is True and doc.meta["published_at"] == stamp


def test_a_pinned_comment_that_was_posted_is_not_recorded_as_owed(queue):
    run, job, _ = queue
    stamp = (datetime.now(UTC) + timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    dest = run._mark_job_uploaded(job, doc_for(job), "abcdefghijk", "ok",
                                  scheduled_for=stamp, pinned_comment="ok")
    assert "pinned_comment_pending" not in frontmatter(dest)


def test_a_publish_time_already_past_is_an_ordinary_receipt(queue):
    run, job, _ = queue
    stamp = (datetime.now(UTC) - timedelta(minutes=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    dest = run._mark_job_uploaded(job, doc_for(job), "abcdefghijk", "ok", scheduled_for=stamp)
    meta = frontmatter(dest)
    assert "scheduled_publish" not in meta and meta["published_at"] != stamp


def test_a_recovered_private_video_keeps_its_schedule(queue):
    """A leg died after the upload; the next one finds the video on YouTube."""
    run, job, _ = queue
    public_at = (datetime.now(UTC) + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    uploaded = (datetime.now(UTC) - timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    video = {"video_id": "abcdefghijk", "privacy_status": "private", "upload_status": "processed",
             "published_at": uploaded, "publish_at": public_at}
    dest = run._mark_job_uploaded(job, doc_for(job), "abcdefghijk", recovered_video=video)
    meta = frontmatter(dest)
    assert meta["published_at"] == public_at
    assert meta["uploaded_at"] == uploaded
    assert meta["scheduled_publish"] is True and meta["privacy_status"] == "private"
    assert meta["receipt_recovered_from_youtube"] is True


def test_a_scheduled_receipt_serves_its_slot_and_a_failed_one_does_not(queue):
    from scripts import scheduler_supervisor as sup

    run, job, published = queue
    stamp = "2099-01-01T10:14:00Z"
    dest = run._mark_job_uploaded(job, doc_for(job), "abcdefghijk", "ok", scheduled_for=stamp)
    slot = datetime(2099, 1, 1, 6, 14, tzinfo=UTC)
    assert sup.published_channels_since(slot, published) == {"prayer2"}
    text = dest.read_text(encoding="utf-8")
    dest.write_text(text.replace("scheduled_publish: true",
                                 "scheduled_publish: true\nscheduled_publish_failed: true"),
                    encoding="utf-8")
    assert sup.published_channels_since(slot, published) == set()


# ---------------------------------------------------------------- the upload

class FakeRequest:
    def __init__(self, answer=None, error=None):
        self.answer, self.error = answer, error

    def next_chunk(self):
        if self.error:
            raise self.error
        return None, self.answer

    def execute(self):
        return {}


class FakeYouTube:
    """Records every videos.insert body; refuses publishAt when told to."""

    def __init__(self, refuse_publish_at=False):
        self.bodies: list[dict] = []
        self.refuse = refuse_publish_at

    def videos(self):
        outer = self

        class Videos:
            def insert(self, part, body, media_body):
                import copy

                outer.bodies.append(copy.deepcopy(body))
                status = dict(body["status"])
                if outer.refuse and "publishAt" in status:
                    return FakeRequest(error=RuntimeError(
                        "<HttpError 400 ... 'reason': 'invalidPublishAt'>"))
                return FakeRequest(answer={"id": "abcdefghijk", "status": status})

        return Videos()

    def __getattr__(self, name):
        def resource():
            raise RuntimeError(f"{name} is not available in this test")

        return resource


@pytest.fixture()
def uploader(tmp_path, monkeypatch):
    from pipeline import upload as up

    video = tmp_path / "final.mp4"
    video.write_bytes(b"0" * 32)
    fake = FakeYouTube()
    discovery = types.ModuleType("googleapiclient.discovery")
    discovery.build = lambda *a, **k: fake
    http = types.ModuleType("googleapiclient.http")
    http.MediaFileUpload = lambda *a, **k: object()
    monkeypatch.setitem(sys.modules, "googleapiclient.discovery", discovery)
    monkeypatch.setitem(sys.modules, "googleapiclient.http", http)
    monkeypatch.setattr(up, "_credentials", lambda: object())
    monkeypatch.setattr(up, "check_existing_channel_duplicate", lambda *a, **k: None)
    monkeypatch.setattr(up.CONFIG, "allow_duplicate_uploads", False, raising=False)
    monkeypatch.setattr(up.CONFIG, "playlist_id", "", raising=False)
    monkeypatch.setattr(up.CONFIG, "auto_publish", True, raising=False)
    monkeypatch.setattr(up.CONFIG, "default_privacy", "private", raising=False)
    monkeypatch.delenv("PUBLISH_AT", raising=False)
    monkeypatch.delenv("PUBLISH_LEAD_MINUTES", raising=False)
    job = tmp_path / "0901-psalm-23-morning-prayer.md"
    job.write_text(JOB.replace("privacy: public\n", ""), encoding="utf-8")
    return up, fake, doc_for(job), video


def soon(hours: float = 3) -> str:
    """A publish time the resolver accepts whenever the suite runs: far enough
    ahead, and never past the next production slot."""
    now = datetime.now(UTC)
    limit = produce_plan.next_slot(now)
    when = min(now + timedelta(hours=hours), limit)
    if when - now < timedelta(minutes=produce_plan.PUBLISH_MARGIN_MINUTES + 2):
        pytest.skip("within minutes of a production slot; no valid explicit time exists")
    return when.replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_with_nothing_configured_the_upload_is_public_at_once(uploader):
    up, fake, doc, video = uploader
    result = up.upload(doc, video)
    assert fake.bodies[0]["status"]["privacyStatus"] == "public"
    assert "publishAt" not in fake.bodies[0]["status"]
    assert result.scheduled_for == "" and result.privacy_status == "public"


def test_a_publish_time_uploads_private_and_reports_when_it_goes_public(uploader, monkeypatch):
    up, fake, doc, video = uploader
    when = soon()
    monkeypatch.setenv("PUBLISH_AT", when)
    result = up.upload(doc, video)
    assert fake.bodies[0]["status"]["privacyStatus"] == "private"
    assert fake.bodies[0]["status"]["publishAt"] == when
    assert result.scheduled_for == when and result.privacy_status == "private"
    # The comment could not be posted in this rig: it is reported, not hidden.
    assert result.pinned_comment in {"failed", "skipped"}


def test_youtube_refusing_the_time_still_releases_the_video(uploader, monkeypatch):
    up, fake, doc, video = uploader
    fake.refuse = True
    monkeypatch.setenv("PUBLISH_AT", soon())
    result = up.upload(doc, video)
    assert len(fake.bodies) == 2
    assert "publishAt" not in fake.bodies[1]["status"]
    assert fake.bodies[1]["status"]["privacyStatus"] == "public"
    assert result.scheduled_for == "" and result.privacy_status == "public"


def test_an_upload_meant_to_stay_private_is_never_given_a_publish_time(uploader, monkeypatch):
    """A publish time makes a video public. Auto-publish off means it must not."""
    up, fake, doc, video = uploader
    monkeypatch.setattr(up.CONFIG, "auto_publish", False, raising=False)
    monkeypatch.setenv("PUBLISH_AT", soon())
    result = up.upload(doc, video)
    assert fake.bodies[0]["status"]["privacyStatus"] == "private"
    assert "publishAt" not in fake.bodies[0]["status"]
    assert result.scheduled_for == ""


def test_a_short_is_never_scheduled_by_the_long_form_rule(uploader, monkeypatch):
    up, fake, doc, video = uploader
    doc.meta["format"] = "short"
    monkeypatch.setenv("PUBLISH_AT", soon())
    up.upload(doc, video)
    assert "publishAt" not in fake.bodies[0]["status"]


# ---------------------------------------------------------------- the confirmation

class StatusYouTube:
    def __init__(self, status: dict | None):
        self.status, self.updates, self.comments = status, [], []

    def videos(self):
        outer = self

        class Videos:
            def list(self, part, id):
                items = [] if outer.status is None else [{"id": id, "status": dict(outer.status)}]
                return types.SimpleNamespace(execute=lambda: {"items": items})

            def update(self, part, body):
                outer.updates.append(body)
                outer.status["privacyStatus"] = body["status"]["privacyStatus"]
                return types.SimpleNamespace(execute=lambda: {})

        return Videos()

    def commentThreads(self):
        outer = self

        class Threads:
            def insert(self, part, body):
                outer.comments.append(body)
                return types.SimpleNamespace(execute=lambda: {"id": "comment-1"})

        return Threads()


@pytest.fixture()
def scheduled(queue):
    run, job, published = queue
    planned = datetime(2099, 1, 1, 10, 14, tzinfo=UTC)
    dest = run._mark_job_uploaded(job, doc_for(job), "abcdefghijk", "ok",
                                  scheduled_for="2099-01-01T10:14:00Z", pinned_comment="failed")
    return dest, published, planned


def run_confirm(published, now, youtube):
    return confirm.confirm_channel("prayer2", now=now, youtube_client=youtube,
                                   published_dir=published)


def test_before_its_time_nothing_is_asked_of_youtube(scheduled):
    dest, published, planned = scheduled

    class Untouchable:
        def __getattr__(self, name):
            raise AssertionError("no API call is allowed before the publish time")

    rows = run_confirm(published, planned - timedelta(minutes=1), Untouchable())
    assert rows[0]["state"] == "waiting for its time"
    assert frontmatter(dest)["scheduled_publish"] is True


def test_a_video_youtube_published_is_confirmed_and_gets_its_comment(scheduled):
    dest, published, planned = scheduled
    youtube = StatusYouTube({"privacyStatus": "public", "uploadStatus": "processed"})
    rows = run_confirm(published, planned + timedelta(minutes=3), youtube)
    meta = frontmatter(dest)
    assert rows[0]["state"] == "confirmed public"
    assert meta["scheduled_publish"] is False and meta["privacy_status"] == "public"
    assert meta["published_at"] == "2099-01-01T10:14:00Z"      # the plan is not rewritten
    assert meta["publish_confirmed_at"] == "2099-01-01T10:17:00Z"
    assert len(youtube.comments) == 1 and "pinned_comment_pending" not in meta
    assert youtube.updates == []
    # Settled: the next pass has nothing to do.
    assert run_confirm(published, planned + timedelta(hours=1), youtube) == []


def test_still_private_just_after_its_time_is_given_a_few_minutes(scheduled):
    dest, published, planned = scheduled
    youtube = StatusYouTube({"privacyStatus": "private", "uploadStatus": "processed"})
    run_confirm(published, planned + timedelta(minutes=5), youtube)
    assert youtube.updates == [] and frontmatter(dest)["scheduled_publish"] is True


def test_still_private_twenty_minutes_late_is_published_here(scheduled):
    dest, published, planned = scheduled
    youtube = StatusYouTube({"privacyStatus": "private", "uploadStatus": "processed",
                             "embeddable": True, "selfDeclaredMadeForKids": False,
                             "publishAt": "2099-01-01T10:14:00Z"})
    rows = run_confirm(published, planned + timedelta(minutes=25), youtube)
    assert len(youtube.updates) == 1
    sent = youtube.updates[0]["status"]
    assert sent["privacyStatus"] == "public" and "publishAt" not in sent
    assert sent["embeddable"] is True and sent["selfDeclaredMadeForKids"] is False
    assert rows[0]["published_here"] is True
    assert frontmatter(dest)["scheduled_publish"] is False


@pytest.mark.parametrize("status", [
    None,                                                             # the video is gone
    {"privacyStatus": "private", "uploadStatus": "rejected", "rejectionReason": "duplicate"},
])
def test_a_video_that_will_never_go_public_stops_serving_its_slot(scheduled, status):
    from scripts import scheduler_supervisor as sup

    dest, published, planned = scheduled
    youtube = StatusYouTube(status)
    run_confirm(published, planned + timedelta(minutes=30), youtube)
    meta = frontmatter(dest)
    assert meta["scheduled_publish_failed"] is True and meta["scheduled_publish_error"]
    assert youtube.updates == []
    assert sup.published_channels_since(planned - timedelta(hours=4), published) == set()


def test_another_channels_receipt_is_left_alone(scheduled):
    dest, published, planned = scheduled
    youtube = StatusYouTube({"privacyStatus": "public", "uploadStatus": "processed"})
    rows = confirm.confirm_channel("prayer3", now=planned + timedelta(hours=1),
                                   youtube_client=youtube, published_dir=published)
    assert rows == [] and frontmatter(dest)["scheduled_publish"] is True


# ---------------------------------------------------------------- the wiring

def test_the_workflows_carry_the_switch_and_the_confirmation():
    produce = (ROOT / ".github/workflows/produce.yml").read_text(encoding="utf-8")
    data = yaml.safe_load(produce)
    assert "publish_at" in data[True]["workflow_dispatch"]["inputs"]
    release = next(s for s in data["jobs"]["produce"]["steps"]
                   if s.get("name") == "Render and upload the long-form edition")
    # Manual dispatch input, or the payload of the publish-now repository_dispatch.
    assert release["env"]["PUBLISH_AT"] == \
        "${{ inputs.publish_at || github.event.client_payload.publish_at }}"
    assert release["env"]["PUBLISH_LEAD_MINUTES"] == "${{ vars.PRODUCE_PUBLISH_LEAD_MINUTES }}"
    monitor = (ROOT / ".github/workflows/monitor.yml").read_text(encoding="utf-8")
    # Before the thumbnail pass, and unable to stop it.
    assert re.search(r"python -m scripts\.confirm_scheduled_publish --all-channels \\\n\s+"
                     r"\|\| echo [^\n]+\n\s+"
                     r"python -m scripts\.sync_published_thumbnails --all-channels", monitor)


def test_the_configured_lead_fits_inside_every_gap_between_slots():
    """Whatever lead is committed, no slot's public time may reach the next slot."""
    lead = produce_plan.PUBLISH_LEAD_MINUTES
    if lead == 0:
        return
    slot = produce_plan.current_slot(at(14, 12, 0))
    for _ in range(6):
        following = produce_plan.next_slot(slot)
        assert slot + timedelta(minutes=lead) < following
        slot = following


def test_inspecting_a_scheduled_video_reports_its_publish_time(monkeypatch):
    """Recovery after a dead leg: YouTube's publishedAt is only the upload time."""
    from pipeline import upload as up

    title = "Psalm 23 Morning Prayer"
    item = {"id": "abcdefghijk",
            "snippet": {"channelId": "UC-test", "title": title,
                        "publishedAt": "2026-11-14T08:01:00Z"},
            "status": {"privacyStatus": "private", "uploadStatus": "processed",
                       "publishAt": "2026-11-14T14:14:00Z"},
            "contentDetails": {"duration": "PT5M"}}

    class Client:
        def videos(self):
            return types.SimpleNamespace(
                list=lambda **_k: types.SimpleNamespace(execute=lambda: {"items": [item]}))

    discovery = types.ModuleType("googleapiclient.discovery")
    discovery.build = lambda *a, **k: Client()
    monkeypatch.setitem(sys.modules, "googleapiclient.discovery", discovery)
    monkeypatch.setattr(up, "_credentials", lambda: object())
    monkeypatch.setattr(up, "verify_target_channel", lambda _yt: {"id": "UC-test"})
    monkeypatch.setattr(up.CONFIG, "expected_youtube_channel_id", "UC-test", raising=False)
    info = up.inspect_existing_longform("abcdefghijk", title)
    assert info["publish_at"] == "2026-11-14T14:14:00Z"
    assert info["published_at"] == "2026-11-14T08:01:00Z"
    item["status"] = {"privacyStatus": "public", "uploadStatus": "processed"}
    assert "publish_at" not in up.inspect_existing_longform("abcdefghijk", title)


# ------------------------------------------- a time written on the job itself

def stamped_job(tmp_path, line: str):
    job = tmp_path / "0902-stamped.md"
    job.write_text(JOB.replace("privacy: public\n", line + "\n"), encoding="utf-8")
    return doc_for(job)


@pytest.mark.parametrize("quoted", [True, False])   # unquoted: YAML makes it a datetime
def test_a_publish_time_written_on_the_job_is_sent_as_text(uploader, tmp_path, quoted):
    """The oldest way to schedule one video: a line in its own front matter."""
    up, fake, _doc, video = uploader
    when = soon()
    line = f'publish_at: "{when}"' if quoted else f"publish_at: {when}"
    result = up.upload(stamped_job(tmp_path, line), video)
    assert fake.bodies[0]["status"]["privacyStatus"] == "private"
    assert fake.bodies[0]["status"]["publishAt"] == when
    assert result.scheduled_for == when


def test_the_job_may_simply_say_next_slot(uploader, tmp_path):
    up, fake, _doc, video = uploader
    now = datetime.now(UTC)
    following = produce_plan.next_slot(now)
    if following - now < timedelta(minutes=produce_plan.PUBLISH_MARGIN_MINUTES + 2):
        pytest.skip("within minutes of a production slot")
    result = up.upload(stamped_job(tmp_path, "publish_at: next-slot"), video)
    want = following.strftime("%Y-%m-%dT%H:%M:%SZ")
    assert fake.bodies[0]["status"]["publishAt"] == want and result.scheduled_for == want


def test_next_slot_is_the_slot_after_now_and_never_closer_than_the_margin():
    resolve = publish_schedule.resolve_longform_publish_at
    assert resolve(at(13, 16, 40), environ={}, requested="next-slot") == "2026-11-13T19:14:00Z"
    assert resolve(at(13, 19, 20), environ={}, requested="Next-Slot") == "2026-11-13T23:14:00Z"
    assert resolve(at(13, 23, 20), environ={}, requested="Next-Slot") == "2026-11-14T06:14:00Z"
    assert resolve(at(13, 16, 40), environ={"PUBLISH_AT": "next-slot"}) == "2026-11-13T19:14:00Z"
    # Twelve minutes before the slot there is no room left: public now.
    assert resolve(at(13, 19, 2), environ={}, requested="next-slot") is None


def test_a_time_on_the_job_obeys_the_same_limits_and_outranks_the_run():
    resolve = publish_schedule.resolve_longform_publish_at
    now = at(13, 16, 40)
    # Past the next slot (19:14): refused, public now.
    assert resolve(now, environ={}, requested="2026-11-14T14:14:00Z") is None
    # Too close, already past, or no timezone: public now.
    assert resolve(now, environ={}, requested="2026-11-13T16:50:00Z") is None
    assert resolve(now, environ={}, requested="2026-11-13T12:00:00Z") is None
    assert resolve(now, environ={}, requested="2026-11-13T18:00:00") is None
    # The job names one video; the environment names the whole run.
    assert resolve(now, environ={"PUBLISH_AT": "2026-11-13T18:00:00Z", "PUBLISH_LEAD_MINUTES": "270"},
                   requested="2026-11-13T19:14:00Z") == "2026-11-13T19:14:00Z"
    # A refused time on the job does not fall through to another source.
    assert resolve(now, environ={"PUBLISH_AT": "2026-11-13T18:00:00Z"},
                   requested="2026-11-20T18:00:00Z") is None


def test_a_time_too_far_ahead_on_the_job_publishes_now(uploader, tmp_path):
    up, fake, _doc, video = uploader
    result = up.upload(stamped_job(tmp_path, 'publish_at: "2099-01-01T14:14:00Z"'), video)
    assert fake.bodies[0]["status"]["privacyStatus"] == "public"
    assert "publishAt" not in fake.bodies[0]["status"] and result.scheduled_for == ""


def test_a_refused_time_written_on_the_job_still_releases_the_video(uploader, tmp_path):
    up, fake, _doc, video = uploader
    fake.refuse = True
    result = up.upload(stamped_job(tmp_path, f'publish_at: "{soon()}"'), video)
    assert len(fake.bodies) == 2 and "publishAt" not in fake.bodies[1]["status"]
    assert result.privacy_status == "public" and result.scheduled_for == ""


def test_the_word_is_never_sent_to_youtube_for_an_upload_that_stays_private(uploader, tmp_path):
    up, fake, _doc, video = uploader
    up.CONFIG.auto_publish = False          # private stays private: no schedule applies
    up.upload(stamped_job(tmp_path, "publish_at: next-slot"), video)
    assert fake.bodies[0]["status"]["privacyStatus"] == "private"
    assert "publishAt" not in fake.bodies[0]["status"]


# ------------------------------------ nothing else may publish a held video early

def test_the_thumbnail_pass_does_not_promote_a_video_held_for_its_time():
    """`sync_published_thumbnails` makes a private long-form public when its
    receipt wants public. A scheduled video is private on purpose."""
    source = (ROOT / "scripts" / "sync_published_thumbnails.py").read_text(encoding="utf-8")
    block = source[source.index("# 1. Promote valid full-length prayers"):
                   source.index("yt.videos().update(", source.index("# 1. Promote valid"))]
    assert 'not st.get("publishAt")' in block
    assert 'doc.meta.get("scheduled_publish")' in block


def test_only_the_confirmation_and_the_thumbnail_pass_can_change_privacy():
    """Every place that writes `privacyStatus` to a live video is known. A new
    one has to decide what it does with a scheduled video before it merges."""
    writers = set()
    for folder in ("pipeline", "scripts"):
        for path in sorted((ROOT / folder).glob("*.py")):
            text = path.read_text(encoding="utf-8")
            if "videos().update(" in text.replace("\n", "").replace(" ", "") \
                    or ".update(part=" in text:
                if '"privacyStatus"' in text:
                    writers.add(f"{folder}/{path.name}")
    assert writers == {
        "pipeline/upload.py",                      # snippet-only update; insert sets privacy
        "scripts/cleanup_duplicate_shorts.py",     # manual tool, Shorts, makes private
        "scripts/confirm_scheduled_publish.py",    # owns scheduled videos
        "scripts/sync_published_thumbnails.py",    # guarded above
    }


# ------------------------------------------------------- the owed comment, once

class CommentingYouTube(StatusYouTube):
    """Also answers who the channel is and what is already under the video."""

    def __init__(self, status, existing_authors=(), refuse_comment=False):
        super().__init__(status)
        self.existing, self.refuse_comment, self.lists = list(existing_authors), refuse_comment, 0

    def channels(self):
        return types.SimpleNamespace(list=lambda part, mine: types.SimpleNamespace(
            execute=lambda: {"items": [{"id": "UC-own"}]}))

    def commentThreads(self):
        outer = self

        class Threads:
            def list(self, **kwargs):
                outer.lists += 1
                items = [{"snippet": {"topLevelComment": {"snippet": {
                    "authorChannelId": {"value": author}}}}} for author in outer.existing]
                return types.SimpleNamespace(execute=lambda: {"items": items})

            def insert(self, part, body):
                def execute():
                    if outer.refuse_comment:
                        raise RuntimeError("403 commentsDisabled")
                    outer.comments.append(body)
                    outer.existing.append("UC-own")
                    return {"id": "comment-1"}
                return types.SimpleNamespace(execute=execute)

        return Threads()


PUBLIC = {"privacyStatus": "public", "uploadStatus": "processed"}


def test_a_comment_that_is_already_there_is_not_posted_again(scheduled):
    """The pass posted it, then its receipt edit was lost (push refused)."""
    dest, published, planned = scheduled
    before = dest.read_text(encoding="utf-8")
    youtube = CommentingYouTube(PUBLIC, existing_authors=["UC-viewer"])
    run_confirm(published, planned + timedelta(minutes=3), youtube)
    assert len(youtube.comments) == 1
    dest.write_text(before, encoding="utf-8")            # the edit never reached main
    rows = run_confirm(published, planned + timedelta(hours=3), youtube)
    assert len(youtube.comments) == 1                    # asked YouTube, did not repeat it
    assert rows[0]["pinned_comment"] == "posted"
    assert "pinned_comment_pending" not in frontmatter(dest)


def test_a_viewers_comment_is_not_mistaken_for_the_channels(scheduled):
    dest, published, planned = scheduled
    youtube = CommentingYouTube(PUBLIC, existing_authors=["UC-viewer", "UC-another"])
    run_confirm(published, planned + timedelta(minutes=3), youtube)
    assert len(youtube.comments) == 1


def test_a_refused_comment_is_retried_on_later_passes_then_given_up(scheduled):
    dest, published, planned = scheduled
    youtube = CommentingYouTube(PUBLIC, refuse_comment=True)
    rows = run_confirm(published, planned + timedelta(minutes=3), youtube)
    meta = frontmatter(dest)
    assert meta["scheduled_publish"] is False and meta["pinned_comment_pending"] is True
    assert meta["pinned_comment_attempts"] == 1 and "still owed" in rows[0]["pinned_comment"]
    # The publish is settled; only the comment is still owed, and it is revisited.
    rows = run_confirm(published, planned + timedelta(hours=3), youtube)
    assert rows[0]["state"] == "confirmed; comment owed"
    assert frontmatter(dest)["pinned_comment_attempts"] == 2
    rows = run_confirm(published, planned + timedelta(hours=6), youtube)
    meta = frontmatter(dest)
    assert "given up" in rows[0]["pinned_comment"]
    assert meta["pinned_comment_failed"] is True and "pinned_comment_pending" not in meta
    assert run_confirm(published, planned + timedelta(hours=9), youtube) == []
    assert youtube.updates == []


def test_a_comment_refused_once_is_posted_on_the_next_pass(scheduled):
    dest, published, planned = scheduled
    youtube = CommentingYouTube(PUBLIC, refuse_comment=True)
    run_confirm(published, planned + timedelta(minutes=3), youtube)
    youtube.refuse_comment = False
    rows = run_confirm(published, planned + timedelta(hours=3), youtube)
    meta = frontmatter(dest)
    assert rows[0]["pinned_comment"] == "posted" and len(youtube.comments) == 1
    assert "pinned_comment_pending" not in meta and "pinned_comment_attempts" not in meta
