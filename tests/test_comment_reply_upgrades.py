"""The comment engine after the 2026-11-07 audit: voice, coverage, and at-most-once.

Everything here is a defect that was read out of the code and the bundled
discovery document, not a hypothetical:

* the engine answered as The Secret Place on every channel's credentials;
* it read `textOriginal`, which is only guaranteed to the comment's own author;
* it fetched one page of threads and ignored `nextPageToken`, so a backlog older
  than the newest page was unreachable while the run reported success;
* it treated `replies` as authoritative when the API calls it "a limited number
  of replies (if any)";
* a bare link made a viewer a scammer, and a long run of digits was a phone;
* the ledger row was written after the insert, so a crash in between double-posted;
* curated fallbacks went out verbatim, repeatedly, whenever Gemini was down.
"""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

import yaml

from pipeline import comment_replies as cr
from pipeline.channel_capabilities import brand_for, known_channels
from pipeline.config import CONFIG

ROOT = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------- #
# A Data API surface that can paginate, audit replies and fail on demand
# --------------------------------------------------------------------------- #
class FakeAPI:
    def __init__(self, pages, own="UC_OWN", own_reply_authors=None):
        self.pages = list(pages)
        self.own = own
        self.thread_calls = []
        self.reply_calls = []
        self.inserted = []
        #: cid -> list of author channel ids returned by comments.list(parentId=)
        self.own_reply_authors = own_reply_authors or {}
        self.insert_error = None

    def channels(self):
        outer = self

        class _Channels:
            def list(self, **kwargs):
                return mock.Mock(execute=mock.Mock(return_value={"items": [{"id": outer.own}]}))

        return _Channels()

    def commentThreads(self):
        outer = self

        class _Threads:
            def list(self, **kwargs):
                outer.thread_calls.append(kwargs)
                if not outer.pages:
                    return mock.Mock(execute=mock.Mock(return_value={"items": []}))
                return mock.Mock(execute=mock.Mock(return_value=outer.pages.pop(0)))

        return _Threads()

    def comments(self):
        outer = self

        class _Comments:
            def insert(self, part=None, body=None):
                def go():
                    if outer.insert_error:
                        raise outer.insert_error
                    outer.inserted.append(body)
                    return {"id": f"reply_{len(outer.inserted)}"}

                return mock.Mock(execute=mock.Mock(side_effect=go))

            def list(self, **kwargs):
                outer.reply_calls.append(kwargs)
                parent = kwargs.get("parentId")
                authors = outer.own_reply_authors.get(parent, [])
                items = [{"snippet": {"authorChannelId": {"value": a}}} for a in authors]
                return mock.Mock(execute=mock.Mock(return_value={"items": items}))

        return _Comments()


def thread(cid, text, *, author="Mary Bello", channel="UC_VIEWER", replies=None,
           total_replies=None, published="2026-11-06T20:00:00Z", likes=0,
           can_reply=None, public=None, text_display=True):
    snippet = {
        "videoId": "SG69BbNlfRw",
        "totalReplyCount": len(replies or []) if total_replies is None else total_replies,
        "topLevelComment": {"snippet": {
            "authorDisplayName": author,
            "authorChannelId": {"value": channel},
            "publishedAt": published,
            "likeCount": likes,
        }},
    }
    # Real API: textDisplay is always present, textOriginal only for your own.
    if text_display:
        snippet["topLevelComment"]["snippet"]["textDisplay"] = text
    else:
        snippet["topLevelComment"]["snippet"]["textOriginal"] = text
    if can_reply is not None:
        snippet["canReply"] = can_reply
    if public is not None:
        snippet["isPublic"] = public
    item = {"id": cid, "snippet": snippet}
    if replies:
        item["replies"] = {"comments": replies}
    return item


def other_reply():
    return {"snippet": {"authorChannelId": {"value": "UC_SOMEONE"}}}


