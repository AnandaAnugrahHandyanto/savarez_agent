import importlib
import json
import sys
from pathlib import Path

import pytest


@pytest.fixture
def cron_env(tmp_path, monkeypatch):
    hermes_home = tmp_path / '.hermes'
    hermes_home.mkdir()
    (hermes_home / 'cron').mkdir()
    (hermes_home / 'cron' / 'output').mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv('HERMES_HOME', str(hermes_home))

    import cron.jobs as jobs_mod
    import cron.scheduler as scheduler_mod

    monkeypatch.setattr(jobs_mod, 'HERMES_DIR', hermes_home)
    monkeypatch.setattr(jobs_mod, 'CRON_DIR', hermes_home / 'cron')
    monkeypatch.setattr(jobs_mod, 'JOBS_FILE', hermes_home / 'cron' / 'jobs.json')
    monkeypatch.setattr(jobs_mod, 'OUTPUT_DIR', hermes_home / 'cron' / 'output')

    importlib.reload(scheduler_mod)
    return hermes_home, scheduler_mod


def _job(job_id='job1'):
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
    }


def test_delivery_success_commits_state(cron_env, monkeypatch):
    hermes_home, scheduler_mod = cron_env
    commit_calls = []

    monkeypatch.setattr(scheduler_mod, 'get_due_jobs', lambda: [_job('job-success')])
    monkeypatch.setattr(scheduler_mod, 'advance_next_run', lambda job_id: True)
    monkeypatch.setattr(scheduler_mod, 'run_job', lambda job: (True, 'output', 'REPORT BODY', None))
    monkeypatch.setattr(scheduler_mod, 'save_job_output', lambda job_id, output: str(hermes_home / 'cron' / 'output' / f'{job_id}.md'))
    monkeypatch.setattr(scheduler_mod, '_deliver_result', lambda job, content, adapters=None, loop=None: None)
    monkeypatch.setattr(scheduler_mod, 'mark_job_run', lambda job_id, success, error=None, delivery_error=None: None)

    def fake_terminal(command: str, timeout=None, workdir=None):
        commit_calls.append(command)
        return {'output': 'STATE_COMMITTED=1', 'exit_code': 0}

    monkeypatch.setattr(scheduler_mod, '_commit_qmt_daily_report_state', lambda: (True, None))
    executed = scheduler_mod.tick(verbose=False)
    assert executed == 1


def test_delivery_failure_does_not_commit_state(cron_env, monkeypatch):
    hermes_home, scheduler_mod = cron_env
    marks = []

    monkeypatch.setattr(scheduler_mod, 'get_due_jobs', lambda: [_job('job-fail')])
    monkeypatch.setattr(scheduler_mod, 'advance_next_run', lambda job_id: True)
    monkeypatch.setattr(scheduler_mod, 'run_job', lambda job: (True, 'output', 'REPORT BODY', None))
    monkeypatch.setattr(scheduler_mod, 'save_job_output', lambda job_id, output: str(hermes_home / 'cron' / 'output' / f'{job_id}.md'))
    monkeypatch.setattr(scheduler_mod, '_deliver_result', lambda job, content, adapters=None, loop=None: 'network timeout')
    monkeypatch.setattr(scheduler_mod, '_commit_qmt_daily_report_state', lambda: (_ for _ in ()).throw(AssertionError('should not commit on delivery failure')))
    monkeypatch.setattr(scheduler_mod, 'mark_job_run', lambda job_id, success, error=None, delivery_error=None: marks.append((job_id, success, error, delivery_error)))

    executed = scheduler_mod.tick(verbose=False)
    assert executed == 1
    assert marks == [('job-fail', True, None, 'network timeout')]


def test_run_post_deliver_script_uses_repo_root_cwd(cron_env):
    hermes_home, scheduler_mod = cron_env
    scripts_dir = hermes_home / 'scripts'
    scripts_dir.mkdir(parents=True, exist_ok=True)
    script = scripts_dir / 'cwd_probe.py'
    script.write_text(
        "from pathlib import Path\n"
        "print(Path.cwd())\n",
        encoding='utf-8',
    )

    ok, output = scheduler_mod._run_post_deliver_script('cwd_probe.py')

    assert ok is True
    assert output == str(Path(scheduler_mod.__file__).resolve().parents[1])
