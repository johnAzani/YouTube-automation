# Channel parity — every channel is a first-class citizen

The rule, in one sentence:

> **Every channel has every capability, runs the same code, and is described by the
> same data shape. An update made for one channel is an update for all of them.**

This is not a style preference. The automation grew a second channel by bolting on
`if channel == "prayer2"` branches, and each one became a silent second-class
citizen: The Morning Altar had no autonomous brain, no Shorts and no queue row of
its own; The Secret Place had no per-channel supply loop, no per-channel watchdog
alarm and a different supply command in the workflow. None of it was visible from
the other channel's runs, and none of it failed a test. The parity lock exists so
that it cannot happen again.

## The three pieces

| Piece | Purpose |
|---|---|
| `pipeline/channel_capabilities.py` | **The only place that knows which channel is which.** Each channel's equipment files, roadmap, branding strings, pinned-comment templates, Shorts dressing, key namespace, supply target and legacy row names. |
| `scripts/channel_parity.py` | Prints the matrix and re-proves the invariants in production (`automation-health.yml` runs it daily). |
| `tests/test_channel_parity.py` | **The lock.** CI fails when the channels drift apart. |

## What parity means concretely

Every channel, by construction, has all of these (`REQUIRED_CAPABILITIES` in
`pipeline/channel_capabilities.py`):

| Capability | Where it lives |
|---|---|
| `brain_supply` — unattended long-form authoring from its own roadmap | `pipeline/gemini_brain.py`, `pipeline/supply.py`, `scripts/gemini_brain.py --ensure-supply-for <channel>` |
| `backlog_expansion` — lengthening under-floor scripts on its own quota | `tools/expand_scripts.py::under_gate(channel_id=…)` |
| `factcheck_gate` — worksheet + approval choke point before publishing | `scripts/factcheck.py`, `pipeline/supply.py::set_status` |
| `per_channel_queue_rows` — its own queue-health and watchdog rows | `scripts/automation_health.py`, `scripts/pipeline_watchdog.py` |
| `scheduled_production` — its own leg of the scheduled Produce run | `.github/workflows/produce.yml` |
| `companion_shorts` — Shorts queued, authored, dressed and published per channel | `pipeline/short_release.py`, `pipeline/short_script.py`, `pipeline/gemini_brain.py` |
| `branded_authoring` — refuses output branded for another channel | `GeminiBrain._enforce_channel_metadata` (brand data from the matrix) |
| `roadmap_queue` — its own roadmap, globally unique job ids | `scripts/continuous_research.py` |
| `per_channel_quota` — its own Gemini key pool | `pipeline/gemini_tts.py::gemini_key_names` + `ChannelProfile.secret_prefix` |
| `owner_idle_safety` — free-tier exhaustion idles only that channel | workflows + `idle`/`blocked` reporting; $0 lock |

There are **no per-channel feature flags**. A capability is available on every
channel or on none: a flag is how "later" becomes "never" and then "nobody
remembers".

## The rules for changing anything

1. **Never compare a channel id to a literal.** Read
   `pipeline/channel_capabilities.capabilities_for(channel_id)`. The parity test
   parses every file in `pipeline/`, `scripts/` and `tools/` and fails on a
   comparison against `"prayer2"`, `"secret-place"` or `"morning-altar"` outside
   the small allowlist (the registry, the profiles, the roadmap map, dataclass
   defaults).
2. **New capability → all channels.** Add it to `REQUIRED_CAPABILITIES`, give
   every channel what it needs in the matrix, wire it for every channel, and say
   so in the table above. If one channel genuinely must not have it, the
   capability does not ship.
3. **New channel → registry entries only.** Add the profile to
   `pipeline.channels.CHANNELS`, a block to `pipeline/channel_capabilities.py`
   (equipment files, roadmap, brand, Shorts dressing), a roadmap to
   `scripts/continuous_research.py`, and the secrets mapping to
   `produce.yml` / `gemini_brain.yml`. The parity test lists anything you missed.
4. **Workflows gate on data, never on names.** A step's `if:` must not mention a
   channel. Secret mapping (`secrets.PRAYER2_*` ternaries in `env:`) is the sole
   exception, because GitHub cannot resolve a secret name from a variable.
5. **Branding is data.** Titles, tags, CTAs, pinned comments, Short dressing and
   the phrases that must/must not appear are all in the brand block. No f-string
   in the pipeline should contain a channel name.
6. **Both channels or neither, in the same commit.** A PR that improves one
   channel's pipeline and leaves the other's behaviour unchanged is either
   routed through the matrix (and then both change together) or is not ready.

## What "same" does *not* mean

Parity is about **capability and code path**, not identical output. These are
legitimately per-channel *data*, all declared in the matrix:

- time of day (night arc vs sunrise arc) and therefore equipment, roadmap and prompts;
- brand name, handle, CTA, pinned comment, Shorts title/tags/description;
- the Selar/store funnel, which belongs to Channel 1 only (`include_sanctuary_links`);
- the Gemini key pool and the YouTube OAuth project;
- Short key namespace (channel 1 keeps its historic unprefixed keys; later
  channels namespaced, e.g. `short-morningpsalm143v8`).

## Verifying

```bash
python scripts/channel_parity.py          # matrix + invariant checks, exit 0 = parity
python -m pytest tests/test_channel_parity.py -q
```

`automation-health.yml` runs the first daily and prints it to the run summary, so
drift is visible without opening the test suite.

## Known shared-data follow-ups (not parity gaps)

Both channels share these, so neither is second-class — but each is single-channel
*data* dressed as shared infrastructure, and each is the next parity-shaped
improvement. They are listed here rather than silently fixed so the decision is
visible:

1. **Render-layer copy.** End-screen captions, dark-screen descriptions and the
   printable journal are written in Channel 1's night voice. The Morning Altar's
   renders therefore inherit night-flavoured on-screen copy.
2. **Metrics history.** The metrics snapshot behind the brain audit's subscriber
   and watch-hour figures only has Channel 1 history, so the audit labels those
   numbers instead of presenting them as the second channel's.

Neither is a capability gap: both channels run the same code and the same steps.
