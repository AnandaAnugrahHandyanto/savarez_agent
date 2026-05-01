"""Regression tests for cron post-delivery scripts."""

import importlib
import json
from pathlib import Path

import pytest


@pytest.fixture
def cron_env(tmp_path, monkeypatch):
    hermes_home = tmp_path / '.hermes'
    hermes_home.mkdir()
    (hermes_home / 'cron').mkdir()
    (hermes_home / 'cron' / 'output').mkdir(parents=True, exist_ok=True)
    (hermes_home / 'scripts').mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv('HERMES_HOME', str(hermes_home))

    import cron.jobs as jobs_mod
    import cron.scheduler as scheduler_mod
    import tools.cronjob_tools as cron_tool_mod

    monkeypatch.setattr(jobs_mod, 'HERMES_DIR', hermes_home)
    monkeypatch.setattr(jobs_mod, 'CRON_DIR', hermes_home / 'cron')
    monkeypatch.setattr(jobs_mod, 'JOBS_FILE', hermes_home / 'cron' / 'jobs.json')
    monkeypatch.setattr(jobs_mod, 'OUTPUT_DIR', hermes_home / 'cron' / 'output')

    importlib.reload(scheduler_mod)
    importlib.reload(cron_tool_mod)
    return hermes_home, scheduler_mod, cron_tool_mod


def _job(job_id='job1', post_deliver_script=None):
    return {
        'id': job_id,
        'name': 'demo-job',
        'deliver': 'feishu',
        'schedule': {'kind': 'cron', 'expr': '30 9 * * 1-5', 'display': '30 9 * * 1-5'},
        'schedule_display': '30 9 * * 1-5',
        'repeat': {'times': None, 'completed': 0},
        'enabled': True,
        'state': 'scheduled',
        'origin': {'platform': 'feishu', 'chat_id': 'chat123'},
        'post_deliver_script': post_deliver_script,
    }


def test_tick_runs_post_deliver_script_only_after_success(cron_env, monkeypatch):
    hermes_home, scheduler_mod, _ = cron_env
    script = hermes_home / 'scripts' / 'commit.py'
    script.write_text('print("committed")\n', encoding='utf-8')
    marks = []

    monkeypatch.setattr(scheduler_mod, 'get_due_jobs', lambda: [_job('job-success', 'commit.py')])
    monkeypatch.setattr(scheduler_mod, 'advance_next_run', lambda job_id: True)
    monkeypatch.setattr(scheduler_mod, 'run_job', lambda job: (True, 'output', 'REPORT BODY', None))
    monkeypatch.setattr(scheduler_mod, 'save_job_output', lambda job_id, output: str(hermes_home / 'cron' / 'output' / f'{job_id}.md'))
    monkeypatch.setattr(scheduler_mod, '_deliver_result', lambda job, content, adapters=None, loop=None: None)
    monkeypatch.setattr(scheduler_mod, 'mark_job_run', lambda job_id, success, error=None, delivery_error=None: marks.append((job_id, success, error, delivery_error)))

    executed = scheduler_mod.tick(verbose=False)
    assert executed == 1
    assert marks == [('job-success', True, None, None)]


def test_tick_skips_post_deliver_script_on_delivery_failure(cron_env, monkeypatch):
    hermes_home, scheduler_mod, _ = cron_env
    script = hermes_home / 'scripts' / 'commit.py'
    script.write_text('print("committed")\n', encoding='utf-8')
    marks = []

    monkeypatch.setattr(scheduler_mod, 'get_due_jobs', lambda: [_job('job-fail', 'commit.py')])
    monkeypatch.setattr(scheduler_mod, 'advance_next_run', lambda job_id: True)
    monkeypatch.setattr(scheduler_mod, 'run_job', lambda job: (True, 'output', 'REPORT BODY', None))
    monkeypatch.setattr(scheduler_mod, 'save_job_output', lambda job_id, output: str(hermes_home / 'cron' / 'output' / f'{job_id}.md'))
    monkeypatch.setattr(scheduler_mod, '_deliver_result', lambda job, content, adapters=None, loop=None: 'network timeout')
    monkeypatch.setattr(scheduler_mod, 'mark_job_run', lambda job_id, success, error=None, delivery_error=None: marks.append((job_id, success, error, delivery_error)))

    executed = scheduler_mod.tick(verbose=False)
    assert executed == 1
    assert marks == [('job-fail', True, None, 'network timeout')]


def test_cronjob_tool_accepts_post_deliver_script(cron_env, monkeypatch):
    _, _, cron_tool_mod = cron_env
    monkeypatch.setenv('HERMES_INTERACTIVE', '1')

    result = json.loads(cron_tool_mod.cronjob(
        action='create',
        schedule='every 1h',
        prompt='Monitor things',
        post_deliver_script='commit.py',
    ))
    assert result['success'] is True
    assert result['job']['post_deliver_script'] == 'commit.py'


def test_cronjob_tool_rejects_invalid_post_deliver_script(cron_env, monkeypatch):
    _, _, cron_tool_mod = cron_env
    monkeypatch.setenv('HERMES_INTERACTIVE', '1')

    result = json.loads(cron_tool_mod.cronjob(
        action='create',
        schedule='every 1h',
        prompt='Monitor things',
        post_deliver_script='/tmp/evil.py',
    ))
    assert result['success'] is False
