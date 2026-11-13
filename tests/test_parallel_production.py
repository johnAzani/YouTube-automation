"""Channels are produced side by side, and a slot is served once.

Measured 8-13 November (docs/PARALLEL_PRODUCTION_2026-11-13.md): ten channels in
a row took 537 minutes, production held ``content-state`` for 1,412 minutes of
12 November, and that day published 17 long-forms of the 30 scheduled, with
three channels getting none. These tests pin what replaced the serial matrix:

* the plan job sets the lane count, a dispatch can carry several channels, and a
  late schedule event does not publish a slot that already has its video;
* the supervisor recovers every missing channel in ONE dispatch, tries a failing
  channel twice per slot, and steps in after 30 minutes rather than 90;
* nothing two lanes write can share a path (ids are allocated in per-channel
  blocks), and five lanes finishing in the same minute all land their receipts.
"""
from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import produce_plan as plan  # noqa: E402
from scripts import scheduler_supervisor as sup  # noqa: E402

UTC = timezone.utc
WORKFLOW = ROOT / ".github" / "workflows" / "produce.yml"


def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def plan_script() -> str:
    step = next(s for s in workflow()["jobs"]["plan"]["steps"] if s.get("id") == "plan")
    return step["run"]


# --- the plan job ---------------------------------------------------------------

def test_channel_list_parsing_keeps_order_and_drops_repeats():
    assert plan.parse_channels(" prayer4, prayer7 prayer4,,") == ["prayer4", "prayer7"]
    assert plan.parse_channels("PRAYER5\nprayer6") == ["prayer5", "prayer6"]
    assert plan.parse_channels("") == [] and plan.parse_channels(None) == []


@pytest.mark.parametrize("raw,count,expected", [
    ("", 10, 5),          # unset variable: five lanes
    (None, 10, 5),
    ("1", 10, 1),         # the switch back to one at a time
    ("10", 10, 10),
    ("99", 10, 10),       # never more lanes than the ceiling
    ("8", 3, 3),          # never more lanes than legs
    ("abc", 10, 5),       # a typo in the variable must not stop production
    ("0", 10, 5),
    ("-2", 10, 5),
    ("5", 0, 1),          # an empty matrix still yields a valid number
])
def test_lane_count_is_always_a_valid_matrix_value(raw, count, expected):
    assert plan.max_parallel(raw, count) == expected


def _receipt(directory: Path, name: str, channel: str, when: str, fmt: str = "longform") -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(
        "---\n"
        f'id: "{name[:4]}"\ntitle: "T {name}"\nslug: {name[:-3]}\nstatus: published\n'
        f"format: {fmt}\nchannel: {channel}\n"
        f'published_at: "{when}"\nyoutube_video_id: "vid{name[:4]}"\n'
        "---\n\nbody\n", encoding="utf-8")


def test_a_late_schedule_event_skips_channels_the_slot_already_served(tmp_path):
    """Slot 14:14. The supervisor's run published prayer4 at 15:02; the schedule
    event arrives at 17:50. prayer4 must not get a second video for that slot."""
    pub = tmp_path / "published"
    _receipt(pub, "0207-a.md", "prayer4", "2026-11-12T15:02:00Z")
    _receipt(pub, "0304-b.md", "prayer5", "2026-11-12T13:50:00Z")       # before the slot
    _receipt(pub, "short-x.md", "prayer6", "2026-11-12T15:10:00Z", fmt="short")  # not a long-form
    now = datetime(2026, 11, 12, 17, 50, tzinfo=UTC)
    owed, served, slot = plan.split_served(["prayer4", "prayer5", "prayer6"], now, pub)
    assert slot == datetime(2026, 11, 12, 14, 14, tzinfo=UTC)
    assert served == ["prayer4"]
    assert owed == ["prayer5", "prayer6"]


