"""Choose which of three thumbnail concepts YouTube is shown, and rotate when a test closes.

Why this exists. `pipeline/thumbnail_ctr.py` has rendered three genuinely different
concepts for every long-form since the CTR pack was built (an imperative, a
curiosity clause, and a textless poster), and the pipeline has uploaded the first
one - ``hook`` - every single time. The other two have never been on screen, so the
choice between them has never been tested on the channel that has to live with it.

What can and cannot be tested from here is worth stating plainly, because it
decides the design:

* **A per-video A/B/C test is not available to this repository.** YouTube's
  "Test & Compare" is a Studio-only feature with no Data API equivalent. Nothing in
  this code can open a test, and nothing can read which variant won.
* **A cross-video rotation is available, and is a real test.** Every long-form
  carries an ``a/b_sequence`` (one of ABAB..., ABCB..., rotated by its job id) and
  the first letter says which concept goes live. Different videos then carry
  different concepts in the same period, on the same channel, in the same niche.
  ``thumbnail-campaign.yml`` measures the click rate that follows, per concept,
  using the reach files - so the question "which concept earns more clicks" gets
  an answer from the channel's own traffic rather than from a study of other
  people's videos.

The rotation is deterministic: the same job always gets the same sequence, so a
re-run reproduces the same thumbnail and a receipt never disagrees with YouTube.
The sequence is the project's standard A/B rotation (``pipeline/experiment.py``),
and the campaign reports every concept it can measure, naming the ones with too few
impressions to trust.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

#: The pack's own labels, in a stable order. A concept is never renamed: a receipt
#: that says ``thumbnail_concept: quiet`` has to keep meaning the quiet frame.
CONCEPTS = ("hook", "quiet", "poster")
#: The rotation every release joins. ABCB rather than ABAB: three concepts is what
#: the pack renders, and a two-letter sequence could never show the poster.
SEQUENCE = "ABCB"
#: Where a receipt records which concept went live, so the campaign can read it.
RECEIPT_FIELD = "thumbnail_concept"
#: Below this many impressions a concept's click rate is noise.
MIN_IMPRESSIONS = 300
CAMPAIGN_PATH = ROOT / "content" / "research" / "thumbnail_campaign.json"


def sequence_for(doc_key: str) -> str:
    """The rotation this release joins; rotated by its job id so all three get used."""
    digest = hashlib.sha1((doc_key or "default").encode("utf-8")).hexdigest()
    shift = int(digest[:8], 16) % len(SEQUENCE)
    return SEQUENCE[shift:] + SEQUENCE[:shift]


def letter_to_concept(letter: str) -> str:
    """``A`` -> ``hook``, ``B`` -> ``quiet``, ``C`` -> ``poster``."""
    index = "ABC".find((letter or "A").strip().upper()[:1])
    if index < 0 or index >= len(CONCEPTS):
        return CONCEPTS[0]
    return CONCEPTS[index]


def concept_for(doc_key: str) -> str:
    """Which concept this release puts live, deterministically from its job id."""
    return letter_to_concept(sequence_for(doc_key)[:1])


def rotation_report(doc_key: str) -> dict:
    """Everything the run page needs to say about this release's assignment."""
    sequence = sequence_for(doc_key)
    concept = letter_to_concept(sequence[:1])
    return {
        "sequence": sequence,
        "concept": concept,
        "letter": sequence[:1],
        "note": ("the letter picks which of the pack's three concepts goes live; the "
                 "sequence is this release's place in the rotation, so the concepts "
                 "are compared across videos rather than inside one"),
    }


# --------------------------------------------------------------------------- #
# Closing the loop: the concept that earns the click goes live
# --------------------------------------------------------------------------- #
#: How much traffic the losing concepts need before the winner is copied. Above
#: the per-concept trust floor, because adopting a leader on exactly the floor
#: would crown the concept that happened to cross it first.
IMPRESSIONS_TO_ADOPT = MIN_IMPRESSIONS


def load_campaign(path: Path | None = None) -> dict:
    """The committed campaign reading, or ``{}`` when it has not been written."""
    target = Path(path) if path else CAMPAIGN_PATH
    try:
        return json.loads(target.read_text(encoding="utf-8")) or {}
    except (OSError, ValueError):
        return {}


