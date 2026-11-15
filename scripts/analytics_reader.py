#!/usr/bin/env python3
"""Read each granted channel's YouTube Analytics and write down where it stands.

What the owner decided on 14 November 2026 may be kept in this public repository:
watch hours, traffic sources and retention (and, once the daily reach files are
read, thumbnail impressions and click rate). Views and the subscriber count are
public on YouTube already. Revenue is never asked for here, so it cannot be
written, logged or shown: `ask()` refuses any question that names a money metric
and `write_report()` refuses any report that contains one.

Run by `.github/workflows/channel-analytics.yml`, once a day, for every channel:

* a channel whose token does not carry the Analytics scopes yet, or whose Cloud
  project has the YouTube Analytics API off, is reported and left alone. Its
  file, if it has one, is not touched;
* a granted channel gets `content/analytics/<channel>.json`: watch hours over
  the 365 days the Partner Program counts (long-form and live apart from
  Shorts, because watch time in the Shorts feed does not count), Shorts views
  over 90 days, the last 28 days by kind of video, by traffic source and by
  day, and up to 50 videos by watch time with how long people stayed;
* `content/analytics/README.md` is rewritten from every file present: one table
  toward the Partner Program, then each channel's sources and videos.

Only GET requests, apart from the token refresh. Nothing on YouTube changes.
It never fails the job: a refusal is reported by Google's reason code only.
YouTube's own figures run about two days behind.
"""
import argparse
import datetime
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT))
import permission_probe as probe  # noqa: E402  (same folder; stdlib only)
from pipeline.channels import CHANNELS  # noqa: E402  (stdlib only)

ANALYTICS = probe.ANALYTICS
DATA = probe.DATA
OUT_DIR = ROOT / 'content' / 'analytics'
PUBLISHED_DIR = ROOT / 'content' / 'published'
SCHEMA = 1
MAX_VIDEOS = 50
#: What the YouTube Partner Program asks for (support.google.com/youtube/answer/72851,
#: read 14 November 2026). The full tier turns on ads; the early tier turns on fan funding.
NEEDS = {'subscribers': 1000, 'watch_hours': 4000, 'shorts_views_90d': 10_000_000}
EARLY_NEEDS = {'subscribers': 500, 'watch_hours': 3000, 'shorts_views_90d': 3_000_000}
#: The same page: a channel applying from 1 February 2027 needs twice the watch time.
NEEDS_FROM = (datetime.date(2027, 2, 1),
              {'subscribers': 1000, 'watch_hours': 8000, 'shorts_views_90d': 20_000_000})
#: Any metric that is money. Not asked for, not written, not printed.
MONEY = re.compile(r'revenue|earning|cpm|adimpression|monetizedplayback|gross', re.I)
VIDEO_ID = re.compile(r'^[A-Za-z0-9_-]{11}$')
#: Kinds of video as the API names them (letters only, lower case) -> where the hours go.
LONG_FORM = ('videoondemand', 'livestream')
SOURCES = {
    'SHORTS': 'Shorts feed', 'YT_SEARCH': 'YouTube search', 'SUBSCRIBER': 'Home and subscriptions',
    'RELATED_VIDEO': 'Suggested videos', 'YT_CHANNEL': 'Channel page', 'YT_OTHER_PAGE': 'Other YouTube pages',
    'EXT_URL': 'Other sites and apps', 'NO_LINK_OTHER': 'Direct or unknown', 'NO_LINK_EMBEDDED': 'Embedded players',
    'PLAYLIST': 'Playlists', 'NOTIFICATION': 'Notifications', 'END_SCREEN': 'End screens',
    'HASHTAGS': 'Hashtag pages', 'ADVERTISING': 'Advertising', 'SOUND_PAGE': 'Shorts sound pages',
    'VIDEO_REMIXES': 'Remixes', 'LIVE_REDIRECT': 'Live redirects', 'CAMPAIGN_CARD': 'Campaign cards',
    'ANNOTATION': 'Cards and annotations', 'PROMOTED': 'Promoted', 'PRODUCT_PAGE': 'Product pages',
}


