"""The church year: which prayers belong to which days, and when they go out.

Before 14 November 2026 nothing in any passage list knew what day it was. A
channel prayed Psalm 91 on Christmas morning and Proverbs 3 on crossover night,
the two nights of the year a Nigerian Christian is most likely to be looking
for a prayer. Advent 2026 begins on 29 November.

A season is a span of dates worked out for any year (Easter moves; the rule for
it is here, not a table that runs out). Each channel has a few passages for
each season, chosen for what that channel is for. While a season is open:

* the brain writes that channel's seasonal Shorts first, even when its queue is
  already full (``GeminiBrain._seasonal_pass``), and tells the writer what day
  the prayer is for;
* the selector sends a seasonal Short out ahead of everything else, never
  before its season opens, and withdraws it once the season has closed
  (``pipeline/short_release.py``).

No passage is given to two channels, and none is on another channel's evergreen
list or roadmap: ten channels praying the same verse on the same day is the
templated content YouTube's inauthentic-content policy describes.

Dates are read in Nigeria time (UTC+1), where the channels' reports are read.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

#: Hours ahead of UTC the calendar is read in (West Africa Time).
CALENDAR_UTC_OFFSET_HOURS = 1
#: A season's Shorts are written this many days before it opens, so the first
#: is ready on the first morning rather than written on it.
AUTHOR_LEAD_DAYS = 2
#: Seasonal Shorts written per brain pass, on top of the ordinary allowance.
MAX_SEASONAL_PER_PASS = 2


@dataclass(frozen=True)
class Season:
    name: str        # key into PASSAGES
    label: str       # how the day is named to the writer and in notices
    start: date      # first day a seasonal Short may publish
    end: date        # last day

    def open_on(self, day: date) -> bool:
        return self.start <= day <= self.end


#: What the writer is told about the day, in a sentence.
OCCASIONS: dict[str, str] = {
    "advent": ("Advent, the weeks of waiting before Christmas: the promise of Christ's "
               "coming, light on its way into the dark"),
    "christmas": "Christmas: the birth of Jesus Christ, God with us",
    "new_year": ("the crossing from the old year into the new one (crossover night and the "
                 "first days of January): thanks for the year behind, trust for the year ahead"),
    "holy_week": "Holy Week: the days from Palm Sunday to the cross and the silent Saturday",
    "easter": "Easter: the resurrection of Jesus Christ",
}

#: season -> channel -> passages, most fitting first.
PASSAGES: dict[str, dict[str, tuple[str, ...]]] = {
    "advent": {
        "secret-place": ("Isaiah 9:2", "Lamentations 3:25-26"),
        "prayer2": ("Romans 13:11-12", "Luke 1:78-79"),
        "prayer3": ("Galatians 4:4-5", "James 5:7-8"),
        "prayer4": ("Luke 1:68-71", "Isaiah 59:20"),
        "prayer5": ("Matthew 1:20-21", "Luke 1:16-17"),
        "prayer6": ("Malachi 4:2", "Isaiah 35:5-6"),
        "prayer7": ("Luke 1:53", "Isaiah 55:1"),
        "prayer8": ("Isaiah 7:14", "Luke 1:30-31"),
        "prayer9": ("Psalm 96:11-13", "Isaiah 52:9"),
        "prayer10": ("Isaiah 40:3", "Micah 5:2"),
    },
    "christmas": {
        "secret-place": ("Luke 2:10-11", "John 1:5"),
        "prayer2": ("Isaiah 9:6", "John 1:14"),
        "prayer3": ("Titus 2:11", "John 1:16"),
        "prayer4": ("1 John 3:8", "Isaiah 9:7"),
        "prayer5": ("Luke 2:6-7", "Matthew 2:11"),
        "prayer6": ("John 3:16-17", "Hebrews 4:15-16"),
        "prayer7": ("2 Corinthians 8:9", "Ephesians 1:3"),
        "prayer8": ("Matthew 1:23", "Matthew 2:13-14"),
        "prayer9": ("Luke 2:13-14", "2 Corinthians 9:15"),
        "prayer10": ("Matthew 2:9-10", "Matthew 2:12"),
    },
    "new_year": {
        "secret-place": ("Psalm 31:15", "Hebrews 13:8"),
        "prayer2": ("Revelation 21:5", "Isaiah 42:9"),
        "prayer3": ("Philippians 3:13-14", "Hebrews 12:1-2"),
        "prayer4": ("Exodus 14:13", "Deuteronomy 28:13"),
        "prayer5": ("Psalm 115:14", "Isaiah 54:13"),
        "prayer6": ("Psalm 92:14", "Proverbs 4:20-22"),
        "prayer7": ("Psalm 65:11", "Job 8:7"),
        "prayer8": ("Deuteronomy 11:12", "Exodus 23:20"),
        "prayer9": ("1 Samuel 7:12", "Psalm 136:1"),
        "prayer10": ("Isaiah 58:11", "Psalm 73:23-24"),
    },
    "holy_week": {
        "secret-place": ("Luke 23:46",),
        "prayer2": ("Zechariah 9:9",),
        "prayer3": ("Mark 14:38",),
        "prayer4": ("Hebrews 2:14-15",),
        "prayer5": ("John 19:26-27",),
        "prayer6": ("Isaiah 53:4-5",),
        "prayer7": ("Romans 8:32",),
        "prayer8": ("John 10:11",),
        "prayer9": ("Matthew 21:9",),
        "prayer10": ("Luke 22:42",),
    },
    "easter": {
        "secret-place": ("John 20:19",),
        "prayer2": ("Matthew 28:5-6",),
        "prayer3": ("Philippians 3:10",),
        "prayer4": ("1 Corinthians 15:55-57",),
        "prayer5": ("Luke 24:29-31",),
        "prayer6": ("John 11:25-26",),
        "prayer7": ("1 Peter 1:3-4",),
        "prayer8": ("Revelation 1:17-18",),
        "prayer9": ("Job 19:25",),
        "prayer10": ("Luke 24:32",),
    },
}


def easter_sunday(year: int) -> date:
    """Western Easter (the date most Nigerian churches keep), by the Gregorian rule."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    weekday = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * weekday) // 451
    month = (h + weekday - 7 * m + 114) // 31
    day = (h + weekday - 7 * m + 114) % 31 + 1
    return date(year, month, day)


