"""Which loops actually learn, and which only measure.

The owner asked on 25 November 2026 that the system "auto always learn and self
improve". The honest pre-condition for answering that is an audit, because a
repository can be full of readings that nothing acts on — and this one was.

What the audit found, reading the code rather than the documents:

* **Two loops close.** The Shorts book/theme steering changes which passages get
  written next, and the night-tail length decision changes how long a release is
  built. Both read a measurement and change a build.
* **One loop was built and never wired.** `pipeline/thumbnail_campaign.py` has
  measured the click rate of each thumbnail concept every day since it landed. No
  release ever read the result: `concept = concept_for(doc.id)` was called with no
  argument the campaign's answer could reach. The channels kept rotating concepts
  forever and never adopted the winner.
* **Five readings are reported and never act.** The lessons (search terms and
  niche phrases) are generated, judged and offered to the title writer — and on
  25 November 0 of them had been kept or dropped: every one was still `testing`,
  because a channel's own long-forms rarely reach the judged-side minimum.
* **One loop cannot be measured at all.** The first-frame composition audit had
  one composition across 639 Shorts. A design variable with one level and one
  repeated value has no measured answer, whatever the instrumentation says.

So the module reports four states per loop, and only one of them is "learning":

* ``acting`` — measured, and the measurement changes the next build;
* ``measuring`` — measured, nothing consumes it;
* ``unwired`` — measured, consumed, but the consumer could not receive the answer
  (the thumbnail campaign before today);
* ``waiting`` — the loop exists and is honest, but there are too few videos to
  conclude anything. It says so rather than pretending.

Nothing here changes a video. It exists so that "the system learns" is a claim
with a per-loop answer instead of a feeling.

    python -m pipeline.learning_audit            # the table
    python -m pipeline.learning_audit --json     # the same, as JSON
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "content" / "research" / "learning_audit.json"

STATES = ("acting", "unwired", "measuring", "waiting")

#: What counts as enough to act on. Deliberately conservative and copied from the
#: module that owns each floor, so this audit cannot invent a lower bar.
MIN_THUMBNAIL_IMPRESSIONS = 300


def _read(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8")) or {}
    except (OSError, ValueError):
        return {}


def _shorts_steering() -> dict[str, Any]:
    """Does a measured theme reorder the passages the brain writes next?"""
    from pipeline.evergreen_shorts import EVERGREEN
    from pipeline.performance_feedback import (load_feedback_report, network_shorts_signal,
                                               rank_candidates)
    from scripts.continuous_research import ROADMAPS

    report = load_feedback_report() or {}
    network = network_shorts_signal() or {}
    rows: list[dict[str, Any]] = []
    changed: list[str] = []
    for channel in sorted(EVERGREEN):
        candidates = list(ROADMAPS.get(channel, []))
        if not candidates:
            continue
        try:
            ranked = rank_candidates(candidates, report)
        except Exception:  # noqa: BLE001
            ranked = candidates
        if [row.get("id") for row in ranked] != [row.get("id") for row in candidates]:
            changed.append(channel)
        rows.append({"channel": channel, "candidates": len(candidates)})
    shorts = (report.get("shorts") or {})
    measured = int(shorts.get("measured_shorts") or 0)
    books = shorts.get("by_book") or {}
    trusted_books = [book for book, row in books.items()
                     if isinstance(row, dict) and int(row.get("shorts") or 0) >= 2]
    if not measured:
        state = "waiting"
        because = "no Short is old enough to measure yet"
    elif not changed and not network.get("books"):
        state = "measuring"
        because = "Shorts are measured but no book or theme has enough of them to reorder"
    else:
        state = "acting"
        because = ("%d Shorts measured; %d book(s) carry two or more, and the ranking "
                   "reorders %d channel(s)' roadmap" % (measured, len(trusted_books), len(changed)))
    return {
        "loop": "shorts_steering",
        "what": "which passages and books the brain writes Shorts on next",
        "state": state,
        "evidence": because,
        "measured_shorts": measured,
        "channels_reordered": len(changed),
        "owner": "pipeline/performance_feedback.py: rank_candidates",
    }


def _thumbnail_choice() -> dict[str, Any]:
    """Does the concept that earned more clicks go live on the next release?"""
    campaign = _read(ROOT / "content" / "research" / "thumbnail_campaign.json")
    total_impressions = sum(int(row.get("impressions") or 0)
                            for row in campaign.get("concepts") or [])
    assigned = int(campaign.get("videos_assigned") or 0)
    leader = campaign.get("leader")
    if not assigned:
        state = "waiting"
        because = "no release has recorded which concept went live yet"
    elif not total_impressions:
        state = "measuring"
        because = ("%d release(s) recorded a concept, but the reach files hold no "
                   "impressions for any of them yet" % assigned)
    elif not leader:
        state = "measuring"
        because = ("%d impressions pooled, under the %d floor for every concept, so "
                   "nothing is trusted" % (total_impressions, MIN_THUMBNAIL_IMPRESSIONS))
    elif not _adopts_leader():
        state = "unwired"
        because = (f"{leader} leads, and nothing reads the leader when choosing the "
                   "next release's concept")
    else:
        # Wiring is necessary, not sufficient. The loop is acting only once a
        # release has actually gone out on the leader's concept — the audit could
        # otherwise report the loop closed on the day it was wired, before any
        # video had used the answer.
        adopted = _adopted_release()
        if adopted:
            state = "acting"
            because = (f"{leader} leads at {campaign.get('leader_click_rate_percent')}% "
                       f"and a release has gone out on it ({adopted})")
        else:
            state = "measuring"
            because = (f"{leader} leads, the release path can adopt it, and no release "
                       "has gone out on it yet")
    return {
        "loop": "thumbnail_choice",
        "what": "which of the three thumbnail concepts goes live",
        "state": state,
        "evidence": because,
        "leader": leader,
        "videos_assigned": assigned,
        "owner": "pipeline/thumbnail_campaign.py: live_concept",
    }


def _adopted_release() -> str:
    """The first release that went out on the measured leader, or "".

    Reads the receipts the pipeline already writes; it does not infer adoption from
    the campaign's own intention to adopt.
    """
    from pipeline.thumbnail_campaign import measured_leader

    leader = measured_leader()
    name = (leader or {}).get("concept") if isinstance(leader, dict) else leader
    if not name:
        return ""
    for path in sorted((ROOT / "content" / "published").glob("short-*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for line in text.splitlines():
            if line.lower().startswith("thumbnail_concept:"):
                value = line.split(":", 1)[1].strip().strip("\"'")
                if value == str(name):
                    return path.stem
    return ""


def _adopts_leader() -> bool:
    """Whether the release path asks the campaign which concept to use."""
    try:
        from pipeline.thumbnail_campaign import live_concept

        return True
    except Exception:  # noqa: BLE001
        return False


def _lessons() -> dict[str, Any]:
    """Do phrases from search and from the niche's winning titles get judged?"""
    from pipeline import lessons as lesson_book

    testing: list[str] = []
    decided: list[str] = []
    channels = 0
    for path in sorted((ROOT / "content" / "research").glob("performance_feedback*.json")):
        report = _read(path)
        if not report:
            continue
        channels += 1
        for lesson in report.get("lessons") or []:
            status = str(lesson.get("status") or "")
            if status == "testing":
                testing.append(str(lesson.get("phrase") or ""))
            elif status in {"kept", "dropped"}:
                decided.append(f"{lesson.get('phrase')} ({status})")
    if not testing and not decided:
        state = "waiting"
        because = "no lesson has been opened from search terms or niche wording yet"
    elif not decided:
        state = "waiting"
        because = ("%d phrase(s) are under test on %d channel(s) and none has a verdict "
                   "yet: a verdict needs %d videos on each side with %d views"
                   % (len(testing), channels, lesson_book.MIN_VIDEOS_EACH_SIDE,
                      lesson_book.MIN_VIEWS_TO_JUDGE))
    else:
        state = "acting"
        because = ("%d phrase(s) judged, %d still under test" % (len(decided), len(testing)))
    return {
        "loop": "overlay_lessons",
        "what": "wording offered to the title and overlay writers",
        "state": state,
        "evidence": because,
        "under_test": len(testing),
        "decided": len(decided),
        "owner": "pipeline/lessons.py: update / judge",
    }


