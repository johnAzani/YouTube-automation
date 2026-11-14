#!/usr/bin/env python3
"""What can this channel's credentials do today? Read-only.

Run by `.github/workflows/channel-credential-audit.yml` (the step body there is
this file, word for word, so the job needs no checkout and no repository
permission). For one channel it reports, as annotations on the run:

* the scopes the stored refresh token carries, and whether Google reports a
  time limit on it (a consent screen left in "Testing" ends every token after
  seven days);
* what the channel is allowed to do on YouTube that only its owner can switch
  on (videos over fifteen minutes, live streaming);
* whether the YouTube Analytics API and the YouTube Reporting API answer for
  this token and this Google Cloud project, and with what refusal if not.

Rules it keeps:

* Only GET requests, apart from the token refresh itself. Nothing on YouTube is
  created, changed or deleted.
* No secret, token, channel statistic or analytics figure is printed. Refusals
  are reported by Google's own reason codes only, never by message text.
* It never fails the job: it is a report, and the step above it is the check.
"""
import datetime
import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

SCOPE_PREFIX = 'https://www.googleapis.com/auth/'
DATA = 'https://www.googleapis.com/youtube/v3/'
ANALYTICS = 'https://youtubeanalytics.googleapis.com/v2/reports'
REPORTING = 'https://youtubereporting.googleapis.com/v1/'
# Everything the automation could use on a channel it does not yet monetise.
WANTED_SCOPES = ('youtube', 'youtube.force-ssl', 'youtube.upload', 'youtube.readonly',
                 'yt-analytics.readonly', 'yt-analytics-monetary.readonly')
CODE = re.compile(r'[^A-Za-z0-9_.-]')


def short_scopes(scope_field):
    """'https://www.googleapis.com/auth/youtube.upload ...' -> ['youtube.upload', ...], sorted."""
    names = []
    for scope in str(scope_field or '').split():
        names.append(scope[len(SCOPE_PREFIX):] if scope.startswith(SCOPE_PREFIX) else scope.rsplit('/', 1)[-1])
    return sorted(set(names))


def missing_scopes(have):
    """Wanted scopes the token does not carry. `youtube` and `youtube.force-ssl` cover the narrower two."""
    have = set(have)
    broad = bool(have & {'youtube', 'youtube.force-ssl'})
    missing = []
    for scope in WANTED_SCOPES:
        if scope in have:
            continue
        if scope in ('youtube.upload', 'youtube.readonly') and broad:
            continue
        if scope == 'youtube' and 'youtube.force-ssl' in have:
            continue
        if scope == 'yt-analytics.readonly' and 'yt-analytics-monetary.readonly' in have:
            continue
        missing.append(scope)
    return missing


def token_lifetime(token):
    """Google adds `refresh_token_expires_in` (seconds) only when the refresh token has an end date."""
    seconds = token.get('refresh_token_expires_in')
    if seconds in (None, ''):
        return 'no end date reported'
    try:
        return 'ENDS in %.1f days' % (float(seconds) / 86400)
    except (TypeError, ValueError):
        return 'end date unreadable'


def project_group(client_id):
    """A short fingerprint of the Google Cloud project behind an OAuth client (its number, hashed).

    Channels that show the same fingerprint share one project and so one daily quota.
    """
    number = str(client_id or '').split('-', 1)[0].strip()
    return hashlib.sha256(number.encode()).hexdigest()[:6] if number else 'none'


def refusal(status, body):
    """'403 PERMISSION_DENIED accessNotConfigured SERVICE_DISABLED' from a Google error body: codes only."""
    parts = [str(status)]
    try:
        error = json.loads(body or b'{}').get('error')
    except (ValueError, AttributeError):
        error = None
    if isinstance(error, str):          # the OAuth token endpoint: {"error": "invalid_grant"}
        parts.append(error)
    elif isinstance(error, dict):
        if error.get('status'):
            parts.append(str(error['status']))
        for item in (error.get('errors') or [])[:1]:
            if isinstance(item, dict) and item.get('reason'):
                parts.append(str(item['reason']))
        for item in error.get('details') or []:
            if isinstance(item, dict) and item.get('reason'):
                parts.append(str(item['reason']))
    seen, clean = set(), []
    for part in parts:
        part = CODE.sub('', part)[:60]
        if part and part not in seen:
            seen.add(part)
            clean.append(part)
    return ' '.join(clean)


def get(url, access_token):
    """(status, parsed JSON or None, refusal text). Never raises, never returns message text."""
    request = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + access_token})
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            return response.status, json.load(response), ''
    except urllib.error.HTTPError as exc:
        return exc.code, None, refusal(exc.code, exc.read())
    except Exception as exc:  # noqa: BLE001 - a report, not a check
        return 0, None, 'no answer (' + type(exc).__name__ + ')'


def verdict(status, why):
    return 'works' if status == 200 else 'REFUSED ' + (why or str(status))


def note(channel, part, text):
    print('::notice title=Permissions %s: %s::%s' % (channel, part, text))