def own_reply():
    return {"snippet": {"authorChannelId": {"value": "UC_OWN"}}}


class EngineCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.log = Path(self.tmp.name) / "replied.json"
        patcher = mock.patch.object(cr, "DEFAULT_REPLIED_LOG", self.log)
        patcher.start()
        self.addCleanup(patcher.stop)

    def engine(self, api, **kwargs):
        return cr.CommentReplyEngine(youtube_service=api, replied_log_path=self.log, **kwargs)


# --------------------------------------------------------------------------- #
# 1. The voice belongs to the channel, not to the module
# --------------------------------------------------------------------------- #
class TestTheReplySpeaksInTheChannelsVoice(EngineCase):
    def test_the_prompt_names_only_the_channel_it_answers_for(self):
        for channel_id in known_channels():
            brand = brand_for(channel_id)
            prompt = cr.build_system_prompt(channel_id)
            self.assertIn(brand.display_name, prompt)
            self.assertIn(brand.comment_farewell, prompt)
            for other in known_channels():
                if other == channel_id:
                    continue
                self.assertNotIn(brand_for(other).display_name, prompt,
                                 f"{channel_id}'s prompt carries {brand_for(other).display_name}")

    def test_every_brand_declares_a_comment_voice(self):
        for channel_id in known_channels():
            brand = brand_for(channel_id)
            self.assertIn(brand.display_name, brand.comment_persona)
            self.assertTrue(brand.comment_farewell.strip())

    def test_fallbacks_close_in_the_channel_daypart_and_nowhere_else(self):
        for channel_id in known_channels():
            brand = brand_for(channel_id)
            reply = cr.generate_fallback_reply("Grace", "Please pray for my mother",
                                               "PRAYER_REQUEST", channel_id=channel_id,
                                               comment_id="c1")
            self.assertIn(brand.comment_farewell, reply)
            for other in known_channels():
                if other == channel_id:
                    continue
                self.assertNotIn(brand_for(other).display_name, reply)

    def test_the_engine_records_which_channel_answered(self):
        api = FakeAPI([{"items": [thread("c1", "Amen, thank you Jesus")]}])
        engine = self.engine(api, channel_id="prayer3")
        items = engine.fetch_candidate_comments()
        with mock.patch("time.sleep", return_value=None):
            engine.post_reply(items[0], "Amen, Grace. Go in His peace.", dry_run=False)
        row = json.loads(self.log.read_text(encoding="utf-8"))["c1"]
        self.assertEqual(row["channel_id"], "prayer3")

    def test_a_fallback_is_deterministic_for_the_same_comment(self):
        a = cr.generate_fallback_reply("Grace", "Please pray for my surgery",
                                       "PRAYER_REQUEST", comment_id="c_same")
        b = cr.generate_fallback_reply("Grace", "Please pray for my surgery",
                                       "PRAYER_REQUEST", comment_id="c_same")
        self.assertEqual(a, b, "a retried comment must receive the sentence it would have had")


# --------------------------------------------------------------------------- #
# 2. Handles are not names
# --------------------------------------------------------------------------- #
class TestSalutations(unittest.TestCase):
    def test_camel_case_handles_keep_the_first_name(self):
        self.assertEqual(cr._clean_salutation("@HarleyAmaya-r3f"), "Harley")
        self.assertNotIn("Harleyamaya", cr._clean_salutation("@HarleyAmaya-r3f"))

    def test_a_digit_suffixed_handle_is_not_mangled_into_a_name(self):
        self.assertEqual(cr._clean_salutation("@gbertmags2453"), "Friend")

    def test_a_plain_handle_still_yields_a_warm_name(self):
        self.assertEqual(cr._clean_salutation("@grace-i8g"), "Grace")

    def test_display_names_are_unchanged(self):
        self.assertEqual(cr._clean_salutation("Mary Bello"), "Mary")
        self.assertEqual(cr._clean_salutation("user12345"), "Friend")
        self.assertEqual(cr._clean_salutation(""), "Friend")

    def test_the_fallback_reads_naturally_when_the_name_is_unknown(self):
        reply = cr.generate_fallback_reply("@gbertmags2453", "Amen!", "AMEN_AFFIRMATION")
        self.assertIn("Dear friend,", reply)
        self.assertNotIn("@", reply)


