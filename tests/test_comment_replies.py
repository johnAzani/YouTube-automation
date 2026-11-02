"""Unit and integration tests for autonomous comment reply engine."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock, patch

from pipeline.comment_replies import (
    CommentFetchError,
    CommentItem,
    CommentReplyEngine,
    _reply_is_safe,
    classify_comment_intent,
    error_kind,
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


class TestChannelWideFetchActuallyWorks(unittest.TestCase):
    """The bug that made reply automation look alive while doing nothing.

    `fetch_candidate_comments` passed `allForChannelId`, which is not a parameter of
    commentThreads.list. googleapiclient rejects the call outright, the broad except
    swallowed it, and every scheduled pulse printed "no unresponded candidate
    comments" and exited 0 — three times a day, forever, in green.
    """

    def test_the_request_the_real_client_builds_is_valid(self):
        from googleapiclient.discovery import build

        youtube = build("youtube", "v3", developerKey="test", cache_discovery=False)
        request = youtube.commentThreads().list(
            part="snippet,replies", allThreadsRelatedToChannelId="UC_OWN",
            maxResults=16, textFormat="plainText")
        self.assertIn("allThreadsRelatedToChannelId=UC_OWN", request.uri)

    def test_the_old_parameter_name_is_rejected_by_the_client(self):
        from googleapiclient.discovery import build

        youtube = build("youtube", "v3", developerKey="test", cache_discovery=False)
        with self.assertRaises(TypeError):
            youtube.commentThreads().list(part="snippet", allForChannelId="UC_OWN")

    def test_the_engine_asks_for_the_channel_wide_listing(self):
        seen = {}
        youtube = MagicMock()
        youtube.channels().list().execute.return_value = {"items": [{"id": "UC_OWN"}]}

        def listing(**kwargs):
            seen.update(kwargs)
            return MagicMock(execute=MagicMock(return_value={"items": []}))

        youtube.commentThreads().list.side_effect = listing
        engine = CommentReplyEngine(youtube_service=youtube,
                                    replied_log_path=Path("/tmp/nonexistent-log.json"))
        engine.fetch_candidate_comments(video_id=None, max_results=5)
        self.assertEqual(seen.get("allThreadsRelatedToChannelId"), "UC_OWN")
        self.assertNotIn("allForChannelId", seen)

    def test_a_broken_listing_is_an_error_not_an_empty_inbox(self):
        youtube = MagicMock()
        youtube.channels().list().execute.return_value = {"items": [{"id": "UC_OWN"}]}
        youtube.commentThreads().list.side_effect = RuntimeError("boom")
        engine = CommentReplyEngine(youtube_service=youtube,
                                    replied_log_path=Path("/tmp/nonexistent-log.json"))
        with self.assertRaises(CommentFetchError):
            engine.fetch_candidate_comments(video_id=None, max_results=5)


class TestErrorClassification(unittest.TestCase):
    def test_daily_quota_is_quota(self):
        self.assertEqual(error_kind(Exception("HttpError 403 ... quotaExceeded")), "quota")

    def test_disabled_comments_are_not_quota(self):
        self.assertEqual(
            error_kind(Exception("HttpError 403 ... commentsDisabled")), "comments_disabled")

    def test_missing_scope_is_forbidden(self):
        self.assertEqual(
            error_kind(Exception('HttpError 403 ... "reason": "insufficientPermissions"')),
            "forbidden")


class TestCrisisIsHeldNotPosted(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.log = Path(self.tmp.name) / "replied.json"

    def comment(self):
        return CommentItem(comment_id="c_crisis", video_id="v1", author_name="Ann",
                           author_channel_id="UC_A", text="I want to end my life",
                           published_at="", category="CRISIS_DISTRESS")

    def test_nothing_is_posted_but_it_is_recorded_for_a_human(self):
        youtube = MagicMock()
        engine = CommentReplyEngine(youtube_service=youtube, replied_log_path=self.log)
        posted = engine.post_reply(self.comment(), "Dear Ann, call 988...")
        self.assertFalse(posted)
        youtube.comments().insert.assert_not_called()
        saved = load_replied_log(self.log)
        self.assertEqual(saved["c_crisis"]["category"], "CRISIS_ESCALATED")
        self.assertIn("988", saved["c_crisis"]["draft_reply"])

    def test_opting_in_still_posts_when_asked_explicitly(self):
        youtube = MagicMock()
        youtube.comments().insert().execute.return_value = {"id": "reply_1"}
        engine = CommentReplyEngine(youtube_service=youtube, replied_log_path=self.log)
        with patch("time.sleep", return_value=None):
            self.assertTrue(engine.post_reply(self.comment(), "Dear Ann, call 988...",
                                              allow_crisis=True))


class TestReplyInvariantsOnRealOutput(unittest.TestCase):
    """The prompt promises no links and no solicitation; the code must enforce it."""

    def test_a_reply_with_a_link_is_refused(self):
        self.assertFalse(_reply_is_safe("Pray with us at https://example.com tonight"))

    def test_a_reply_with_a_phone_or_handle_is_refused(self):
        self.assertFalse(_reply_is_safe("Message me on @pastorjoe for prayers"))
        self.assertFalse(_reply_is_safe("Call +2348012345678 for a miracle"))

    def test_a_reply_asking_for_money_is_refused(self):
        self.assertFalse(_reply_is_safe("Please send your tithe to support this ministry"))

    def test_the_creator_name_is_refused(self):
        self.assertFalse(_reply_is_safe("John Azani is praying for you"))

    def test_an_ordinary_pastoral_reply_passes(self):
        self.assertTrue(_reply_is_safe(
            "We are standing with you in prayer tonight, and asking the Lord to "
            "give you deep rest under His wings."))


class CrisisEscalationIsFiledOnce(unittest.TestCase):
    """One viewer produced three issues (#206, #207, #209).

    The comment job runs on a schedule. Every pass re-held the same disclosure and
    filed a brand-new issue for it, so a real escalation looked like noise and the
    owner had to open three identical tickets to find one person.
    """

    HELD = [
        {"comment_id": "c-1", "author": "viewer-one", "video_id": "v1",
         "text": "I don't want to be here anymore", "draft": "draft one"},
        {"comment_id": "c-2", "author": "viewer-two", "video_id": "v2",
         "text": "nobody would miss me", "draft": "draft two"},
    ]

    def _module(self):
        import scripts.reply_comments as rc
        return rc

    def test_a_disclosure_already_in_the_issue_is_not_reported_again(self):
        rc = self._module()
        known = "- comment: `c-1` on video `v1`\n- comment: `c-2` on video `v2`"
        self.assertEqual(rc.unreported(known, self.HELD), [])

    def test_only_the_new_disclosure_is_added(self):
        rc = self._module()
        known = "- comment: `c-1` on video `v1`"
        fresh = rc.unreported(known, self.HELD)
        self.assertEqual([row["comment_id"] for row in fresh], ["c-2"])

    def test_an_empty_known_text_reports_everything(self):
        rc = self._module()
        self.assertEqual(len(rc.unreported("", self.HELD)), 2)

    def test_no_token_means_no_issue_and_no_crash(self):
        rc = self._module()
        with mock.patch.dict(os.environ, {"GH_TOKEN": "", "GITHUB_TOKEN": ""}):
            self.assertIn("no token", rc._escalate_crisis(self.HELD))

    def test_it_comments_on_the_open_issue_instead_of_opening_another(self):
        rc = self._module()
        calls = []

        class Result:
            def __init__(self, stdout="", returncode=0):
                self.stdout, self.returncode, self.stderr = stdout, returncode, ""

        def fake_gh(*args):
            calls.append(args)
            if args[:2] == ("issue", "list"):
                return Result('[{"number": 42}]')
            if args[:2] == ("issue", "view"):
                return Result("body mentions c-1")
            return Result("")

        with mock.patch.dict(os.environ, {"GH_TOKEN": "t"}), \
             mock.patch.object(rc, "_gh", fake_gh):
            where = rc._escalate_crisis(self.HELD)
        self.assertIn("#42", where)
        self.assertNotIn("issue", [c[0] for c in calls if c[:2] == ("issue", "create")])
        comment = [c for c in calls if c[:2] == ("issue", "comment")]
        self.assertEqual(len(comment), 1)
        self.assertIn("c-2", comment[0][-1])
        self.assertNotIn("c-1", comment[0][-1].split("### viewer-two")[0])

    def test_it_says_so_and_does_nothing_when_everything_is_known(self):
        rc = self._module()
        calls = []

        class Result:
            def __init__(self, stdout="", returncode=0):
                self.stdout, self.returncode, self.stderr = stdout, returncode, ""

        def fake_gh(*args):
            calls.append(args)
            if args[:2] == ("issue", "list"):
                return Result('[{"number": 42}]')
            if args[:2] == ("issue", "view"):
                return Result("c-1 and c-2 are both named here")
            return Result("")

        with mock.patch.dict(os.environ, {"GH_TOKEN": "t"}), \
             mock.patch.object(rc, "_gh", fake_gh):
            where = rc._escalate_crisis(self.HELD)
        self.assertIn("already reported", where)
        self.assertEqual([c for c in calls if c[:2] in (("issue", "comment"),
                                                        ("issue", "create"))], [])
