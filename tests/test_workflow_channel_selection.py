"""Channel routing must not silently fall back to another channel's secrets."""
import json
import os
import re
import subprocess
import sys

import pytest
import yaml

from pipeline.channels import CHANNELS


@pytest.mark.parametrize(('filename', 'selector', 'keys'), [
    ('comments.yml', 'matrix.channel', ('YOUTUBE_CLIENT_ID', 'YOUTUBE_CLIENT_SECRET', 'YOUTUBE_REFRESH_TOKEN', 'YOUTUBE_EXPECTED_CHANNEL_ID', 'GEMINI_API_KEY')),
    ('gemini_brain.yml', 'matrix.channel', ('GEMINI_API_KEY',)),
    ('growth-autopilot.yml', 'matrix.channel', ('YOUTUBE_CLIENT_ID', 'YOUTUBE_CLIENT_SECRET', 'YOUTUBE_REFRESH_TOKEN')),
    ('metrics.yml', 'matrix.channel', ('YOUTUBE_CLIENT_ID', 'YOUTUBE_CLIENT_SECRET', 'YOUTUBE_REFRESH_TOKEN', 'YOUTUBE_EXPECTED_CHANNEL_ID')),
    ('set-thumbnail.yml', 'inputs.channel', ('YOUTUBE_CLIENT_ID', 'YOUTUBE_CLIENT_SECRET', 'YOUTUBE_REFRESH_TOKEN', 'YOUTUBE_EXPECTED_CHANNEL_ID')),
])
def test_workflow_secrets_use_only_selected_prefix(filename, selector, keys):
    with open('.github/workflows/' + filename, encoding='utf-8') as f:
        workflow = yaml.safe_load(f)
    if filename == 'comments.yml':
        env = next(step['env'] for job in workflow['jobs'].values() for step in job.get('steps', [])
                   if step.get('name') == 'Run Comment Reply Engine')
    elif filename == 'set-thumbnail.yml':
        env = workflow['env']
    else:
        env = next(job['env'] for job in workflow['jobs'].values()
                   if all(key in job.get('env', {}) for key in keys))
    expected = {cid: profile.secret_prefix for cid, profile in CHANNELS.items()}
    for key in keys:
        expr = env[key]
        list_match = re.search(r"contains\(fromJSON\('([^']+)'\), " + re.escape(selector) + r"\)", expr)
        assert list_match and set(json.loads(list_match.group(1))) == set(expected)
        maps = re.findall(r"fromJSON\('({[^']+})'\)\[" + re.escape(selector) + r"\]", expr)
        assert maps and all(json.loads(mapping) == expected for mapping in maps)
        assert expr.endswith("|| '' }}")
        assert not re.search(r'\b(?:secrets|vars)\.', expr), 'no literal fallback to another channel'


@pytest.mark.parametrize(('event', 'variable', 'channel', 'allowed'), [
    ('workflow_dispatch', 'INPUT_CHANNEL', 'prayer8', True),
    ('workflow_dispatch', 'INPUT_CHANNEL', 'prayer9', False),
    ('repository_dispatch', 'CLIENT_CHANNEL', 'prayer9', False),
    ('repository_dispatch', 'CLIENT_CHANNEL', 'not-a-channel', False),
])
def test_produce_plan_rejects_unregistered_targets(tmp_path, event, variable, channel, allowed):
    with open('.github/workflows/produce.yml', encoding='utf-8') as f:
        workflow = yaml.safe_load(f)
    run = next(step['run'] for step in workflow['jobs']['plan']['steps'] if step.get('id') == 'plan')
    script = run.split("python3 - <<'PY'\n", 1)[1].rsplit('\nPY', 1)[0]
    output = tmp_path / 'output'
    env = {**os.environ, 'EVENT_NAME': event, variable: channel, 'GITHUB_OUTPUT': str(output)}
    result = subprocess.run([sys.executable, '-c', script], env=env, capture_output=True, text=True)
    assert (result.returncode == 0) == allowed, result.stdout + result.stderr
    if allowed:
        assert json.loads(output.read_text().strip().split('=', 1)[1]) == [channel]
    else:
        assert 'Refusing unknown or inactive' in result.stderr
        assert not output.exists()
