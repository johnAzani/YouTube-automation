"""The third channel: registered, fully capable, and live since 2026-11-07.

Owner decision, 6 November 2026: the third channel is still a prayer channel — the
middle of the day, between The Secret Place's night and The Morning Altar's
sunrise. It is registered here in full, because "registered" and "live" are
different states and the codebase has to say so out loud:

* **registered** — it has a profile, a brand, equipment, a roadmap and Shorts
  capabilities, and `tests/test_channel_parity.py` holds it to the same standard
  as the two channels that already publish;
* **live** — it has a Google Cloud project, an OAuth refresh token and a Gemini
  key, so `provisioned` is True and the scheduler gives it three production legs
  a day.

It went live on 2026-11-07, the day after it was registered: the owner created the
`The Midday Watch` Cloud project, registered the three scopes, published the OAuth
consent screen to production (so the refresh token does not expire after 7 days)
and added the `PRAYER3_*` secrets. The flip below is that day, recorded because a
flag that changes meaning without a date is a flag nobody can audit later.

Building it any other way is how a channel ends up silently doing less.
"""
from __future__ import annotations

import unittest
from pathlib import Path

import yaml

from pipeline import channel_capabilities as cc
from pipeline.channels import CHANNELS, get_channel, normalize_channel_id, scheduled_channels
from scripts.continuous_research import roadmap_for_channel

ROOT = Path(__file__).resolve().parents[1]
CID = "prayer3"


class TestTheThirdChannelIsRegistered(unittest.TestCase):
    def test_profile_is_complete(self):
        profile = get_channel(CID)
        self.assertEqual(profile.display_name, "The Midday Watch")
        self.assertEqual(profile.secret_prefix, "PRAYER3_")
        self.assertEqual(profile.secret_name("YOUTUBE_REFRESH_TOKEN"),
                         "PRAYER3_YOUTUBE_REFRESH_TOKEN")
        self.assertEqual(profile.secret_name("GEMINI_API_KEY"), "PRAYER3_GEMINI_API_KEY")

    def test_frontmatter_aliases_resolve(self):
        for alias in ("midday", "noonday", "the-midday-watch", "channel3", "prayer3"):
            with self.subTest(alias=alias):
                self.assertEqual(normalize_channel_id(alias), CID)

    def test_it_is_scheduled_now_that_it_has_credentials(self):
        """Live 2026-11-07. While the flag was False the channel could still *run*:
        produce.yml keys off the refresh-token secret, not off this flag — so the
        flag being False kept it out of the health monitor and the supervisor while
        it was scheduled anyway. That is the state this test exists to prevent."""
        self.assertIn(CID, CHANNELS)
        self.assertIn(CID, scheduled_channels(),
                      "the refresh token exists, so the channel runs; a channel that "
                      "runs must be a channel the monitor and supervisor can see")
        self.assertTrue(CHANNELS[CID].provisioned)

    def test_the_flag_is_still_the_only_switch(self):
        """Nothing else keys off the channel's name: same capabilities either way."""
        import dataclasses

        off = dataclasses.replace(CHANNELS[CID], provisioned=False)
        self.assertFalse(off.provisioned)
        self.assertEqual(cc.capabilities_for(CID).supply_min_publishable, 6)


class TestItsBrand(unittest.TestCase):
    def test_voice_is_the_middle_of_the_day(self):
        brand = cc.brand_for(CID)
        self.assertEqual(brand.short_target_window_utc, "12:14")
        self.assertEqual(brand.short_key_namespace, "midday")
        self.assertIn("noon", brand.closing_cta.lower())
        self.assertIn("The Midday Watch", brand.title_suffix)

    def test_it_forbids_both_neighbours_and_they_forbid_it(self):
        brand = cc.brand_for(CID)
        for other in ("secret-place", "prayer2"):
            other_brand = cc.brand_for(other)
            self.assertIn(other_brand.display_name, brand.forbidden_phrases)
            self.assertIn(other_brand.handle, brand.forbidden_phrases)
            self.assertIn("The Midday Watch", other_brand.forbidden_phrases)
            self.assertIn("@TheMiddayWatch", other_brand.forbidden_phrases)

    def test_its_own_equipment_files_say_its_name(self):
        for module in ("system_instruction", "theological_rubric"):
            self.assertIn("The Midday Watch", cc.equipment_text(CID, module))
        # The internal id belongs in the instruction that writes frontmatter.
        self.assertIn("prayer3", cc.equipment_text(CID, "system_instruction"))

    def test_its_prompt_never_names_the_neighbours(self):
        from pipeline.brain_equipment.equipment_registry import compile_full_brain_prompt

        prompt = compile_full_brain_prompt(CID)
        for other in ("The Secret Place", "The Morning Altar",
                      "@TheSecretPlace", "@TheMorningAltarDaily"):
            self.assertNotIn(other, prompt)


