"""One-off, explicitly approved description replacement; never retries writes."""
import json
import os
from pathlib import Path
import urllib.parse
import urllib.request

VIDEO_ID = 'FNRQnoo_-cU'
OWNER = 'UCxBoxqN7pCUFMxJwZH6CRGQ'
TITLE = 'Pray This Joshua 24:15 Family Prayer Over Your Home | Family Prayer #Shorts'
NOTE = 'This receipt was recovered from an existing YouTube video.'
DESCRIPTIONS = {
    'en': '“As for me and my house, we will serve the LORD.” — Joshua 24:15\n\nJoin us in prayer for peace, kindness, provision, and God’s protection over your family and home.\n\nPray the full Joshua 24:15 family prayer: https://youtu.be/NjhW7YUzhis\n\n#FamilyPrayer #Joshua2415 #PrayerForYourHome',
    'es': '“Pero yo y mi casa serviremos a Jehová.” — Josué 24:15\n\nAcompáñanos en oración por la paz, la bondad, la provisión y la protección de Dios sobre tu familia y tu hogar.\n\nOración completa: https://youtu.be/NjhW7YUzhis',
    'pt': '“Porém eu e a minha casa serviremos ao SENHOR.” — Josué 24:15\n\nJunte-se a nós em oração pela paz, bondade, provisão e proteção de Deus sobre sua família e seu lar.\n\nOração completa: https://youtu.be/NjhW7YUzhis',
}
FIELDS = ('title', 'description', 'tags', 'categoryId', 'defaultLanguage', 'defaultAudioLanguage')


def request(url, *, headers=None, data=None, method=None):
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers or {}, data=data, method=method), timeout=35) as response:
        return json.load(response)


def run():
    configured = os.environ.get('EXPECTED_CHANNEL', '').strip()
    if configured != OWNER:
        raise ValueError('Configured channel is not the independently verified owner')
    token = request('https://oauth2.googleapis.com/token', data=urllib.parse.urlencode({
        'client_id': os.environ['CLIENT_ID'], 'client_secret': os.environ['CLIENT_SECRET'],
        'refresh_token': os.environ['REFRESH_TOKEN'], 'grant_type': 'refresh_token',
    }).encode())['access_token']
    headers = {'Authorization': 'Bearer ' + token}
    channels = request('https://www.googleapis.com/youtube/v3/channels?part=id&mine=true', headers=headers).get('items', [])
    if len(channels) != 1 or channels[0].get('id') != OWNER:
        raise ValueError('Authenticated channel mismatch')
    def read_video():
        items = request('https://www.googleapis.com/youtube/v3/videos?part=snippet,localizations,status&id=' + VIDEO_ID, headers=headers).get('items', [])
        if len(items) != 1 or items[0].get('id') != VIDEO_ID:
            raise ValueError('Video not found uniquely')
        return items[0]
    before = read_video()
    snippet = before.get('snippet', {})
    localizations = before.get('localizations', {})
    if snippet.get('channelId') != OWNER or snippet.get('title') != TITLE or before.get('status', {}).get('privacyStatus') != 'public':
        raise ValueError('Video identity, title or privacy differs from expected')
    if NOTE not in snippet.get('description', '') or any(
        lang not in localizations or NOTE not in localizations[lang].get('description', '')
        for lang in DESCRIPTIONS
    ):
        raise ValueError('Descriptions differ from incident; refusing to overwrite')
    if not snippet.get('categoryId') or not snippet.get('defaultLanguage'):
        raise ValueError('Required snippet fields missing; refusing to overwrite')
    backup = Path('family-short-metadata-before.json')
    backup.write_text(json.dumps({'id': VIDEO_ID, 'snippet': snippet, 'localizations': localizations, 'status': before.get('status', {})}, ensure_ascii=False, indent=2), encoding='utf-8')
    new_snippet = {k: snippet[k] for k in FIELDS if k in snippet}
    new_snippet['description'] = DESCRIPTIONS['en']
    new_locs = {lang: dict(values) for lang, values in localizations.items()}
    for lang, desc in DESCRIPTIONS.items():
        new_locs[lang]['description'] = desc
    payload = {'id': VIDEO_ID, 'snippet': new_snippet, 'localizations': new_locs}
    print('Preflight passed; submitting exactly one description update.', flush=True)
    request('https://www.googleapis.com/youtube/v3/videos?part=snippet%2Clocalizations',
            headers={**headers, 'Content-Type': 'application/json'},
            data=json.dumps(payload, ensure_ascii=False).encode('utf-8'), method='PUT')
    print('Update returned success; checking live metadata.', flush=True)
    after = read_video()
    actual_snippet = after.get('snippet', {})
    if actual_snippet.get('description') != DESCRIPTIONS['en']:
        raise ValueError('Live English description does not match')
    for key in FIELDS:
        if key != 'description' and actual_snippet.get(key) != snippet.get(key):
            raise ValueError('A preserved snippet field differs: ' + key)
    if after.get('localizations', {}) != new_locs:
        raise ValueError('Live localizations differ from the intended result')
    if after.get('status', {}).get('privacyStatus') != before.get('status', {}).get('privacyStatus'):
        raise ValueError('Privacy differs from the prior value')
    if actual_snippet.get('channelId') != OWNER:
        raise ValueError('Owner changed unexpectedly')
    print('::notice title=Approved descriptions verified::The existing public Short has all three approved descriptions; title, tags, category, language, localization titles, other localizations and privacy are unchanged.')


if __name__ == '__main__':
    try:
        run()
    except Exception as exc:
        # Never log credential-bearing requests or responses. A failed write or
        # post-write read is ambiguous: the operator must investigate, not retry.
        print(f'::error title=Description update not verified::{type(exc).__name__}. Do not retry without inspecting the live video.')
        raise SystemExit(1)