def measured_leader(campaign: dict | None = None) -> tuple[str, dict] | None:
    """``(concept, row)`` the traffic has settled on, or ``None``.

    A leader is only returned when every concept has cleared the impression floor.
    One concept measured against two unmeasured ones is not a comparison, and
    copying the only concept that happened to receive impressions would turn the
    rotation into a self-fulfilling choice.
    """
    report = load_campaign() if campaign is None else campaign
    rows = [row for row in (report.get("concepts") or []) if isinstance(row, dict)]
    if not rows or not report.get("leader"):
        return None
    # `measurable` is written by the builder; a hand-written report may only have
    # `approved`, so either is accepted and neither is inferred from the other.
    if not all(row.get("measurable") or row.get("approved") for row in rows):
        return None
    if any(int(row.get("impressions") or 0) < IMPRESSIONS_TO_ADOPT for row in rows):
        return None
    leader = next((row for row in rows if row.get("concept") == report["leader"]), None)
    if not leader or not int(leader.get("impressions") or 0):
        return None
    # The rate is quoted, never required: a hand-written report may carry clicks
    # and impressions and leave the division to the reader.
    return str(report["leader"]), leader

def leader_summary(row: dict) -> dict:
    """The leader, as the audit and the run page quote it.

    A hand-written report may carry `approved` and a raw `clicks` count instead of
    a `measurable` flag and a percentage; quote whichever is present rather than
    inventing the other.
    """
    return {
        "concept": row.get("concept"),
        "click_rate_percent": row.get("click_rate_percent"),
        "impressions": row.get("impressions"),
        "clicks": row.get("clicks"),
        "approved": bool(row.get("measurable") or row.get("approved")),
    }


def live_concept(doc_key: str, campaign: dict | None = None) -> str:
    """The concept this release puts live: the measured winner, else its turn.

    Before 25 November 2026 this was always ``concept_for(doc_key)`` — a
    deterministic rotation that nothing could influence. The campaign has measured
    a click rate per concept since it landed, and no release ever read the answer,
    so the channels would have rotated forever and adopted nothing. This is the
    point where the measurement reaches the build.

    The rotation does not stop when a winner is known: every release still records
    which concept it carried, and the losing concepts keep collecting impressions
    on the videos already published, so a winner can be displaced if the traffic
    changes its mind.
    """
    leader = measured_leader(campaign)
    return leader[0] if leader else concept_for(doc_key)


def concept_decision(doc_key: str, campaign: dict | None = None) -> dict:
    """Why this release puts live what it does, for the run page and the receipt."""
    report = load_campaign() if campaign is None else campaign
    leader = measured_leader(report)
    if leader:
        concept, row = leader
        rate = row.get("click_rate_percent")
        quoted = (f"at {rate}%" if rate is not None
                  else f"on {row.get('clicks')} clicks")
        return {
            "concept": concept,
            "source": "measured",
            "why": ("every concept has cleared %d impressions and %s leads %s "
                    "(pooled over %s impressions), so the winner goes live"
                    % (IMPRESSIONS_TO_ADOPT, concept, quoted, row.get("impressions"))),
        }
    return {
        "concept": concept_for(doc_key),
        "source": "rotation",
        "why": _why_not_adopted(report),
        "sequence": sequence_for(doc_key),
    }


def _why_not_adopted(report: dict) -> str:
    """The reason the rotation still decides, in the terms the reading uses."""
    rows = [row for row in (report.get("concepts") or []) if isinstance(row, dict)]
    if not rows:
        return ("no release has recorded which concept went live yet, so there is "
                "nothing to copy; this release takes its turn in the rotation")
    if not any(int(row.get("impressions") or 0) for row in rows):
        return ("no concept has impressions in the reach files yet, so there is "
                "nothing to copy; this release takes its turn in the rotation")
    # Trust is the flag the builder writes; a hand-written report may only carry
    # `approved`, so both are accepted and neither is inferred from the other.
    def trusted(row: dict) -> bool:
        return bool(row.get("measurable") or row.get("approved"))

    unmeasured = [row["concept"] for row in rows if not trusted(row)]
    if unmeasured:
        if len(unmeasured) == len(rows):
            return ("no concept has cleared %d impressions yet, so there is nothing to "
                    "copy; this release takes its turn in the rotation"
                    % IMPRESSIONS_TO_ADOPT)
        return ("%s has not cleared %d impressions, so a click-rate comparison is not a "
                "comparison yet; this release takes its turn in the rotation"
                % (", ".join(unmeasured), IMPRESSIONS_TO_ADOPT))
    if not report.get("leader"):
        return ("every concept has cleared the floor and none leads clearly enough to "
                "be copied; the rotation continues")
    # A leader exists but `measured_leader` still refused it: the impression floor
    # is the only other reason, so say so rather than hand back a shrug.
    short = [row["concept"] for row in rows
             if int(row.get("impressions") or 0) < IMPRESSIONS_TO_ADOPT]
    if short:
        return ("%s is under the %d-impression floor, so a click-rate comparison is not "
                "a comparison yet; this release takes its turn in the rotation"
                % (", ".join(short), IMPRESSIONS_TO_ADOPT))
    return ("the traffic has not settled on a winner that every concept was measured "
            "against; the rotation continues")


