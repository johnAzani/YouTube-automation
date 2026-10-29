"""Autonomous Pinned Comment & First-Hour Engagement Engine.

Generates and inserts high-conversion pastoral pinned comments immediately upon
video upload to trigger First-Hour Engagement Velocity ($V_{1hr}$), driving
algorithmic distribution in YouTube's recommendation engine.

Cost & Safety Invariants:
  • $0.00 / month hard cost lock (consumes 50 YouTube Data API units per upload).
  • Zero mentions of personal names (John Azani); speaks exclusively as The Secret Place.
  • Anti-spam compliant; encourages faith declarations ("AMEN") and prayer requests.
"""
from __future__ import annotations

import re
from typing import Any

from .config import CONFIG
from .script_doc import ScriptDoc


def generate_pastoral_pinned_comment(doc: ScriptDoc) -> str:
    """Generate an authoritative, comforting pinned comment for the video.

    If the video is a Short, automatically generates a high-conversion bridge comment
    linking viewers directly to the full-length long-form prayer video.
    """
    title_lower = (doc.title or "").lower()
    is_short = (
        getattr(doc, "format", "") == "short"
        or doc.meta.get("format") == "short"
        or "#shorts" in title_lower
        or (getattr(doc, "slug", "") and "short-" in getattr(doc, "slug", ""))
    )

    if is_short:
        try:
            from .shorts_bridge import generate_short_bridge_comment
            short_key = getattr(doc, "slug", "") or doc.title
            return generate_short_bridge_comment(short_key)
        except Exception:
            pass

    if "psalm 91" in title_lower:
        scripture_hook = "Psalm 91:4 — 'He shall cover you with His feathers, and under His wings you shall take refuge; His truth shall be your shield and buckler.'"
        theme = "divine protection and angelic shelter"
    elif "psalm 23" in title_lower:
        scripture_hook = "Psalm 23:1-2 — 'The Lord is my shepherd; I shall not want. He makes me to lie down in green pastures; He leads me beside the still waters.'"
        theme = "divine rest, healing, and peace"
    elif "psalm 121" in title_lower:
        scripture_hook = "Psalm 121:3-4 — 'He that keepeth thee will not slumber. Behold, He that keepeth Israel shall neither slumber nor sleep.'"
        theme = "unsleeping protection and peaceful sleep"
    elif "psalm 27" in title_lower:
        scripture_hook = "Psalm 27:1 — 'The Lord is my light and my salvation; whom shall I fear? The Lord is the strength of my life; of whom shall I be afraid?'"
        theme = "courage and freedom from nighttime anxiety"
    else:
        scripture_hook = "Numbers 6:24-26 — 'The Lord bless you and keep you; the Lord make His face shine upon you and give you peace.'"
        theme = "sacred peace and restorative sleep"

    comment = (
        f"🕊️ Beloved family, if you are listening to this tonight, write 'AMEN' in faith to claim "
        f"God's promise of {theme} over your home, your children, and your mind.\n\n"
        f"📖 {scripture_hook}\n\n"
        f"Drop your prayer requests below — our pastoral editorial team reads and intercedes over "
        f"every single name before this night closes. Rest in holy stillness tonight. You are not alone. 🙏✨"
    )
    return comment.strip()


def post_pastoral_pinned_comment(
    youtube: Any,
    video_id: str,
    comment_text: str,
    dry_run: bool = False,
) -> str | None:
    """Insert a top-level comment on the newly uploaded video."""
    if dry_run or not youtube:
        print(f"[pinned-comment] [dry-run] Would post pinned comment on video '{video_id}':")
        print(f"  \"{comment_text[:120]}...\"")
        return f"mock_comment_{video_id}"

    try:
        req = youtube.commentThreads().insert(
            part="snippet",
            body={
                "snippet": {
                    "videoId": video_id,
                    "topLevelComment": {
                        "snippet": {
                            "textOriginal": comment_text,
                        }
                    },
                }
            },
        )
        res = req.execute()
        comment_id = res.get("id")
        print(f"[pinned-comment] Successfully posted pastoral comment on video '{video_id}' (ID: {comment_id})")
        return comment_id
    except Exception as exc:
        print(f"[pinned-comment] Notice: error posting pinned comment: {exc}")
        return None
