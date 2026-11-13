"""Rehearse the produce leg's own shell against a real Git remote (no network).

The steps under test are read out of ``.github/workflows/produce.yml`` and run
with ``bash -e``, exactly as a runner would, against a bare repository standing
in for ``origin``. Nothing here is a re-implementation of the workflow: if the
YAML changes, the rehearsal changes with it.

What it pins, and why:

* ``actions/checkout`` leaves every leg on the commit the *run* was created at.
  Runs wait behind the ``content-state`` lock for hours and a ten-channel matrix
  takes hours more, so a leg used to begin on a tree older than its own
  channel's previous publish. Between 8 and 13 November that rewrote four
  long-form receipts and replaced three real Short receipts with "recovered"
  stubs (1e4286c, 56983d3, c34235b, e19ed94).
* The commit guard added on 13 November stops the overwrite, but on the same
  stale tree it refuses the whole commit — including the receipt for the video
  the leg really uploaded. ``test_without_the_refresh_...`` keeps that visible.
* Two legs of different channels can finish at the same moment. The commit loop
  must land both, which is the mock rehearsal the remediation plan asks for
  before ``max-parallel`` was raised. It now comes from the plan job
  (``scripts/produce_plan.py``, default 5); see ``test_parallel_production.py``.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "produce.yml"
REFRESH_STEP = "Advance to latest main and snapshot starting commit"
COMMIT_STEP = "Commit queue state (job moved to published/)"

REAL_RECEIPT = (
    "---\nid: \"0200\"\nchannel: prayer4\nstatus: published\n"
    "published_at: \"2026-11-13T00:40:37Z\"\nyoutube_video_id: \"ZDnZNjXPaQI\"\n"
    "thumbnail_pending: true\nthumbnail_retry_after: \"2026-11-20T01:58:01Z\"\n"
    "thumbnail_retry_reason: \"permission\"\n---\n\nThe full script body.\n"
)
RECOVERED_STUB = (
    "---\nid: \"0200\"\nchannel: prayer4\nstatus: published\n"
    "published_at: \"2026-11-13T07:27:44Z\"\nyoutube_video_id: \"ZDnZNjXPaQI\"\n"
    "receipt_recovered_from_youtube: true\nmetadata_retrofit_approved: false\n---\n"
)


def _steps() -> list[dict]:
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return data["jobs"]["produce"]["steps"]


def _step(name: str) -> dict:
    return next(s for s in _steps() if s.get("name") == name)


def git(repo: Path, *args: str, check: bool = True) -> str:
    proc = subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True)
    if check and proc.returncode:
        raise AssertionError(f"git {' '.join(args)} failed: {proc.stderr}")
    return proc.stdout.strip()


def _job(job_id: str, channel: str) -> str:
    return f"---\nid: \"{job_id}\"\nchannel: {channel}\nstatus: approved\n---\n\nScript {job_id}.\n"


class Rehearsal:
    """A bare ``origin`` plus the runner environment a leg's steps expect."""

    def __init__(self, tmp: Path) -> None:
        self.tmp = tmp
        self.origin = tmp / "origin.git"
        self.bin = tmp / "bin"
        self.bin.mkdir()
        # The workflow calls `python`; a runner's sleep would only slow the test.
        # A wrapper, not a symlink: a symlinked interpreter loses its virtualenv.
        for name, body in (("python", f'exec "{sys.executable}" "$@"'), ("sleep", "exit 0")):
            shim = self.bin / name
            shim.write_text(f"#!/bin/sh\n{body}\n")
            shim.chmod(0o755)

        seed = tmp / "seed"
        seed.mkdir()
        git(seed, "init", "-q", "-b", "main")
        self._identity(seed)
        (seed / "scripts").mkdir()
        for name in ("guard_produce_commit.py", "build_dashboard_data.py"):
            shutil.copy(ROOT / "scripts" / name, seed / "scripts" / name)
        for rel, body in {
            "content/queue/0200-midnight-first.md": _job("0200", "prayer4"),
            "content/queue/0201-midnight-second.md": _job("0201", "prayer4"),
            "content/queue/0300-family-first.md": _job("0300", "prayer5"),
        }.items():
            (seed / rel).parent.mkdir(parents=True, exist_ok=True)
            (seed / rel).write_text(body)
        git(seed, "add", ".")
        git(seed, "commit", "-qm", "seed")
        git(tmp, "clone", "-q", "--bare", str(seed), str(self.origin))
        # A runner fetches the run's commit by SHA; let the stand-in allow it.
        git(self.origin, "config", "uploadpack.allowAnySHA1InWant", "true")
        self.seed_sha = git(seed, "rev-parse", "HEAD")

    @staticmethod
    def _identity(repo: Path) -> None:
        git(repo, "config", "user.email", "test@example.com")
        git(repo, "config", "user.name", "Test")

    def tip(self) -> str:
        return git(self.origin, "rev-parse", "main")

    def origin_file(self, rel: str) -> str | None:
        proc = subprocess.run(["git", "show", f"main:{rel}"], cwd=self.origin,
                              text=True, capture_output=True)
        return proc.stdout if proc.returncode == 0 else None

    def checkout(self, name: str, sha: str | None = None) -> Path:
        """What ``actions/checkout@v4`` leaves behind: depth 1, pinned to a SHA."""
        work = self.tmp / name
        work.mkdir()
        git(work, "init", "-q", "-b", "main")
        self._identity(work)
        git(work, "remote", "add", "origin", self.origin.as_uri())
        git(work, "fetch", "-q", "--no-tags", "--depth=1", "origin",
            f"+{sha or self.tip()}:refs/remotes/origin/main")
        git(work, "checkout", "-q", "-B", "main", "refs/remotes/origin/main")
        return work

    def run_step(self, work: Path, name: str, *, ref: str = "refs/heads/main",
                 start_sha: str | None = None) -> subprocess.CompletedProcess:
        script = work / f".step-{abs(hash(name))}.sh"
        script.write_text(_step(name)["run"])
        github_env = self.tmp / f"{work.name}.github_env"
        github_env.touch()
        env = {
            **os.environ,
            "PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}",
            "PYTHONPATH": str(ROOT),
            "GITHUB_ENV": str(github_env),
            "GITHUB_REF": ref,
            "GITHUB_STEP_SUMMARY": str(self.tmp / "summary.md"),
            "GIT_TERMINAL_PROMPT": "0",
        }
        env.pop("START_SHA", None)
        exported = self.exported(work)
        if start_sha or exported.get("START_SHA"):
            env["START_SHA"] = start_sha or exported["START_SHA"]
        try:
            return subprocess.run(["bash", "-e", str(script)], cwd=work, env=env,
                                  text=True, capture_output=True, timeout=120)
        finally:
            script.unlink()

    def exported(self, work: Path) -> dict[str, str]:
        path = self.tmp / f"{work.name}.github_env"
        if not path.is_file():
            return {}
        return dict(line.split("=", 1) for line in path.read_text().splitlines() if "=" in line)

    @staticmethod
    def publish(work: Path, queue_name: str, receipt: str) -> None:
        """The state change a successful upload makes: queue file -> receipt."""
        (work / "content/queue" / queue_name).unlink()
        dest = work / "content/published" / queue_name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(receipt)


