"""Unit and integration tests for autonomous comment reply engine."""
import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from pipeline.comment_replies import (
    CommentItem,
    CommentReplyEngine,
    classify_comment_intent,
    generate_fallback_reply,
    generate_reply_with_gemini,
    is_crisis,
    is_scam_or_spam,
    load_replied_log,
    save_replied_log,
)
from pipeline.quota_handler import QuotaExceededError


class TestCommentClassification(unittest.TestCase):
    def test_crisis_detection(self):
        self.assertTrue(is_crisis("I want to end my life, feeling hopeless"))
        self.assertTrue(is_crisis("Feeling suicidal tonight"))
        self.assertEqual(classify_comment_intent("I want to kill myself"), "CRISIS_DISTRESS")

    def test_scam_detection(self):
        self.assertTrue(is_scam_or_spam("Contact the prophet on WhatsApp +1234567890"))
        self.assertTrue(is_scam_or_spam("Invest in crypto bitcoin for huge returns"))
        self.assertTrue(is_scam_or_spam("Join my telegram channel http://t.me/fake"))
        self.assertEqual(classify_comment_intent("DM me on WhatsApp for personal prayer"), "SPAM_SCAM")

    def test_prayer_request_detection(self):
        cat = classify_comment_intent("Please pray for my mother Mary who is having cancer surgery tomorrow")
        self.assertEqual(cat, "PRAYER_REQUEST")

    def test_amen_affirmation_detection(self):
        self.assertEqual(classify_comment_intent("Amen and Amen!"), "AMEN_AFFIRMATION")
        self.assertEqual(classify_comment_intent("Hallelujah, glory to God!"), "AMEN_AFFIRMATION")
        self.assertEqual(classify_comment_intent("I receive this blessing"), "AMEN_AFFIRMATION")

    def test_testimony_detection(self):
        cat = classify_comment_intent("I have severe insomnia and this prayer finally helped me sleep peacefully")
        self.assertEqual(cat, "TESTIMONY_REST")

    def test_inquiry_detection(self):
        cat = classify_comment_intent("Which Bible translation is being used here?")
        self.assertEqual(cat, "INQUIRY")


class TestReplySafetyAndInvariants(unittest.TestCase):
    def test_zero_mention_of_creator_names(self):
        categories = ["PRAYER_REQUEST", "AMEN_AFFIRMATION", "TESTIMONY_REST", "INQUIRY", "CRISIS_DISTRESS"]
        for cat in categories:
            reply = generate_fallback_reply("Sarah Connor", "Test text", cat)
            self.assertNotIn("John Azani", reply)
            self.assertNotIn("Azani John", reply)
            self.assertNotIn("John", reply)  # No creator name leaks

    def test_no_financial_solicitation_in_replies(self):
        categories = ["PRAYER_REQUEST", "AMEN_AFFIRMATION", "TESTIMONY_REST", "INQUIRY", "CRISIS_DISTRESS"]
        for cat in categories:
            reply = generate_fallback_reply("David", "Please pray for me", cat)
            self.assertNotIn("donate", reply.lower())
            self.assertNotIn("tithe", reply.lower())
            self.assertNotIn("paypal", reply.lower())
            self.assertNotIn("http", reply.lower())

    def test_crisis_reply_contains_lifeline_resources(self):
        reply = generate_fallback_reply("HopelessSoul", "I want to end my life", "CRISIS_DISTRESS")
        self.assertIn("988", reply)
        self.assertIn("741741", reply)
        self.assertIn("111", reply)

    def test_scam_comment_returns_empty_reply(self):
        item = CommentItem(
            comment_id="c123",
            video_id="v1",
            author_name="CryptoScammer",
            author_channel_id="ch1",
            text="Contact me on WhatsApp +123456789",
            published_at="2026-10-29T10:00:00Z",
            category="SPAM_SCAM",
        )
        reply = generate_reply_with_gemini(item)
        self.assertEqual(reply, "")


class TestDeduplicationAndEngine(unittest.TestCase):
    def setUp(self):
        self.test_log_path = Path("/tmp/test_replied_comments.json")
        if self.test_log_path.exists():
            self.test_log_path.unlink()

    def tearDown(self):
        if self.test_log_path.exists():
            self.test_log_path.unlink()

    def test_load_and_save_replied_log(self):
        data = {"c_001": {"author": "Mary", "category": "PRAYER_REQUEST"}}
        save_replied_log(data, self.test_log_path)
        loaded = load_replied_log(self.test_log_path)
        self.assertEqual(loaded, data)

    def test_engine_skips_already_replied_comments(self):
        mock_youtube = MagicMock()
        mock_youtube.channels().list().execute.return_value = {
            "items": [{"id": "UC_CHANNEL_OWN"}]
        }
        mock_youtube.commentThreads().list().execute.return_value = {
            "items": [
                {
                    "id": "c_already_done",
                    "snippet": {
                        "videoId": "7RDX0fbIOtQ",
                        "topLevelComment": {
                            "snippet": {
                                "authorDisplayName": "Grace",
                                "authorChannelId": {"value": "UC_OTHER"},
                                "textOriginal": "Amen!",
                                "publishedAt": "2026-10-29T08:00:00Z",
                            }
                        },
                        "totalReplyCount": 0,
                    },
                },
                {
                    "id": "c_new_comment",
                    "snippet": {
                        "videoId": "7RDX0fbIOtQ",
                        "topLevelComment": {
                            "snippet": {
                                "authorDisplayName": "Samuel",
                                "authorChannelId": {"value": "UC_OTHER_2"},
                                "textOriginal": "Please pray for my healing",
                                "publishedAt": "2026-10-29T09:00:00Z",
                            }
                        },
                        "totalReplyCount": 0,
                    },
                },
            ]
        }

        save_replied_log({"c_already_done": {"replied": True}}, self.test_log_path)
        engine = CommentReplyEngine(
            youtube_service=mock_youtube,
            replied_log_path=self.test_log_path,
        )

        candidates = engine.fetch_candidate_comments(video_id="7RDX0fbIOtQ")
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].comment_id, "c_new_comment")
        self.assertEqual(candidates[0].author_name, "Samuel")
        self.assertEqual(candidates[0].category, "PRAYER_REQUEST")

    def test_engine_dry_run_does_not_call_youtube_insert(self):
        mock_youtube = MagicMock()
        engine = CommentReplyEngine(
            youtube_service=mock_youtube,
            replied_log_path=self.test_log_path,
        )
        item = CommentItem(
            comment_id="c_test",
            video_id="v1",
            author_name="Ruth",
            author_channel_id="ch_ruth",
            text="Amen",
            published_at="2026-10-29T10:00:00Z",
            category="AMEN_AFFIRMATION",
        )
        success = engine.post_reply(item, "Amen, Ruth! God bless you.", dry_run=True)
        self.assertTrue(success)
        mock_youtube.comments().insert.assert_not_called()


if __name__ == "__main__":
    unittest.main()
