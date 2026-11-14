#!/usr/bin/env python3
"""Start the YouTube bulk reports this studio reads, once per channel, and say how many are ready.

Thumbnail impressions and click rate are the one measure the studio cannot get
any other dependable way: YouTube writes them into a daily file (the Reporting
API's "reach" report) and only for a channel that has asked for it. Asking is a
"reporting job". It costs nothing and changes nothing viewers can see. YouTube
starts writing within 48 hours of the job, and keeps each daily file 60 days.

Run by `.github/workflows/reporting-jobs.yml` for every channel. For one channel:

* a channel whose token does not carry the Analytics scopes yet, or whose Cloud
  project has the Reporting API off, is reported and left alone (exit 0), so the
  nine channels still to be granted do not turn the run red;
* a wanted report with no job gets one (the only write this script makes);
* a report that already has a job is never given a second one;
* nothing is deleted, no report is downloaded, no figure is printed.

`--dry-run` lists what would be started and starts nothing.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import permission_probe as probe  # noqa: E402  (same folder; stdlib-only helpers)

REPORTING = probe.REPORTING
#: report type id -> the job name shown in the API. Only reports the studio will read.
WANTED = {
    'channel_reach_basic_a1': 'studio thumbnail impressions and click rate',
}


def note(channel, text, level='notice'):
    print('::%s title=Reporting jobs %s::%s' % (level, channel, text))


def access_token():
    """(access token, refusal). Refusal is Google's code only, never its message."""
    form = urllib.parse.urlencode({
        'client_id': os.environ.get('CLIENT_ID', ''), 'client_secret': os.environ.get('CLIENT_SECRET', ''),
        'refresh_token': os.environ.get('REFRESH_TOKEN', ''), 'grant_type': 'refresh_token',
    }).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token', data=form),
                                    timeout=25) as response:
            return json.load(response).get('access_token', ''), ''
    except urllib.error.HTTPError as exc:
        return '', probe.refusal(exc.code, exc.read())
    except Exception as exc:  # noqa: BLE001
        return '', 'no answer (' + type(exc).__name__ + ')'


def create_job(report_type, name, token):
    """(status, job dict or None, refusal). The one request here that is not a GET."""
    body = json.dumps({'reportTypeId': report_type, 'name': name}).encode()
    request = urllib.request.Request(REPORTING + 'jobs', data=body, method='POST', headers={
        'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            return response.status, json.load(response), ''
    except urllib.error.HTTPError as exc:
        return exc.code, None, probe.refusal(exc.code, exc.read())
    except Exception as exc:  # noqa: BLE001
        return 0, None, 'no answer (' + type(exc).__name__ + ')'


def plan(offered, jobs):
    """(to start, already running, not offered) for WANTED, given what YouTube offers and what exists.

    `offered` is a list of report type ids; `jobs` the API's job dicts. A system-managed
    job (YouTube's own) does not count as ours.
    """
    running = {}
    for job in jobs or []:
        if job.get('systemManaged'):
            continue
        running.setdefault(str(job.get('reportTypeId')), job)
    start, have, absent = [], [], []
    for report_type in WANTED:
        if report_type in running:
            have.append(report_type)
        elif report_type in set(offered or []):
            start.append(report_type)
        else:
            absent.append(report_type)
    return start, have, absent


def day(stamp):
    """'2026-11-14T16:40:02Z' -> '2026-11-14'; anything else -> 'unknown date'."""
    text = str(stamp or '')[:10]
    return text if len(text) == 10 and text[4] == '-' and text[7] == '-' and text.replace('-', '').isdigit() \
        else 'unknown date'


def main(argv=None):
    args = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    args.add_argument('--dry-run', action='store_true')
    args = args.parse_args(argv)
    channel = os.environ.get('CHANNEL', '?')

    token, why = access_token()
    if not token:
        note(channel, 'token refresh REFUSED ' + why + '; nothing started', 'warning')
        return 0
    status, data, why = probe.get(REPORTING + 'reportTypes?pageSize=100', token)
    if status != 200:
        note(channel, 'not granted yet (%s); nothing started' % (why or status))
        return 0
    offered = [str(row.get('id')) for row in (data or {}).get('reportTypes') or []]
    status, data, why = probe.get(REPORTING + 'jobs', token)
    if status != 200:
        note(channel, 'could not list jobs (%s); nothing started' % (why or status), 'warning')
        return 0
    jobs = (data or {}).get('jobs') or []
    start, have, absent = plan(offered, jobs)

    for report_type in absent:
        note(channel, '%s is not offered to this channel' % report_type, 'warning')
    for report_type in start:
        if args.dry_run:
            note(channel, 'would start %s' % report_type)
            continue
        status, job, why = create_job(report_type, WANTED[report_type], token)
        if status == 200 and job:
            note(channel, 'STARTED %s on %s; first daily file within 48 hours' % (
                report_type, day(job.get('createTime'))))
        else:
            note(channel, 'could not start %s (%s)' % (report_type, why or status), 'warning')
    for job in jobs:
        report_type = str(job.get('reportTypeId'))
        if report_type not in have or job.get('systemManaged'):
            continue
        status, data, why = probe.get(REPORTING + 'jobs/%s/reports?pageSize=100' % urllib.parse.quote(
            str(job.get('id'))), token)
        if status == 200:
            reports = (data or {}).get('reports') or []
            newest = max((str(r.get('endTime') or '') for r in reports), default='')
            note(channel, '%s running since %s; %d%s daily file%s ready%s' % (
                report_type, day(job.get('createTime')), len(reports),
                '+' if (data or {}).get('nextPageToken') else '', '' if len(reports) == 1 else 's',
                ', newest up to ' + day(newest) if reports else ''))
        else:
            note(channel, '%s running since %s; files not listed (%s)' % (
                report_type, day(job.get('createTime')), why or status))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
