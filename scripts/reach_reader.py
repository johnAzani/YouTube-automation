#!/usr/bin/env python3
"""Download each granted channel's daily reach files and write down what they say.

Thumbnail impressions (how often YouTube showed a video's thumbnail) and click
rate (how often that was clicked) come from one place only: the daily "reach"
file of the YouTube Reporting API, which `scripts/reporting_jobs.py` asks
YouTube to write. This reads those files.

What the owner decided on 14 November 2026 may be kept in this public
repository includes thumbnail impressions and click rate. Revenue never: the
reach file holds none, only the four columns named in `COLUMNS` are read out of
it, and `write_reach()` refuses a report that names money.

Run by `.github/workflows/channel-analytics.yml`, once a day, for every channel:

* a channel not granted yet, with no reach job, or with no file ready is
  reported and left alone. Its file, if it has one, is not touched;
* a channel with files gets `content/analytics/<channel>.reach.json`, rebuilt
  from every daily file YouTube still holds (it keeps each one 60 days):
  impressions and clicks per video over those days, and per day. Days YouTube
  has dropped stay in the per-day list from the earlier file.

Only GET requests, apart from the token refresh. Nothing on YouTube changes and
no reporting job is created or deleted here. It never fails the job. The access
token is sent to youtubereporting.googleapis.com only, and no redirect is
followed.

The click rate's unit is settled from the file, not assumed: a row with a click
rate above zero stands for at least one click and no more clicks than
impressions, and only one reading (a fraction of 1, or a percentage) fits every
row. When neither or both fit, impressions are written and the click rate is
left out and said to be undetermined.
"""
import argparse
import csv
import datetime
import io
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
from scripts import analytics_reader as base  # noqa: E402  (stdlib only)

REPORTING = probe.REPORTING
REPORT_TYPE = 'channel_reach_basic_a1'
HOST = 'youtubereporting.googleapis.com'
OUT_DIR = base.OUT_DIR
SCHEMA = 1
#: The only columns read out of a daily file. Every other column is a way the
#: same impressions are split (country, subscribed or not) and is summed over.
COLUMNS = ('date', 'video_id', 'video_thumbnail_impressions', 'video_thumbnail_impressions_ctr')
MAX_FILES = 70                 # YouTube keeps 60 days
MAX_FILE_BYTES = 25 * 1024 * 1024
MAX_PAGES = 5
DAY = re.compile(r'^\d{4}-\d{2}-\d{2}$')


def note(channel, text, level='notice'):
    print('::%s title=Reach %s::%s' % (level, channel, text))


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401, PLR0913
        return None  # a redirect would carry the access token to another address


