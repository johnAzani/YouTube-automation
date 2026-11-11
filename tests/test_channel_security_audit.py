"""Production credentials and new-channel monitoring must fail closed."""
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import yaml

from pipeline.channels import CHANNELS
from scripts import automation_monitor as monitor

ROOT = Path(__file__).resolve().parents[1]


def test_production_uses_only_the_selected_prefix_for_every_secret():
    workflow = yaml.safe_load((ROOT / '.github/workflows/produce.yml').read_text())
    job = workflow['jobs']['produce']
    env = job['env']
    fields = {'YOUTUBE_CLIENT_ID': 'YOUTUBE_CLIENT_ID', 'YOUTUBE_CLIENT_SECRET': 'YOUTUBE_CLIENT_SECRET',
              'YOUTUBE_REFRESH_TOKEN': 'YOUTUBE_REFRESH_TOKEN', 'YOUTUBE_PLAYLIST_ID': 'YOUTUBE_PLAYLIST_ID',
              'YOUTUBE_EXPECTED_CHANNEL_ID': 'YOUTUBE_CHANNEL_ID', 'GEMINI_API_KEY': 'GEMINI_API_KEY'}
    for field, suffix in fields.items():
        expression = env[field]
        mappings = re.findall(r"fromJSON\('([^']+)'\)\[matrix.channel\]", expression)
        assert mappings and all(json.loads(item) == {cid: p.secret_prefix for cid, p in CHANNELS.items()}
                                for item in mappings)
        assert "format('{0}" + suffix + "'" in expression
        assert not re.search(r'secrets\.[A-Z_]+', expression)
        # Only expected ID can fall back, and only between vars/secrets using the same prefix.
        assert (' || ' in expression) == (field == 'YOUTUBE_EXPECTED_CHANNEL_ID')
    names = [step.get('name') for step in job['steps']]
    assert names.index("Require the selected channel's own credentials") < names.index('Repair the queue before publishing')
    assert names.index('Verify the authenticated channel before production') < names.index('Repair the queue before publishing')
    verify = next(step for step in job['steps'] if step.get('name') == 'Verify the authenticated channel before production')
    assert 'verify_target_channel(youtube)' in verify['run']
    required = next(step for step in job['steps'] if step.get('name') == "Require the selected channel's own credentials")
    assert 'YOUTUBE_EXPECTED_CHANNEL_ID' in required['run']


def test_monitor_reports_channels_with_no_receipts_even_if_another_has_published(tmp_path):
    pub = tmp_path / 'published'
    pub.mkdir()
    (pub / 'one.md').write_text('---\nchannel: secret-place\nyoutube_video_id: abc\npublished_at: 2026-01-01T12:00:00Z\n---\n')
    report = monitor.MonitorReport()
    with mock.patch('pipeline.channels.scheduled_channels', return_value=('secret-place', 'prayer5', 'prayer6')):
        with mock.patch.object(monitor, 'ROOT', tmp_path):
            monitor.check_outcomes(report, now=datetime(2026, 1, 1, 13, tzinfo=timezone.utc),
                                   published_dir=pub, log_path=tmp_path / 'none.json')
    rows = {r['outcome']: r for r in report.outcomes}
    assert rows['last upload (secret-place)']['severity'] == 'ok'
    for cid in ('prayer5', 'prayer6'):
        assert rows[f'last upload ({cid})']['severity'] == 'blocking'
        assert 'no published receipt recorded' in rows[f'last upload ({cid})']['detail']
    assert not report.healthy


def test_diagnostic_workflow_is_read_only_and_independent_for_both_channels():
    workflow = yaml.safe_load((ROOT / '.github/workflows/channel-credential-audit.yml').read_text())
    assert workflow['permissions'] == {}
    job = workflow['jobs']['audit']
    assert job['strategy']['fail-fast'] is False and job['strategy']['matrix']['number'] == [5, 6]
    script = job['steps'][0]['run']
    assert 'channels?part=id&mine=true' in script and 'EXPECTED_CHANNEL' in script
    assert 'upload itself was not tested' in script
    assert 'videos.insert' not in script and 'thumbnails.set' not in script