# --------------------------------------------------------------------------- #
# 3. Classification: fewer silent deletions, requests before testimony
# --------------------------------------------------------------------------- #
class TestClassificationRefinements(unittest.TestCase):
    def test_a_shared_scripture_link_is_not_a_scam(self):
        cat = cr.classify_comment_intent(
            "This is the verse https://www.bible.com/verse/psalm-91 — thank you for this prayer")
        self.assertNotEqual(cat, "SPAM_SCAM", "a viewer sharing the verse is not a fraudster")

    def test_a_link_inside_a_pitch_is_still_a_scam(self):
        self.assertEqual(cr.classify_comment_intent("Join my telegram http://t.me/fake"),
                         "SPAM_SCAM")

    def test_one_financial_word_is_a_prayer_need_not_an_advert(self):
        self.assertEqual(
            cr.classify_comment_intent("Please pray for me, my trading business has collapsed"),
            "PRAYER_REQUEST")

    def test_two_financial_signals_are_an_advert(self):
        self.assertEqual(cr.classify_comment_intent("Invest in crypto bitcoin for huge returns"),
                         "SPAM_SCAM")

    def test_scripture_digits_are_not_a_phone_number(self):
        self.assertEqual(cr.classify_comment_intent("Psalm 91 2026 11 07 123456789 heals me"),
                         "PRAYER_REQUEST")

    def test_an_explicit_request_outranks_testimony_wording(self):
        # The old order tested testimony first, so this was thanked, not prayed for.
        cat = cr.classify_comment_intent(
            "I have severe insomnia, please pray for me to sleep peacefully tonight")
        self.assertEqual(cat, "PRAYER_REQUEST")

    def test_a_question_without_a_question_mark_is_still_a_question(self):
        self.assertEqual(cr.classify_comment_intent("what music is playing in the background"),
                         "INQUIRY")

    def test_a_short_amen_that_names_a_burden_is_still_an_amen(self):
        # "family" is a prayer keyword, so this was answered as a request for
        # prayer the viewer had not made.
        self.assertEqual(
            cr.classify_comment_intent(
                "Amen! Thank you Lord, I receive this peace over my family tonight"),
            "AMEN_AFFIRMATION")

    def test_an_amen_that_turns_into_a_need_is_a_request(self):
        self.assertEqual(
            cr.classify_comment_intent(
                "Amen, I receive this prayer for my husband's job, he has been "
                "without work for months now"),
            "PRAYER_REQUEST")

    def test_a_plain_testimony_is_still_a_testimony(self):
        self.assertEqual(
            cr.classify_comment_intent("This prayer finally helped me sleep peacefully"),
            "TESTIMONY_REST")


