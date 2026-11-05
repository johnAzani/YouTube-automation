"""Channel parity lock.

The rule this file enforces, in one sentence:

    The Secret Place and The Morning Altar (and any channel added later) have the
    same capabilities, run the same code, and are described by the same data
    shape — so an update made for one channel is an update for all of them.

Each test fails in a direction that used to be silent:

* a capability that exists for one channel only;
* a channel branch written as a literal instead of read from
  ``pipeline/channel_capabilities.py`` (that is what let "The Morning Altar has
  no brain / no Shorts" and "The Secret Place has no per-channel queue row"
  exist at the same time, each invisible from the other channel's runs);
* a workflow that stops covering a channel, or gates a *step* on a channel name;
* branding that could leak from one channel into the other.

If a change genuinely must apply to one channel only, it does not belong here as
a special case: either it is a capability of every channel, or it does not ship.
"""
from __future__ import annotations

import ast
import dataclasses
import re
import tempfile
import unittest
from pathlib import Path

import yaml

from pipeline import channel_capabilities as cc
from pipeline.channels import CHANNELS
from pipeline.script_doc import parse_script
from scripts.continuous_research import roadmap_for_channel

ROOT = Path(__file__).resolve().parents[1]

#: Production code allowed to name a channel literally: the registry itself, the
#: channel profiles, the roadmap namespace map, and dataclass defaults that mean
#: "channel 1 unless told otherwise". Everything else reads the capability matrix.
LITERAL_CHANNEL_ALLOWLIST = {
    "pipeline/channels.py",
    "pipeline/channel_capabilities.py",
    "pipeline/config.py",              # CHANNEL_ID default for local runs
    "pipeline/short_release.py",       # ShortEdition dataclass default
    "pipeline/short_script.py",        # ShortSpec dataclass default
    "scripts/continuous_research.py",  # roadmap namespace -> roadmap list
}

CHANNEL_SCOPED_WORKFLOWS = ("produce.yml", "gemini_brain.yml")
WORKFLOWS_WITH_CHANNEL_CHOICE = ("produce.yml", "comments.yml", "metrics.yml")


class TestCapabilityMatrix(unittest.TestCase):
    def test_every_registered_channel_has_a_block(self):
        self.assertEqual(set(cc.known_channels()), set(CHANNELS))

    def test_no_declared_field_is_empty_for_any_channel(self):
        """The matrix has no per-channel feature flags: all or nothing."""
        for channel_id in cc.known_channels():
            caps = cc.capabilities_for(channel_id)
            self.assertEqual(caps.channel_id, channel_id)
            for field in dataclasses.fields(cc.ChannelCapabilities):
                if field.name == "legacy_queue_alias":
                    continue  # channel 1 keeps a historic row name; that is data
                value = getattr(caps, field.name)
                self.assertTrue(value not in (None, "", (), {}, []),
                                f"{channel_id} declares an empty {field.name}")

    def test_capability_list_is_honest(self):
        self.assertGreaterEqual(len(cc.REQUIRED_CAPABILITIES), 8)
        self.assertEqual(len(set(cc.REQUIRED_CAPABILITIES)),
                         len(cc.REQUIRED_CAPABILITIES))

    def test_unknown_channel_fails_closed(self):
        with self.assertRaises(ValueError):
            cc.capabilities_for("channel-that-does-not-exist")


class TestEquipmentParity(unittest.TestCase):
    def test_every_channel_compiles_every_required_module(self):
        from pipeline.brain_equipment.equipment_registry import compile_full_brain_prompt

        for channel_id in cc.known_channels():
            caps = cc.capabilities_for(channel_id)
            for module in cc.REQUIRED_EQUIPMENT:
                self.assertTrue(cc.equipment_text(channel_id, module),
                                f"{channel_id} has no {module} text")
            prompt = compile_full_brain_prompt(channel_id)
            self.assertIn(caps.brand.display_name, prompt)
            self.assertIn("DOCOGA REELS v2", prompt)

    def test_a_prompt_never_carries_the_other_channels_name(self):
        from pipeline.brain_equipment.equipment_registry import compile_full_brain_prompt

        for channel_id in cc.known_channels():
            caps = cc.capabilities_for(channel_id)
            prompt = compile_full_brain_prompt(channel_id)
            for phrase in caps.brand.forbidden_phrases:
                if phrase.startswith("The ") or phrase.startswith("@"):
                    self.assertNotIn(phrase, prompt,
                                     f"{channel_id} prompt carries {phrase!r}")

    def test_equipment_files_are_distinct_per_channel(self):
        seen: dict[str, str] = {}
        for channel_id in cc.known_channels():
            for module in cc.REQUIRED_EQUIPMENT:
                name = cc.capabilities_for(channel_id).equipment[module]
                self.assertNotIn(name, seen,
                                 f"{module} file {name} is shared by {channel_id} "
                                 f"and {seen.get(name)}")
                seen[name] = channel_id