def test_an_event_delivered_after_the_next_slot_serves_the_slot_it_lands_in(tmp_path):
    pub = tmp_path / "published"
    _receipt(pub, "0207-a.md", "prayer4", "2026-11-12T15:02:00Z")
    now = datetime(2026, 11, 12, 19, 40, tzinfo=UTC)      # the 14:14 event, 5h26m late
    owed, served, slot = plan.split_served(["prayer4"], now, pub)
    assert slot == datetime(2026, 11, 12, 19, 14, tzinfo=UTC)
    assert owed == ["prayer4"] and served == []


def test_the_slots_the_plan_uses_are_the_crons_in_the_workflow():
    crons = [row["cron"] for row in workflow()[True]["schedule"]]
    assert sorted(crons) == ["14 14 * * *", "14 19 * * *", "14 6 * * *"]
    assert plan.current_slot(datetime(2026, 11, 13, 6, 13, tzinfo=UTC)) == \
        datetime(2026, 11, 12, 19, 14, tzinfo=UTC)
    assert plan.current_slot(datetime(2026, 11, 13, 6, 14, tzinfo=UTC)) == \
        datetime(2026, 11, 13, 6, 14, tzinfo=UTC)


def test_the_plan_step_runs_on_a_bare_runner_python():
    """The plan job installs nothing, so the helper must import with stdlib only."""
    code = (
        "import sys; sys.path.insert(0, '.')\n"
        "import builtins; real = builtins.__import__\n"
        "def guard(name, *a, **k):\n"
        "    if name.split('.')[0] in {'yaml', 'requests', 'dotenv', 'google'}:\n"
        "        raise ImportError('not installed on the plan runner: ' + name)\n"
        "    return real(name, *a, **k)\n"
        "builtins.__import__ = guard\n"
        "from datetime import datetime, timezone\n"
        "from scripts import produce_plan as p\n"
        "owed, served, slot = p.split_served(['secret-place', 'prayer2'],\n"
        "    datetime(2026, 11, 13, 7, 0, tzinfo=timezone.utc))\n"
        "assert slot is not None and sorted(owed + served) == ['prayer2', 'secret-place']\n"
        "print(p.max_parallel('', 10))\n"
    )
    proc = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "5"


def test_workflow_wires_lanes_and_multi_channel_dispatch():
    data = workflow()
    produce = data["jobs"]["produce"]
    assert produce["strategy"]["max-parallel"] == \
        "${{ fromJSON(needs.plan.outputs.max_parallel || '1') }}"
    assert produce["strategy"]["fail-fast"] is False
    assert data["jobs"]["plan"]["outputs"]["max_parallel"] == "${{ steps.plan.outputs.max_parallel }}"
    inputs = data[True]["workflow_dispatch"]["inputs"]
    assert inputs["channels"]["type"] == "string" and inputs["channels"]["default"] == ""
    assert inputs["channel"]["type"] == "choice"          # the single-channel form still works
    env = next(s for s in data["jobs"]["plan"]["steps"] if s.get("id") == "plan")["env"]
    assert env["INPUT_CHANNELS"] == "${{ inputs.channels }}"
    assert env["CLIENT_CHANNELS"] == "${{ github.event.client_payload.channels }}"
    assert env["PRODUCE_MAX_PARALLEL"] == "${{ vars.PRODUCE_MAX_PARALLEL }}"
    script = plan_script()
    assert "produce_plan.split_served(channels, now)" in script
    assert 'fh.write(f"max_parallel={lanes}\\n")' in script
    # The slot check can only ever remove channels from a *scheduled* run.
    assert script.index('if event == "schedule":') < script.index("split_served") \
        < script.index('elif event == "workflow_dispatch":')
    # Unknown channels are still refused after the list is parsed.
    assert script.index("parse_channels") < script.index("Refusing unknown or inactive")


def test_the_plan_reads_receipts_from_the_current_tip_not_the_creation_commit():
    """Without an explicit ref, checkout pins the commit the run was created at.
    After hours in the queue that tree lacks the receipts the slot check needs."""
    steps = workflow()["jobs"]["plan"]["steps"]
    checkout = steps[0]
    assert checkout["uses"].startswith("actions/checkout@")
    assert checkout["with"]["ref"] == "${{ github.ref }}"
    assert steps[1].get("id") == "plan"