# --------------------------------------------------------------------------- #
# 4. Coverage: pages, canReply, the reliable text field, truncated replies
# --------------------------------------------------------------------------- #
class TestCoverage(EngineCase):
    def test_the_engine_walks_past_the_first_page(self):
        # Page 1 is entirely comments the ledger already knows: the backlog worth
        # answering lives on page 2, which the old one-call fetch never saw.
        self.log.write_text(json.dumps({"c1": {"comment_id": "c1", "reply_id": "r"}}))
        api = FakeAPI([
            {"items": [thread("c1", "Amen")], "nextPageToken": "PAGE2"},
            {"items": [thread("c2", "Please pray for my family")]},
        ])
        items = self.engine(api).fetch_candidate_comments()
        self.assertEqual([i.comment_id for i in items], ["c2"],
                         "the second page holds the comment nobody had answered")
        self.assertEqual(len(api.thread_calls), 2)
        self.assertEqual(api.thread_calls[1].get("pageToken"), "PAGE2")

    def test_pagination_stops_at_the_page_budget(self):
        pages = [{"items": [thread(f"c{i}", "Amen")], "nextPageToken": "MORE"} for i in range(6)]
        api = FakeAPI(pages)
        self.engine(api).fetch_candidate_comments(max_pages=2)
        self.assertEqual(len(api.thread_calls), 2)

    def test_the_listing_asks_for_the_largest_page(self):
        api = FakeAPI([{"items": []}])
        self.engine(api).fetch_candidate_comments()
        self.assertEqual(api.thread_calls[0]["maxResults"], 100)
        self.assertEqual(api.thread_calls[0]["moderationStatus"], "published")

    def test_text_display_is_read_when_text_original_is_absent(self):
        # textOriginal is only guaranteed to the comment's own author, so this is
        # what every reply to a viewer actually sees.
        api = FakeAPI([{"items": [thread("c1", "Please pray for my mother's surgery")]}])
        items = self.engine(api).fetch_candidate_comments()
        self.assertEqual(items[0].text, "Please pray for my mother's surgery")
        self.assertEqual(items[0].category, "PRAYER_REQUEST")

    def test_text_original_still_works_when_it_is_what_we_get(self):
        api = FakeAPI([{"items": [thread("c1", "Healing for my son", text_display=False)]}])
        items = self.engine(api).fetch_candidate_comments()
        self.assertEqual(items[0].text, "Healing for my son")

    def test_a_thread_that_cannot_be_replied_to_is_recorded_not_retried(self):
        api = FakeAPI([{"items": [thread("c1", "Amen", can_reply=False)]}])
        self.assertEqual(self.engine(api).fetch_candidate_comments(), [])
        self.assertEqual(json.loads(self.log.read_text())["c1"]["category"], "CANNOT_REPLY")

    def test_can_reply_absent_is_not_treated_as_no(self):
        api = FakeAPI([{"items": [thread("c1", "Amen", can_reply=None)]}])
        self.assertEqual(len(self.engine(api).fetch_candidate_comments()), 1)

    def test_a_private_thread_is_not_answered(self):
        api = FakeAPI([{"items": [thread("c1", "Amen", public=False)]}])
        self.assertEqual(self.engine(api).fetch_candidate_comments(), [])
        self.assertEqual(json.loads(self.log.read_text())["c1"]["category"], "NOT_PUBLIC")

    def test_truncated_replies_are_checked_against_the_replies_endpoint(self):
        # totalReplyCount 3, the listing shows one reply by someone else.
        api = FakeAPI([{"items": [thread("c1", "Amen", replies=[other_reply()],
                                         total_replies=3)]}],
                      own_reply_authors={"c1": ["UC_OWN"]})
        self.assertEqual(self.engine(api).fetch_candidate_comments(), [])
        self.assertEqual(api.reply_calls[0]["parentId"], "c1")
        self.assertEqual(json.loads(self.log.read_text())["c1"]["category"], "PREVIOUSLY_REPLIED")

    def test_a_reply_from_someone_else_does_not_block_us(self):
        api = FakeAPI([{"items": [thread("c1", "Please pray for me",
                                         replies=[other_reply()], total_replies=1)]}])
        self.assertEqual(len(self.engine(api).fetch_candidate_comments()), 1)

    def test_prayer_requests_outrank_a_fresh_amen(self):
        api = FakeAPI([{"items": [
            thread("c_amen", "Amen!", published="2026-11-07T09:00:00Z", likes=0),
            thread("c_pray", "Please pray for my daughter", published="2026-11-05T09:00:00Z"),
        ]}])
        items = self.engine(api).fetch_candidate_comments()
        self.assertEqual(items[0].comment_id, "c_pray")

    def test_a_failing_reply_audit_does_not_lose_the_candidate(self):
        api = FakeAPI([{"items": [thread("c1", "Please pray for me",
                                         replies=[other_reply()], total_replies=3)]}])
        api.comments = lambda: mock.Mock(list=mock.Mock(
            return_value=mock.Mock(execute=mock.Mock(side_effect=RuntimeError("boom")))))
        self.assertEqual(len(self.engine(api).fetch_candidate_comments()), 1)