class TestRoadmapParity(unittest.TestCase):
    def test_every_channel_has_its_own_roadmap(self):
        for channel_id in cc.known_channels():
            roadmap = roadmap_for_channel(channel_id)
            self.assertTrue(roadmap, f"{channel_id} has an empty roadmap")

    def test_roadmaps_are_not_shared_objects(self):
        roadmaps = [roadmap_for_channel(c) for c in cc.known_channels()]
        for i, roadmap in enumerate(roadmaps):
            for other in roadmaps[i + 1:]:
                self.assertIsNot(roadmap, other)

    def test_job_ids_are_globally_unique(self):
        seen: set[str] = set()
        for channel_id in cc.known_channels():
            for candidate in roadmap_for_channel(channel_id):
                self.assertNotIn(candidate["id"], seen,
                                 f"{candidate['id']} is used by more than one roadmap")
                seen.add(candidate["id"])

    def test_each_roadmap_stays_in_its_own_time_of_day(self):
        for channel_id in cc.known_channels():
            text = " ".join(
                f"{c['scripture']} {c['theme']} {c['primary_intent']}"
                for c in roadmap_for_channel(channel_id)).lower()
            if channel_id == "prayer2":
                for word in ("sleep", "bedtime", "insomnia", "before you sleep"):
                    self.assertNotIn(word, text, f"morning roadmap carries {word!r}")
            else:
                for word in ("every sunrise", "morning altar"):
                    self.assertNotIn(word, text, f"night roadmap carries {word!r}")


class TestBrandParity(unittest.TestCase):
    def test_brands_are_distinct_and_self_consistent(self):
        brands = [cc.brand_for(c) for c in cc.known_channels()]
        for brand in brands:
            self.assertIn(brand.display_name, brand.closing_cta)
            self.assertIn(brand.display_name, brand.producer_line)
            self.assertIn(brand.display_name, brand.title_suffix)
            self.assertTrue(brand.authoring_directive)
            self.assertTrue(brand.required_phrases)
        names = [b.display_name for b in brands]
        self.assertEqual(len(names), len(set(names)))

    def test_every_brand_forbids_the_other_brands_identity(self):
        brands = {cid: cc.brand_for(cid) for cid in cc.known_channels()}
        for channel_id, brand in brands.items():
            for other_id, other in brands.items():
                if other_id == channel_id:
                    continue
                self.assertIn(other.display_name, brand.forbidden_phrases)
                self.assertIn(other.handle, brand.forbidden_phrases)

    def test_pinned_comments_are_branded_per_channel(self):
        comments = {}
        for channel_id in cc.known_channels():
            comment = cc.pinned_comment_for(
                channel_id, theme="peace", scripture_hook="Psalm 1:1 — text", footer="")
            self.assertIn("AMEN", comment)
            for other_id in cc.known_channels():
                if other_id != channel_id:
                    self.assertNotIn(cc.brand_for(other_id).display_name, comment,
                                     f"{channel_id} comment carries "
                                     f"{cc.brand_for(other_id).display_name}")
            comments[channel_id] = comment
        self.assertEqual(len(set(comments.values())), len(comments))

    def test_short_dressing_is_branded_per_channel(self):
        titles, end_cards = {}, {}
        for channel_id in cc.known_channels():
            brand = cc.brand_for(channel_id)
            titles[channel_id] = brand.short_title_template.format(
                label="Psalm 121", hook="Keeper")
            end_cards[channel_id] = brand.short_end_card
        self.assertEqual(len(set(titles.values())), len(titles))
        self.assertEqual(len(set(end_cards.values())), len(end_cards))


