# Why the thumbnail loop cannot learn yet

26 November 2026. The learning audit reported `thumbnail_choice` as *measuring*
with the sentence:

> 8 release(s) recorded a concept, but the reach files hold no impressions for any
> of them yet.

That sentence is true and useless. It reads as *the videos got no traffic*. What
the repository actually held that morning:

| reading | value |
| :--- | :--- |
| releases that recorded a thumbnail concept | 11 |
| videos in the reach files | 113 |
| impressions in the reach files | 15,081 |
| assigned videos that join to an impression row | **0** |
| channels with a reach file | **1** (`secret-place`) |
| channels holding an assigned video | prayer2, prayer3, prayer6, prayer7, prayer8, prayer10 |

The join is empty because of **coverage**, not traffic. Every assigned video sits
on a channel whose reach file has not been written, and `secret-place` — the one
channel that has a reach file — holds no video with a recorded concept.

Those are different problems and they have different fixes:

* **no traffic yet** → wait, or make better videos;
* **no reach coverage** → grant the remaining channels and let
  `scripts/reach_reader.py` write their files.

Reporting the second as the first would have sent the next person to look at
thumbnails.

## What changed

`pipeline/thumbnail_campaign.py` now records, next to the concept rows:

* `videos_in_reach` — assigned videos that actually join to an impression row;
* `channels_with_reach` / `channels_without_reach` — where the gap is;
* `network_impressions_in_reach_files` — how much traffic exists network-wide, so
  "no impressions" can never again be said while impressions exist.

`pipeline/learning_audit.py` reads those and names the cause: with traffic
present but no join, it says the concepts are waiting on reach coverage and lists
the channels. With a partial join, it says how many assigned videos are on
uncovered channels. Only when neither applies does it say "no impressions yet".

## What this does not fix

The loop is still `measuring`. Nothing here grants a channel; it only makes the
blocker legible so it can be fixed in the right place. `secret-place`'s reach file
covers **long-form** videos — its 113 rows contain no Short that carries a
concept, which is a second, separate reason that channel contributes nothing to
the campaign even though its file exists.

No causal claim is made here: this compares counts of impressions and clicks
between videos that the rotation put different concepts on, and at zero covered
videos it compares nothing at all.