# --------------------------------------------------------------------------- #
# 5. Never answer as the wrong ministry
# --------------------------------------------------------------------------- #
class TestIdentityGuard(EngineCase):
    def test_a_token_that_belongs_to_another_channel_refuses_to_reply(self):
        api = FakeAPI([{"items": []}], own="UC_WRONG")
        engine = self.engine(api, channel_id="prayer2")
        with mock.patch.multiple(CONFIG, expected_youtube_channel_id="UC_EXPECTED"):
            with self.assertRaises(cr.CommentFetchError):
                engine.fetch_candidate_comments()

    def test_matching_credentials_are_allowed_through(self):
        api = FakeAPI([{"items": [thread("c1", "Amen")]}], own="UC_RIGHT")
        engine = self.engine(api, channel_id="prayer2")
        with mock.patch.multiple(CONFIG, expected_youtube_channel_id="UC_RIGHT"):
            self.assertEqual(len(engine.fetch_candidate_comments()), 1)

    def test_an_unset_expectation_does_not_block(self):
        api = FakeAPI([{"items": [thread("c1", "Amen")]}], own="UC_ANY")
        with mock.patch.multiple(CONFIG, expected_youtube_channel_id=""):
            self.assertEqual(len(self.engine(api).fetch_candidate_comments()), 1)


# --------------------------------------------------------------------------- #
# 6. At most once: reserve, then reconcile
# --------------------------------------------------------------------------- #
class TestAtMostOnce(EngineCase):
    def candidate(self):
        return cr.CommentItem(comment_id="c1", video_id="v1", author_name="Grace",
                              author_channel_id="UC_V", text="Please pray for me",
                              published_at="2026-11-06T20:00:00Z",
                              category="PRAYER_REQUEST")

    def test_the_reservation_is_written_before_the_insert(self):
        seen = {}
        ledger_path = self.log
        inner = FakeAPI([]).comments()

        class API(FakeAPI):
            def comments(self):
                class _C:
                    def insert(self, part=None, body=None):
                        seen["ledger_at_insert"] = json.loads(ledger_path.read_text())

                        def go():
                            return {"id": "reply_9"}
                        return mock.Mock(execute=mock.Mock(side_effect=go))

                    def list(self, **kwargs):
                        return inner.list(**kwargs)

                return _C()

        engine = self.engine(API([]))
        with mock.patch("time.sleep", return_value=None):
            self.assertTrue(engine.post_reply(self.candidate(), "Dear Grace, we are praying."))
        self.assertEqual(seen["ledger_at_insert"]["c1"]["status"], "pending")
        self.assertEqual(json.loads(self.log.read_text())["c1"]["status"], "posted")

    def test_an_unconfirmed_insert_is_rechecked_not_repeated(self):
        api = FakeAPI([])
        api.insert_error = RuntimeError("connection reset by peer")
        engine = self.engine(api)
        with mock.patch("time.sleep", return_value=None):
            self.assertFalse(engine.post_reply(self.candidate(), "Dear Grace, we are praying."))
        row = json.loads(self.log.read_text())["c1"]
        self.assertEqual(row["status"], "unconfirmed")
        self.assertIn("connection reset", row["error"])

    def test_reconcile_marks_a_reply_that_actually_landed(self):
        self.log.write_text(json.dumps({"c1": {"comment_id": "c1", "status": "unconfirmed"}}))
        api = FakeAPI([], own_reply_authors={"c1": ["UC_OWN"]})
        engine = self.engine(api)
        self.assertEqual(engine.reconcile_unconfirmed()["confirmed"], 1)
        self.assertEqual(json.loads(self.log.read_text())["c1"]["status"], "posted")

    def test_reconcile_releases_a_reply_that_did_not_land_so_it_can_be_retried(self):
        self.log.write_text(json.dumps({"c1": {"comment_id": "c1", "status": "unconfirmed"}}))
        api = FakeAPI([], own_reply_authors={"c1": ["UC_SOMEONE_ELSE"]})
        engine = self.engine(api)
        self.assertEqual(engine.reconcile_unconfirmed()["retryable"], 1)
        self.assertEqual(json.loads(self.log.read_text()), {})

    def test_a_reservation_left_by_a_crashed_run_blocks_a_second_reply(self):
        self.log.write_text(json.dumps({"c1": {"comment_id": "c1", "status": "pending"}}))
        api = FakeAPI([{"items": [thread("c1", "Please pray for me")]}])
        self.assertEqual(self.engine(api).fetch_candidate_comments(), [])