def _run_plan(tmp_path, env: dict) -> dict:
    out = tmp_path / "gh_output"
    out.write_text("")
    base = {"PATH": "/usr/bin:/bin", "GITHUB_OUTPUT": str(out), "HOME": str(tmp_path)}
    script = plan_script().replace("python3 - <<'PY'", f'"{sys.executable}" - <<\'PY\'')
    proc = subprocess.run(["bash", "-c", script], cwd=ROOT, env={**base, **env},
                          capture_output=True, text=True)
    values = dict(line.split("=", 1) for line in out.read_text().splitlines() if "=" in line)
    return {"rc": proc.returncode, "log": proc.stdout + proc.stderr, **values}


def test_plan_step_executed_for_a_multi_channel_dispatch(tmp_path):
    """Run the real plan script from the workflow, not a copy of it."""
    result = _run_plan(tmp_path, {"EVENT_NAME": "workflow_dispatch",
                                  "INPUT_CHANNEL": "secret-place",
                                  "INPUT_CHANNELS": "prayer4, prayer7,prayer4"})
    assert result["rc"] == 0, result["log"]
    assert result["channels"] == '["prayer4", "prayer7"]'
    assert result["max_parallel"] == "2"


def test_plan_step_executed_for_a_single_channel_dispatch(tmp_path):
    result = _run_plan(tmp_path, {"EVENT_NAME": "workflow_dispatch", "INPUT_CHANNEL": "prayer6",
                                  "INPUT_CHANNELS": "", "PRODUCE_MAX_PARALLEL": "7"})
    assert result["rc"] == 0, result["log"]
    assert result["channels"] == '["prayer6"]' and result["max_parallel"] == "1"


def test_plan_step_refuses_an_unknown_channel_in_the_list(tmp_path):
    result = _run_plan(tmp_path, {"EVENT_NAME": "workflow_dispatch",
                                  "INPUT_CHANNELS": "prayer4,not-a-channel"})
    assert result["rc"] != 0
    assert "Refusing unknown or inactive production channel(s): not-a-channel" in result["log"]
    assert "channels" not in result


def test_plan_step_executed_for_a_scheduled_slot(tmp_path):
    ready = {f"PRAYER{n}_READY": "true" for n in range(3, 11)}
    result = _run_plan(tmp_path, {"EVENT_NAME": "schedule", **ready, "PRODUCE_MAX_PARALLEL": ""})
    assert result["rc"] == 0, result["log"]
    import json
    channels = json.loads(result["channels"])
    assert len(channels) == len(set(channels))
    assert set(channels) <= {"secret-place", *[f"prayer{n}" for n in range(2, 11)]}
    assert int(result["max_parallel"]) == max(1, min(5, len(channels)))


# --- nothing two lanes write can share a path -----------------------------------

def test_job_ids_are_allocated_in_per_channel_blocks():
    from pipeline.channels import CHANNELS
    from scripts.continuous_research import roadmap_for_channel

    owner: dict[str, str] = {}
    for cid in CHANNELS:
        for row in roadmap_for_channel(cid):
            assert owner.setdefault(row["id"], cid) == cid, \
                f"job id {row['id']} is in the roadmaps of {owner[row['id']]} and {cid}"
    assert len(owner) > 100


def test_no_content_file_name_is_shared_by_two_channels():
    """A lane commits files by path. Two channels with the same file name would
    be two lanes writing one path, which the commit guard refuses."""
    from pipeline.script_doc import parse_script

    for folder in ("queue", "published"):
        ids: dict[str, str] = {}
        for path in sorted((ROOT / "content" / folder).glob("*.md")):
            try:
                channel = str(parse_script(path).meta.get("channel") or "secret-place")
            except Exception:  # noqa: BLE001 - unparseable files are another test's business
                continue
            if path.name.startswith("short-"):
                continue
            assert ids.setdefault(path.name[:4], channel) == channel, \
                f"{folder}: id {path.name[:4]} is used by {ids[path.name[:4]]} and {channel}"