@pytest.fixture()
def rig(tmp_path):
    return Rehearsal(tmp_path)


def _first_run_publishes_0200(rig: Rehearsal) -> None:
    leg = rig.checkout("run-a-prayer4")
    assert rig.run_step(leg, REFRESH_STEP).returncode == 0
    rig.publish(leg, "0200-midnight-first.md", REAL_RECEIPT)
    done = rig.run_step(leg, COMMIT_STEP)
    assert done.returncode == 0, done.stdout + done.stderr
    assert rig.origin_file("content/published/0200-midnight-first.md") == REAL_RECEIPT


def test_the_refresh_runs_before_anything_reads_content_state():
    names = [s.get("name") or s.get("uses") for s in _steps()]
    refresh = names.index(REFRESH_STEP)
    assert names.index("actions/checkout@v4") < refresh
    for later in ("Repair the queue before publishing", "Check this channel's queue",
                  "Render the Short (9:16)",
                  "Record videos that are live but not yet in the repo",
                  "Render and upload the long-form edition", COMMIT_STEP):
        assert refresh < names.index(later), later
    # START_SHA must describe the refreshed tree, so it is written by the same
    # step and by nothing else.
    assert sum("START_SHA=" in str(s.get("run", "")) for s in _steps()) == 1
    assert "START_SHA=" in _step(REFRESH_STEP)["run"]
    assert "if" not in _step(REFRESH_STEP), "a skipped refresh is a stale leg"