# --------------------------------------------------------------------------- #
# 7. Fallbacks may not become the boilerplate they replaced
# --------------------------------------------------------------------------- #
class TestFallbackIsNotBoilerplate(EngineCase):
    def candidate(self):
        return cr.CommentItem(comment_id="c1", video_id="v1", author_name="Grace",
                              author_channel_id="UC_V", text="Amen", published_at="",
                              category="AMEN_AFFIRMATION", reply_source="template")

    def test_the_third_use_of_one_sentence_is_held(self):
        text = cr.generate_fallback_reply("Grace", "Amen", "AMEN_AFFIRMATION",
                                          comment_id="c_seed")
        seeded = {f"old{i}": {"comment_id": f"old{i}", "reply_id": "r",
                              "reply_text": text, "status": "posted"} for i in (1, 2)}
        self.log.write_text(json.dumps(seeded))
        api = FakeAPI([])
        engine = self.engine(api)
        held = engine.post_reply(self.candidate(), text)
        self.assertFalse(held)
        self.assertEqual(api.inserted, [], "the same paragraph must not go out a third time")
        self.assertEqual(engine.last_skip_reason, "template_repeat")
        self.assertEqual(json.loads(self.log.read_text())["c1"]["category"],
                         "HELD_TEMPLATE_REPEAT")

    def test_a_gemini_reply_is_never_capped(self):
        text = "Grace, what a beautiful thing to say."
        seeded = {f"old{i}": {"comment_id": f"old{i}", "reply_text": text} for i in (1, 2)}
        self.log.write_text(json.dumps(seeded))
        item = self.candidate()
        item.reply_source = "gemini"
        api = FakeAPI([])
        with mock.patch("time.sleep", return_value=None):
            self.assertTrue(self.engine(api).post_reply(item, text))
        self.assertEqual(len(api.inserted), 1)