def note(channel, text, level='notice'):
    print('::%s title=Analytics %s::%s' % (level, channel, text))


def needs(today):
    """The full-tier thresholds in force on `today`."""
    return dict(NEEDS_FROM[1]) if today >= NEEDS_FROM[0] else dict(NEEDS)


def access_token(client_id, client_secret, refresh_token):
    """(access token, refusal). Refusal is Google's code only, never its message."""
    if not (client_id and client_secret and refresh_token):
        return '', 'credentials not present in this run'
    form = urllib.parse.urlencode({'client_id': client_id, 'client_secret': client_secret,
                                   'refresh_token': refresh_token, 'grant_type': 'refresh_token'}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token', data=form),
                                    timeout=25) as response:
            return json.load(response).get('access_token', ''), ''
    except urllib.error.HTTPError as exc:
        return '', 'token refresh refused ' + probe.refusal(exc.code, exc.read())
    except Exception as exc:  # noqa: BLE001
        return '', 'token refresh got no answer (' + type(exc).__name__ + ')'


def number(value):
    """An int or a float from whatever the API sent; anything else is 0."""
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    try:
        result = float(value)
    except (TypeError, ValueError):
        return 0
    if result != result or result in (float('inf'), float('-inf')):
        return 0
    return int(result) if result == int(result) else result


def hours(minutes):
    return round(number(minutes) / 60.0, 2)


def word(value, limit=40):
    """A dimension value reduced to safe characters (it ends up in a public file and a log)."""
    return probe.CODE.sub('', str(value or ''))[:limit]


def ask(start, end, query, token, get=None):
    """(rows as dicts keyed by column name, '' or the refusal). One GET to the Analytics API."""
    if MONEY.search(query):
        raise ValueError('this reader never asks YouTube about money')
    url = '%s?ids=channel==MINE&startDate=%s&endDate=%s&%s' % (ANALYTICS, start, end, query)
    status, data, why = (get or probe.get)(url, token)
    if status != 200:
        return [], why or str(status)
    names = [word(header.get('name')) for header in (data or {}).get('columnHeaders') or []]
    rows = []
    for row in (data or {}).get('rows') or []:
        if isinstance(row, list) and len(row) == len(names):
            rows.append(dict(zip(names, row)))
    return rows, ''