def advent_sunday(year: int) -> date:
    """The fourth Sunday before Christmas Day."""
    christmas = date(year, 12, 25)
    last_sunday = christmas - timedelta(days=(christmas.weekday() + 1) % 7 or 7)
    return last_sunday - timedelta(days=21)


def seasons_touching(year: int) -> list[Season]:
    """Every season with a day in ``year``, in date order."""
    easter = easter_sunday(year)
    found = [
        # The new year that began as this year opened, and the one that ends it.
        Season("new_year", "the New Year", date(year - 1, 12, 30), date(year, 1, 2)),
        Season("holy_week", "Holy Week", easter - timedelta(days=7), easter - timedelta(days=1)),
        Season("easter", "Easter", easter, easter + timedelta(days=2)),
        Season("advent", "Advent", advent_sunday(year), date(year, 12, 23)),
        Season("christmas", "Christmas", date(year, 12, 24), date(year, 12, 26)),
        Season("new_year", "the New Year", date(year, 12, 30), date(year + 1, 1, 2)),
    ]
    return sorted(found, key=lambda season: season.start)


def today(now: datetime | None = None) -> date:
    """The calendar day in Nigeria."""
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return (moment.astimezone(timezone.utc)
            + timedelta(hours=CALENDAR_UTC_OFFSET_HOURS)).date()


def open_seasons(day: date | None = None) -> list[Season]:
    """Seasons whose Shorts may publish on ``day``."""
    day = day or today()
    return [season for season in seasons_touching(day.year) if season.open_on(day)]


@dataclass(frozen=True)
class Due:
    reference: str
    season: Season
    not_before: date     # first day this Short may publish

    @property
    def not_after(self) -> date:
        return self.season.end


def release_day(season: Season, index: int, count: int) -> date:
    """The first day the ``index``-th of a channel's ``count`` Shorts for a season may publish.

    Spread across the season rather than spent on its first morning: two Advent
    Shorts go out on Advent Sunday and twelve days later, two Christmas Shorts
    on Christmas Eve and Christmas Day.
    """
    span = (season.end - season.start).days + 1
    return season.start + timedelta(days=(span // max(count, 1)) * index)


def due(channel_id: str, day: date | None = None) -> list[Due]:
    """The seasonal Shorts this channel should have written by now, soonest first.

    A Short is due from ``AUTHOR_LEAD_DAYS`` before its release day until its
    season closes.
    """
    from .channels import normalize_channel_id

    day = day or today()
    channel = normalize_channel_id(channel_id)
    out: list[Due] = []
    for season in seasons_touching(day.year):
        references = PASSAGES.get(season.name, {}).get(channel, ())
        for index, reference in enumerate(references):
            release = release_day(season, index, len(references))
            if release - timedelta(days=AUTHOR_LEAD_DAYS) <= day <= season.end:
                out.append(Due(reference, season, release))
    return sorted(out, key=lambda item: item.not_before)


def next_season(day: date | None = None) -> Season | None:
    """The next season to open after ``day`` (for reports)."""
    day = day or today()
    for year in (day.year, day.year + 1):
        for season in seasons_touching(year):
            if season.start > day:
                return season
    return None


def _as_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except (TypeError, ValueError):
        return None


def manifest_window(manifest: dict, day: date | None = None) -> str:
    """Where a queued Short stands against its dates: ``"none"``, ``"early"``, ``"open"`` or ``"closed"``.

    ``none``: the manifest has no dates (every ordinary Short). ``early``: its
    first day has not come. ``open``: it may publish today and goes first.
    ``closed``: its last day has passed.
    """
    first = _as_date((manifest or {}).get("not_before"))
    last = _as_date((manifest or {}).get("not_after"))
    if first is None and last is None:
        return "none"
    day = day or today()
    if first is not None and day < first:
        return "early"
    if last is not None and day > last:
        return "closed"
    return "open"