def download(url, token):
    """(bytes or None, refusal). One GET; the token goes to Google's reporting host only."""
    parsed = urllib.parse.urlparse(str(url or ''))
    if parsed.scheme != 'https' or parsed.hostname != HOST:
        return None, 'download address is not on ' + HOST
    request = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + token})
    try:
        with urllib.request.build_opener(_NoRedirect).open(request, timeout=40) as response:
            data = response.read(MAX_FILE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        return None, probe.refusal(exc.code, exc.read())
    except Exception as exc:  # noqa: BLE001
        return None, 'no answer (' + type(exc).__name__ + ')'
    if len(data) > MAX_FILE_BYTES:
        return None, 'file larger than %d MB' % (MAX_FILE_BYTES // (1024 * 1024))
    return data, ''


def iso_day(value):
    """'20261112' or '2026-11-12...' -> '2026-11-12'; anything else -> ''."""
    text = str(value or '').strip()
    if re.match(r'^\d{8}$', text):
        text = '%s-%s-%s' % (text[:4], text[4:6], text[6:])
    text = text[:10]
    if not DAY.match(text):
        return ''
    try:
        datetime.date.fromisoformat(text)
    except ValueError:
        return ''
    return text


def parse(data):
    """(rows, columns seen, why not). Rows are (day, video id, impressions, click rate as written)."""
    try:
        text = data.decode('utf-8-sig')
    except (UnicodeDecodeError, AttributeError):
        return [], [], 'file is not text'
    reader = csv.reader(io.StringIO(text))
    try:
        header = [base.word(name, 60).lower() for name in next(reader)]
    except StopIteration:
        return [], [], ''  # an empty file: a day with nothing in it
    except csv.Error:
        return [], [], 'file is not a table'
    missing = [name for name in COLUMNS if name not in header]
    if missing:
        return [], header, 'column missing: ' + ', '.join(missing)
    at = {name: header.index(name) for name in COLUMNS}
    rows = []
    try:
        for line in reader:
            if len(line) < len(header):
                continue
            day, video = iso_day(line[at['date']]), line[at['video_id']].strip()
            if not day or not base.VIDEO_ID.match(video):
                continue
            shown = base.number(line[at['video_thumbnail_impressions']])
            rate = float(base.number(line[at['video_thumbnail_impressions_ctr']]))
            if shown < 0 or rate < 0:
                continue
            rows.append((day, video, float(shown), rate))
    except csv.Error:
        return [], header, 'file is not a table'
    return rows, header, ''


def rate_unit(rows):
    """'fraction', 'percent', 'none seen' or 'undetermined', from the rows themselves.

    A click rate above zero stands for at least one click (half a click, to allow
    for rounding in the file) and never for more clicks than impressions.
    """
    seen = [(shown, rate) for _day, _video, shown, rate in rows if shown > 0 and rate > 0]
    if not seen:
        return 'none seen'
    as_fraction = all(rate <= 1.000001 and shown * rate >= 0.5 for shown, rate in seen)
    as_percent = all(rate <= 100.0001 and shown * rate / 100.0 >= 0.5 for shown, rate in seen)
    if as_fraction != as_percent:
        return 'fraction' if as_fraction else 'percent'
    return 'undetermined'


def percent(clicks, shown):
    return round(100.0 * clicks / shown, 2) if shown and clicks is not None else None


def build(channel, rows, files, today, job_since='', previous=None, columns=()):
    """The whole report for one channel from the rows of every file read. `today` is the read's time stamp."""
    unit = rate_unit(rows)
    scale = {'fraction': 1.0, 'percent': 0.01, 'none seen': 0.0}.get(unit)
    cells = {}
    for day, video, shown, rate in rows:
        cell = cells.setdefault((day, video), [0.0, 0.0])
        cell[0] += shown
        cell[1] += shown * rate * (scale or 0.0)
    by_day, videos = {}, {}
    for (day, video), (shown, clicks) in cells.items():
        shown = int(round(shown))
        clicks = None if scale is None else min(shown, int(round(clicks)))
        total = by_day.setdefault(day, {'day': day, 'impressions': 0, 'clicks': None if scale is None else 0})
        total['impressions'] += shown
        entry = videos.setdefault(video, {'video_id': video, 'impressions': 0,
                                          'clicks': None if scale is None else 0,
                                          'first_day': day, 'last_day': day})
        entry['impressions'] += shown
        entry['first_day'], entry['last_day'] = min(entry['first_day'], day), max(entry['last_day'], day)
        if clicks is not None:
            total['clicks'] += clicks
            entry['clicks'] += clicks
    for entry in videos.values():
        entry['click_rate_percent'] = percent(entry['clicks'], entry['impressions'])
    read_days = sorted(by_day)
    shown = sum(row['impressions'] for row in by_day.values())
    clicks = None if scale is None else sum(row['clicks'] for row in by_day.values())
    # Days YouTube no longer holds stay as the earlier read wrote them.
    kept = {}
    for row in (previous or {}).get('by_day') or []:
        if isinstance(row, dict) and DAY.match(str(row.get('day'))) and row['day'] not in by_day:
            kept[row['day']] = {'day': row['day'], 'impressions': int(base.number(row.get('impressions'))),
                                'clicks': None if row.get('clicks') is None else int(base.number(row['clicks']))}
    # When the unit cannot be settled, a few rows as the file wrote them, so the
    # rule can be corrected from the committed file or the run's log.
    samples = [[int(shown), rate] for _day, _video, shown, rate in rows if shown > 0 and rate > 0][:5] \
        if unit == 'undetermined' else []
    return {
        'click_rate_samples_as_written': samples,
        'schema': SCHEMA, 'channel': channel, 'report': REPORT_TYPE,
        'generated_at': str(today),
        'job_since': job_since, 'files_read': files,
        'click_rate_unit_in_file': unit,
        'columns_seen': list(columns),
        'window': {'first_day': read_days[0] if read_days else None,
                   'last_day': read_days[-1] if read_days else None,
                   'days': len(read_days), 'impressions': shown, 'clicks': clicks,
                   'click_rate_percent': percent(clicks, shown), 'videos': len(videos)},
        'by_day': [dict(row) for _day, row in sorted({**kept, **by_day}.items())],
        'videos': sorted(videos.values(), key=lambda row: (-row['impressions'], row['video_id'])),
        'notes': ['clicks are impressions times the click rate in the file, rounded',
                  'videos cover the days in window; by_day also keeps days YouTube no longer holds'],
    }


def write_reach(report, out_dir=None):
    """Write `<channel>.reach.json`; refuses a report that names money or an unknown channel."""
    channel = report.get('channel')
    if channel not in CHANNELS:
        raise ValueError('unknown channel')
    leaked = base.money_keys(report) + [name for name in report.get('columns_seen', []) if base.MONEY.search(name)]
    if leaked:
        raise ValueError('a money figure must not be written: ' + ', '.join(leaked))
    directory = Path(out_dir or OUT_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / ('%s.reach.json' % channel)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + '\n', encoding='utf-8')
    tmp.replace(path)
    return path


def list_files(token, get=None):
    """(files newest-per-day, job start day, why not). Files are the API's report dicts."""
    get = get or probe.get
    status, data, why = get(REPORTING + 'jobs', token)
    if status != 200:
        return [], '', 'not granted yet (%s)' % (why or status)
    jobs = [job for job in (data or {}).get('jobs') or []
            if str(job.get('reportTypeId')) == REPORT_TYPE and not job.get('systemManaged')]
    if not jobs:
        return [], '', 'no reach job yet (the reporting-jobs run starts one)'
    job = sorted(jobs, key=lambda item: str(item.get('createTime') or ''))[0]
    newest, page = {}, ''
    for _ in range(MAX_PAGES):
        url = REPORTING + 'jobs/%s/reports?pageSize=100' % urllib.parse.quote(str(job.get('id')), safe='')
        if page:
            url += '&pageToken=' + urllib.parse.quote(page, safe='')
        status, data, why = get(url, token)
        if status != 200:
            return [], '', 'files not listed (%s)' % (why or status)
        for item in (data or {}).get('reports') or []:
            start = str(item.get('startTime') or '')
            if start and str(item.get('createTime') or '') >= str(newest.get(start, {}).get('createTime') or ''):
                newest[start] = item  # YouTube may write a day again; the later file replaces the earlier
        page = str((data or {}).get('nextPageToken') or '')
        if not page:
            break
    files = [newest[start] for start in sorted(newest, reverse=True)][:MAX_FILES]
    return files, iso_day(job.get('createTime')), ''


def read_channel(channel, token, today, previous=None, get=None, fetch=None):
    """(report or None, why not, files that could not be read)."""
    files, since, why = list_files(token, get)
    if why:
        return None, why, []
    if not files:
        return None, 'reach job running since %s, no daily file yet' % (since or 'an unknown date'), []
    rows, failed, columns, read = [], [], [], 0
    for item in files:
        data, why = (fetch or download)(item.get('downloadUrl'), token)
        if data is None:
            failed.append(why)
            continue
        found, header, why = parse(data)
        if why:
            failed.append(why + (' (columns: %s)' % ', '.join(header[:12]) if header else ''))
            continue
        columns = header or columns
        rows += found
        read += 1
    if not read:
        return None, 'no daily file could be read (%s)' % '; '.join(sorted(set(failed)))[:300], failed
    return build(channel, rows, read, today, since, previous, columns), '', failed


def load(out_dir=None):
    """Every readable reach report in the folder, in the registry's channel order."""
    return base.load_reach(out_dir or OUT_DIR)


def headline(report):
    """One plain sentence for the run's annotation."""
    window = report['window']
    if not window['days']:
        return '%d daily file%s read, no row in %s yet' % (
            report['files_read'], '' if report['files_read'] == 1 else 's',
            'it' if report['files_read'] == 1 else 'them')
    text = '%d daily file%s (%s to %s): %s thumbnail impressions on %d video%s' % (
        report['files_read'], '' if report['files_read'] == 1 else 's', window['first_day'], window['last_day'],
        base.count(window['impressions']), window['videos'], '' if window['videos'] == 1 else 's')
    if window['clicks'] is None:
        return text + '; click rate not determined (the file\'s unit could not be settled)'
    return text + ', %s clicks, %s%% click rate' % (base.count(window['clicks']),
                                                   base.amount(window['click_rate_percent'] or 0))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--channel', action='append', help='only this channel (repeatable); default: all')
    parser.add_argument('--out', default=str(OUT_DIR))
    parser.add_argument('--no-write', action='store_true', help='read and report; write no file')
    args = parser.parse_args(argv)
    today = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    wanted = [c for c in (args.channel or list(CHANNELS)) if c in CHANNELS]

    # At most ten annotations of a kind show per step: channels with nothing to
    # read share one line per reason.
    waiting = {}
    for channel in wanted:
        try:
            names = CHANNELS[channel].secret_names()
            token, why = base.access_token(*(os.environ.get(names[key], '').strip()
                                             for key in ('client_id', 'client_secret', 'refresh_token')))
            if not token:
                waiting.setdefault(why, []).append(channel)
                continue
            report, why, failed = read_channel(channel, token, today, load(args.out).get(channel))
            if report is None:
                waiting.setdefault(why, []).append(channel)
                continue
            if not args.no_write:
                write_reach(report, args.out)
            odd = report['window']['clicks'] is None or bool(failed)
            note(channel, '%s; %s%s' % (
                headline(report), 'not written (dry run)' if args.no_write else 'file written',
                '; %d file%s not read (%s)' % (len(failed), '' if len(failed) == 1 else 's',
                                               '; '.join(sorted(set(failed)))[:200]) if failed else ''),
                'warning' if odd else 'notice')
            print('[reach] %s columns: %s; click rate written in the file as: %s%s' % (
                channel, ', '.join(report['columns_seen']) or 'none', report['click_rate_unit_in_file'],
                '; sample rows (impressions, click rate): %s' % report['click_rate_samples_as_written']
                if report['click_rate_samples_as_written'] else ''))
        except Exception as exc:  # noqa: BLE001 - one channel must not cost the others, or the job
            waiting.setdefault('stopped early (%s)' % type(exc).__name__, []).append(channel)
    for why, channels in waiting.items():
        level = 'warning' if 'stopped early' in why or 'could be read' in why or \
            ('refused' in why and 'not granted' not in why) else 'notice'
        note('skipped', '%s: %s; no file written' % (', '.join(channels), why), level)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
