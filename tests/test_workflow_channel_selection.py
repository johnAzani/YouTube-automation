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


@pytest.mark.parametrize(('filename', 'step_id'), [
    ('produce.yml', 'plan'), ('gemini_brain.yml', 'plan'),
    ('comments.yml', 'plan'), ('growth-autopilot.yml', 'discover'),
    ('metrics.yml', 'discover'),
])
@pytest.mark.parametrize(('target', 'inactive', 'allowed'), [
    ('prayer8', False, True), ('prayer8', True, False),
    ('prayer9', False, False), ('not-a-channel', False, False),
])
def test_planners_gate_manual_channel(tmp_path, filename, step_id, target, inactive, allowed):
    with open('.github/workflows/' + filename, encoding='utf-8') as f:
        workflow = yaml.safe_load(f)
    run = next(step['run'] for step in workflow['jobs']['plan']['steps'] if step.get('id') == step_id)
    script = run.split("python3 - <<'PY'\n", 1)[1].rsplit('\nPY', 1)[0]
    # Simulate a future existing profile being marked inactive, without
    # altering the registry or any real workflow credentials.
    if inactive:
        script = ("import pipeline.channels as c\n"
                  "orig = c.scheduled_channels\n"
                  "c.scheduled_channels = lambda: tuple(x for x in orig() if x != 'prayer8')\n" + script)
    output = tmp_path / 'out'
    env = {**os.environ, 'EVENT_NAME': 'workflow_dispatch', 'INPUT_CHANNEL': target,
           'GITHUB_OUTPUT': str(output)}
    result = subprocess.run([sys.executable, '-c', script], env=env, capture_output=True, text=True)
    assert (result.returncode == 0) == allowed, result.stdout + result.stderr
    if allowed:
        assert json.loads(output.read_text().strip().split('=', 1)[1]) == [target]
    else:
        assert 'Refusing unknown or inactive' in result.stderr
        assert not output.exists()


@pytest.mark.parametrize(('filename', 'step_id'), [
    ('produce.yml', 'plan'), ('gemini_brain.yml', 'plan'),
    ('comments.yml', 'plan'), ('growth-autopilot.yml', 'discover'),
    ('metrics.yml', 'discover'),
])
def test_schedule_skips_inactive_without_blocking_other_channels(tmp_path, filename, step_id):
    with open('.github/workflows/' + filename, encoding='utf-8') as f:
        workflow = yaml.safe_load(f)
    run = next(step['run'] for step in workflow['jobs']['plan']['steps'] if step.get('id') == step_id)
    script = run.split("python3 - <<'PY'\n", 1)[1].rsplit('\nPY', 1)[0]
    script = ("import pipeline.channels as c\n"
              "orig = c.scheduled_channels\n"
              "c.scheduled_channels = lambda: tuple(x for x in orig() if x != 'prayer8')\n" + script)
    output = tmp_path / 'out'
    env = {**os.environ, 'EVENT_NAME': 'schedule', 'INPUT_CHANNEL': '',
           'GITHUB_OUTPUT': str(output), 'YOUTUBE_REFRESH_TOKEN': 'present'}
    env.update({f'PRAYER{i}_READY': 'true' for i in range(2, 9)})
    env.update({f'PRAYER{i}_YOUTUBE_REFRESH_TOKEN': 'present' for i in range(2, 9)})
    result = subprocess.run([sys.executable, '-c', script], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    channels = json.loads(output.read_text().strip().split('=', 1)[1])
    assert 'prayer8' not in channels
    assert 'secret-place' in channels


def test_brain_manual_both_skips_inactive(tmp_path):
    with open('.github/workflows/gemini_brain.yml', encoding='utf-8') as f:
        workflow = yaml.safe_load(f)
    run = next(step['run'] for step in workflow['jobs']['plan']['steps'] if step.get('id') == 'plan')
    script = run.split("python3 - <<'PY'\n", 1)[1].rsplit('\nPY', 1)[0]
    script = ("import pipeline.channels as c\n"
              "orig = c.scheduled_channels\n"
              "c.scheduled_channels = lambda: tuple(x for x in orig() if x != 'prayer8')\n" + script)
    output = tmp_path / 'out'
    env = {**os.environ, 'EVENT_NAME': 'workflow_dispatch', 'INPUT_CHANNEL': 'both',
           'GITHUB_OUTPUT': str(output), 'PRAYER8_READY': 'true'}
    result = subprocess.run([sys.executable, '-c', script], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    channels = json.loads(output.read_text().strip().split('=', 1)[1])
    assert 'prayer8' not in channels and 'secret-place' in channels


@pytest.mark.parametrize(('filename', 'step_id', 'job'), [
    ('produce.yml', 'plan', 'produce'), ('gemini_brain.yml', 'plan', 'brain-replenish'),
    ('comments.yml', 'plan', 'reply'), ('growth-autopilot.yml', 'discover', 'growth'),
    ('metrics.yml', 'discover', 'snapshot'),
])
def test_empty_plan_never_starts_work(tmp_path, filename, step_id, job):
    with open('.github/workflows/' + filename, encoding='utf-8') as f:
        workflow = yaml.safe_load(f)
    run = next(step['run'] for step in workflow['jobs']['plan']['steps'] if step.get('id') == step_id)
    script = run.split("python3 - <<'PY'\n", 1)[1].rsplit('\nPY', 1)[0]
    script = "import pipeline.channels as c\nc.scheduled_channels = lambda: ()\n" + script
    output = tmp_path / 'out'
    env = {**os.environ, 'EVENT_NAME': 'schedule', 'INPUT_CHANNEL': '',
           'GITHUB_OUTPUT': str(output), 'YOUTUBE_REFRESH_TOKEN': 'present'}
    env.update({f'PRAYER{i}_READY': 'true' for i in range(2, 9)})
    result = subprocess.run([sys.executable, '-c', script], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(output.read_text().strip().split('=', 1)[1]) == []
    assert "needs.plan.outputs.channels != '[]'" in workflow['jobs'][job]['if']
