"""What the YouTube Data API charges for the calls this pipeline makes.

The API is free and metered in *units*. A Google Cloud project has two
allowances, and this repository holds two different beliefs about which one an
upload spends:

* an **upload allowance** — since Google's 1 June 2026 granular-quota change,
  ``videos.insert`` is billed at **1 unit against a separate allowance of 100
  calls a day** (``pipeline/upload.py``, ``requirements.txt``, ``docs/SETUP.md``);
* the **shared pool** — every other method, **10,000 units a day** on a default
  project, where ``thumbnails.set`` is 50, ``commentThreads.insert`` 50,
  ``comments.insert`` 50, ``playlistItems.insert`` 50, ``videos.update`` 50,
  ``captions.insert`` 400 and every ``list`` 1.

Before that change an upload cost 1,600 units of the shared pool — six a day —
and ``pipeline/quota_handler.py``, ``pipeline/channels.py`` and
``docs/FAST_TRACK_4000_WATCH_HOURS.md`` §5.1 still say so.

The receipts settle which one is running here, without trusting either
document: under 1,600 units an upload, seven uploads in one quota day is
impossible, and ``secret-place`` uploaded **eight** on 11 November 2026 by
Pacific quota day, with nine channel-days at seven. So the upload allowance is
the one in force, and the price that matters is the shared pool's — where a
caption track costs eight comments, a comment costs four hundred uploads' worth
of the upload allowance, and a reply costs what
``pipeline/comment_replies.py`` used to call twenty-five replies.

Where the numbers come from: Google's published method-level prices. The
discovery document bundled with the client carries **no method-level price at
all** — the only quota sentences in it are the part cost ("the snippet part has
a quota cost of 2 units") and the live-chat methods, which is exactly the
sentence a 2026-11-07 audit read as the price of a comment reply.

Reading: ``docs/API_BUDGET_RESEARCH_2026-11-17.md``.
"""
from __future__ import annotations

from typing import Any, Mapping

# Method-level prices, in units. Google publishes these on each method's page
# (not in the discovery document); none of them has changed since the granular
# upload allowance above.
UNIT_COST: dict[str, int] = {
    # The upload allowance: 100 calls a day, one unit each, separate from the pool.
    "videos.insert": 1,
    # Reads: one unit each, however many ids or pages.
    "videos.list": 1,
    "channels.list": 1,
    "playlistItems.list": 1,
    "commentThreads.list": 1,
    "comments.list": 1,
    "playlists.list": 1,
    # Writes: fifty units each.
    "thumbnails.set": 50,
    "commentThreads.insert": 50,
    "comments.insert": 50,
    "playlistItems.insert": 50,
    "playlists.insert": 50,
    "videos.update": 50,
    "videos.delete": 50,
    # The expensive ones.
    "captions.list": 50,
    "captions.insert": 400,
    "captions.download": 200,
    "search.list": 100,
}

# A default Google Cloud project's day, for everything except ``videos.insert``.
SHARED_POOL_UNITS = 10_000
# A default project's upload allowance, calls a day.
UPLOADS_PER_DAY = 100
# The list calls every upload makes around its insert: two ``channels.list``
# (own id, uploads playlist), one ``playlistItems.list`` and the ``videos.list``
# that confirms the upload landed.
UPLOAD_VERIFY_UNITS = 4


def price_upload(*, thumbnail: bool = False, comment: bool = False,
                 caption: bool = False, playlist: bool = False) -> tuple[int, dict[str, int]]:
    """Units one upload spends, from what it actually did."""
    parts = {"videos.insert": UNIT_COST["videos.insert"],
             "list calls": UPLOAD_VERIFY_UNITS}
    if thumbnail:
        parts["thumbnails.set"] = UNIT_COST["thumbnails.set"]
    if comment:
        parts["commentThreads.insert"] = UNIT_COST["commentThreads.insert"]
    if caption:
        parts["captions.insert"] = UNIT_COST["captions.insert"]
    if playlist:
        parts["playlistItems.insert"] = UNIT_COST["playlistItems.insert"]
    return sum(parts.values()), parts


def price_receipt(meta: Mapping[str, Any]) -> tuple[int, dict[str, int]]:
    """Units one receipt's upload spent, read off the receipt itself.

    A receipt records the three calls that cost real money — ``thumbnail_revision``
    (50), ``top_comment: "ok"`` (50) and ``caption_track: "ok"`` (400) — so a
    receipt written before 17 November prices low by whatever it never recorded:
    long-form receipts carried no caption status at all until that day.
    """
    def _flag(key: str) -> bool:
        return str(meta.get(key) or "").strip().lower().startswith("ok")

    return price_upload(
        thumbnail=bool(str(meta.get("thumbnail_revision") or "").strip()),
        comment=_flag("top_comment"),
        caption=_flag("caption_track"),
        playlist=_flag("playlist"),
    )