# --------------------------------------------------------------------------- #
# What the traffic said
# --------------------------------------------------------------------------- #
def _concept_of_receipt(path: Path) -> tuple[str, str]:
    """``(concept, video_id)`` from a long-form receipt; empty strings when unknown."""
    try:
        from .script_doc import parse_script

        doc = parse_script(path)
    except Exception:  # noqa: BLE001 - one unreadable receipt is not a failure
        return "", ""
    vid = str(doc.meta.get("youtube_video_id") or "").strip()
    concept = str(doc.meta.get(RECEIPT_FIELD) or "").strip()
    if not concept:
        # Receipts written before the rotation existed carry no concept. Their
        # thumbnail_revision says only which pack rendered, never which frame went
        # live, so they are not counted rather than guessed at.
        return "", vid
    return (concept if concept in CONCEPTS else ""), vid


def assignments_by_channel(published_dir: Path | None = None) -> dict[str, str]:
    """``video_id -> channel`` for the receipts that recorded a concept.

    Kept apart from `read_assignments` so the campaign's own reading stays
    ``video_id -> concept``; this exists only so a coverage gap can be named.
    """
    directory = Path(published_dir) if published_dir else ROOT / "content" / "published"
    out: dict[str, str] = {}
    if not directory.is_dir():
        return out
    for path in sorted(directory.glob("*.md")):
        if path.name.startswith("short-"):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        concept, vid = _concept_of_receipt(path)
        if not (vid and concept):
            continue
        channel = ""
        for line in text.splitlines()[:40]:
            if line.lower().startswith("channel:"):
                channel = line.split(":", 1)[1].strip().strip("\"'")
                break
        out[vid] = channel
    return out


def read_assignments(published_dir: Path | None = None) -> dict[str, str]:
    """``video_id -> concept`` for every receipt that recorded one."""
    directory = Path(published_dir) if published_dir else ROOT / "content" / "published"
    out: dict[str, str] = {}
    if not directory.is_dir():
        return out
    for path in sorted(directory.glob("*.md")):
        if path.name.startswith("short-"):
            continue
        concept, vid = _concept_of_receipt(path)
        if vid and concept:
            out[vid] = concept
    return out


def read_reach(directory: Path | None = None) -> dict[str, dict]:
    """``video_id -> {impressions, clicks, click_rate_percent}`` from the reach files."""
    base = Path(directory) if directory else ROOT / "content" / "analytics"
    out: dict[str, dict] = {}
    if not base.is_dir():
        return out
    for path in sorted(base.glob("*.reach.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8")) or {}
        except (OSError, ValueError):
            continue
        for row in payload.get("videos") or []:
            if not isinstance(row, dict):
                continue
            vid = str(row.get("video_id") or "").strip()
            if not vid:
                continue
            slot = out.setdefault(vid, {"impressions": 0, "clicks": 0})
            slot["impressions"] += int(row.get("impressions") or 0)
            slot["clicks"] += int(row.get("clicks") or 0)
            if payload.get("channel"):
                slot["channel"] = str(payload["channel"])
    for row in out.values():
        row["click_rate_percent"] = (round(100.0 * row["clicks"] / row["impressions"], 2)
                                     if row["impressions"] else None)
    return out


