"""Multi-channel registry, routing and wrong-channel guard.

Channel 2 (The Morning Altar, `prayer2`) runs on its own GCP project,
YouTube quota pool, Gemini project and PRAYER2_* secrets. These tests pin
the invariants that keep the channels from ever being crossed: prefixed
secret names, frontmatter routing, and the pre-upload channel check.
"""
import unittest
from pathlib import Path

from pipeline.channels import (
    CHANNELS,
    channel_for_doc,
    get_channel,
    normalize_channel_id,
)
from pipeline.config import CONFIG
from pipeline.metadata import build_description
from pipeline.script_doc import ScriptDoc, parse_script
from pipeline.upload import verify_target_channel

ROOT = Path(__file__).resolve().parent.parent


class _FakeRequest:
    def __init__(self, payload):
        self._payload = payload

    def execute(self):
        return self._payload


class _FakeChannels:
    def __init__(self, payload):
        self._payload = payload

    def list(self, **_kwargs):
        return _FakeRequest(self._payload)


class _FakeYouTube:
    def __init__(self, payload):
        self._payload = payload

    def channels(self):
        return _FakeChannels(self._payload)


class ChannelRegistryTests(unittest.TestCase):
    def test_profiles_and_secret_prefixes(self):
        self.assertEqual(set(CHANNELS), {"secret-place", "prayer2"})
        prayer2 = get_channel("prayer2")
        self.assertEqual(prayer2.display_name, "The Morning Altar")
        self.assertEqual(prayer2.secret_prefix, "PRAYER2_")
        # Owner decision 2026-11-05: The Morning Altar publishes on the
        # same terms as The Secret Place — public, auto-published.
        self.assertEqual(prayer2.default_privacy, "public")
        self.assertTrue(prayer2.auto_publish)
        secret_place = get_channel("secret-place")
        self.assertEqual(secret_place.default_privacy, prayer2.default_privacy)
        self.assertEqual(secret_place.auto_publish, prayer2.auto_publish)
        self.assertEqual(
            prayer2.secret_names()["refresh_token"], "PRAYER2_YOUTUBE_REFRESH_TOKEN"
        )
        self.assertEqual(
            prayer2.secret_names()["gemini_api_key"], "PRAYER2_GEMINI_API_KEY"
        )
        # Channel 1 keeps the original unprefixed names (existing production).
        self.assertEqual(get_channel("secret-place").secret_names()["client_id"],
                         "YOUTUBE_CLIENT_ID")

    def test_aliases_and_default(self):
        self.assertEqual(normalize_channel_id(""), "secret-place")
        self.assertEqual(normalize_channel_id(None), "secret-place")
        self.assertEqual(normalize_channel_id("morning-altar"), "prayer2")
        self.assertEqual(normalize_channel_id("Channel2"), "prayer2")

    def test_unknown_channel_fails_closed(self):
        with self.assertRaises(ValueError):
            get_channel("no-such-channel")

    def test_doc_channel_routing(self):
        self.assertEqual(channel_for_doc({}), "secret-place")
        self.assertEqual(channel_for_doc({"channel": "prayer2"}), "prayer2")
        doc = ScriptDoc(path=Path("x.md"), meta={"channel": "morning-altar"})
        self.assertEqual(doc.channel, "prayer2")


class WrongChannelGuardTests(unittest.TestCase):
    def setUp(self):
        self._expected = CONFIG.expected_youtube_channel_id
        self._channel_id = CONFIG.channel_id

    def tearDown(self):
        CONFIG.expected_youtube_channel_id = self._expected
        CONFIG.channel_id = self._channel_id

    def _youtube(self, channel_id="UC-mine", title="The Morning Altar"):
        return _FakeYouTube(
            {"items": [{"id": channel_id, "snippet": {"title": title}}]}
        )

    def test_matching_channel_passes(self):
        CONFIG.channel_id = "prayer2"
        CONFIG.expected_youtube_channel_id = "UC-mine"
        result = verify_target_channel(self._youtube())
        self.assertEqual(result["id"], "UC-mine")

    def test_wrong_channel_token_aborts_before_upload(self):
        CONFIG.channel_id = "prayer2"
        CONFIG.expected_youtube_channel_id = "UC-morning-altar"
        with self.assertRaisesRegex(RuntimeError, "wrong channel"):
            verify_target_channel(self._youtube(channel_id="UC-secret-place"))

    def test_no_expected_id_still_reports_authorized_channel(self):
        CONFIG.expected_youtube_channel_id = ""
        result = verify_target_channel(self._youtube())
        self.assertEqual(result["title"], "The Morning Altar")

    def test_no_channel_for_credentials_aborts(self):
        CONFIG.expected_youtube_channel_id = ""
        with self.assertRaisesRegex(RuntimeError, "no channel"):
            verify_target_channel(_FakeYouTube({"items": []}))


class ChannelAwareDescriptionTests(unittest.TestCase):
    def setUp(self):
        self._channel_id = CONFIG.channel_id
        self._channel_name = CONFIG.channel_name
        self._channel_handle = CONFIG.channel_handle

    def tearDown(self):
        CONFIG.channel_id = self._channel_id
        CONFIG.channel_name = self._channel_name
        CONFIG.channel_handle = self._channel_handle

    def _faith_doc(self):
        return ScriptDoc(
            path=Path("0036.md"),
            meta={
                "title": "Psalm 5 Morning Prayer",
                "slug": "psalm-5-morning-prayer",
                "niche": "faith and prayer",
                "format": "longform",
                "description": "Begin the day with Psalm 5.",
            },
        )

    def test_prayer2_description_never_borrows_selar_funnel(self):
        CONFIG.channel_id = "prayer2"
        CONFIG.channel_name = "The Morning Altar"
        CONFIG.channel_handle = "@TheMorningAltarDaily"
        text = build_description(self._faith_doc())
        self.assertNotIn("selar.com", text)
        self.assertNotIn("The Secret Place", text)
        self.assertIn("The Morning Altar", text)

    def test_secret_place_description_keeps_sanctuary_links(self):
        CONFIG.channel_id = "secret-place"
        text = build_description(self._faith_doc())
        self.assertIn("selar.com", text)


