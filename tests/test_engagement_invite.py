"""Like, comment, share and subscribe — in the comment, not on the last frame.

A subscribe card on a Short is a closer. The four YouTube actions still matter
(Help counts them after average % viewed), so they live in the first comment
and the description, named for this channel, not spoken over the loop.
"""
from pipeline.channel_capabilities import (
    engagement_invite,
    known_channels,
    pinned_comment_for,
    short_pinned_comment_for,
    with_engagement_invite,
    brand_for,
)
from pipeline.shorts_bridge import (
    enrich_short_description_with_bridge,
    generate_short_bridge_comment,
)


def test_every_channel_asks_for_all_four_actions():
    for channel in known_channels():
        line = engagement_invite(channel)
        name = brand_for(channel).display_name
        assert "like it" in line
        assert "comments" in line
        assert "share it" in line
        assert f"subscribe to {name}" in line
        # Named for this channel so ten invites are not the same sentence.
        for other in known_channels():
            if other == channel:
                continue
            assert brand_for(other).display_name not in line


def test_the_invite_is_appended_once():
    line = engagement_invite("secret-place")
    once = with_engagement_invite("A prayer.", "secret-place")
    twice = with_engagement_invite(once, "secret-place")
    assert once == twice
    assert once.count(line) == 1
    assert once.startswith("A prayer.")


def test_longform_and_short_comments_carry_the_invite():
    longform = pinned_comment_for("secret-place", theme="peace", scripture_hook="Psalm 23")
    short = short_pinned_comment_for(
        "secret-place", url="https://youtu.be/7RDX0fbIOtQ",
        scripture="Psalm 91", theme="peace")
    invite = engagement_invite("secret-place")
    assert invite in longform and invite in short
    assert generate_short_bridge_comment("short-psalm91").endswith(invite)


def test_a_short_description_keeps_hashtags_last():
    orig = "Rest tonight under God's divine shield. Psalm 91.\n\n#Shorts #Psalm91"
    enriched = enrich_short_description_with_bridge(orig, "short-psalm91")
    invite = engagement_invite("secret-place")
    assert invite in enriched
    assert orig.splitlines()[0] in enriched
    last = enriched.rstrip().splitlines()[-1]
    assert last.lstrip().startswith("#")
    assert invite not in last
    again = enrich_short_description_with_bridge(enriched, "short-psalm91")
    assert again.count(invite) == 1
