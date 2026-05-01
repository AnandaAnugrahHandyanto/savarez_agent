from __future__ import annotations

import argparse
import json
import os
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .approval_store import ApprovalStore
from .paths import ensure_team_state_dir, get_hermes_home
from .registry_store import RegistryStore
from .source_bridge import audit_team_state_vs_legacy, backfill_team_state_from_legacy
from .task_store import TaskStore

TZ = timezone(timedelta(hours=8))
CRON_FACTS_STALE_SEC = 5 * 60
MAX_HISTORY = 20


def _now_iso() -> str:
    return datetime.now(TZ).isoformat()


def _team_data_root() -> Path:
    path = ensure_team_state_dir() / 'legacy-edict'
    path.mkdir(parents=True, exist_ok=True)
    return path


def _health_status_path() -> Path:
    return _team_data_root() / 'health_status.json'


def _health_state_path() -> Path:
    return _team_data_root() / 'health_probe_state.json'


def _cron_snapshot_path() -> Path:
    return _team_data_root() / 'cron_facts_snapshot.json'


def _qmt_status_path() -> Path:
    return _team_data_root() / 'qmt_live_check_status.json'


def _atomic_json_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return default


def _default_probe_state() -> dict[str, Any]:
    return {
        'lastScanAt': '',
        'lastRemediationAt': '',
        'scanHistory': [],
        'remediationHistory': [],
    }


def _load_probe_state() -> dict[str, Any]:
    state = _load_json(_health_state_path(), _default_probe_state())
    if not isinstance(state, dict):
        return _default_probe_state()
    merged = _default_probe_state()
    merged.update(state)
    return merged


def _save_probe_state(state: dict[str, Any]) -> None:
    payload = _default_probe_state()
    payload.update(state)
    _atomic_json_write(_health_state_path(), payload)


def _make_finding(
    level: str,
    code: str,
    detail: str,
    recommendation: str,
    *,
    auto_apply_supported: bool = False,
) -> dict[str, Any]:
    return {
        'level': level,
        'code': code,
        'detail': detail,
        'recommendation': recommendation,
        'autoApplySupported': auto_apply_supported,
    }


