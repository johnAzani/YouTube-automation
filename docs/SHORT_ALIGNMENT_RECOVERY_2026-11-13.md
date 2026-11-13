# Shorts stuck behind one rejected take (13 November 2026)

## What happened

In the two production runs of the afternoon and evening of 13 November (started
4:50pm and 8:58pm Nigeria time), seven channels failed their Short with the
same message, for the same Short both times:

`cannot prepare Charon narration for <short> (Short speech alignment unavailable or incomplete; refusing to render)`

| Channel | Short stuck at the head of its queue |
|---|---|
| The Secret Place | `short-psalm3v3` |
| The Morning Altar | `short-morningpsalm37v23` |
| The Midday Watch | `short-middaygalatians6v9` |
| The Family Altar | `short-familyproverbs24v3` |
| The Healing Balm | `short-healingjeremiah17v14` |
| The Covenant Shield | `short-shieldproverbs18v10` |
| The Praise Garden | `short-gardenpsalm103v2` |

The Midnight Watch and The Provision Table released Shorts in the same runs, on
the same runners, so the speech model and the environment were working.

## Why it never recovered

1. A Short's narration (`assets/deepdive/short-*.mp3`) and its provenance file
   are saved to the Actions cache at the end of a leg and restored by the next.
2. When alignment rejected a take, nothing deleted it. The long-form path purges
   its take on the same signal (`_purge_corrupted_speech_artifacts`); the Short
   path did not.
3. On the next run the restored take still looked valid (same text hash, same
   audio checksum), so it was not re-synthesised. It was aligned again and
   refused again.
4. A channel releases its queued Shorts in order, so every later Short waited
   behind the stuck one.

The error also hid its cause: the message carried no detail from the aligner,
and run logs cannot be read from the build sandbox. Whether the seven takes are
bad audio or something about those texts is therefore not known yet.

## What changed (`pipeline/short_release.py`)

- A take that alignment rejects is deleted (audio, provenance, word timings),
  so it cannot be cached and replayed.
- If the rejected take came from the cache, one fresh take is synthesised and
  aligned in the same run. If the take had just been synthesised, the run stops
  there, so a Short still costs at most one speech request per run.
- The error now carries the aligner's reason, for example
  `[ValueError: ...]`, and it reaches the run page annotation.
- A missing speech model or a crash in the aligner is not treated as a bad
  take: the audio is kept and nothing is counted.
- Each rejected take is counted on the Short's queue manifest
  (`alignment_failures`, `last_alignment_error`). At three, the manifest becomes
  `status: alignment_paused` and the channel's next Short releases instead.
  Setting `status: approved` again and removing `alignment_failures` puts it
  back in line.

## What to expect

At the next slot each of the seven channels discards its saved take and speaks
a new one. If the new take aligns, the Short goes out. If it does not, the run
page now says why, and after three takes the channel moves on to its next Short.

## Tests

`tests/test_short_alignment_recovery.py` (10).