def read_channel(channel, token, today, get=None):
    """(report or None, why not). None when the core question is refused: nothing to write."""
    get = get or probe.get
    year = (today - datetime.timedelta(days=365), today)
    quarter = (today - datetime.timedelta(days=90), today)
    month = (today - datetime.timedelta(days=28), today)
    coverage = {}

    def question(label, window, query):
        rows, why = ask(window[0], window[1], query, token, get)
        coverage[label] = ('refused ' + why) if why else ('%d row%s' % (len(rows), '' if len(rows) == 1 else 's'))
        return rows, why

    kinds, why = question('watch time by kind of video, 365 days', year,
                          'metrics=views,estimatedMinutesWatched&dimensions=creatorContentType')
    if why:
        return None, why

    def split(rows):
        table = {}
        for row in rows:
            kind = re.sub(r'[^a-z]', '', str(row.get('creatorContentType') or '').lower()) or 'unspecified'
            entry = table.setdefault(kind, {'views': 0, 'minutes': 0})
            entry['views'] += number(row.get('views'))
            entry['minutes'] += number(row.get('estimatedMinutesWatched'))
        return table

    def by_kind(table):
        long_minutes = sum(table.get(kind, {}).get('minutes', 0) for kind in LONG_FORM)
        short_minutes = table.get('shorts', {}).get('minutes', 0)
        other_minutes = sum(v['minutes'] for k, v in table.items() if k not in LONG_FORM + ('shorts',))
        return {
            'long_form_and_live': hours(long_minutes), 'shorts': hours(short_minutes), 'other': hours(other_minutes),
            'total': hours(long_minutes + short_minutes + other_minutes),
        }

    year_table = split(kinds)
    quarter_rows, _ = question('views by kind of video, 90 days', quarter,
                               'metrics=views&dimensions=creatorContentType')
    month_rows, _ = question('watch time by kind of video, 28 days', month,
                             'metrics=views,estimatedMinutesWatched&dimensions=creatorContentType')
    month_table = split(month_rows)
    source_rows, _ = question('where viewers came from, 28 days', month,
                              'metrics=views,estimatedMinutesWatched&dimensions=insightTrafficSourceType&sort=-views')
    day_rows, _ = question('watch time by day, 28 days', month,
                           'metrics=views,estimatedMinutesWatched&dimensions=day&sort=day')
    # A per-video report must be sorted by views or watch time and capped (settled live, 14 Nov).
    video_rows, _ = question('videos by watch time, 365 days', year,
                             'metrics=estimatedMinutesWatched,views,averageViewDuration,averageViewPercentage'
                             '&dimensions=video&sort=-estimatedMinutesWatched&maxResults=%d' % MAX_VIDEOS)

    subscribers = None
    status, data, _why = get(DATA + 'channels?part=statistics&mine=true', token)
    if status == 200 and (data or {}).get('items'):
        stats = data['items'][0].get('statistics') or {}
        if not stats.get('hiddenSubscriberCount') and str(stats.get('subscriberCount', '')).isdigit():
            subscribers = int(stats['subscriberCount'])
    coverage['subscriber count (public)'] = 'read' if subscribers is not None else 'not available'

    threshold = needs(today)
    counted = by_kind(year_table)
    month_hours = by_kind(month_table)
    report = {
        'schema': SCHEMA,
        'channel': channel,
        'generated_at': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'source': 'YouTube Analytics API; figures run about two days behind. Revenue is never written here.',
        'windows': {'year': [str(year[0]), str(year[1])], 'quarter': [str(quarter[0]), str(quarter[1])],
                    'month': [str(month[0]), str(month[1])]},
        'partner_program': {
            'needs': threshold,
            'early_tier_needs': dict(EARLY_NEEDS),
            'subscribers': subscribers,
            # Watch time in the Shorts feed does not count, so it is kept apart.
            'watch_hours_365d': counted,
            'watch_hours_counted': counted['long_form_and_live'],
            'shorts_views_90d': sum(number(r.get('views')) for r in quarter_rows
                                    if re.sub(r'[^a-z]', '', str(r.get('creatorContentType') or '').lower()) == 'shorts'),
            'kinds_seen_365d': sorted(year_table),
            'long_form_hours_a_day_needed': round(threshold['watch_hours'] / 365.0, 1),
            'long_form_hours_a_day_last_28_days': round(month_hours['long_form_and_live'] / 28.0, 2),
        },
        'last_28_days': {
            'views': sum(v['views'] for v in month_table.values()),
            'watch_hours': month_hours,
            'views_by_kind': {kind: values['views'] for kind, values in sorted(month_table.items())},
            'traffic_sources': [
                {'source': word(r.get('insightTrafficSourceType')), 'views': number(r.get('views')),
                 'watch_hours': hours(r.get('estimatedMinutesWatched'))}
                for r in source_rows if word(r.get('insightTrafficSourceType'))],
            'by_day': [
                {'day': str(r.get('day'))[:10], 'views': number(r.get('views')),
                 'watch_hours': hours(r.get('estimatedMinutesWatched'))}
                for r in day_rows if re.match(r'^\d{4}-\d{2}-\d{2}$', str(r.get('day'))[:10])],
        },
        'videos_365d': [
            {'video_id': str(r.get('video')), 'watch_hours': hours(r.get('estimatedMinutesWatched')),
             'views': number(r.get('views')), 'average_view_seconds': number(r.get('averageViewDuration')),
             'average_view_percent': round(float(number(r.get('averageViewPercentage'))), 1)}
            for r in video_rows if VIDEO_ID.match(str(r.get('video')))][:MAX_VIDEOS],
        'not_included': ['thumbnail impressions and click rate: only in the daily reach files '
                         '(scripts/reporting_jobs.py), which nothing downloads yet'],
        'coverage': coverage,
    }
    return report, ''


