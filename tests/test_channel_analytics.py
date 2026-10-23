import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from scripts import channel_analytics as analytics
from scripts.youtube_oauth import scopes_for


class AnalyticsTests(unittest.TestCase):
    def service(self, responses):
        service = MagicMock()
        service.reports.return_value.query.return_value.execute.side_effect = responses
        return service

    def test_paginates_without_dropping_rows(self):
        service = self.service([{'rows': [[1]] * 200}, {'rows': [[2]]}])
        result = analytics.fetch_report(service, '2026-09-01', '2026-09-30', 'day', 'views')
        self.assertEqual(result['status'], 'collected')
        self.assertEqual(len(result['rows']), 201)
        self.assertEqual(service.reports.return_value.query.call_args.kwargs['startIndex'], 201)

    def test_empty_is_not_zero(self):
        result = analytics.fetch_report(self.service([{}]), '2026-09-01', '2026-09-30', 'day', 'views')
        self.assertEqual(result['status'], 'no_data')
        self.assertEqual(result['rows'], [])

    def test_permission_error_does_not_leak_exception_text(self):
        class Denied(Exception):
            resp = type('Response', (), {'status': 403})()
        result = analytics.fetch_report(self.service([Denied('sensitive text')]), '2026-09-01', '2026-09-30', 'day', 'views')
        self.assertEqual(result['status'], 'permission_or_api_error')
        self.assertEqual(result['http_status'], 403)
        self.assertNotIn('sensitive text', str(result))

    def test_bounded_pagination_is_explicitly_incomplete(self):
        result = analytics.fetch_report(self.service([{'rows': [[1]] * 200}]), '2026-09-01', '2026-09-30', 'day', 'views', max_pages=1)
        self.assertEqual(result['status'], 'truncated')

    def test_inventory_keeps_unrequested_reports_visible(self):
        result = analytics.collect(self.service([{}] * len(analytics.REPORTS)), '2026-09-01', '2026-09-30')
        self.assertEqual(result['reports']['revenue']['status'], 'not_requested')
        self.assertEqual(result['reports']['retention']['status'], 'not_requested')
        self.assertTrue(result['studio_exports_required'])

    def test_analytics_token_has_no_upload_permission(self):
        self.assertNotIn('https://www.googleapis.com/auth/youtube.upload', scopes_for('analytics'))
        self.assertNotIn(analytics.MONEY_SCOPE, scopes_for('analytics'))
        self.assertIn(analytics.MONEY_SCOPE, scopes_for('analytics-revenue'))
        self.assertIn('https://www.googleapis.com/auth/youtube.upload', scopes_for('upload'))

    def test_private_file_permissions_and_source_path_rejection(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(analytics, 'ROOT', Path(tmp)):
            path = Path(tmp) / 'output/private-analytics/report.json'
            analytics.write_private({'reports': {}}, path)
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
            with self.assertRaises(ValueError):
                analytics.write_private({}, Path(tmp) / 'tracked.json')
            link = path.with_name('link.json')
            link.symlink_to(path)
            with self.assertRaises(ValueError):
                analytics.write_private({}, link)

    def test_public_actions_refused_before_reading_credentials(self):
        with patch.dict(os.environ, {'GITHUB_ACTIONS': 'true'}), patch('sys.argv', ['channel_analytics.py']):
            with self.assertRaises(SystemExit) as error:
                analytics.main()
            self.assertEqual(error.exception.code, 2)