class TestShortsParity(unittest.TestCase):
    """Shorts used to be a Secret Place-only capability. They are not any more."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.docs = {}
        for channel_id in cc.known_channels():
            brand = cc.brand_for(channel_id)
            path = self.dir / f"9100-{channel_id}.md"
            path.write_text(
                "---\n"
                'id: "9100"\n'
                f'title: "Psalm 143:8 Sunrise Prayer {brand.title_suffix}"\n'
                f"channel: {brand.declaration}\n"
                "status: approved\nformat: longform\nvoice: Charon\n"
                "---\n\n## Scene 1 — Mercy\n"
                "Cause me to hear thy lovingkindness in the morning.\n",
                encoding="utf-8")
            self.docs[channel_id] = path

    def test_short_keys_are_namespaced_valid_and_unique(self):
        from pipeline.gemini_brain import short_key_for_doc

        used: dict[str, str] = {}
        for channel_id in cc.known_channels():
            key = short_key_for_doc(parse_script(self.docs[channel_id]))
            self.assertRegex(key, r"^short-[a-z0-9]+$")
            self.assertNotIn(key, used,
                             f"{key} is generated for both {channel_id} and {used.get(key)}")
            used[key] = channel_id

    def test_channel_one_keys_keep_their_historic_shape(self):
        from pipeline.gemini_brain import short_key_for_doc

        key = short_key_for_doc(parse_script(self.docs["secret-place"]))
        self.assertFalse(key.startswith("short-morning"))

    def test_hand_written_editions_resolve_only_for_their_channel(self):
        from pipeline.short_release import EDITIONS, resolve_edition

        for key, edition in EDITIONS.items():
            for channel_id in cc.known_channels():
                resolved = resolve_edition(key, channel_id=channel_id)
                if channel_id == edition.channel:
                    self.assertIsNotNone(resolved)
                else:
                    self.assertIsNone(resolved, f"{key} resolved for {channel_id}")

    def test_queue_report_and_selection_are_channel_scoped(self):
        from pipeline.short_release import queue_report, select_next_queued_short

        qdir = self.dir / "shorts-queue"
        qdir.mkdir()
        for channel_id in cc.known_channels():
            (qdir / f"{channel_id}.yml").write_text(
                f"short: short-{channel_id.replace('-', '')}unittest\n"
                f"channel: {channel_id}\nstatus: draft\n", encoding="utf-8")
        for channel_id in cc.known_channels():
            rows = queue_report(qdir, channel_id=channel_id)
            self.assertEqual([r["channel"] for r in rows], [channel_id])
            # Nothing is approved here, so selection returns nothing for either
            # channel — and never the other channel's manifest.
            self.assertIsNone(select_next_queued_short(queue_dir=qdir,
                                                       channel_id=channel_id))

    def test_a_brain_stages_only_its_own_channels_short(self):
        from unittest import mock

        from pipeline.gemini_brain import BrainAuthoringError, GeminiBrain

        for channel_id in cc.known_channels():
            brain = GeminiBrain(api_key="", channel_id=channel_id)
            with mock.patch("pipeline.gemini_brain.SHORTS_QUEUE_DIR", self.dir / "q"):
                manifest, key = brain.generate_companion_short(
                    parse_script(self.docs[channel_id]))
                data = yaml.safe_load(manifest.read_text(encoding="utf-8"))
                self.assertEqual(data["channel"], channel_id)
                self.assertRegex(key, r"^short-[a-z0-9]+$")

                other = next(c for c in cc.known_channels() if c != channel_id)
                with self.assertRaises(BrainAuthoringError):
                    brain.generate_companion_short(parse_script(self.docs[other]))


class TestQueueAndReceiptParity(unittest.TestCase):
    """Health rows and published receipts are per channel, for every channel."""

    def test_every_channel_gets_both_queue_rows(self):
        from scripts.automation_health import queue_health

        by_queue = {row["queue"]: row for row in queue_health()}
        for channel_id in cc.known_channels():
            self.assertIn(f"longform:{channel_id}", by_queue)
            self.assertIn(f"shorts:{channel_id}", by_queue)
            self.assertEqual(by_queue[f"longform:{channel_id}"]["channel"], channel_id)

    def test_the_legacy_row_stays_with_the_channel_that_had_it(self):
        from scripts.automation_health import queue_health

        by_queue = {row["queue"]: row for row in queue_health()}
        legacy_owner = next((cid for cid in cc.known_channels()
                             if cc.capabilities_for(cid).legacy_queue_alias), None)
        if legacy_owner is None:
            self.assertNotIn("longform", by_queue)
        else:
            self.assertEqual(by_queue["longform"]["channel"], legacy_owner)

    def test_a_short_receipt_records_its_channel(self):
        from pipeline.short_release import _write_published_record, resolve_edition

        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "receipt.md"
            edition = next(ed for ed in
                           (resolve_edition(k) for k in _edition_keys()) if ed is not None)
            probe = type("Probe", (), {"width": 1080, "height": 1920,
                                       "duration_seconds": 42.0})()
            _write_published_record(dest, edition, "abcdefghijk",
                                    "https://youtu.be/abcdefghijk", "public", probe, 6)
            text = dest.read_text(encoding="utf-8")
            self.assertIn(f"channel: {edition.channel}", text)
            self.assertIn("format: short", text)


def _edition_keys() -> list[str]:
    from pipeline.short_release import EDITIONS

    return sorted(EDITIONS)


class TestWorkflowParity(unittest.TestCase):
    def test_channel_scoped_workflows_cover_every_channel(self):
        for name in CHANNEL_SCOPED_WORKFLOWS:
            text = (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
            for channel_id in cc.known_channels():
                self.assertIn(f'"{channel_id}"', text,
                              f"{name} does not schedule {channel_id}")

    def test_no_step_is_gated_on_a_channel_name(self):
        """A capability step must run for every channel, not for one named channel.

        Secret mapping (`secrets.PRAYER2_*` ternaries in `env:`) is the one thing
        that must name a channel — GitHub cannot look a secret up by a variable
        name — so only `if:` conditions and `run:` scripts are checked.
        """
        offenders: list[str] = []
        for name in CHANNEL_SCOPED_WORKFLOWS:
            data = yaml.safe_load((ROOT / ".github/workflows" / name).read_text())
            for job_name, job in (data.get("jobs") or {}).items():
                for step in job.get("steps") or []:
                    blobs = [str(step.get("if", "")), str(step.get("run", ""))]
                    for blob in blobs:
                        if re.search(r"channel\s*(?:==|!=)\s*['\"][a-z0-9-]+['\"]", blob):
                            offenders.append(f"{name}:{job_name}:{step.get('name', '')}")
        self.assertEqual(offenders, [],
                         "channel-gated steps belong in a capability instead: "
                         + "; ".join(offenders))

    def test_supply_and_shorts_steps_are_channel_parameterised(self):
        brain = (ROOT / ".github/workflows/gemini_brain.yml").read_text(encoding="utf-8")
        produce = (ROOT / ".github/workflows/produce.yml").read_text(encoding="utf-8")
        self.assertIn('--ensure-supply-for "$CHANNEL_ID"', brain)
        self.assertIn('--ensure-supply-for "$CHANNEL_ID"', produce)
        self.assertIn("--author-shorts", brain)
        self.assertIn("pipeline.short_release --next", produce)

    def test_channel_choice_inputs_offer_every_channel(self):
        for name in WORKFLOWS_WITH_CHANNEL_CHOICE:
            data = yaml.safe_load((ROOT / ".github/workflows" / name).read_text())
            text = str(data)
            for channel_id in cc.known_channels():
                self.assertIn(channel_id, text, f"{name} cannot target {channel_id}")

    def test_the_supervisor_dispatches_every_channel(self):
        text = (ROOT / "scripts/scheduler_supervisor.py").read_text(encoding="utf-8")
        self.assertNotIn('for channel in ("secret-place", "prayer2")', text)
        self.assertIn("known_channels()", text)


class TestNoHardcodedChannelBranches(unittest.TestCase):
    """The lock that keeps parity true after today.

    A new ``if channel == "prayer2"`` anywhere in production code is tomorrow's
    "this channel silently does less". It fails here instead, and the fix is to
    declare the difference in the capability matrix.
    """

    CHANNEL_IDS = {"prayer2", "secret-place", "morning-altar"}

    def _production_files(self):
        for folder in ("pipeline", "scripts", "tools"):
            for path in sorted((ROOT / folder).rglob("*.py")):
                rel = path.relative_to(ROOT).as_posix()
                if rel in LITERAL_CHANNEL_ALLOWLIST:
                    continue
                yield rel, path

    def test_no_comparison_names_a_channel(self):
        offenders: list[str] = []
        for rel, path in self._production_files():
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if not isinstance(node, (ast.Compare, ast.IfExp)):
                    continue
                for child in ast.walk(node):
                    if (isinstance(child, ast.Constant)
                            and isinstance(child.value, str)
                            and child.value in self.CHANNEL_IDS):
                        offenders.append(
                            f"{rel}:{node.lineno}: {ast.get_source_segment(source, node)}")
                        break
        self.assertEqual(
            offenders, [],
            "channel comparisons belong in pipeline/channel_capabilities.py:\n  "
            + "\n  ".join(offenders))

    def test_no_channel_set_membership_lists(self):
        """`channel in {"prayer2", "morning-altar"}` is the same defect in disguise."""
        offenders: list[str] = []
        for rel, path in self._production_files():
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, (ast.Set, ast.Tuple, ast.List)):
                    values = {e.value for e in node.elts
                              if isinstance(e, ast.Constant) and isinstance(e.value, str)}
                    if values & self.CHANNEL_IDS:
                        offenders.append(f"{rel}:{node.lineno}")
        self.assertEqual(offenders, [], "channel lists found:\n  " + "\n  ".join(offenders))


if __name__ == "__main__":
    unittest.main()