class TestItsRoadmap(unittest.TestCase):
    def test_it_has_its_own_scriptures_and_ids(self):
        roadmap = roadmap_for_channel(CID)
        self.assertGreaterEqual(len(roadmap), 30)
        self.assertEqual(roadmap[0]["id"], "0045")
        ids = [row["id"] for row in roadmap]
        self.assertEqual(len(ids), len(set(ids)))
        others = {r["id"] for c in ("secret-place", "prayer2")
                  for r in roadmap_for_channel(c)}
        self.assertFalse(others & set(ids), "job ids must be globally unique")

    def test_no_entry_belongs_to_a_neighbour(self):
        text = " ".join(f"{r['scripture']} {r['theme']} {r['primary_intent']}"
                        for r in roadmap_for_channel(CID)).lower()
        for word in ("every sunrise", "morning altar", "before you sleep", "bedtime"):
            self.assertNotIn(word, text)


class TestItsShortsCannotCollide(unittest.TestCase):
    def test_short_keys_are_namespaced(self):
        from pipeline.channel_capabilities import short_key

        self.assertEqual(short_key(CID, "short-psalm55v17"), "short-middaypsalm55v17")
        keys = {c: short_key(c, "short-psalm55v17") for c in ("secret-place", "prayer2", CID)}
        self.assertEqual(len(set(keys.values())), 3)


class TestTheWorkflowsKnowIt(unittest.TestCase):
    def wf(self, name):
        return (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")

    def test_every_channel_scoped_workflow_maps_its_secrets(self):
        """Each workflow maps the secrets it actually uses, and no channel is left out.

        The brain authors text, so it needs only the Gemini key; the three that
        touch YouTube need the OAuth triple. A workflow that silently kept the
        channel-1 secrets for a third channel would upload to the wrong channel.
        """
        uploaders = ("produce.yml", "comments.yml", "metrics.yml")
        for name in uploaders:
            with self.subTest(workflow=name):
                text = self.wf(name)
                if name == "produce.yml":
                    import yaml
                    env = yaml.safe_load(text)["jobs"]["produce"]["env"]
                    for key in ("YOUTUBE_CLIENT_ID", "YOUTUBE_REFRESH_TOKEN", "YOUTUBE_CLIENT_SECRET"):
                        self.assertIn('"prayer3":"PRAYER3_"', env[key])
                        self.assertIn("secrets[format(", env[key])
                else:
                    data = yaml.safe_load(text)
                    if name == "comments.yml":
                        env = next(step["env"] for job in data["jobs"].values()
                                   for step in job.get("steps", [])
                                   if step.get("name") == "Run Comment Reply Engine")
                    else:
                        env = next(job["env"] for job in data["jobs"].values()
                                   if "YOUTUBE_CLIENT_ID" in job.get("env", {}))
                    for key in ("YOUTUBE_CLIENT_ID", "YOUTUBE_REFRESH_TOKEN", "YOUTUBE_CLIENT_SECRET"):
                        self.assertIn('"prayer3":"PRAYER3_"', env[key])
                        self.assertIn("secrets[format(", env[key])
        brain = self.wf("gemini_brain.yml")
        self.assertIn('"prayer3":"PRAYER3_"', brain)
        self.assertIn("format('{0}GEMINI_API_KEY'", brain)
        self.assertNotIn("secrets.PRAYER3_YOUTUBE_REFRESH_TOKEN", brain,
                         "the brain never uploads; mapping a YouTube token there "
                         "would only widen the blast radius")

    def test_the_scheduled_list_is_behind_a_credential_probe(self):
        """The registry flag is the decision; the probe is the runtime truth."""
        produce = self.wf("produce.yml")
        self.assertIn("PRAYER3_READY", produce)
        self.assertIn("secrets.PRAYER3_YOUTUBE_REFRESH_TOKEN != ''", produce)
        brain = self.wf("gemini_brain.yml")
        self.assertIn("PRAYER3_READY", brain)
        self.assertIn("secrets.PRAYER3_GEMINI_API_KEY != ''", brain)

    def test_a_manual_dispatch_can_target_it_today(self):
        for name in ("produce.yml", "gemini_brain.yml", "comments.yml", "metrics.yml"):
            data = yaml.safe_load(self.wf(name))
            text = str(data)
            with self.subTest(workflow=name):
                self.assertIn(CID, text)


if __name__ == "__main__":
    unittest.main()