def build_campaign(assignments: dict[str, str] | None = None,
                   reach: dict[str, dict] | None = None,
                   today: date | None = None) -> dict:
    """Click rate per concept, over only the videos that recorded a concept.

    Pooled impressions per concept, so a video with more traffic counts for more -
    the question is which frame earns clicks, not which video was luckier.
    """
    assignments = read_assignments() if assignments is None else assignments
    reach = read_reach() if reach is None else reach
    today = today or date.today()

    rows: dict[str, dict] = {concept: {"concept": concept, "videos": 0, "impressions": 0,
                                       "clicks": 0} for concept in CONCEPTS}
    for vid, concept in assignments.items():
        slot = rows.setdefault(concept, {"concept": concept, "videos": 0,
                                         "impressions": 0, "clicks": 0})
        slot["videos"] += 1
        reading = reach.get(vid)
        if reading:
            slot["impressions"] += reading["impressions"]
            slot["clicks"] += reading["clicks"]

    measured = []
    for row in rows.values():
        row["click_rate_percent"] = (round(100.0 * row["clicks"] / row["impressions"], 2)
                                     if row["impressions"] else None)
        row["measurable"] = row["impressions"] >= MIN_IMPRESSIONS
        measured.append(row)

    # Two different reasons a concept can show no traffic, and they need different
    # fixes. On 26 November 2026 the reading said "no impressions for any concept"
    # while the reach files held 15,081 of them: every assigned video belonged to a
    # channel with no reach file yet, so the join matched nothing. That sentence
    # reads as "the videos got no traffic", which was false and would have sent
    # someone looking at thumbnails instead of at which channels are granted.
    covered = sorted({reach[vid]["channel"] for vid in assignments
                      if vid in reach and reach[vid].get("channel")})
    ownership = assignments_by_channel()
    uncovered = sorted({ownership.get(vid) or "unknown" for vid in assignments
                        if vid not in reach} - {""})
    reach_impressions = sum(int(row.get("impressions") or 0) for row in reach.values())
    trusted = [row for row in measured if row["measurable"]]
    leader = max(trusted, key=lambda row: row["click_rate_percent"]) if trusted else None
    return {
        "schema": 1,
        "as_of": today.isoformat(),
        "concepts": sorted(measured, key=lambda row: -(row["impressions"] or 0)),
        "leader": leader["concept"] if leader else None,
        "leader_click_rate_percent": leader["click_rate_percent"] if leader else None,
        "min_impressions": MIN_IMPRESSIONS,
        "videos_assigned": len(assignments),
        "videos_in_reach": sum(1 for vid in assignments if vid in reach),
        "channels_with_reach": covered,
        "channels_without_reach": uncovered,
        "network_impressions_in_reach_files": reach_impressions,
        "note": ("A per-video Test & Compare cannot be opened or read by the Data API; this "
                 "compares the concepts the rotation put live on different videos of the "
                 "same channel. A concept under the impression floor is shown and not "
                 "trusted."),
        "privacy": "Impressions, clicks and a click rate. No revenue, no viewer.",
        "cost_lock": "$0.00 — reads committed reach files; no API call.",
    }


def write_campaign(report: dict, path: Path | None = None) -> Path:
    target = Path(path) if path else CAMPAIGN_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return target


def headline(report: dict) -> list[str]:
    lines = [f"Videos carrying a recorded concept: {report.get('videos_assigned', 0)}"]
    for row in report.get("concepts") or []:
        rate = row.get("click_rate_percent")
        mark = "" if row.get("measurable") else "  (under the impression floor, not trusted)"
        lines.append(f"  {row['concept']:<7} {row['videos']:>3} videos  "
                     f"{row['impressions']:>6} impressions  "
                     f"{'—' if rate is None else f'{rate:.2f}%'} CTR{mark}")
    if report.get("leader"):
        lines.append(f"Leader: {report['leader']} at {report['leader_click_rate_percent']}%")
    else:
        lines.append("No concept has enough impressions to be trusted yet.")
    return lines


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Thumbnail concept campaign reading")
    parser.add_argument("--out", default="", help="Where to write the report")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    report = build_campaign()
    for line in headline(report):
        print(line)
    if args.dry_run:
        print("[dry-run] not written")
        return 0
    path = write_campaign(report, Path(args.out) if args.out else None)
    print(f"[+] campaign written: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
