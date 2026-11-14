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
  this token and this Google Cloud project, and with what refusal if not;
* one verdict line: the grant is complete, or what the owner still has to do;
* whether the @handle the descriptions link to is the channel's handle on YouTube.

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
# Scopes meant for a network (a YouTube Content Manager), not for a channel's own automation.
# Google's channels reference: a token that uses `youtubepartner-channel-audit` "must be revoked
# ... within two weeks of the date that the token was issued", so it does not belong on a token
# that is meant to be minted once. `youtubepartner` does nothing without a Content Manager.
NETWORK_SCOPES = ('youtubepartner', 'youtubepartner-channel-audit')
CODE = re.compile(r'[^A-Za-z0-9_.-]')
# The @handle each channel's descriptions link to (`pipeline/channels.py`; a test keeps the two
# lists equal). A handle is only a guess until YouTube confirms it: The Secret Place's links
# pointed at a name the channel never had, and every one of them opened "404 Not Found".
HANDLES = {
    'secret-place': '@SecretPlaceSanctuary', 'prayer2': '@TheMorningAltarDaily',
    'prayer3': '@TheMiddayWatch', 'prayer4': '@TheMidnightWatchDaily',
    'prayer5': '@TheFamilyAltarDaily', 'prayer6': '@TheHealingBalmDaily',
    'prayer7': '@TheProvisionTableDaily', 'prayer8': '@TheCovenantShieldDaily',
    'prayer9': '@ThePraiseGardenDaily', 'prayer10': '@TheGuidedPathPrayer',
}


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


def network_scopes(have):
    """Scopes on the token that are for a network, not a channel (see NETWORK_SCOPES)."""
    return [scope for scope in NETWORK_SCOPES if scope in set(have)]


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


def answered(status, why, data):
    """Like `verdict`, but for a report: says whether it came back with rows or empty.

    Only the number of rows is shown, never what is in them. An API that answers
    with nothing looks the same as one that works until somebody reads the data.
    """
    if status != 200:
        return verdict(status, why)
    rows = len((data or {}).get('rows') or [])
    return 'works (%d row%s)' % (rows, '' if rows == 1 else 's') if rows else 'works, NO ROWS'


def left_to_grant(scopes, analytics, reporting, long_uploads):
    """What the owner still has to do for this channel, in plain words; empty when the grant is whole.

    `analytics` and `reporting` are (status, refusal) of one plain request to each API.
    """
    left = []
    missing = missing_scopes(scopes)
    if missing:
        left.append('mint a token with: ' + ', '.join(missing))
    for name, (status, why) in (('YouTube Analytics API', analytics), ('YouTube Reporting API', reporting)):
        if status == 200:
            continue
        if 'SERVICE_DISABLED' in why or 'accessNotConfigured' in why:
            left.append('enable the %s in this Google Cloud project' % name)
        elif 'SCOPE_INSUFFICIENT' in why or 'insufficientPermissions' in why:
            if not missing:
                left.append('%s refuses this token on scope' % name)
        else:
            left.append('%s refused (%s)' % (name, why or status))
    if long_uploads == 'eligible':
        left.append('verify a phone number in YouTube Studio')
    elif long_uploads == 'disallowed':
        left.append('YouTube does not allow this channel long videos (standing)')
    return left


def handle_check(channel, custom_url):
    """(matches, sentence): does YouTube's own name for the channel equal the one the links use?

    Handles are not case-sensitive on YouTube, so neither is the comparison.
    """
    live = '@' + CODE.sub('', str(custom_url or ''))[:40]
    linked = HANDLES.get(channel, '')
    if live == '@':
        return False, 'YouTube returned no handle for this channel; links use %s' % (linked or 'nothing')
    if not linked:
        return False, 'YouTube says %s; no handle is registered for this channel' % live
    if live.lower() == linked.lower():
        return True, '%s is the channel\'s handle on YouTube; subscribe links resolve' % live
    return False, ('MISMATCH: YouTube says %s, descriptions link to %s, so those links open '
                   'a 404 page' % (live, linked))