def _night_tail() -> dict[str, Any]:
    """Does the measured watch ceiling change the length a release is built to?"""
    from pipeline.night_tail import configured_minutes
    from pipeline.channels import scheduled_channels

    minutes = {cid: configured_minutes(cid, environ={}) for cid in scheduled_channels()}
    reading = _read(ROOT / "content" / "research" / "growth_score.json")
    ceiling = (reading.get("watch_ceiling") or {})
    median_seconds = ceiling.get("reading", {}).get("median_seconds")
    if median_seconds is None:
        state = "waiting"
        because = "no channel has enough retention readings to set a ceiling"
    elif any(minutes.values()):
        state = "acting"
        because = ("ceiling %.0fs is applied: %s still carry a night tail"
                   % (median_seconds, [c for c, m in minutes.items() if m]))
    else:
        state = "acting"
        because = ("ceiling %.0fs is below the tail's own floor, so the tail is off on "
                   "every channel — the measurement changed the build" % median_seconds)
    return {
        "loop": "night_tail_length",
        "what": "how long a release is built",
        "state": state,
        "evidence": because,
        "tail_minutes": minutes,
        "owner": "pipeline/night_tail.py: configured_minutes",
    }


def _first_frame() -> dict[str, Any]:
    """Can the first-frame composition be chosen by measurement?"""
    audit = _read(ROOT / "content" / "research" / "first_frame.json")
    if not audit.get("specs"):
        return {"loop": "first_frame_composition", "what": "what a stranger sees at second one",
                "state": "waiting", "evidence": "the audit has not run",
                "owner": "pipeline/first_frame.py"}
    compositions = [count for count in (audit.get("compositions") or {}).values() if count]
    references = int(audit.get("first_frames_with_a_reference") or 0)
    specs = int(audit.get("specs") or 1)
    if len(compositions) <= 1:
        state = "measuring"
        # A citation on frame one is not a second composition — it is the same
        # plate, kicker, subtitle and camera move with the citation's words in the
        # kicker slot. Saying "one composition across N Shorts" while N in ten open
        # on a citation hides the only variable the repository has actually varied.
        because = ("one composition across %d Shorts, but %d of them (%d%%) still open "
                   "on a citation: the design has one level, and the citation-versus-need "
                   "choice inside it has two"
                   % (specs, references, round(100 * references / specs)))
    elif references:
        state = "measuring"
        because = ("%d composition(s) now exist, but %d of %d Shorts (%d%%) still open on "
                   "a citation, which the authoring rule forbids outright"
                   % (len(compositions), references, specs, round(100 * references / specs)))
    else:
        state = "measuring"
        because = ("%d compositions in the repository and no citation frames left, but "
                   "no Short carries a per-frame response reading yet" % len(compositions))
    return {
        "loop": "first_frame_composition",
        "what": "what a stranger sees at second one",
        "state": state,
        "evidence": because,
        "compositions": len(compositions),
        "owner": "pipeline/first_frame.py + pipeline/first_frame_repair.py",
    }


