from datetime import date
import unittest

from scripts.monetization_plan import gaps, reader, snapshot_values


class MonetizationPlanTests(unittest.TestCase):
    def test_unavailable_query_is_not_a_zero(self):
        values = snapshot_values({"coverage": {"subscriber count (public)": "read",
                                                 "views by kind of video, 90 days": "refused scope"},
                                  "partner_program": {"subscribers": 1260, "shorts_views_90d": 0}})
        self.assertEqual(gaps(values, reader.needs(date(2026, 11, 20))),
                         {"subscribers": 0, "watch_hours": None, "shorts_views_90d": None})

    def test_new_applicant_threshold_switch_does_not_change_fan_funding(self):
        values = {"subscribers": 1260, "watch_hours": 22.77, "shorts_views_90d": 4671}
        before = gaps(values, reader.needs(date(2027, 1, 31)))
        after = gaps(values, reader.needs(date(2027, 2, 1)))
        self.assertAlmostEqual(before["watch_hours"], 3977.23)
        self.assertAlmostEqual(after["watch_hours"], 7977.23)
        self.assertEqual(after["shorts_views_90d"], 19995329)
        self.assertAlmostEqual(gaps(values, reader.EARLY_NEEDS)["watch_hours"], 2977.23)