def money_keys(value, path=''):
    """Every place in a report where a money metric appears (there must be none)."""
    found = []
    if isinstance(value, dict):
        for key, item in value.items():
            where = '%s.%s' % (path, key) if path else str(key)
            if MONEY.search(str(key)):
                found.append(where)
            found += money_keys(item, where)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found += money_keys(item, '%s[%d]' % (path, index))
    return found


def write_report(report, out_dir=None):
    """Write `<channel>.json`; refuses a report that names money or an unknown channel."""
    channel = report.get('channel')
    if channel not in CHANNELS:
        raise ValueError('unknown channel')
    leaked = money_keys(report)
    if leaked:
        raise ValueError('a money figure must not be written: ' + ', '.join(leaked))
    directory = Path(out_dir or OUT_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / ('%s.json' % channel)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + '\n', encoding='utf-8')
    tmp.replace(path)
    return path


def load_reports(out_dir=None):
    """Every readable report in the folder, in the registry's channel order."""
    directory = Path(out_dir or OUT_DIR)
    reports = {}
    for channel in CHANNELS:
        path = directory / ('%s.json' % channel)
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and data.get('schema') == SCHEMA and data.get('channel') == channel:
            reports[channel] = data
    return reports


def titles(published_dir=None):
    """{video id: title} from the receipts, so a table can name a video."""
    found = {}
    directory = Path(published_dir or PUBLISHED_DIR)
    if not directory.is_dir():
        return found
    for path in sorted(directory.glob('*.md')):
        try:
            head = path.read_text(encoding='utf-8')[:6000]
        except OSError:
            continue
        video = re.search(r'^youtube_video_id:\s*["\']?([A-Za-z0-9_-]{11})["\']?\s*$', head, re.M)
        title = re.search(r'^title:\s*(.+?)\s*$', head, re.M)
        if video and title:
            found[video.group(1)] = title.group(1).strip().strip('"\'')
    return found


def count(value):
    return '{:,}'.format(int(number(value)))


def amount(value):
    """Hours, with no false precision: 0, 0.4, 12.3, 1,204."""
    value = float(number(value))
    if value >= 100:
        return '{:,.0f}'.format(value)
    text = ('%.1f' % value) if value >= 1 else ('%.2f' % value)
    return text.rstrip('0').rstrip('.') if '.' in text else text