def test_per_channel_resources_stay_per_channel():
    steps = workflow()["jobs"]["produce"]["steps"]
    chunk_keys = [str(s["with"]["key"]) for s in steps
                  if "actions/cache" in str(s.get("uses", "")) and "chunks-tts" in str(s.get("with", {}).get("key", ""))]
    assert len(chunk_keys) == 2 and all("${{ matrix.channel }}" in key for key in chunk_keys)
    artifacts = [str(s["with"]["name"]) for s in steps if "upload-artifact" in str(s.get("uses", ""))]
    assert artifacts and all("${{ matrix.channel }}" in name for name in artifacts)
    env = workflow()["jobs"]["produce"]["env"]
    for name in ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN", "GEMINI_API_KEY"):
        assert "matrix.channel" in env[name]


def test_commit_step_has_an_attempt_for_every_lane():
    step = next(s for s in workflow()["jobs"]["produce"]["steps"]
                if s.get("name") == "Commit queue state (job moved to published/)")
    line = next(l for l in step["run"].splitlines() if l.strip().startswith("for attempt in"))
    attempts = len(line.split("in", 1)[1].replace("; do", "").split())
    assert attempts >= plan.MAX_PARALLEL_CEILING + 1
    assert "RANDOM" in step["run"]            # lanes must not retry in lockstep


# --- the supervisor --------------------------------------------------------------

class _Proc:
    returncode = 0
    stdout = ""
    stderr = ""


def _dispatch(done: set[str], channels: list[str], attempted=None):
    calls: list[list[str]] = []

    def fake_run(cmd, **_kwargs):
        calls.append(cmd)
        return _Proc()

    with mock.patch.object(sup, "_channels", return_value=channels), \
         mock.patch.object(sup, "_channel_has_supply", return_value=True), \
         mock.patch("scripts.automation_monitor.active_quota_cooldown", return_value=None), \
         mock.patch.object(sup.subprocess, "run", side_effect=fake_run), \
         mock.patch.object(sup, "published_channels_since", return_value=done):
        ok, message = sup.dispatch("produce.yml", "2026-11-12T14:14:00+00:00",
                                   now=datetime(2026, 11, 12, 15, 0, tzinfo=UTC),
                                   attempted=attempted or [])
    return ok, message, calls


TEN = ["secret-place"] + [f"prayer{n}" for n in range(2, 11)]


def test_one_dispatch_recovers_every_channel_that_owes_the_slot():
    ok, message, calls = _dispatch({"prayer2", "prayer5"}, TEN)
    assert ok
    assert calls == [["gh", "workflow", "run", "produce.yml", "-f",
                      "channels=secret-place,prayer3,prayer4,prayer6,prayer7,prayer8,prayer9,prayer10"]]
    assert message.startswith("dispatched secret-place, prayer3, prayer4")
    assert len(message) < 300


def test_a_channel_that_failed_twice_is_left_for_the_next_slot():
    ok, message, calls = _dispatch(set(), ["secret-place", "prayer2", "prayer3"],
                                   attempted=["prayer2", "prayer3", "prayer2"])
    assert ok
    # Least-tried first; prayer2 has had its two tries.
    assert calls == [["gh", "workflow", "run", "produce.yml", "-f", "channels=secret-place,prayer3"]]
    assert "prayer2 left out (already tried 2x)" in message


def test_nothing_is_dispatched_when_every_missing_channel_is_spent():
    ok, message, calls = _dispatch(set(), ["secret-place", "prayer2"],
                                   attempted=["secret-place", "prayer2"] * 2)
    assert ok and calls == []
    assert message.startswith("nothing dispatched")


def test_production_is_recovered_after_30_minutes_and_everything_else_after_90():
    assert sup._dispatch_after("produce.yml") == timedelta(minutes=30)
    for name in ("gemini_brain.yml", "comments.yml", "keepalive.yml"):
        assert sup._dispatch_after(name) == timedelta(minutes=90)