def _make_check(
    name: str,
    category: str,
    status: str,
    data: dict[str, Any] | None = None,
    error: str | None = None,
    findings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload = {
        'name': name,
        'category': category,
        'status': status,
        'data': data or {},
        'findings': findings or [],
    }
    if error:
        payload['error'] = error
    return payload


def _check_status_counts(results: list[dict[str, Any]]) -> dict[str, int]:
    counts = {'ok': 0, 'warn': 0, 'error': 0}
    for item in results:
        status = str(item.get('status') or '')
        if status in counts:
            counts[status] += 1
    return counts


def _flatten_findings(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for item in results:
        for finding in item.get('findings') or []:
            findings.append(
                {
                    **finding,
                    'check': item.get('name'),
                    'category': item.get('category'),
                    'status': item.get('status'),
                }
            )
    return findings


def _build_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    counts = _check_status_counts(results)
    by_category: dict[str, dict[str, int]] = {}
    for item in results:
        category = str(item.get('category') or 'uncategorized')
        bucket = by_category.setdefault(category, {'total': 0, 'ok': 0, 'warn': 0, 'error': 0})
        bucket['total'] += 1
        status = str(item.get('status') or '')
        if status in {'ok', 'warn', 'error'}:
            bucket[status] += 1
    return {
        'totalChecks': len(results),
        'okCount': counts['ok'],
        'warnCount': counts['warn'],
        'errorCount': counts['error'],
        'findingCount': sum(len(item.get('findings') or []) for item in results),
        'byCategory': by_category,
    }


def _build_environment(legacy_root: Path | None) -> dict[str, Any]:
    return {
        'hermesHome': str(get_hermes_home()),
        'teamStateDir': str(ensure_team_state_dir()),
        'teamDataRoot': str(_team_data_root()),
        'legacyRoot': str(legacy_root) if legacy_root else '',
        'cronSnapshotPath': str(_cron_snapshot_path()),
        'qmtStatusPath': str(_qmt_status_path()),
    }


def _record_scan(payload: dict[str, Any]) -> dict[str, Any]:
    state = _load_probe_state()
    history = state.get('scanHistory') or []
    summary = payload.get('summary') or {}
    history.insert(
        0,
        {
            'scannedAt': payload.get('timestamp') or _now_iso(),
            'overall': payload.get('overall') or 'unknown',
            'okCount': int(summary.get('okCount', 0) or 0),
            'warnCount': int(summary.get('warnCount', 0) or 0),
            'errorCount': int(summary.get('errorCount', 0) or 0),
            'findingCount': int(summary.get('findingCount', 0) or 0),
        },
    )
    state['lastScanAt'] = payload.get('timestamp') or _now_iso()
    state['scanHistory'] = history[:MAX_HISTORY]
    _save_probe_state(state)
    payload['scanHistory'] = state['scanHistory']
    payload['remediationHistory'] = state.get('remediationHistory', [])
    payload['lastRemediationAt'] = state.get('lastRemediationAt', '')
    return payload


def _record_remediation(actions: list[dict[str, Any]]) -> None:
    state = _load_probe_state()
    history = state.get('remediationHistory') or []
    timestamp = _now_iso()
    history.insert(
        0,
        {
            'remediatedAt': timestamp,
            'actionCount': len(actions),
            'appliedCount': sum(1 for item in actions if item.get('outcome') == 'applied'),
            'actions': actions,
        },
    )
    state['lastRemediationAt'] = timestamp
    state['remediationHistory'] = history[:MAX_HISTORY]
    _save_probe_state(state)


def _load_last_report() -> dict[str, Any]:
    report = _load_json(_health_status_path(), {})
    if not isinstance(report, dict):
        report = {}
    results = report.get('checks') if isinstance(report.get('checks'), list) else []
    report['checks'] = results
    report['summary'] = report.get('summary') or _build_summary(results)
    report['globalFindings'] = report.get('globalFindings') or _flatten_findings(results)
    report['environment'] = report.get('environment') or _build_environment(None)
    report['plannedRemediations'] = report.get('plannedRemediations') or plan_remediations(report)
    report.setdefault('overall', 'unknown')
    report.setdefault('timestamp', '')
    report['hermesHome'] = str(get_hermes_home())
    report['teamStateDir'] = str(ensure_team_state_dir())
    state = _load_probe_state()
    report['scanHistory'] = state.get('scanHistory', [])
    report['remediationHistory'] = state.get('remediationHistory', [])
    report['lastRemediationAt'] = state.get('lastRemediationAt', '')
    return report


def check_tasks() -> dict[str, Any]:
    store = TaskStore(ensure_team_state_dir())
    tasks = store.list_tasks()
    archive = store.list_archive()
    blocked = [item['id'] for item in tasks if item.get('state') == 'blocked']
    by_state: dict[str, int] = {}
    for item in tasks:
        state = str(item.get('state') or 'unknown')
        by_state[state] = by_state.get(state, 0) + 1
    findings: list[dict[str, Any]] = []
    status = 'ok'
    if blocked:
        status = 'warn'
        findings.append(
            _make_finding(
                'WARN',
                'TASK_BLOCKED',
                f'Found {len(blocked)} blocked task(s): {", ".join(blocked[:5])}',
                'Unblock or reassign the listed tasks, then rerun the probe.',
            )
        )
    return _make_check(
        'task_state',
        'tasking',
        status,
        {
            'active': len(tasks),
            'archived': len(archive),
            'byState': by_state,
            'blockedIds': blocked,
            'tasksPath': str(store.tasks_path),
            'archivePath': str(store.archive_path),
        },
        findings=findings,
    )


def check_registry() -> dict[str, Any]:
    store = RegistryStore(ensure_team_state_dir())
    registry = store.load()
    tasks = registry.get('tasks') or {}
    scheduled = [task_id for task_id, item in tasks.items() if (item or {}).get('lastStatus') == 'scheduled']
    findings: list[dict[str, Any]] = []
    status = 'ok'
    if not store.path.exists():
        status = 'warn'
        findings.append(
            _make_finding(
                'WARN',
                'REGISTRY_FILE_MISSING',
                f'Registry file missing: {store.path}',
                'Initialize or restore the Hermes team registry before relying on execution mapping state.',
                auto_apply_supported=True,
            )
        )
    return _make_check(
        'registry_state',
        'registry',
        status,
        {
            'tasks': len(tasks),
            'scheduled': len(scheduled),
            'scheduledIds': scheduled[:5],
            'registryPath': str(store.path),
        },
        findings=findings,
    )


def check_approvals() -> dict[str, Any]:
    store = ApprovalStore(ensure_team_state_dir())
    approvals = store.list_approvals()
    pending = []
    for item in approvals:
        status = str(item.get('status') or '').lower()
        if status in {'pending', 'requested'}:
            pending.append(item.get('approval_id') or item.get('approvalId') or 'unknown')
    findings: list[dict[str, Any]] = []
    status = 'warn' if pending else 'ok'
    if pending:
        findings.append(
            _make_finding(
                'WARN',
                'APPROVAL_PENDING',
                f'Found {len(pending)} pending approval(s): {", ".join(pending[:5])}',
                'Resolve or close the pending approvals to clear execution bottlenecks.',
            )
        )
    if not store.path.exists():
        status = 'warn'
        findings.append(
            _make_finding(
                'WARN',
                'APPROVAL_FILE_MISSING',
                f'Approval file missing: {store.path}',
                'Seed Hermes approval state or confirm that no approvals are expected in this environment.',
                auto_apply_supported=True,
            )
        )
    return _make_check(
        'approval_state',
        'approval',
        status,
        {
            'approvals': len(approvals),
            'pendingIds': pending[:5],
            'approvalsPath': str(store.path),
        },
        findings=findings,
    )


def _empty_cron_snapshot(*, stub: bool, reason: str) -> dict[str, Any]:
    return {
        'generatedAt': _now_iso(),
        'summary': {
            'totalJobs': 0,
            'problematicJobs': 0,
            'timeouts': 0,
            'deliveryFailed': 0,
        },
        'stub': stub,
        'reason': reason,
        'source': 'hermes_team.health_probe',
    }


def _cron_jobs_file() -> Path:
    return get_hermes_home() / 'cron' / 'jobs.json'


def _load_cron_jobs_payload() -> dict[str, Any] | None:
    jobs_file = _cron_jobs_file()
    if not jobs_file.exists():
        return None
    try:
        return json.loads(jobs_file.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        try:
            return json.loads(jobs_file.read_text(encoding='utf-8'), strict=False)
        except json.JSONDecodeError:
            return None


def _build_live_cron_snapshot() -> dict[str, Any] | None:
    payload = _load_cron_jobs_payload()
    jobs_file = _cron_jobs_file()
    if payload is None:
        return None
    jobs = payload.get('jobs') or []
    if not isinstance(jobs, list):
        jobs = []

    job_rows = []
    problematic_jobs = 0
    timeout_count = 0
    delivery_failed = 0
    for raw in jobs:
        job = raw if isinstance(raw, dict) else {}
        last_status = str(job.get('last_status') or job.get('lastStatus') or '').lower()
        last_error = str(job.get('last_error') or job.get('lastError') or '')
        last_delivery_error = str(job.get('last_delivery_error') or job.get('lastDeliveryError') or '')
        delivery_failed_flag = bool(last_delivery_error)
        timeout_flag = 'timeout' in last_error.lower() or 'timeout' in last_delivery_error.lower()
        problematic_flag = last_status == 'error' or delivery_failed_flag
        if problematic_flag:
            problematic_jobs += 1
        if timeout_flag:
            timeout_count += 1
        if delivery_failed_flag:
            delivery_failed += 1
        job_rows.append(
            {
                'id': job.get('id'),
                'name': job.get('name'),
                'enabled': bool(job.get('enabled', True)),
                'state': job.get('state'),
                'schedule': job.get('schedule_display') or (job.get('schedule') or {}).get('display'),
                'deliver': job.get('deliver'),
                'lastStatus': job.get('last_status') or job.get('lastStatus'),
                'lastRunAt': job.get('last_run_at') or job.get('lastRunAt'),
                'lastError': last_error or None,
                'lastDeliveryError': last_delivery_error or None,
                'problematic': problematic_flag,
                'timeout': timeout_flag,
                'deliveryFailed': delivery_failed_flag,
            }
        )

    return {
        'generatedAt': _now_iso(),
        'source': 'hermes_team.health_probe.live_cron_jobs',
        'jobsFile': str(jobs_file),
        'jobsUpdatedAt': payload.get('updated_at') or payload.get('updatedAt'),
        'stub': False,
        'summary': {
            'totalJobs': len(job_rows),
            'problematicJobs': problematic_jobs,
            'timeouts': timeout_count,
            'deliveryFailed': delivery_failed,
        },
        'jobs': job_rows,
    }


def check_cron_snapshot() -> dict[str, Any]:
    snapshot_path = _cron_snapshot_path()
    findings: list[dict[str, Any]] = []
    payload = _build_live_cron_snapshot()
    if payload is not None:
        _atomic_json_write(snapshot_path, payload)
    elif snapshot_path.exists():
        try:
            payload = json.loads(snapshot_path.read_text(encoding='utf-8'))
        except json.JSONDecodeError as exc:
            findings.append(
                _make_finding(
                    'ERROR',
                    'CRON_SNAPSHOT_INVALID',
                    f'Cron facts snapshot contains invalid JSON: {exc}',
                    'Repair the snapshot generator or use `--remediate --apply` to replace it with a stub and keep the broken file as backup.',
                    auto_apply_supported=True,
                )
            )
            return _make_check(
                'cron_facts_snapshot',
                'observability',
                'error',
                {
                    'path': str(snapshot_path),
                    'exists': True,
                    'stub': False,
                },
                error=f'invalid json: {exc}',
                findings=findings,
            )
    else:
        findings.append(
            _make_finding(
                'WARN',
                'CRON_SNAPSHOT_MISSING',
                f'Cron facts snapshot is missing and no cron jobs source was found: {snapshot_path}',
                'Ensure HERMES_HOME/cron/jobs.json exists or use `--remediate --apply` to seed a stub snapshot.',
                auto_apply_supported=True,
            )
        )
        return _make_check(
            'cron_facts_snapshot',
            'observability',
            'warn',
            {
                'path': str(snapshot_path),
                'exists': False,
                'jobsFile': str(_cron_jobs_file()),
                'totalJobs': 0,
                'problematicJobs': 0,
                'timeouts': 0,
                'deliveryFailed': 0,
                'stale': True,
                'stub': False,
            },
            error=f'missing: {snapshot_path}',
            findings=findings,
        )

    summary = payload.get('summary') or {}
    generated_at = payload.get('generatedAt')
    age_sec = None
    if generated_at:
        try:
            age_sec = int(max(0, datetime.now(TZ).timestamp() - datetime.fromisoformat(str(generated_at)).timestamp()))
        except ValueError:
            age_sec = None
    stale = age_sec is None or age_sec > CRON_FACTS_STALE_SEC
    problematic = int(summary.get('problematicJobs', 0) or 0)
    timeouts = int(summary.get('timeouts', 0) or 0)
    delivery_failed = int(summary.get('deliveryFailed', 0) or 0)
    stub = bool(payload.get('stub'))
    if stub:
        findings.append(
            _make_finding(
                'WARN',
                'CRON_SNAPSHOT_STUB',
                'Cron facts snapshot is a remediation stub, not a live upstream export.',
                'Replace the stub by rerunning the real cron facts collector.',
            )
        )
    if stale:
        findings.append(
            _make_finding(
                'WARN',
                'CRON_SNAPSHOT_STALE',
                f'Cron facts snapshot is stale (ageSec={age_sec}, budget={CRON_FACTS_STALE_SEC}).',
                'Refresh the snapshot from the upstream cron facts pipeline.',
            )
        )
    if problematic:
        findings.append(
            _make_finding(
                'WARN',
                'CRON_PROBLEMATIC_JOBS',
                f'Cron facts summary reports {problematic} problematic job(s).',
                'Inspect the cron job failures/timeouts and clear the problematic status at the source.',
            )
        )
    if timeouts:
        findings.append(
            _make_finding(
                'WARN',
                'CRON_TIMEOUTS_PRESENT',
                f'Cron facts summary reports {timeouts} timeout(s).',
                'Inspect long-running cron jobs and delivery plumbing for timeout causes.',
            )
        )
    if delivery_failed:
        findings.append(
            _make_finding(
                'WARN',
                'CRON_DELIVERY_FAILED',
                f'Cron facts summary reports {delivery_failed} delivery failure(s).',
                'Investigate post-delivery state submission and channel delivery failures.',
            )
        )
    status = 'warn' if findings else 'ok'
    return _make_check(
        'cron_facts_snapshot',
        'observability',
        status,
        {
            'path': str(snapshot_path),
            'exists': snapshot_path.exists(),
            'jobsFile': str(payload.get('jobsFile') or _cron_jobs_file()),
            'generatedAt': generated_at,
            'ageSec': age_sec,
            'stale': stale,
            'stub': stub,
            'totalJobs': int(summary.get('totalJobs', 0) or 0),
            'problematicJobs': problematic,
            'timeouts': timeouts,
            'deliveryFailed': delivery_failed,
        },
        findings=findings,
    )


def check_qmt() -> dict[str, Any] | None:
    qmt_path = _qmt_status_path()
    if not qmt_path.exists():
        return None
    try:
        payload = json.loads(qmt_path.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        return _make_check(
            'qmt_health',
            'market',
            'error',
            {'path': str(qmt_path), 'exists': True},
            error=f'invalid json: {qmt_path}',
            findings=[
                _make_finding(
                    'ERROR',
                    'QMT_STATUS_INVALID',
                    f'QMT live check payload is invalid JSON: {qmt_path}',
                    'Repair the QMT live check writer so the health probe can trust the snapshot again.',
                )
            ],
        )
    market_ok = bool(payload.get('market_data_ok'))
    trading_ok = bool(payload.get('trading_ok'))
    status = 'ok' if market_ok and trading_ok else 'warn'
    findings: list[dict[str, Any]] = []
    if not market_ok or not trading_ok:
        findings.append(
            _make_finding(
                'WARN',
                'QMT_CHAIN_DOWN',
                f'QMT chain degraded (market={market_ok}, trading={trading_ok}).',
                'Inspect the QMT market/trading bridges and refresh the live check snapshot after recovery.',
            )
        )
    return _make_check(
        'qmt_health',
        'market',
        status,
        {
            'path': str(qmt_path),
            'exists': True,
            'marketChain': 'ok' if market_ok else 'down',
            'tradingChain': 'ok' if trading_ok else 'down',
            'ts': payload.get('ts'),
        },
        findings=findings,
    )


def check_bridge_consistency(legacy_root: Path | None) -> dict[str, Any] | None:
    if legacy_root is None:
        return None
    audit = audit_team_state_vs_legacy(legacy_root)
    mismatch = (
        len(audit['diff']['missingTaskIdsInHermes'])
        + len(audit['diff']['extraTaskIdsInHermes'])
        + len(audit['diff']['missingRegistryTaskIdsInHermes'])
        + len(audit['diff']['extraRegistryTaskIdsInHermes'])
        + len(audit['diff']['missingApprovalTaskIdsInHermes'])
        + len(audit['diff']['extraApprovalTaskIdsInHermes'])
    )
    findings: list[dict[str, Any]] = []
    status = 'ok'
    if mismatch:
        status = 'warn'
        findings.append(
            _make_finding(
                'WARN',
                'BRIDGE_PARITY_GAP',
                f'Read-only legacy parity audit found {mismatch} mismatch item(s).',
                'Complete Hermes bootstrap/backfill or keep the legacy root attached only for audit comparison until parity is restored.',
                auto_apply_supported=True,
            )
        )
    return _make_check(
        'bridge_readonly_consistency',
        'bridge',
        status,
        {
            'checked': len(audit['legacy']['taskIds']),
            'ok': len(audit['legacy']['taskIds']) - len(audit['diff']['missingTaskIdsInHermes']),
            'mismatch': mismatch,
            'sourceOfTruth': str(legacy_root),
            'summary': audit.get('summary') or {},
            'samples': [
                {'taskId': task_id, 'reason': 'missingTaskIdsInHermes'}
                for task_id in audit['diff']['missingTaskIdsInHermes'][:3]
            ],
        },
        findings=findings,
    )


def plan_remediations(payload: dict[str, Any]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in payload.get('checks', []):
        for finding in item.get('findings') or []:
            code = str(finding.get('code') or '')
            action_name = ''
            safe = False
            auto_apply_supported = bool(finding.get('autoApplySupported'))
            if code in {'CRON_SNAPSHOT_MISSING', 'CRON_SNAPSHOT_INVALID'}:
                action_name = 'write_stub_snapshot'
                safe = True
            elif code == 'CRON_SNAPSHOT_STALE':
                action_name = 'refresh_snapshot_from_upstream'
            elif code == 'CRON_PROBLEMATIC_JOBS':
                action_name = 'inspect_problematic_jobs'
            elif code == 'CRON_TIMEOUTS_PRESENT':
                action_name = 'inspect_timeout_jobs'
            elif code == 'CRON_DELIVERY_FAILED':
                action_name = 'inspect_delivery_failures'
            elif code == 'TASK_BLOCKED':
                action_name = 'unblock_or_reassign_tasks'
            elif code == 'APPROVAL_PENDING':
                action_name = 'resolve_pending_approvals'
            elif code == 'QMT_CHAIN_DOWN':
                action_name = 'repair_qmt_bridges'
            elif code == 'BRIDGE_PARITY_GAP':
                action_name = 'complete_team_state_backfill'
                safe = True
            elif code in {'REGISTRY_FILE_MISSING', 'APPROVAL_FILE_MISSING'}:
                action_name = 'seed_missing_state_file'
                safe = True
            if not action_name:
                continue
            dedupe = (str(item.get('name')), code, action_name)
            if dedupe in seen:
                continue
            seen.add(dedupe)
            data = item.get('data') or {}
            action = {
                'check': item.get('name'),
                'category': item.get('category'),
                'code': code,
                'action': action_name,
                'safe': safe,
                'autoApplySupported': auto_apply_supported,
                'path': data.get('path') or data.get('registryPath') or data.get('approvalsPath') or '',
                'detail': finding.get('detail') or '',
                'recommendation': finding.get('recommendation') or '',
                'outcome': 'planned',
            }
            actions.append(action)
    return actions


def remediate(payload: dict[str, Any], apply: bool) -> list[dict[str, Any]]:
    actions = []
    for action in plan_remediations(payload):
        planned = deepcopy(action)
        if not apply:
            actions.append(planned)
            continue
        if not planned.get('autoApplySupported') or not planned.get('safe'):
            planned['outcome'] = 'skipped'
            planned['detail'] = 'Manual-only remediation; auto-apply not supported.'
            actions.append(planned)
            continue
        try:
            if planned['action'] == 'write_stub_snapshot':
                snapshot_path = _cron_snapshot_path()
                if snapshot_path.exists() and planned['code'] == 'CRON_SNAPSHOT_INVALID':
                    backup = snapshot_path.with_name(f"{snapshot_path.stem}.invalid-{datetime.now(TZ).strftime('%Y%m%d-%H%M%S')}{snapshot_path.suffix}")
                    snapshot_path.replace(backup)
                    planned['backupPath'] = str(backup)
                _atomic_json_write(snapshot_path, _empty_cron_snapshot(stub=True, reason=planned['code']))
                planned['path'] = str(snapshot_path)
                planned['detail'] = 'Stub cron snapshot written. Replace it with a live upstream export.'
                planned['outcome'] = 'applied'
            elif planned['action'] == 'seed_missing_state_file':
                state_dir = ensure_team_state_dir()
                if planned['code'] == 'REGISTRY_FILE_MISSING':
                    store = RegistryStore(state_dir)
                    payload = {'tasks': {}}
                    store.save(payload)
                    planned['path'] = str(store.path)
                    planned['detail'] = 'Seeded empty Hermes registry file.'
                elif planned['code'] == 'APPROVAL_FILE_MISSING':
                    store = ApprovalStore(state_dir)
                    payload = []
                    store.save(payload)
                    planned['path'] = str(store.path)
                    planned['detail'] = 'Seeded empty Hermes approval file.'
                else:
                    planned['detail'] = 'Unknown missing state file code.'
                planned['outcome'] = 'applied'
            elif planned['action'] == 'complete_team_state_backfill':
                legacy_root = str((payload.get('environment') or {}).get('legacyRoot') or '').strip()
                if not legacy_root:
                    planned['outcome'] = 'skipped'
                    planned['detail'] = 'Missing legacy root; cannot backfill Hermes state from legacy audit source.'
                else:
                    result = backfill_team_state_from_legacy(Path(legacy_root))
                    planned['path'] = legacy_root
                    planned['detail'] = (
                        'Merged missing legacy state into Hermes '
                        f"(tasks={result.get('tasksAdded', 0)}, archive={result.get('archiveAdded', 0)}, "
                        f"registry={result.get('registryTasksAdded', 0)}, approvals={result.get('approvalsAdded', 0)})."
                    )
                    planned['result'] = result
                    planned['outcome'] = 'applied'
            else:
                planned['outcome'] = 'skipped'
                planned['detail'] = 'No auto-apply handler implemented.'
        except Exception as exc:
            planned['outcome'] = 'failed'
            planned['detail'] = str(exc)
        actions.append(planned)
    if apply:
        _record_remediation(actions)
    return actions


def run_checks(legacy_root: Path | None = None) -> dict[str, Any]:
    results: list[dict[str, Any]] = [
        check_tasks(),
        check_registry(),
        check_approvals(),
        check_cron_snapshot(),
    ]
    bridge = check_bridge_consistency(legacy_root)
    if bridge:
        results.append(bridge)
    qmt = check_qmt()
    if qmt:
        results.append(qmt)

    has_error = any(item.get('status') == 'error' for item in results)
    has_warn = any(item.get('status') == 'warn' for item in results)
    overall = 'error' if has_error else 'warn' if has_warn else 'ok'
    payload = {
        'timestamp': _now_iso(),
        'overall': overall,
        'checks': results,
        'summary': _build_summary(results),
        'environment': _build_environment(legacy_root),
        'globalFindings': _flatten_findings(results),
        'hermesHome': str(get_hermes_home()),
        'teamStateDir': str(ensure_team_state_dir()),
    }
    payload['plannedRemediations'] = plan_remediations(payload)
    _atomic_json_write(_health_status_path(), payload)
    return _record_scan(payload)


def _print_summary(payload: dict[str, Any]) -> None:
    summary = payload.get('summary') or {}
    print('=' * 60)
    print('🧭 Hermes Team · 健康探针')
    print('=' * 60)
    print(
        f"总体: {payload.get('overall', 'unknown')} | checks={summary.get('totalChecks', 0)} | "
        f"ok={summary.get('okCount', 0)} warn={summary.get('warnCount', 0)} error={summary.get('errorCount', 0)}"
    )
    print(f"发现: {summary.get('findingCount', 0)} | HERMES_HOME={payload.get('hermesHome', 'unknown')}")


def _print_checks(payload: dict[str, Any], failures_only: bool = False) -> None:
    for item in payload.get('checks', []):
        if failures_only and item.get('status') == 'ok':
            continue
        icon = {'ok': '✅', 'warn': '⚠️', 'error': '❌'}.get(item.get('status'), '•')
        print(f"{icon} {item.get('name')} [{item.get('category')}]: {item.get('status')}")
        data = item.get('data') or {}
        if item.get('name') == 'task_state':
            print(f"   └─ active={data.get('active', 0)} archived={data.get('archived', 0)} by_state={data.get('byState', {})}")
        elif item.get('name') == 'registry_state':
            print(f"   └─ tasks={data.get('tasks', 0)} scheduled={data.get('scheduled', 0)}")
        elif item.get('name') == 'approval_state':
            print(f"   └─ approvals={data.get('approvals', 0)} pending={data.get('pendingIds', [])}")
        elif item.get('name') == 'cron_facts_snapshot':
            print(
                f"   └─ total={data.get('totalJobs', 0)} problematic={data.get('problematicJobs', 0)} "
                f"timeouts={data.get('timeouts', 0)} delivery_failed={data.get('deliveryFailed', 0)} "
                f"stale={data.get('stale')} stub={data.get('stub')}"
            )
        elif item.get('name') == 'bridge_readonly_consistency':
            print(f"   └─ checked={data.get('checked', 0)} ok={data.get('ok', 0)} mismatch={data.get('mismatch', 0)}")
        elif item.get('name') == 'qmt_health':
            print(
                f"   └─ market={data.get('marketChain', 'unknown')} trading={data.get('tradingChain', 'unknown')} ts={data.get('ts', '')}"
            )
        for finding in item.get('findings') or []:
            print(f"      • {finding.get('level')} {finding.get('code')}: {finding.get('detail')}")
            print(f"        ↳ {finding.get('recommendation')}")
        if item.get('error'):
            print(f"   └─ error: {item['error']}")


def _print_status(payload: dict[str, Any]) -> None:
    _print_summary(payload)
    scans = payload.get('scanHistory') or []
    if scans:
        print('\nRecent scans')
        print('-' * 60)
        for entry in scans[:5]:
            print(
                f"{entry.get('scannedAt', '')[:19]}  overall={entry.get('overall')} "
                f"ok={entry.get('okCount')} warn={entry.get('warnCount')} error={entry.get('errorCount')} findings={entry.get('findingCount')}"
            )
    remediations = payload.get('remediationHistory') or []
    if remediations:
        print('\nRecent remediations')
        print('-' * 60)
        for entry in remediations[:5]:
            print(
                f"{entry.get('remediatedAt', '')[:19]}  actions={entry.get('actionCount')} applied={entry.get('appliedCount')}"
            )


def _print_remediation(actions: list[dict[str, Any]], apply: bool) -> None:
    mode = 'Apply' if apply else 'Dry run'
    print(f"\nRuntime remediation ({mode})")
    print('-' * 60)
    if not actions:
        print('No remediation actions generated.')
        return
    for action in actions:
        print(f"{str(action.get('outcome', 'planned')).upper():8} {action.get('check')}  {action.get('code')}")
        print(f"         action={action.get('action')} safe={action.get('safe')} auto={action.get('autoApplySupported')}")
        if action.get('path'):
            print(f"         path={action.get('path')}")
        if action.get('detail'):
            print(f"         {action.get('detail')}")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Hermes team health probe')
    parser.add_argument('--legacy-root', help='Optional read-only legacy workspace root for parity audit')
    parser.add_argument('--json', action='store_true', help='Print JSON payload')
    parser.add_argument('--status', action='store_true', help='Print status from the latest persisted report')
    parser.add_argument('--findings', action='store_true', help='Print findings only from the latest or fresh report')
    parser.add_argument('--failures', action='store_true', help='Only show WARN / ERROR checks in human output')
    parser.add_argument('--remediate', action='store_true', help='Plan safe remediations from a fresh scan')
    parser.add_argument('--apply', action='store_true', help='Apply supported remediations')
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or [])
    legacy_root = Path(args.legacy_root).expanduser().resolve() if args.legacy_root else None
    env_legacy = os.getenv('HERMES_OPENCLAW_WORKSPACE')
    if legacy_root is None and env_legacy:
        legacy_root = Path(env_legacy).expanduser().resolve()

    if args.status:
        payload = _load_last_report()
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0
        _print_status(payload)
        return 0

    if args.remediate:
        payload = run_checks(legacy_root=legacy_root)
        actions = remediate(payload, apply=args.apply)
        if args.apply:
            payload = run_checks(legacy_root=legacy_root)
        if args.json:
            print(json.dumps({'report': payload, 'actions': actions}, ensure_ascii=False, indent=2))
            return 0
        _print_summary(payload)
        _print_checks(payload, failures_only=args.failures)
        _print_remediation(actions, args.apply)
        return 0

    payload = run_checks(legacy_root=legacy_root)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    if args.findings:
        _print_summary(payload)
        _print_checks(payload, failures_only=True)
        return 0
    _print_summary(payload)
    _print_checks(payload, failures_only=args.failures)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