def clock(seconds):
    seconds = int(number(seconds))
    return '%d:%02d' % (seconds // 60, seconds % 60) if seconds < 3600 else \
        '%d:%02d:%02d' % (seconds // 3600, seconds % 3600 // 60, seconds % 60)


def cell(text, limit=70):
    """Text that cannot break a Markdown table."""
    text = re.sub(r'\s+', ' ', str(text)).replace('|', '/').strip()
    return text if len(text) <= limit else text[:limit - 1].rstrip() + '…'


def headline(report):
    """One plain sentence for the run's annotation."""
    program = report['partner_program']
    month = report['last_28_days']
    subscribers = program.get('subscribers')
    text = '%s of %s watch hours counted over 365 days (long-form and live; Shorts %s h not counted); %s; ' \
           'last 28 days: %s long-form hours, %s views' % (
               amount(program['watch_hours_counted']), count(program['needs']['watch_hours']),
               amount(program['watch_hours_365d']['shorts']),
               ('%s of %s subscribers' % (count(subscribers), count(program['needs']['subscribers'])))
               if subscribers is not None else 'subscriber count not available',
               amount(month['watch_hours']['long_form_and_live']), count(month['views']))
    # A kind of video this reader does not know is said out loud, not silently left out.
    odd = [word(kind) for kind in program.get('kinds_seen_365d', []) if kind not in LONG_FORM + ('shorts',)]
    if odd:
        text += '; also seen and counted as neither: %s (%s h)' % (
            ', '.join(odd), amount(program['watch_hours_365d']['other']))
    return text


def summary(reports, published_dir=None):
    """The whole of `content/analytics/README.md`, from the reports that exist."""
    lines = [
        '# Where each channel stands (YouTube Analytics)', '',
        'Written by `scripts/analytics_reader.py`. Do not edit: the next run rewrites it.',
        'YouTube\'s figures run about two days behind. Revenue is never written here.', '']
    if not reports:
        return '\n'.join(lines + ['No channel has been granted Analytics access yet.', ''])
    known = titles(published_dir)
    first = next(iter(reports.values()))
    need = first['partner_program']['needs']
    lines += [
        '## Toward the Partner Program', '',
        '| Channel | Subscribers (need %s) | Watch hours, 365 days (need %s) | Shorts views, 90 days (need %s) '
        '| Long-form hours a day, last 28 days (need %s) | Read |' % (
            count(need['subscribers']), count(need['watch_hours']), count(need['shorts_views_90d']),
            amount(first['partner_program']['long_form_hours_a_day_needed'])),
        '| :--- | ---: | ---: | ---: | ---: | :--- |']
    for channel, report in reports.items():
        program = report['partner_program']
        lines.append('| %s | %s | %s | %s | %s | %s |' % (
            cell(CHANNELS[channel].display_name),
            count(program['subscribers']) if program.get('subscribers') is not None else 'not available',
            amount(program['watch_hours_counted']), count(program['shorts_views_90d']),
            amount(program['long_form_hours_a_day_last_28_days']), str(report.get('generated_at', ''))[:10]))
    waiting = [CHANNELS[c].display_name for c in CHANNELS if c not in reports]
    lines += [
        '',
        'Ads need the subscribers and either the watch hours or the Shorts views. Watch hours counted here are '
        'long-form and live only: time watched in the Shorts feed does not count. A year of the daily figure in '
        'the last column is what the 365-day total becomes. YouTube Studio\'s Earn page holds the official count.',
        '']
    if waiting:
        lines += ['Not granted Analytics access yet: %s.' % ', '.join(waiting), '']
    for channel, report in reports.items():
        month = report['last_28_days']
        program = report['partner_program']
        lines += [
            '## %s' % CHANNELS[channel].display_name, '',
            'Last 28 days (%s to %s): %s views, %s watch hours (%s long-form and live, %s Shorts). '
            'Over 365 days: %s hours long-form and live, %s hours Shorts.' % (
                report['windows']['month'][0], report['windows']['month'][1], count(month['views']),
                amount(month['watch_hours']['total']), amount(month['watch_hours']['long_form_and_live']),
                amount(month['watch_hours']['shorts']), amount(program['watch_hours_365d']['long_form_and_live']),
                amount(program['watch_hours_365d']['shorts'])), '']
        if month['traffic_sources']:
            lines += ['Where viewers came from, last 28 days:', '',
                      '| Source | Views | Watch hours |', '| :--- | ---: | ---: |']
            for row in month['traffic_sources']:
                lines.append('| %s | %s | %s |' % (cell(SOURCES.get(row['source'], row['source'])),
                                                   count(row['views']), amount(row['watch_hours'])))
            lines.append('')
        if report['videos_365d']:
            lines += ['Videos by watch time, 365 days (up to %d):' % MAX_VIDEOS, '',
                      '| Video | Watch hours | Views | Average watched |', '| :--- | ---: | ---: | ---: |']
            for row in report['videos_365d']:
                lines.append('| [%s](https://youtu.be/%s) | %s | %s | %s (%s%%) |' % (
                    cell(known.get(row['video_id'], row['video_id'])), row['video_id'], amount(row['watch_hours']),
                    count(row['views']), clock(row['average_view_seconds']), amount(row['average_view_percent'])))
            lines.append('')
        refused = ['%s (%s)' % (label, answer) for label, answer in sorted(report.get('coverage', {}).items())
                   if str(answer).startswith('refused')]
        if refused:
            lines += ['Not answered on the last read: %s.' % cell('; '.join(refused), 400), '']
    return '\n'.join(lines).rstrip('\n') + '\n'


def issue_lines(channel, out_dir=None):
    """A few lines for the daily snapshot issue, or none when the channel has no report."""
    report = load_reports(out_dir).get(channel)
    if not report:
        return []
    program = report['partner_program']
    return [
        '### Toward the Partner Program (YouTube Analytics, read %s)' % str(report.get('generated_at', ''))[:10],
        '',
        '- Watch hours counted over 365 days: **%s of %s** (long-form and live; Shorts-feed time, %s h, does not count).'
        % (amount(program['watch_hours_counted']), count(program['needs']['watch_hours']),
           amount(program['watch_hours_365d']['shorts'])),
        '- Long-form hours a day over the last 28 days: **%s** (a year at %s a day reaches the threshold).'
        % (amount(program['long_form_hours_a_day_last_28_days']), amount(program['long_form_hours_a_day_needed'])),
        '- Shorts views over 90 days: **%s of %s**.' % (count(program['shorts_views_90d']),
                                                      count(program['needs']['shorts_views_90d'])),
        '',
    ]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--channel', action='append', help='only this channel (repeatable); default: all')
    parser.add_argument('--out', default=str(OUT_DIR))
    parser.add_argument('--no-write', action='store_true', help='read and report; write no file')
    args = parser.parse_args(argv)
    today = datetime.datetime.now(datetime.timezone.utc).date()
    wanted = [c for c in (args.channel or list(CHANNELS)) if c in CHANNELS]

    # GitHub shows at most ten annotations of a kind per step, so channels that are
    # not granted yet share one line per reason instead of taking one each.
    waiting = {}
    for channel in wanted:
        try:
            names = CHANNELS[channel].secret_names()
            token, why = access_token(*(os.environ.get(names[key], '').strip()
                                        for key in ('client_id', 'client_secret', 'refresh_token')))
            if not token:
                waiting.setdefault(why, []).append(channel)
                continue
            report, why = read_channel(channel, token, today)
            if report is None:
                waiting.setdefault('not granted yet (%s)' % why, []).append(channel)
                continue
            if not args.no_write:
                write_report(report, args.out)
            refused = sorted(label for label, answer in report['coverage'].items()
                             if str(answer).startswith('refused'))
            note(channel, '%s; %s%s' % (
                headline(report), 'not written (dry run)' if args.no_write else 'file written',
                '; refused: ' + ', '.join(refused) if refused else ''), 'warning' if refused else 'notice')
            print('[analytics] %s coverage: %s; kinds of video over 365 days: %s' % (
                channel, '; '.join('%s: %s' % item for item in sorted(report['coverage'].items())),
                ', '.join(report['partner_program']['kinds_seen_365d']) or 'none'))
        except Exception as exc:  # noqa: BLE001 - one channel must not cost the others, or the job
            waiting.setdefault('stopped early (%s)' % type(exc).__name__, []).append(channel)
    for why, channels in waiting.items():
        level = 'warning' if ('refused' in why and 'not granted' not in why) or 'stopped early' in why else 'notice'
        note(', '.join(channels), '%s; no file written' % why, level)
    if not args.no_write:
        try:
            reports = load_reports(args.out)
            if reports:
                Path(args.out).mkdir(parents=True, exist_ok=True)
                (Path(args.out) / 'README.md').write_text(summary(reports), encoding='utf-8')
        except Exception as exc:  # noqa: BLE001
            print('::warning title=Analytics summary::not rewritten (%s)' % type(exc).__name__)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
