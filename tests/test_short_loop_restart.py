"""The last spoken frame is the last frame of a prayer Short.

Measured 17 November 2026 on The Secret Place Analytics: Psalm 18:2 sat at
98.8% viewed (125 views, 54.3s) and Psalm 139:11-12 at 99.6% (52 views, 62.2s).
The renderer used to add 1.6s after the narration so a SUBSCRIBE card could
play. Average % viewed is duration-relative; that tail is 3% of a 54s clip —
exactly the gap between watching to the last word and a loop. Documentary
Shorts keep the card. Specs still declare `end: SUBSCRIBE`; it is not painted
onto a prayer Short. Queued specs keep loading.
"""
from pipeline import short_script as ss
from pipeline.short_script import (
    DOCUMENTARY_TAIL_SECONDS,
    PRAYER_TAIL_SECONDS,
    clip_length,
    paints_subscribe_card,
)


def test_a_prayer_short_ends_when_the_voice_does():
    assert PRAYER_TAIL_SECONDS == 0.0
    assert clip_length(54.25, is_prayer=True) == 54.25
    assert clip_length(62.21, is_prayer=True) == 62.21
    assert clip_length(0, is_prayer=True) == 0.0


def test_a_documentary_short_still_has_room_for_its_card():
    assert DOCUMENTARY_TAIL_SECONDS == 1.6
    assert clip_length(40.0, is_prayer=False) == 41.6


def test_the_subscribe_card_is_not_painted_on_a_prayer_short():
    assert paints_subscribe_card(is_prayer=True) is False
    assert paints_subscribe_card(is_prayer=False) is True


def test_the_author_is_told_the_next_frame_is_the_hook():
    prompt = ss.build_prompt("Psalm 23:1-3", avoid_openings=[])
    assert "The renderer does not" in prompt
    assert "paint a subscribe card" in prompt
    assert "next frame is caption 1" in prompt
    # Specs still carry the two-line end card; it is data, not a closer on screen.
    assert '"end": ["SUBSCRIBE"' in prompt