class WorkflowSelectorTests(unittest.TestCase):
    def test_produce_workflow_exposes_channel_selector(self):
        text = (ROOT / ".github" / "workflows" / "produce.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("options: [secret-place, prayer2]", text)
        for name in (
            "PRAYER2_YOUTUBE_CLIENT_ID",
            "PRAYER2_YOUTUBE_CLIENT_SECRET",
            "PRAYER2_YOUTUBE_REFRESH_TOKEN",
            "PRAYER2_GEMINI_API_KEY",
        ):
            self.assertIn(f"secrets.{name}", text)

    def test_scheduled_produce_runs_cover_both_channels(self):
        """A cron slot must produce Morning Altar videos too (2026-11-05).

        The plan job expands a schedule event to both channels and the
        produce job runs them as a sequential matrix; each leg maps only
        its own channel's secrets, and prayer2 is no longer forced private.
        """
        text = (ROOT / ".github" / "workflows" / "produce.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn('schedule)          channels=\'["secret-place","prayer2"]\'', text)
        self.assertIn("matrix:", text)
        self.assertIn("channel: ${{ fromJSON(needs.plan.outputs.channels) }}", text)
        self.assertIn("max-parallel: 1", text)
        self.assertIn("CHANNEL_ID: ${{ matrix.channel || 'secret-place' }}", text)
        self.assertIn("matrix.channel == 'prayer2' && secrets.PRAYER2_YOUTUBE_CLIENT_ID", text)
        self.assertIn("matrix.channel == 'prayer2' && secrets.PRAYER2_GEMINI_API_KEY", text)
        self.assertNotIn("matrix.channel == 'prayer2' && 'false'", text)
        self.assertNotIn("matrix.channel == 'prayer2' && 'private'", text)
        self.assertIn("DEFAULT_PRIVACY: public", text)

    def test_empty_morning_altar_queue_idles_instead_of_failing(self):
        """No approved prayer2 script queued => the leg uploads nothing.

        Morning Altar scripts are human-queued (no brain supply yet), so an
        empty queue is a supply gap, not a breakage: the render step is
        gated on the queue check while Secret Place keeps its hard fault.
        """
        text = (ROOT / ".github" / "workflows" / "produce.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("id: channel_queue", text)
        self.assertIn("Morning Altar queue empty", text)
        self.assertIn("steps.channel_queue.outputs.has_job == 'true'", text)

    def test_produce_workflow_exposes_replacement_run_override(self):
        # A corrected re-render of an already-uploaded job (0036 after the
        # tts-v2 narration defect) must be a conscious, per-run choice:
        # the workflow surfaces allow_duplicate as an explicit tick-box
        # mapped to ALLOW_DUPLICATE_UPLOADS, defaulting to shielded.
        text = (ROOT / ".github" / "workflows" / "produce.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("allow_duplicate:", text)
        self.assertIn("ALLOW_DUPLICATE_UPLOADS: ${{ (inputs.allow_duplicate || false)",
                      text)

    def test_job_0011_is_published_with_the_corrected_tts_v4_upload(self):
        # The corrected replacement (tts-v4) was uploaded by run 42033981791
        # on 2026-11-05 and is live on The Secret Place. Unlike job 0036's
        # run, this one wrote its own receipt: the queue file was consumed
        # and the published record names the new video (BFlkzRVMf8o). The
        # upload landed private (script privacy) for owner review; the
        # defective 7ll7w1hYf7o stays unlisted until the owner deletes it.
        queue_job = ROOT / "content" / "queue" / "0011-psalm-27-the-lord-is-my-light-and-my-salvation--fe.md"
        published = ROOT / "content" / "published" / "0011-psalm-27-the-lord-is-my-light-and-my-salvation--fe.md"
        self.assertFalse(queue_job.exists())
        self.assertTrue(published.is_file())
        doc = parse_script(published)
        self.assertEqual(doc.status, "published")
        self.assertEqual(doc.channel, "secret-place")
        self.assertEqual(doc.meta.get("privacy"), "private")
        self.assertEqual(doc.meta.get("youtube_video_id"), "BFlkzRVMf8o")
        self.assertEqual(doc.meta.get("published_on"), "2026-11-05")

    def test_job_0036_is_published_with_the_corrected_tts_v4_upload(self):
        # The corrected replacement (tts-v4) was uploaded by run 42010285242
        # on 2026-11-05 and is live and public on The Morning Altar. The run
        # still concluded failure because a monitor snapshot had resurrected
        # the retired receipt, so the queue file survived on main; reconciled
        # here with the owner-supplied video id (_vp27ZYPYaY).
        queue_job = ROOT / "content" / "queue" / "0036-psalm-5-morning-prayer-begin-your-day.md"
        published = ROOT / "content" / "published" / "0036-psalm-5-morning-prayer-begin-your-day.md"
        self.assertFalse(queue_job.exists())
        self.assertTrue(published.is_file())
        doc = parse_script(published)
        self.assertEqual(doc.status, "published")
        self.assertEqual(doc.channel, "prayer2")
        self.assertEqual(doc.meta.get("youtube_video_id"), "_vp27ZYPYaY")
        self.assertEqual(doc.meta.get("published_on"), "2026-11-05")


if __name__ == "__main__":
    unittest.main()