def test_a_leg_of_a_run_created_before_the_last_publish_starts_from_current_main(rig):
    created_at = rig.seed_sha                      # the run is created, then waits
    _first_run_publishes_0200(rig)                 # ...while another run publishes
    assert rig.tip() != created_at

    leg = rig.checkout("run-b-prayer4", created_at)
    assert (leg / "content/queue/0200-midnight-first.md").is_file()      # stale
    assert not (leg / "content/published/0200-midnight-first.md").exists()

    refreshed = rig.run_step(leg, REFRESH_STEP)
    assert refreshed.returncode == 0, refreshed.stdout + refreshed.stderr
    assert "Checkout advanced" in refreshed.stdout
    assert git(leg, "rev-parse", "HEAD") == rig.tip()
    assert rig.exported(leg)["START_SHA"] == rig.tip()
    # The leg now sees what its channel already published, so it has nothing to
    # recover and nothing to render twice.
    assert not (leg / "content/queue/0200-midnight-first.md").exists()
    assert (leg / "content/published/0200-midnight-first.md").read_text() == REAL_RECEIPT

    rig.publish(leg, "0201-midnight-second.md", REAL_RECEIPT.replace("0200", "0201"))
    done = rig.run_step(leg, COMMIT_STEP)
    assert done.returncode == 0, done.stdout + done.stderr
    assert rig.origin_file("content/published/0200-midnight-first.md") == REAL_RECEIPT
    assert rig.origin_file("content/published/0201-midnight-second.md") is not None
    assert rig.origin_file("content/queue/0201-midnight-second.md") is None


def test_without_the_refresh_a_stale_leg_loses_the_receipt_of_its_own_upload(rig):
    """Why the refresh is not optional now that the commit guard exists."""
    created_at = rig.seed_sha
    _first_run_publishes_0200(rig)

    leg = rig.checkout("run-b-prayer4", created_at)
    # The stale tree shows 0200 as queued, so the leg "recovers" it from YouTube
    # and then publishes 0201 for real.
    rig.publish(leg, "0200-midnight-first.md", RECOVERED_STUB)
    rig.publish(leg, "0201-midnight-second.md", REAL_RECEIPT.replace("0200", "0201"))
    refused = rig.run_step(leg, COMMIT_STEP, start_sha=created_at)

    assert refused.returncode != 0
    assert "Producer state conflict" in refused.stdout
    # The guard did its job: the real receipt survived...
    assert rig.origin_file("content/published/0200-midnight-first.md") == REAL_RECEIPT
    # ...and the price was the record of a video that is live on the channel.
    assert rig.origin_file("content/published/0201-midnight-second.md") is None
    assert rig.origin_file("content/queue/0201-midnight-second.md") is not None


def test_a_leg_already_at_the_tip_is_left_alone(rig):
    leg = rig.checkout("fresh")
    result = rig.run_step(leg, REFRESH_STEP)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Checkout advanced" not in result.stdout
    assert rig.exported(leg)["START_SHA"] == rig.seed_sha


def test_a_run_on_another_ref_keeps_the_commit_it_asked_for(rig):
    created_at = rig.seed_sha
    _first_run_publishes_0200(rig)
    leg = rig.checkout("branch-rehearsal", created_at)
    result = rig.run_step(leg, REFRESH_STEP, ref="refs/heads/arena/some-branch")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Checkout not advanced" in result.stdout
    assert git(leg, "rev-parse", "HEAD") == created_at
    assert rig.exported(leg)["START_SHA"] == created_at


def test_a_leg_that_cannot_reach_main_stops_before_it_can_publish(rig):
    leg = rig.checkout("offline")
    git(leg, "remote", "set-url", "origin", (rig.tmp / "gone.git").as_uri())
    result = rig.run_step(leg, REFRESH_STEP)
    assert result.returncode != 0
    assert "Stale checkout" in result.stdout
    assert "START_SHA" not in rig.exported(leg)


def test_a_leg_whose_history_diverged_from_main_stops(rig):
    """A fast-forward is the only safe move; anything else is not this run's main."""
    leg = rig.checkout("diverged")
    (leg / "content/queue/0200-midnight-first.md").write_text("local history\n")
    git(leg, "commit", "-qam", "not on main")
    _first_run_publishes_0200(rig)
    result = rig.run_step(leg, REFRESH_STEP)
    assert result.returncode != 0
    assert "Stale checkout" in result.stdout