def _history(now):
    """Every scheduled workflow ran recently except production."""
    from scripts.automation_monitor import workflow_files

    rows = []
    for filename, _name, _crons in workflow_files():
        if filename == "produce.yml":
            continue
        rows.append({"path": f".github/workflows/{filename}", "status": "completed",
                     "conclusion": "success", "event": "schedule",
                     "created_at": (now - timedelta(minutes=5)).isoformat(),
                     "run_started_at": (now - timedelta(minutes=5)).isoformat(),
                     "updated_at": (now - timedelta(minutes=4)).isoformat()})
    return rows


def test_the_supervisor_records_every_channel_it_sent(tmp_path):
    now = datetime(2026, 11, 12, 14, 50, tzinfo=UTC)      # 36 minutes after 14:14
    state: dict = {}
    sent: list = []

    def fake_dispatch(workflow, slot, now=None, attempted=None):
        sent.append((workflow, slot, list(attempted or [])))
        return True, "dispatched prayer4, prayer7; prayer2 left out (already tried 2x)"

    with mock.patch.object(sup, "_channels", return_value=["prayer2", "prayer4", "prayer7"]), \
         mock.patch.object(sup, "_channel_has_supply", return_value=True), \
         mock.patch("scripts.automation_monitor.active_quota_cooldown", return_value=None), \
         mock.patch.object(sup, "published_channels_since", return_value=set()), \
         mock.patch.object(sup, "dispatch", side_effect=fake_dispatch), \
         mock.patch.object(sup, "save_state") as ledger, \
         mock.patch.object(sup, "save_schedule_health"), \
         mock.patch.object(sup, "cancel_run") as cancel:
        # A real pass writes content/monitor/*.json; the test must not.
        out = sup.supervise(now, _history(now), dry_run=False, state=state)
    ledger.assert_called_once_with(state)
    cancel.assert_not_called()
    produce = [row for row in out["dispatched"] if row["workflow"] == "produce.yml"]
    assert len(produce) == 1, out
    entry = state["produce.yml@2026-11-12T14:14:00+00:00"]
    assert entry["attempted_channels"] == ["prayer4", "prayer7"]
    assert entry["attempts"] == 1


def test_the_supervisor_still_waits_out_the_first_half_hour():
    now = datetime(2026, 11, 12, 14, 40, tzinfo=UTC)      # 26 minutes after 14:14
    with mock.patch.object(sup, "_channels", return_value=["prayer2"]), \
         mock.patch.object(sup, "_channel_has_supply", return_value=True), \
         mock.patch("scripts.automation_monitor.active_quota_cooldown", return_value=None), \
         mock.patch.object(sup, "published_channels_since", return_value=set()):
        out = sup.supervise(now, _history(now), dry_run=True, state={})
    assert "produce.yml" not in [row["workflow"] for row in out["dispatched"]]


def test_the_evening_slot_is_still_the_current_slot_after_midnight():
    """With three cron lines, the hours from midnight to 06:14 UTC used to resolve
    to *yesterday 06:14*: the evening slot stopped being recoverable at midnight,
    and a slot check built on it would have called every channel served."""
    from scripts.automation_monitor import prev_occurrence

    crons = ["14 6 * * *", "14 14 * * *", "14 19 * * *"]
    evening = datetime(2026, 11, 12, 19, 14, tzinfo=UTC)
    for hour, minute in ((0, 0), (0, 5), (3, 30), (6, 13)):
        assert prev_occurrence(crons, datetime(2026, 11, 13, hour, minute, tzinfo=UTC)) == evening
    assert prev_occurrence(list(reversed(crons)), datetime(2026, 11, 13, 3, 0, tzinfo=UTC)) == evening
    with mock.patch.object(sup, "_channels", return_value=["prayer2"]), \
         mock.patch.object(sup, "_channel_has_supply", return_value=True), \
         mock.patch("scripts.automation_monitor.active_quota_cooldown", return_value=None), \
         mock.patch.object(sup, "published_channels_since", return_value=set()):
        now = datetime(2026, 11, 13, 0, 30, tzinfo=UTC)
        out = sup.supervise(now, _history(now), dry_run=True, state={})
    assert {"workflow": "produce.yml", "slot": evening.isoformat(), "result": "would dispatch"} \
        in out["dispatched"]