def main():
    channel = os.environ.get('CHANNEL', '?')
    try:
        form = urllib.parse.urlencode({
            'client_id': os.environ.get('CLIENT_ID', ''), 'client_secret': os.environ.get('CLIENT_SECRET', ''),
            'refresh_token': os.environ.get('REFRESH_TOKEN', ''), 'grant_type': 'refresh_token',
        }).encode()
        with urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token', data=form),
                                    timeout=25) as response:
            token = json.load(response)
    except urllib.error.HTTPError as exc:
        note(channel, 'token', 'refresh REFUSED ' + refusal(exc.code, exc.read()))
        return 0
    except Exception as exc:  # noqa: BLE001
        note(channel, 'token', 'refresh got no answer (' + type(exc).__name__ + ')')
        return 0
    access = token.get('access_token', '')
    scopes = short_scopes(token.get('scope'))
    note(channel, 'token', 'scopes=[%s]; missing=[%s]; refresh token: %s; project=%s' % (
        ', '.join(scopes) or 'not disclosed', ', '.join(missing_scopes(scopes)) or 'none',
        token_lifetime(token), project_group(os.environ.get('CLIENT_ID'))))

    # ---- what the channel itself is allowed to do (only its owner can change these) ----
    status, data, why = get(DATA + 'channels?part=status,brandingSettings,contentDetails&mine=true', access)
    facts = []
    uploads = ''
    if status == 200 and data and data.get('items'):
        item = data['items'][0]
        state = item.get('status') or {}
        brand = (item.get('brandingSettings') or {}).get('channel') or {}
        uploads = ((item.get('contentDetails') or {}).get('relatedPlaylists') or {}).get('uploads', '')
        facts.append('videos over 15 min=%s' % CODE.sub('', str(state.get('longUploadsStatus') or 'unknown')))
        facts.append('country=%s' % (CODE.sub('', str(brand.get('country') or ''))[:4] or 'NOT SET'))
        facts.append('keywords=%s' % ('set' if brand.get('keywords') else 'empty'))
        facts.append('trailer=%s' % ('set' if brand.get('unsubscribedTrailer') else 'none'))
    else:
        facts.append('channel lookup %s' % verdict(status, why))
    status, data, why = get(DATA + 'liveBroadcasts?part=id&mine=true&maxResults=1', access)
    facts.append('live streaming=%s' % ('enabled' if status == 200 else 'NOT enabled (%s)' % why))
    status, data, why = get(DATA + 'channelSections?part=id&mine=true', access)
    facts.append('home shelves=%s' % (len((data or {}).get('items') or []) if status == 200 else verdict(status, why)))
    status, data, why = get(DATA + 'playlists?part=id&mine=true&maxResults=50', access)
    facts.append('playlists=%s' % (len((data or {}).get('items') or []) if status == 200 else verdict(status, why)))
    latest = ''
    if uploads:
        status, data, why = get(DATA + 'playlistItems?part=contentDetails&maxResults=1&playlistId='
                                + urllib.parse.quote(uploads), access)
        if status == 200 and (data or {}).get('items'):
            latest = data['items'][0]['contentDetails'].get('videoId', '')
    if latest:
        status, data, why = get(DATA + 'captions?part=id&videoId=' + urllib.parse.quote(latest), access)
        facts.append('caption tracks on newest upload=%s' % (
            len((data or {}).get('items') or []) if status == 200 else verdict(status, why)))
    note(channel, 'channel', '; '.join(facts))

    # ---- measurement: does YouTube Analytics answer for this token and this project? ----
    today = datetime.date.today()
    window = 'ids=channel==MINE&startDate=%s&endDate=%s' % (today - datetime.timedelta(days=28), today)
    answers = []
    for label, query in (
        ('views', 'metrics=views'),
        ('watch time by Shorts/long-form/live', 'metrics=estimatedMinutesWatched&dimensions=creatorContentType'),
        ('where viewers come from', 'metrics=views&dimensions=insightTrafficSourceType'),
        ('how long they stay, per video', 'metrics=averageViewPercentage&dimensions=video&sort=-averageViewPercentage&maxResults=1'),
        ('thumbnail impressions and click rate', 'metrics=videoThumbnailImpressions,videoThumbnailImpressionsClickRate'),
        ('revenue', 'metrics=estimatedRevenue'),
    ):
        status, _data, why = get(ANALYTICS + '?' + window + '&' + query, access)
        answers.append('%s: %s' % (label, verdict(status, why)))
    note(channel, 'analytics api', '; '.join(answers))

    answers = []
    status, data, why = get(REPORTING + 'reportTypes?pageSize=100', access)
    if status == 200:
        ids = [str(row.get('id')) for row in (data or {}).get('reportTypes') or []]
        answers.append('report types: works (%d offered; reach report %s)' % (
            len(ids), 'offered' if 'channel_reach_basic_a1' in ids else 'not offered'))
    else:
        answers.append('report types: ' + verdict(status, why))
    status, data, why = get(REPORTING + 'jobs', access)
    answers.append('report jobs: %s' % (
        '%d running' % len((data or {}).get('jobs') or []) if status == 200 else verdict(status, why)))
    note(channel, 'reporting api', '; '.join(answers))

    note(channel, 'other keys', 'pexels=%s; pixabay=%s; playlist id=%s' % (
        os.environ.get('HAS_PEXELS', '?'), os.environ.get('HAS_PIXABAY', '?'), os.environ.get('HAS_PLAYLIST', '?')))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