def test_two_channels_finishing_together_both_record_their_publish(rig):
    """Mock rehearsal of concurrent legs: main moves between fetch and push."""
    midnight = rig.checkout("prayer4")
    family = rig.checkout("prayer5")
    for leg in (midnight, family):
        assert rig.run_step(leg, REFRESH_STEP).returncode == 0
    rig.publish(midnight, "0200-midnight-first.md", REAL_RECEIPT)
    family_receipt = REAL_RECEIPT.replace("0200", "0300").replace("prayer4", "prayer5")
    rig.publish(family, "0300-family-first.md", family_receipt)

    # Make the race real rather than sequential: the first time the Family leg
    # pushes, the Midnight leg's commit lands on origin first.
    marker = rig.tmp / "raced"
    racer = rig.tmp / "racer.sh"
    racer.write_text(
        "#!/bin/sh\n"
        f"[ -e '{marker}' ] && exit 0\n"
        f": > '{marker}'\n"
        "unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE\n"
        f"cd '{midnight}' && git add -A content && git commit -qm 'midnight publish' "
        "&& git push -q origin HEAD:main\n"
    )
    racer.chmod(0o755)
    hook = family / ".git/hooks/pre-push"
    hook.parent.mkdir(exist_ok=True)
    hook.write_text(f"#!/bin/sh\n'{racer}'\nexit 0\n")
    hook.chmod(0o755)

    done = rig.run_step(family, COMMIT_STEP)
    assert done.returncode == 0, done.stdout + done.stderr
    assert marker.exists(), "the race never happened, so nothing was rehearsed"
    assert "main moved during attempt 1" in done.stdout
    assert "queue state recorded on attempt 2" in done.stdout

    assert rig.origin_file("content/published/0200-midnight-first.md") == REAL_RECEIPT
    assert rig.origin_file("content/published/0300-family-first.md") == family_receipt
    assert rig.origin_file("content/queue/0200-midnight-first.md") is None
    assert rig.origin_file("content/queue/0300-family-first.md") is None
    assert rig.origin_file("content/queue/0201-midnight-second.md") is not None
    # The one cross-channel file is derived from the staged tree on top of the
    # newest main, so the later commit describes both channels' publishes.
    state = json.loads(rig.origin_file("docs/network-state.json"))
    live = {v.get("youtube_video_id") or v.get("video_id") for v in state["videos"]}
    by_channel = {c["id"]: c for c in state["channels"]}
    assert by_channel["prayer4"]["latest_video"] and by_channel["prayer5"]["latest_video"]
    assert len(state["videos"]) == 2, live
    # Nothing but the Family leg's own files rode along in its commit.
    changed = git(rig.origin, "show", "--name-only", "--format=", "main").splitlines()
    assert sorted(p for p in changed if p.startswith("content/")) == [
        "content/published/0300-family-first.md", "content/queue/0300-family-first.md"]


def test_five_lanes_finishing_in_the_same_minute_all_record_their_publish(rig):
    """Five real processes run the commit step at once against one origin.

    This is the worst case the lane count allows by default: every leg fetches
    the same tip, one push wins each round, and the rest have to notice, re-stage
    on the new tip and try again. Every receipt must end up on main.
    """
    from concurrent.futures import ThreadPoolExecutor

    lanes = {"prayer4": "0210", "prayer5": "0310", "prayer6": "0410",
             "prayer7": "0510", "prayer8": "0610"}
    legs = {}
    for channel, job_id in lanes.items():
        leg = rig.checkout(channel)
        assert rig.run_step(leg, REFRESH_STEP).returncode == 0
        receipt = REAL_RECEIPT.replace("0200", job_id).replace("prayer4", channel)
        dest = leg / "content/published" / f"{job_id}-lane.md"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(receipt)
        legs[channel] = (leg, job_id, receipt)

    with ThreadPoolExecutor(max_workers=len(legs)) as pool:
        results = dict(zip(legs, pool.map(
            lambda item: rig.run_step(item[0], COMMIT_STEP), legs.values())))

    for channel, done in results.items():
        assert done.returncode == 0, f"{channel}: {done.stdout}{done.stderr}"
        assert "queue state recorded on attempt" in done.stdout, channel
    retries = sum(done.stdout.count("main moved during attempt") for done in results.values())
    assert retries >= 1, "no push was ever rejected, so no race was rehearsed"
    for channel, (_leg, job_id, receipt) in legs.items():
        assert rig.origin_file(f"content/published/{job_id}-lane.md") == receipt, channel
    # One commit per lane on top of the seed, none lost and none merged away.
    subjects = git(rig.origin, "log", "--format=%s", "main").splitlines()
    assert subjects.count("chore(content): publish job [skip ci]") == len(legs)
    state = json.loads(rig.origin_file("docs/network-state.json"))
    by_channel = {c["id"]: c for c in state["channels"]}
    assert all(by_channel[channel]["latest_video"] for channel in lanes)


def test_one_production_run_at_a_time_with_lanes_inside_it():
    """Channels run side by side inside a run; runs still take turns."""
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert "needs.plan.outputs.max_parallel" in str(
        data["jobs"]["produce"]["strategy"]["max-parallel"])
    assert data["jobs"]["produce"]["strategy"]["fail-fast"] is False
    assert data["concurrency"] == {"group": "content-state", "cancel-in-progress": False}