class TestAPreviewNeverWritesTheLedger(EngineCase):
    """Found by actually running `--simulate` on 2026-11-07.

    The crisis branch of `post_reply` ran before the dry-run check, so a rehearsal
    wrote its synthetic comments into the production ledger at
    `content/comments/replied.json` — and a real dry run would have recorded a real
    viewer as handled without ever answering them.
    """

    def crisis(self):
        return cr.CommentItem(comment_id="c_sim_6", video_id="v1", author_name="Ann",
                              author_channel_id="UC_V", text="I want to end my life",
                              published_at="", category="CRISIS_DISTRESS")

    def test_a_dry_run_holds_a_disclosure_without_recording_it(self):
        engine = self.engine(FakeAPI([]))
        self.assertFalse(engine.post_reply(self.crisis(), "Dear Ann, call 988.", dry_run=True))
        self.assertFalse(self.log.exists(), "a preview must not write the deduplication ledger")

    def test_the_simulation_cli_uses_a_throwaway_ledger(self):
        import scripts.reply_comments as cli

        engine = self.engine(FakeAPI([]))
        with mock.patch.object(sys, "argv",
                               ["reply_comments.py", "--simulate", "--channel", "prayer2"]), \
             mock.patch.object(cli, "CommentReplyEngine", return_value=engine) as ctor, \
             redirect_stdout(io.StringIO()):
            cli.main()
        path = ctor.call_args.kwargs.get("replied_log_path")
        self.assertIsNotNone(path, "the simulation got the production ledger")
        self.assertNotEqual(Path(path), self.log)
        self.assertFalse(self.log.exists())

    def test_a_live_run_still_records_the_hold(self):
        engine = self.engine(FakeAPI([]))
        self.assertFalse(engine.post_reply(self.crisis(), "Dear Ann, call 988."))
        row = json.loads(self.log.read_text())["c_sim_6"]
        self.assertEqual(row["category"], "CRISIS_ESCALATED")
        self.assertEqual(row["status"], "held_for_human")


# --------------------------------------------------------------------------- #
# 8. The workflow answers for every provisioned channel
# --------------------------------------------------------------------------- #
class TestTheWorkflowCoversEveryChannel(unittest.TestCase):
    def setUp(self):
        path = ROOT / ".github" / "workflows" / "comments.yml"
        self.text = path.read_text(encoding="utf-8")
        self.data = yaml.safe_load(self.text)

    def test_a_scheduled_run_expands_to_a_channel_matrix(self):
        job = self.data["jobs"]["reply"]
        self.assertIn("matrix", job["strategy"])
        self.assertIn("fromJSON(needs.plan.outputs.channels)",
                      json.dumps(job["strategy"]["matrix"]))
        self.assertEqual(job["needs"], "plan")

    def test_the_plan_probes_every_optional_channel_for_credentials(self):
        plan = self.data["jobs"]["plan"]
        env = plan["steps"][0]["env"]
        for channel_id in ("PRAYER2", "PRAYER3"):
            self.assertIn(f"{channel_id}_READY", env)
        run = plan["steps"][0]["run"]
        self.assertIn("PRAYER2_READY", run)
        self.assertIn("PRAYER3_READY", run)

    def test_credentials_are_mapped_per_matrix_channel(self):
        env = self.data["jobs"]["reply"]["steps"][-2]["env"]
        for key in ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN",
                    "GEMINI_API_KEY"):
            self.assertIn("matrix.channel", env[key], key)
        self.assertEqual(env["CHANNEL_ID"], "${{ matrix.channel }}")

    def test_the_declared_limit_matches_what_is_passed(self):
        self.assertIn("default: '8'", self.text)
        self.assertIn("LIMIT: ${{ github.event.inputs.limit || '8' }}", self.text)
        self.assertIn("--limit $LIMIT", self.text)

    def test_the_ledger_push_survives_a_race_with_production(self):
        self.assertIn("git pull --rebase", self.text)
        self.assertNotIn("|| true", self.text)


class TestTheCliAnswersAsTheGivenChannel(unittest.TestCase):
    def test_channel_flag_selects_the_voice_without_touching_credentials(self):
        import scripts.reply_comments as cli

        captured = {}

        class Stop(Exception):
            pass

        def fake_engine(**kwargs):
            captured.update(kwargs)
            raise Stop()

        out = io.StringIO()
        with mock.patch.object(sys, "argv",
                               ["reply_comments.py", "--simulate", "--channel", "prayer3"]), \
             mock.patch.object(cli, "CommentReplyEngine", side_effect=fake_engine), \
             redirect_stdout(out):
            with self.assertRaises(Stop):
                cli.main()
        self.assertEqual(captured["channel_id"], "prayer3")
        self.assertIn("THE MIDDAY WATCH", out.getvalue())
