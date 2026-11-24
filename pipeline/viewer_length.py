"""How long to make a video, measured from where viewers actually leave.

Why this exists. The three-hour night tail was built on one argument: a viewer who
leaves a prayer playing all night is worth three watch hours. That argument can now
be checked against the channel's own Analytics, and it does not survive.

Six published long-forms have both a real length and a reading (21 November 2026):

| Length | Watched | Share | Views |
| ---: | ---: | ---: | ---: |
| 188.0 min | 10.9 min | 5.8% | 45 |
| 188.0 min | 8.8 min | 4.7% | 70 |
| 187.0 min | 50.1 min | 26.8% | 1 |
| 186.6 min | 4.5 min | 2.4% | 37 |
| 186.5 min | 10.6 min | 5.7% | 18 |
| 186.2 min | 22.3 min | 12.0% | 21 |

The median view of a three-hour video is **ten minutes and forty-five seconds**, and
the average is fourteen. The one outlier at 50 minutes had a *single* view. So the
hours the tail was supposed to produce are not being produced: nothing is being
watched past minute eleven, whether the video is three hours long or six minutes.

What that costs. The night tail extends every bedtime prayer from about six minutes
to three hours, so 99.7% of the file is never seen. It also makes the channel's own
signals worse, not better: a 4.7% average view percentage on a 188-minute upload is
what YouTube ranks on, and it is the number a would-be viewer sees.

What this module does. It reads the measured seconds watched and returns the length a
release should be built to, inside a safety floor. It never argues for a length from
theory: with too few measured videos it keeps what the channel does today and says
so. The release path reads the answer from the growth report, which carries this
module's verdict.

The floor exists for a separate reason: a prayer is authored to a passage's shape and
the renderer already plans its scenes. Cutting a six-minute prayer to three minutes
would break alignment, not improve retention. So the ceiling only removes length that
was added *after* the prayer was authored - the tail - never length the prayer needs.
"""
from __future__ import annotations

import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:  # ``python -m`` runs this as a module, the CLI as a script
    sys.path.insert(0, str(ROOT))

#: A release shorter than this is not what any channel here publishes: the brain
#: authors to about six minutes and the renderer aligns scene by scene.
FLOOR_SECONDS = 300
#: Above this many minutes the tail was doing the lengthening, not the prayer.
TAIL_THRESHOLD_SECONDS = 900
#: How many measured views a verdict needs before it is allowed to cut anything.
MIN_VIDEOS_TO_CUT = 3
#: A single view must not decide a length: one viewer who fell asleep is the
#: outlier that made the tail look reasonable in the first place.
MIN_VIEWS_PER_VIDEO = 5
#: Round the cut to whole minutes so a length reads like a plan, not a measurement.
MINUTE = 60


@dataclass(frozen=True)
class Reading:
    videos: int
    median_seconds: float
    average_seconds: float
    shortest_seconds: float
    longest_seconds: float

    def as_dict(self) -> dict:
        return {
            "videos": self.videos,
            "median_seconds": round(self.median_seconds, 1),
            "average_seconds": round(self.average_seconds, 1),
            "shortest_seconds": round(self.shortest_seconds, 1),
            "longest_seconds": round(self.longest_seconds, 1),
        }


def measured_views(videos: list[dict], lengths: dict[str, int],
                   min_views: int = MIN_VIEWS_PER_VIDEO) -> list[dict]:
    """Videos with both a real length and enough views for the average to mean something.

    ``videos`` are rows from ``content/analytics/<channel>.json``'s ``videos_365d``
    (they carry ``average_view_seconds``); ``lengths`` maps a video id to its real
    length. A planned length is never used, and a video with two views is not
    evidence - the 50-minute outlier had one.
    """
    out = []
    for row in videos:
        vid = str(row.get("video_id") or "").strip()
        seconds = lengths.get(vid)
        if not vid or not seconds:
            continue
        views = int(row.get("views") or 0)
        if views < min_views:
            continue
        watched, derived = None, False
        raw = row.get("average_view_seconds")
        if raw not in (None, ""):
            try:
                watched = float(raw)
            except (TypeError, ValueError):
                watched = None
        if not watched or watched <= 0:
            # Seconds watched are not always in the committed file. The average
            # share viewed and the video's own length give the same figure:
            # percentage x length. It is derived, and it is labelled as derived.
            percent = row.get("average_view_percent")
            try:
                percent = float(percent)
            except (TypeError, ValueError):
                percent = 0.0
            if percent <= 0:
                continue
            watched, derived = seconds * percent / 100.0, True
        out.append({"video_id": vid, "length_seconds": seconds,
                    "watched_seconds": round(watched, 1), "views": views,
                    "percent": row.get("average_view_percent"),
                    "derived": derived})
    return out


def read(rows: list[dict]) -> Reading | None:
    """The measured shape of attention, or ``None`` when nothing is measured."""
    if not rows:
        return None
    watched = [row["watched_seconds"] for row in rows]
    return Reading(
        videos=len(rows),
        median_seconds=statistics.median(watched),
        average_seconds=statistics.fmean(watched),
        shortest_seconds=min(watched),
        longest_seconds=max(watched),
    )


def ceiling_seconds(reading: Reading | None, *, current_seconds: int) -> dict:
    """The length to build to, and why.

    The rule: never build a video longer than viewers measurably watch. The cut is
    the median watched time, rounded down to whole minutes and held above the floor.
    With too little evidence the current length stands untouched, so this can only
    act on a reading that exists.
    """
    if reading is None or reading.videos < MIN_VIDEOS_TO_CUT:
        return {
            "seconds": int(current_seconds),
            "minutes": round(int(current_seconds) / MINUTE, 1),
            "changed": False,
            "basis": (f"fewer than {MIN_VIDEOS_TO_CUT} videos have a real length, >= "
                      f"{MIN_VIEWS_PER_VIDEO} views and a reading; keeping "
                      f"{round(int(current_seconds) / MINUTE, 1)} minutes"),
        }
    wanted = int(max(FLOOR_SECONDS, reading.median_seconds))
    wanted = (wanted // MINUTE) * MINUTE
    wanted = int(min(wanted, max(int(current_seconds), FLOOR_SECONDS)))
    if current_seconds <= 0:
        current_seconds = wanted
    return {
        "seconds": wanted,
        "minutes": round(wanted / MINUTE, 1),
        "changed": wanted != int(current_seconds),
        "basis": (f"the median view of a measured video is "
                  f"{round(reading.median_seconds / MINUTE, 1)} minutes "
                  f"(across {reading.videos} videos); a release is not built longer than that"),
        "reading": reading.as_dict(),
    }


def tail_is_the_problem(reading: Reading | None, current_seconds: int) -> bool:
    """True when the measured watch time is far below the length being published."""
    if reading is None or current_seconds <= TAIL_THRESHOLD_SECONDS:
        return False
    return reading.median_seconds < current_seconds / 4


def wasted_share(reading: Reading | None, current_seconds: int) -> float | None:
    """The share of each published minute that is never watched."""
    if reading is None or current_seconds <= 0:
        return None
    return round(max(0.0, 1.0 - min(reading.median_seconds / current_seconds, 1.0)), 4)