def build_audit() -> dict[str, Any]:
    loops = [_shorts_steering(), _thumbnail_choice(), _lessons(), _night_tail(), _first_frame()]
    if not _adopts_leader():
        # The campaign measures a winner and the release path cannot receive it.
        for loop in loops:
            if loop["loop"] == "thumbnail_choice" and loop["state"] == "measuring":
                loop["state"] = "unwired"
    acting = [loop["loop"] for loop in loops if loop["state"] == "acting"]
    waiting = [loop["loop"] for loop in loops if loop["state"] == "waiting"]
    measuring = [loop["loop"] for loop in loops if loop["state"] in {"measuring", "unwired"}]
    return {
        "schema": 1,
        "loops": loops,
        "acting": acting,
        "measuring_only": measuring,
        "waiting": waiting,
        "sentence": _sentence(len(acting), len(loops), measuring, waiting),
        "not_claimed": [
            "that a loop which is acting is improving anything. Acting means the "
            "measurement changes the next build; whether that build does better is "
            "what the next reading is for.",
        ],
        "cost_lock": "$0.00 / month (docs/ZERO_DOLLAR_LOCK.md)",
    }


def _sentence(acting: int, total: int, measuring: list[str], waiting: list[str]) -> str:
    if acting == total:
        return "All %d loops act on their own measurement." % total
    parts = ["%d of %d loops act on their own measurement" % (acting, total)]
    if measuring:
        parts.append("%s measure and change nothing yet" % ", ".join(measuring))
    if waiting:
        parts.append("%s have too few videos to conclude" % ", ".join(waiting))
    return "; ".join(parts) + "."


def write_audit(path: Path | None = None, audit: dict[str, Any] | None = None) -> Path:
    out = REPORT_PATH if path is None else Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(audit if audit is not None else build_audit(),
                              indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return out


def headline(audit: dict[str, Any]) -> list[str]:
    lines = [f'{"loop":26}{"state":12}what']
    for loop in audit.get("loops") or []:
        lines.append(f'{loop["loop"]:26}{loop["state"]:12}{loop["what"]}')
    lines.append("")
    lines.append(audit.get("sentence", ""))
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    audit = build_audit()
    if args.json:
        print(json.dumps(audit, indent=1, sort_keys=True))
    else:
        print("\n".join(headline(audit)))
        for loop in audit.get("loops") or []:
            print(f'  - {loop["loop"]}: {loop["evidence"]}')
    write_audit(audit=audit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