def note(channel, part, text, level='notice'):
    print('::%s title=Permissions %s: %s::%s' % (level, channel, part, text))


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
    note(channel, 'token', 'scopes=[%s]; missing=[%s]; network-only=[%s]; refresh token: %s; project=%s' % (
        ', '.join(scopes) or 'not disclosed', ', '.join(missing_scopes(scopes)) or 'none',
        ', '.join(network_scopes(scopes)) or 'none',
        token_lifetime(token), project_group(os.environ.get('CLIENT_ID'))))

    # ---- what the channel itself is allowed to do (only its owner can change these) ----
    status, data, why = get(DATA + 'channels?part=snippet,status,brandingSettings,contentDetails&mine=true', access)
    facts = []
    uploads = ''
    long_uploads = ''
    if status == 200 and data and data.get('items'):
        item = data['items'][0]
        matches, sentence = handle_check(channel, (item.get('snippet') or {}).get('customUrl'))
        note(channel, 'handle', sentence, 'notice' if matches else 'warning')
        state = item.get('status') or {}
        brand = (item.get('brandingSettings') or {}).get('channel') or {}
        uploads = ((item.get('contentDetails') or {}).get('relatedPlaylists') or {}).get('uploads', '')
        long_uploads = CODE.sub('', str(state.get('longUploadsStatus') or 'unknown'))
        facts.append('videos over 15 min=%s' % long_uploads)
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
        # A per-video report must be sorted by views or watch time and capped (14 Nov: sorting by
        # averageViewPercentage was refused 400 badRequest on a token that could read everything else).
        ('how long they stay, per video',
         'metrics=views,averageViewDuration,averageViewPercentage&dimensions=video&sort=-views&maxResults=5'),
        # Refused 400 on 14 Nov with full access: the Analytics API does not serve these two.
        # They come from the Reporting API's daily reach file (scripts/reporting_jobs.py). Kept
        # here so the day Google starts serving them shows up.
        ('thumbnail impressions (Analytics API)', 'metrics=videoThumbnailImpressions,videoThumbnailImpressionsClickRate'),
        ('revenue', 'metrics=estimatedRevenue'),
    ):
        status, data, why = get(ANALYTICS + '?' + window + '&' + query, access)
        answers.append('%s: %s' % (label, answered(status, why, data)))
        if label == 'views':
            analytics = (status, why)
    # The Partner Program counts watch hours over 365 days, so that window has to answer too.
    year = 'ids=channel==MINE&startDate=%s&endDate=%s' % (today - datetime.timedelta(days=365), today)
    for label, query in (
        ('watch time over 365 days', 'metrics=estimatedMinutesWatched'),
        ('watch time by day', 'metrics=estimatedMinutesWatched&dimensions=day'),
        ('subscribers gained and lost', 'metrics=subscribersGained,subscribersLost'),
        ('watch time per video', 'metrics=estimatedMinutesWatched,views&dimensions=video'
                                 '&sort=-estimatedMinutesWatched&maxResults=5'),
    ):
        status, data, why = get(ANALYTICS + '?' + year + '&' + query, access)
        answers.append('%s: %s' % (label, answered(status, why, data)))
    note(channel, 'analytics api', '; '.join(answers))

    answers = []
    status, data, why = get(REPORTING + 'reportTypes?pageSize=100', access)
    reporting = (status, why)
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

    left = left_to_grant(scopes, analytics, reporting, long_uploads)
    note(channel, 'verdict', 'GRANT COMPLETE' if not left else 'still to do: ' + '; '.join(left))
    note(channel, 'other keys', 'pexels=%s; pixabay=%s; playlist id=%s' % (
        os.environ.get('HAS_PEXELS', '?'), os.environ.get('HAS_PIXABAY', '?'), os.environ.get('HAS_PLAYLIST', '?')))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
