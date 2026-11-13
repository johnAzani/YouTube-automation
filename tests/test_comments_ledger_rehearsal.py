"""Every channel's replies must reach the shared reply ledger.

``comments.yml`` runs the channels one after another and each leg commits
``content/comments/replied.json``, one JSON object shared by all channels. Each
leg used to start from the commit the RUN was created at, so the second leg to
post a reply edited a ledger that lacked the first leg's entries. Both appended
at the end of the same object, ``git pull --rebase`` hit a conflict on every
retry, and the step still ended green: the ledger entries were dropped without
a word. (The engine also checks YouTube for an existing reply, so nobody was
answered twice; the record was simply missing until a later pulse rebuilt it.)

These tests run the workflow's own commit step against a local origin.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "comments.yml"
COMMIT_STEP = "Commit replied comments ledger"
LEDGER = "content/comments/replied.json"


def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def step(name: str) -> dict:
    return next(s for s in workflow()["jobs"]["reply"]["steps"] if s.get("name") == name)


def git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True)
    assert proc.returncode == 0, f"git {' '.join(args)}: {proc.stderr}"
    return proc.stdout.strip()


def entry(comment_id: str, channel: str) -> dict:
    return {"comment_id": comment_id, "reply_id": comment_id + ".r", "video_id": "v-" + channel,
            "reply_text": "Amen.", "category": "AMEN_AFFIRMATION"}


class Rig:
    def __init__(self, tmp: Path) -> None:
        self.tmp = tmp
        self.origin = tmp / "origin.git"
        self.bin = tmp / "bin"
        self.bin.mkdir()
        (self.bin / "sleep").write_text("#!/bin/sh\nexit 0\n")
        (self.bin / "sleep").chmod(0o755)
        seed = tmp / "seed"
        seed.mkdir()
        git(seed, "init", "-q", "-b", "main")
        git(seed, "config", "user.email", "t@example.com")
        git(seed, "config", "user.name", "T")
        ledger = seed / LEDGER
        ledger.parent.mkdir(parents=True)
        ledger.write_text(json.dumps({"old-1": entry("old-1", "secret-place"),
                                      "old-2": entry("old-2", "prayer2")}, indent=2) + "\n")
        git(seed, "add", ".")
        git(seed, "commit", "-qm", "seed")
        git(tmp, "clone", "-q", "--bare", str(seed), str(self.origin))
        git(self.origin, "config", "uploadpack.allowAnySHA1InWant", "true")
        self.seed_sha = git(seed, "rev-parse", "HEAD")

    def tip(self) -> str:
        return git(self.origin, "rev-parse", "main")

    def checkout(self, name: str, sha: str) -> Path:
        """What actions/checkout leaves for a branch event: depth 1, branch `main`."""
        work = self.tmp / name
        work.mkdir()
        git(work, "init", "-q", "-b", "main")
        git(work, "remote", "add", "origin", self.origin.as_uri())
        git(work, "fetch", "-q", "--no-tags", "--depth=1", "origin", f"+{sha}:refs/remotes/origin/main")
        git(work, "checkout", "-q", "-B", "main", "refs/remotes/origin/main")
        git(work, "config", "branch.main.remote", "origin")
        git(work, "config", "branch.main.merge", "refs/heads/main")
        return work

    @staticmethod
    def reply(work: Path, comment_id: str, channel: str) -> None:
        """What the reply engine does to the ledger: append one entry, indent 2."""
        path = work / LEDGER
        data = json.loads(path.read_text())
        data[comment_id] = entry(comment_id, channel)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    def commit(self, work: Path) -> subprocess.CompletedProcess:
        script = work / ".commit-step.sh"
        script.write_text(step(COMMIT_STEP)["run"])
        env = {**os.environ, "PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}",
               "GITHUB_REF_NAME": "main", "GIT_TERMINAL_PROMPT": "0"}
        try:
            return subprocess.run(["bash", "-e", str(script)], cwd=work, env=env,
                                  text=True, capture_output=True, timeout=120)
        finally:
            script.unlink()

    def ledger(self) -> dict:
        return json.loads(git(self.origin, "show", f"main:{LEDGER}"))


@pytest.fixture()
def rig(tmp_path):
    return Rig(tmp_path)


def test_each_leg_checks_out_the_branch_tip_not_the_run_commit():
    checkout = workflow()["jobs"]["reply"]["steps"][0]
    assert checkout["uses"].startswith("actions/checkout@")
    assert checkout["with"]["ref"] == "${{ github.ref }}"
    # Still one channel at a time: the ledger is one shared file.
    assert workflow()["jobs"]["reply"]["strategy"]["max-parallel"] == 1
    assert workflow()["concurrency"]["group"] == "comments-reply"


def test_two_channels_replying_in_one_run_both_reach_the_ledger(rig):
    """Each leg starts from the tip, as the checkout now provides."""
    first = rig.checkout("secret-place", rig.tip())
    rig.reply(first, "new-a", "secret-place")
    done = rig.commit(first)
    assert done.returncode == 0, done.stdout + done.stderr

    second = rig.checkout("prayer2", rig.tip())
    rig.reply(second, "new-b", "prayer2")
    done = rig.commit(second)
    assert done.returncode == 0, done.stdout + done.stderr
    assert list(rig.ledger()) == ["old-1", "old-2", "new-a", "new-b"]


def test_a_leg_on_the_run_commit_can_no_longer_lose_its_entries_quietly(rig):
    """The old checkout, kept as a regression: second leg starts from the seed.

    Its ledger edit conflicts with the first leg's. Before, the step retried a
    rebase that could never succeed and exited 0. Now it must say so and fail.
    """
    first = rig.checkout("secret-place", rig.seed_sha)
    second = rig.checkout("prayer2", rig.seed_sha)        # pinned: does not see `first`
    rig.reply(first, "new-a", "secret-place")
    assert rig.commit(first).returncode == 0
    rig.reply(second, "new-b", "prayer2")
    done = rig.commit(second)
    assert "new-b" not in rig.ledger()                    # the conflict is real
    assert done.returncode != 0, "a dropped ledger entry must not look like success"
    assert "Reply ledger not recorded" in done.stdout
    # The checkout is left usable, not stuck mid-rebase.
    assert not (second / ".git" / "rebase-merge").exists()
    assert not (second / ".git" / "rebase-apply").exists()


def test_another_workflow_pushing_meanwhile_does_not_cost_the_ledger(rig):
    """The monitor commits to main every few minutes; that is not a conflict."""
    leg = rig.checkout("prayer3", rig.tip())
    rig.reply(leg, "new-c", "prayer3")
    other = rig.checkout("monitor", rig.tip())
    (other / "content/monitor").mkdir(parents=True)
    (other / "content/monitor/status.json").write_text("{}\n")
    git(other, "config", "user.email", "m@example.com")
    git(other, "config", "user.name", "M")
    git(other, "add", ".")
    git(other, "commit", "-qm", "chore(monitor): snapshot")
    git(other, "push", "-q", "origin", "HEAD:main")

    done = rig.commit(leg)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "new-c" in rig.ledger()
    assert git(rig.origin, "show", "main:content/monitor/status.json") == "{}"


def test_an_unchanged_ledger_commits_nothing(rig):
    leg = rig.checkout("prayer4", rig.tip())
    before = rig.tip()
    done = rig.commit(leg)
    assert done.returncode == 0 and "ledger unchanged" in done.stdout
    assert rig.tip() == before
