#!/usr/bin/env python3
"""Private, read-only YouTube Analytics reports with explicit coverage status.

Run outside public CI, with ANALYTICS_CLIENT_ID, ANALYTICS_CLIENT_SECRET and
ANALYTICS_REFRESH_TOKEN in the environment. Never paste these into chat.
Default output is gitignored output/private-analytics/report.json (mode 0600).
No upload, video edit or publish operations are used.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

READ_SCOPE = 'https://www.googleapis.com/auth/yt-analytics.readonly'
MONEY_SCOPE = 'https://www.googleapis.com/auth/yt-analytics-monetary.readonly'
REPORTS = {
    'daily': ('day', 'views,estimatedMinutesWatched,averageViewDuration,subscribersGained,subscribersLost,likes,comments,shares'),
    'videos': ('video', 'views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained,subscribersLost'),
    'traffic_sources': ('insightTrafficSourceType', 'views,estimatedMinutesWatched'),
    'countries': ('country', 'views,estimatedMinutesWatched'),
    'devices': ('deviceType', 'views,estimatedMinutesWatched'),
    'demographics': ('ageGroup,gender', 'viewerPercentage'),
    'subscription_status': ('subscribedStatus', 'views,estimatedMinutesWatched'),
}
# Studio and API capabilities differ. Do not manufacture absent reports or assume
# all Studio fields are exposed by this integration.
STUDIO_EXPORTS = [
    'thumbnail impressions and click-through rate',
    'new/returning/unique viewers and detailed audience interests',
    'monetization eligibility, copyright claims and policy restrictions',
    'finalized AdSense earnings and payments',
]


def fetch_report(service, start: str, end: str, dimensions: str,
                 metrics: str, *, filters: str | None = None, max_pages: int = 50) -> dict:
    """Page results and distinguish denial, empty data, and bounded truncation.

    Raw API errors are deliberately not serialized: URLs or credential-related
    details can occur in exception messages. Preserve the HTTP status only.
    """
    rows = []
    headers = []
    try:
        for page in range(max_pages):
            query = dict(ids='channel==MINE', startDate=start, endDate=end,
                         dimensions=dimensions, metrics=metrics,
                         startIndex=page * 200 + 1, maxResults=200)
            if filters:
                query['filters'] = filters
            response = service.reports().query(**query).execute()
            headers = response.get('columnHeaders', headers)
            batch = response.get('rows') or []
            rows.extend(batch)
            if len(batch) < 200:
                return dict(status='collected' if rows else 'no_data',
                            columns=headers, rows=rows)
        return dict(status='truncated', columns=headers, rows=rows,
                    reason='Safety pagination limit reached; report is incomplete.')
    except Exception as exc:
        status = getattr(getattr(exc, 'resp', None), 'status', None)
        return dict(status='permission_or_api_error' if status in (401, 403) else 'error',
                    http_status=status, partial_rows=len(rows),
                    reason='Report unavailable. Check API enablement, OAuth scopes, report compatibility and channel access. No missing values were replaced with zero.')


def collect(service, start: str, end: str, *, revenue: bool = False,
            retention_video: str | None = None) -> dict:
    reports = {name: fetch_report(service, start, end, dimensions, metrics)
               for name, (dimensions, metrics) in REPORTS.items()}
    reports['revenue'] = (
        fetch_report(service, start, end, 'day', 'estimatedRevenue,estimatedAdRevenue')
        if revenue else dict(status='not_requested', reason='Requires separate monetary-readonly consent; estimated revenue is not finalized AdSense payment.')
    )
    reports['retention'] = (
        fetch_report(service, start, end, 'elapsedVideoTimeRatio',
                     'audienceWatchRatio,relativeRetentionPerformance',
                     filters=f'video=={retention_video}')
        if retention_video else dict(status='not_requested', reason='Supply --retention-video VIDEO_ID; retention is a per-video report.')
    )
    return dict(start_date=start, end_date=end,
                collected_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                reports=reports, studio_exports_required=STUDIO_EXPORTS,
                caveats=[
                    'This is not a promise of every Studio field. Check each report status.',
                    'Recent Analytics data may be delayed; small audience groups may be withheld.',
                    'No data does not mean zero. Estimated revenue is not a payout.',
                    'Channel subscriber totals are collected separately by metrics_snapshot.py.',
                ])


def write_private(report: dict, path: Path) -> None:
    """Refuse tracked/source paths and symlinks; restrict report permissions."""
    private_root = (ROOT / 'output' / 'private-analytics').resolve()
    target = path.resolve()
    if not target.is_relative_to(private_root) or path.is_symlink():
        raise ValueError('Reports must stay under output/private-analytics/ and cannot be symlinks.')
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as handle:
        os.chmod(target, 0o600)
        json.dump(report, handle, indent=2)
        handle.write('\n')


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--start', type=dt.date.fromisoformat, default=dt.date.today() - dt.timedelta(days=28))
    ap.add_argument('--end', type=dt.date.fromisoformat, default=dt.date.today() - dt.timedelta(days=2))
    ap.add_argument('--revenue', action='store_true')
    ap.add_argument('--retention-video')
    args = ap.parse_args()
    if os.environ.get('GITHUB_ACTIONS') == 'true':
        ap.error('Private Analytics collection is disabled in Actions until private storage is configured.')
    if args.start > args.end:
        ap.error('--start must not be after --end')
    names = ('ANALYTICS_CLIENT_ID', 'ANALYTICS_CLIENT_SECRET', 'ANALYTICS_REFRESH_TOKEN')
    if not all(os.environ.get(name) for name in names):
        ap.error('Missing ANALYTICS_* credentials. Use the separate read-only OAuth flow; never put tokens in chat.')
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    scopes = ['https://www.googleapis.com/auth/youtube.readonly', READ_SCOPE]
    if args.revenue:
        scopes.append(MONEY_SCOPE)
    creds = Credentials(token=None, refresh_token=os.environ[names[2]],
                        client_id=os.environ[names[0]], client_secret=os.environ[names[1]],
                        token_uri='https://oauth2.googleapis.com/token', scopes=scopes)
    try:
        analytics = build('youtubeAnalytics', 'v2', credentials=creds, cache_discovery=False)
        report = collect(analytics, str(args.start), str(args.end),
                         revenue=args.revenue, retention_video=args.retention_video)
    except Exception:
        print('Analytics connection failed. Check credentials and API enablement; details withheld for privacy.', file=sys.stderr)
        return 1
    write_private(report, ROOT / 'output' / 'private-analytics' / 'report.json')
    # Statuses only. No audience/revenue values in logs.
    for name, result in report['reports'].items():
        print(f"{name}: {result['status']}")
    print('Private report saved under output/private-analytics/ (not committed or uploaded).')
    return int(any(r['status'] in ('error', 'permission_or_api_error', 'truncated')
                   for r in report['reports'].values()))


if __name__ == '__main__':
    raise SystemExit(main())
