from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from hermes_team import health_probe, task_hook
from hermes_team.approval_store import ApprovalStore
from hermes_team.health_probe import remediate, run_checks
from hermes_team.registry_api import configure_registry_store
from hermes_team.task_store import TaskStore


def _prepare_health_env(tmp_path, monkeypatch):
    monkeypatch.setenv('HERMES_HOME', str(tmp_path))
    state_dir = tmp_path / 'state' / 'team'
    state_dir.mkdir(parents=True, exist_ok=True)
    configure_registry_store(state_dir)
    task_hook._TASK_STORE = TaskStore(state_dir)
    task_hook._APPROVAL_STORE = ApprovalStore(state_dir)
    return state_dir


def test_health_probe_writes_status_snapshot(tmp_path, monkeypatch):
    state_dir = _prepare_health_env(tmp_path, monkeypatch)
    task = task_hook.create_task('health task', 'desc')
    task_hook.bind_mapping(task['id'], job_id='job-health', note='seed', source='pytest', status='scheduled')
    ApprovalStore(state_dir).save([
        {
            'approval_id': 'APR-1',
            'task_id': task['id'],
            'status': 'approved',
            'created_at': '2026-04-17T12:00:00+08:00',
            'scope': {'task_id': task['id']},
        }
    ])
    team_data_root = state_dir / 'legacy-edict'
    team_data_root.mkdir(parents=True, exist_ok=True)
    (team_data_root / 'cron_facts_snapshot.json').write_text(
        json.dumps(
            {
                'generatedAt': datetime.now(timezone(timedelta(hours=8))).isoformat(),
                'summary': {'totalJobs': 1, 'problematicJobs': 0, 'timeouts': 0, 'deliveryFailed': 0},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )

    payload = run_checks()

    assert payload['overall'] == 'ok'
    names = {item['name'] for item in payload['checks']}
    assert {'task_state', 'registry_state', 'approval_state', 'cron_facts_snapshot'} <= names
    assert payload['summary']['okCount'] == 4
    assert payload['globalFindings'] == []
    status_path = team_data_root / 'health_status.json'
    state_path = team_data_root / 'health_probe_state.json'
    assert status_path.exists()
    assert state_path.exists()
    on_disk = json.loads(status_path.read_text(encoding='utf-8'))
    assert on_disk['overall'] == 'ok'
    assert on_disk['plannedRemediations'] == []


def test_health_probe_builds_live_cron_snapshot_from_jobs_json(tmp_path, monkeypatch):
    state_dir = _prepare_health_env(tmp_path, monkeypatch)
    (state_dir / 'tasks.json').write_text(json.dumps([]), encoding='utf-8')
    (state_dir / 'archive.json').write_text(json.dumps([]), encoding='utf-8')
    (state_dir / 'approvals.json').write_text(json.dumps([]), encoding='utf-8')
    (state_dir / 'task_run_session_registry.json').write_text(json.dumps({'tasks': {}}), encoding='utf-8')
    cron_dir = tmp_path / 'cron'
    cron_dir.mkdir(parents=True, exist_ok=True)
    jobs_path = cron_dir / 'jobs.json'
    jobs_path.write_text(
        json.dumps(
            {
                'updated_at': '2026-04-17T09:33:51.805943+08:00',
                'jobs': [
                    {
                        'id': 'job-live-1',
                        'name': 'live-health-job',
                        'enabled': False,
                        'state': 'completed',
                        'schedule_display': '30 9 * * 1-5',
                        'deliver': 'origin',
                        'last_status': 'ok',
                        'last_run_at': '2026-04-17T09:33:51.805739+08:00',
                        'last_error': None,
                        'last_delivery_error': None,
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )

    payload = run_checks()

    cron = next(item for item in payload['checks'] if item['name'] == 'cron_facts_snapshot')
    assert cron['status'] == 'ok'
    assert cron['data']['jobsFile'] == str(jobs_path)
    assert cron['data']['totalJobs'] == 1
    snapshot = json.loads((state_dir / 'legacy-edict' / 'cron_facts_snapshot.json').read_text(encoding='utf-8'))
    assert snapshot['source'] == 'hermes_team.health_probe.live_cron_jobs'
    assert snapshot['jobsFile'] == str(jobs_path)
    assert snapshot['summary']['totalJobs'] == 1


def test_health_probe_missing_snapshot_generates_findings_and_stub_remediation(tmp_path, monkeypatch):
    state_dir = _prepare_health_env(tmp_path, monkeypatch)
    (state_dir / 'tasks.json').write_text(json.dumps([]), encoding='utf-8')
    (state_dir / 'archive.json').write_text(json.dumps([]), encoding='utf-8')
    (state_dir / 'approvals.json').write_text(json.dumps([]), encoding='utf-8')
    (state_dir / 'task_run_session_registry.json').write_text(json.dumps({'tasks': {}}), encoding='utf-8')

    payload = run_checks()

    assert payload['overall'] == 'warn'
    cron = next(item for item in payload['checks'] if item['name'] == 'cron_facts_snapshot')
    assert cron['status'] == 'warn'
    assert cron['findings'][0]['code'] == 'CRON_SNAPSHOT_MISSING'
    assert payload['plannedRemediations'][0]['action'] == 'write_stub_snapshot'

    actions = remediate(payload, apply=True)
    applied = next(item for item in actions if item['action'] == 'write_stub_snapshot')
    assert applied['outcome'] == 'applied'
    snapshot = json.loads((state_dir / 'legacy-edict' / 'cron_facts_snapshot.json').read_text(encoding='utf-8'))
    assert snapshot['stub'] is True

    rescanned = run_checks()
    cron_after = next(item for item in rescanned['checks'] if item['name'] == 'cron_facts_snapshot')
    assert cron_after['status'] == 'warn'
    assert any(finding['code'] == 'CRON_SNAPSHOT_STUB' for finding in cron_after['findings'])
    assert rescanned['remediationHistory'][0]['appliedCount'] >= 1


def test_health_probe_seeds_missing_registry_and_approval_files(tmp_path, monkeypatch):
    state_dir = _prepare_health_env(tmp_path, monkeypatch)
    (state_dir / 'tasks.json').write_text(json.dumps([]), encoding='utf-8')
    (state_dir / 'archive.json').write_text(json.dumps([]), encoding='utf-8')
    registry_path = state_dir / 'task_run_session_registry.json'
    approvals_path = state_dir / 'approvals.json'
    if registry_path.exists():
        registry_path.unlink()
    if approvals_path.exists():
        approvals_path.unlink()

    payload = run_checks()

    registry = next(item for item in payload['checks'] if item['name'] == 'registry_state')
    approvals = next(item for item in payload['checks'] if item['name'] == 'approval_state')
    assert registry['status'] == 'warn'
    assert approvals['status'] == 'warn'
    assert any(action['action'] == 'seed_missing_state_file' and action['code'] == 'REGISTRY_FILE_MISSING' for action in payload['plannedRemediations'])
    assert any(action['action'] == 'seed_missing_state_file' and action['code'] == 'APPROVAL_FILE_MISSING' for action in payload['plannedRemediations'])

    actions = remediate(payload, apply=True)

    seeded_registry = next(item for item in actions if item['code'] == 'REGISTRY_FILE_MISSING')
    seeded_approvals = next(item for item in actions if item['code'] == 'APPROVAL_FILE_MISSING')
    assert seeded_registry['outcome'] == 'applied'
    assert seeded_approvals['outcome'] == 'applied'
    assert json.loads(registry_path.read_text(encoding='utf-8')) == {'tasks': {}}
    assert json.loads(approvals_path.read_text(encoding='utf-8')) == []


def test_health_probe_bridge_audit_reports_warn_on_parity_gap(tmp_path, monkeypatch):
    state_dir = _prepare_health_env(tmp_path, monkeypatch)
    legacy_root = tmp_path / 'legacy-root'
    legacy_edict = legacy_root / 'data' / 'edict'
    legacy_edict.mkdir(parents=True, exist_ok=True)
    (legacy_edict / 'tasks.json').write_text(json.dumps([{'id': 'LEGACY-1'}]), encoding='utf-8')
    (legacy_edict / 'archive.json').write_text(json.dumps([]), encoding='utf-8')
    (legacy_edict / 'task_run_session_registry.json').write_text(json.dumps({'tasks': {'LEGACY-1': {'jobIds': ['job-1']}}}), encoding='utf-8')
    (legacy_root / 'data' / 'approvals').mkdir(parents=True, exist_ok=True)
    (legacy_root / 'data' / 'approvals' / 'approvals.json').write_text(
        json.dumps([{'approval_id': 'APR-L', 'task_id': 'LEGACY-1', 'status': 'approved', 'scope': {'task_id': 'LEGACY-1'}}]),
        encoding='utf-8',
    )
    (state_dir / 'tasks.json').write_text(json.dumps([]), encoding='utf-8')
    (state_dir / 'archive.json').write_text(json.dumps([]), encoding='utf-8')

    payload = run_checks(legacy_root=legacy_root)

    bridge = next(item for item in payload['checks'] if item['name'] == 'bridge_readonly_consistency')
    assert bridge['status'] == 'warn'
    assert bridge['data']['mismatch'] > 0
    assert any(finding['code'] == 'BRIDGE_PARITY_GAP' for finding in bridge['findings'])
    assert payload['overall'] == 'warn'


def test_health_probe_bridge_gap_can_backfill_from_legacy(tmp_path, monkeypatch):
    state_dir = _prepare_health_env(tmp_path, monkeypatch)
    legacy_root = tmp_path / 'legacy-root'
    legacy_edict = legacy_root / 'data' / 'edict'
    legacy_edict.mkdir(parents=True, exist_ok=True)
    (legacy_edict / 'tasks.json').write_text(json.dumps([{'id': 'LEGACY-1', 'state': 'pending'}]), encoding='utf-8')
    (legacy_edict / 'archive.json').write_text(json.dumps([]), encoding='utf-8')
    (legacy_edict / 'task_run_session_registry.json').write_text(json.dumps({'tasks': {'LEGACY-1': {'jobIds': ['job-1']}}}), encoding='utf-8')
    approvals_dir = legacy_root / 'data' / 'approvals'
    approvals_dir.mkdir(parents=True, exist_ok=True)
    (approvals_dir / 'approvals.json').write_text(
        json.dumps([{'approval_id': 'APR-L', 'task_id': 'LEGACY-1', 'status': 'approved', 'scope': {'task_id': 'LEGACY-1'}}]),
        encoding='utf-8',
    )
    (state_dir / 'tasks.json').write_text(json.dumps([]), encoding='utf-8')
    (state_dir / 'archive.json').write_text(json.dumps([]), encoding='utf-8')
    (state_dir / 'approvals.json').write_text(json.dumps([]), encoding='utf-8')
    (state_dir / 'task_run_session_registry.json').write_text(json.dumps({'tasks': {}}), encoding='utf-8')

    payload = run_checks(legacy_root=legacy_root)

    assert any(action['action'] == 'complete_team_state_backfill' for action in payload['plannedRemediations'])
    actions = remediate(payload, apply=True)
    applied = next(item for item in actions if item['action'] == 'complete_team_state_backfill')
    assert applied['outcome'] == 'applied'

    rescanned = run_checks(legacy_root=legacy_root)
    bridge = next(item for item in rescanned['checks'] if item['name'] == 'bridge_readonly_consistency')
    assert bridge['status'] == 'ok'
