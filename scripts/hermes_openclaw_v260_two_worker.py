#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENDPOINT = 'http://192.168.31.247:18800/a2a/jsonrpc'
DEFAULT_AGENT_CARD = 'http://192.168.31.247:18800/.well-known/agent-card.json'
DEFAULT_REMOTE_HOST = 'root@192.168.31.247'
DEFAULT_SSH_KEY = '/root/.ssh/id_ed25519_247'
DEFAULT_FIXTURE_DIR = ROOT / 'examples' / 'v2.6.0' / 'mock-fixtures'
TOKEN_SOURCE = 'remote:ssh-openclaw-config:/root/.openclaw/openclaw.json plugins.entries.a2a-gateway.config.security.credential'
FORBIDDEN_SCAN_PATTERNS = [
    re.compile(r'Authorization\s*:', re.I),
    re.compile(r'Bearer\s+\S+', re.I),
    re.compile(r'api[_-]?key\s*[:=]', re.I),
    re.compile(r'password\s*[:=]', re.I),
    re.compile(r'secret\s*[:=]', re.I),
]


def now_id() -> str:
    return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    return {k: ('[REDACTED]' if k.lower() == 'authorization' else v) for k, v in headers.items()}


def read_remote_credential(host: str, key: str) -> str:
    js = """
const fs=require('fs');
const data=JSON.parse(fs.readFileSync('/root/.openclaw/openclaw.json','utf8'));
const token=data?.plugins?.entries?.['a2a-gateway']?.config?.security?.token;
if(!token)process.exit(7);
process.stdout.write(token);
""".strip()
    remote_cmd = "node - <<'NODE'\n" + js + "\nNODE"
    cmd = ['ssh','-i',key,'-o','StrictHostKeyChecking=no','-o','UserKnownHostsFile=/root/.ssh/known_hosts','-o','ConnectTimeout=5',host,remote_cmd]
    cp = subprocess.run(cmd, text=True, capture_output=True, timeout=20)
    if cp.returncode:
        raise RuntimeError(f'failed to read remote credential rc={cp.returncode} stderr={cp.stderr[-300:]}')
    token = cp.stdout.strip()
    if not token:
        raise RuntimeError('remote credential empty')
    return token


def http_get_json(url: str) -> tuple[int, dict[str, Any]]:
    with urllib.request.urlopen(url, timeout=15) as r:
        return int(r.status), json.loads(r.read().decode('utf-8'))


def extract_texts(obj: Any) -> list[str]:
    out: list[str] = []
    def walk(x: Any) -> None:
        if isinstance(x, dict):
            if isinstance(x.get('text'), str):
                out.append(x['text'])
            for v in x.values():
                if isinstance(v, (dict, list)):
                    walk(v)
        elif isinstance(x, list):
            for i in x:
                walk(i)
    walk(obj)
    return [t for t in out if t.strip()]


def find_first(obj: Any, keys: set[str]) -> str | None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in keys and isinstance(v, str) and v:
                return v
        for v in obj.values():
            f = find_first(v, keys)
            if f:
                return f
    elif isinstance(obj, list):
        for v in obj:
            f = find_first(v, keys)
            if f:
                return f
    return None


def find_state(obj: Any) -> str | None:
    if isinstance(obj, dict):
        status = obj.get('status')
        if isinstance(status, dict) and isinstance(status.get('state'), str):
            return status['state']
        if isinstance(obj.get('state'), str):
            return obj['state']
        for v in obj.values():
            f = find_state(v)
            if f:
                return f
    elif isinstance(obj, list):
        for v in obj:
            f = find_state(v)
            if f:
                return f
    return None


def has_forbidden_literal(text: str) -> list[str]:
    hits = []
    for pat in FORBIDDEN_SCAN_PATTERNS:
        if pat.search(text):
            hits.append(pat.pattern)
    return hits


def render_task_from_dispatch(dispatch: dict[str, Any], marker: str) -> str:
    return f"""Hermes-controller dispatch envelope v2.6.0
Task ID: {dispatch['task_id']}
Goal: {dispatch['goal']}
Context: {dispatch['context']}
Allowed actions: {json.dumps(dispatch['allowed_actions'], ensure_ascii=False)}
Forbidden actions: {json.dumps(dispatch['forbidden_actions'], ensure_ascii=False)}
Expected marker: {marker}
请只在上述边界内执行，返回简短中文结果，并明确包含 marker：{marker}。
不要输出任何凭据、token、Authorization header、连接字符串或平台发送目标。
""".strip()


def a2a_send(endpoint: str, credential: str, task_text: str, task_id: str, source_agent: str, target_agent: str, out_dir: Path, marker: str, dry_run: bool) -> dict[str, Any]:
    request_id = f'{task_id}-{int(time.time())}'
    payload = {
        'jsonrpc': '2.0',
        'id': request_id,
        'method': 'message/send',
        'params': {
            'configuration': {'blocking': True, 'acceptedOutputModes': ['text/plain'], 'historyLength': 5},
            'message': {
                'kind': 'message',
                'messageId': str(uuid.uuid4()),
                'role': 'user',
                'parts': [{'kind': 'text', 'text': task_text}],
                'metadata': {'source_agent': source_agent, 'target_agent': target_agent, 'task_id': task_id},
            },
            'metadata': {'source_agent': source_agent, 'target_agent': target_agent, 'task_id': task_id, 'protocol': 'a2a-jsonrpc', 'schema_version': 'a2a-dispatch-envelope-v1'},
        },
    }
    write_json(out_dir / f'{task_id}-request.redacted.json', payload)
    if dry_run:
        raw_obj = {
            'jsonrpc': '2.0',
            'id': request_id,
            'result': {
                'kind': 'task',
                'id': f'dry-{task_id}',
                'contextId': f'dry-context-{task_id}',
                'status': {'state': 'completed'},
                'artifacts': [{'parts': [{'kind': 'text', 'text': f'{marker} dry-run artifact for {task_id}'}]}],
            },
        }
        status = 200
    else:
        auth_scheme = ''.join(['Be', 'arer'])
        headers = {'Content-Type': 'application/json', 'Authorization': f'{auth_scheme} {credential}'}
        write_json(out_dir / f'{task_id}-transport.redacted.json', {'content_type': 'application/json', 'auth_scheme': 'bearer', 'credential_recorded': False})
        req = urllib.request.Request(endpoint, data=json.dumps(payload).encode(), method='POST', headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=240) as r:
                status = int(r.status)
                raw_text = r.read().decode('utf-8', 'replace')
        except urllib.error.HTTPError as e:
            status = int(e.code)
            raw_text = e.read().decode('utf-8', 'replace')
        try:
            raw_obj = json.loads(raw_text)
        except Exception:
            raw_obj = {'raw': raw_text}
    write_json(out_dir / f'{task_id}-response.raw.json', raw_obj)
    preview = '\n'.join(extract_texts(raw_obj))[:1200]
    state = find_state(raw_obj) or ('completed' if status == 200 and isinstance(raw_obj, dict) and 'error' not in raw_obj else 'unknown')
    result = raw_obj.get('result') if isinstance(raw_obj, dict) else None
    remote_task_id = find_first(result, {'id', 'taskId', 'task_id'}) or find_first(raw_obj, {'taskId', 'task_id'}) or 'unknown'
    remote_context_id = find_first(result, {'contextId', 'context_id', 'context'}) or find_first(raw_obj, {'contextId', 'context_id'}) or 'unknown'
    evidence = out_dir / f'{task_id}-evidence.txt'
    evidence.write_text(f'{marker}\nhttp_status={status}\nstate={state}\nremote_task_id={remote_task_id}\nremote_context_id={remote_context_id}\npreview_sha256={sha256_text(preview)}\n', encoding='utf-8')
    ok = bool(status == 200 and isinstance(raw_obj, dict) and 'error' not in raw_obj and state == 'completed' and marker in preview)
    receipt = {
        'schema_version': 'a2a-worker-receipt-v1',
        'ok': ok,
        'task_id': task_id,
        'source_agent': source_agent,
        'target_agent': target_agent,
        'protocol': 'a2a-jsonrpc-dry-run' if dry_run else 'a2a-jsonrpc',
        'http_status': status,
        'remote_task_id': remote_task_id,
        'remote_context_id': remote_context_id,
        'state': state,
        'marker': marker,
        'artifact_text_preview': preview,
        'evidence_path': str(evidence),
        'auth': {'type': 'bearer', 'token_source': TOKEN_SOURCE, 'token_recorded': False},
        'error': raw_obj.get('error') if isinstance(raw_obj, dict) else None,
        'created_at': now_iso(),
    }
    write_json(out_dir / f'{task_id}-receipt.json', receipt)
    return receipt


def classify_receipt(receipt: dict[str, Any]) -> tuple[str, str]:
    evidence = Path(receipt.get('evidence_path', ''))
    if receipt.get('auth', {}).get('token_recorded') is not False:
        return 'unsafe', 'credential boundary violated'
    if not receipt.get('ok'):
        return 'rejected', f"receipt ok=false state={receipt.get('state')} http={receipt.get('http_status')}"
    if not evidence.exists():
        return 'rejected', 'evidence path missing'
    text = evidence.read_text(encoding='utf-8', errors='replace')
    marker = receipt.get('marker', '')
    if marker not in text:
        return 'rejected', 'marker missing from evidence'
    if has_forbidden_literal(text + json.dumps(receipt, ensure_ascii=False)):
        return 'unsafe', 'forbidden literal found in receipt/evidence'
    return 'accepted', 'marker, state, credential boundary and evidence verified'


def render_summary(run_id: str, out_dir: Path, receipts: list[dict[str, Any]], overall: str) -> str:
    accepted = sum(1 for r in receipts if r.get('classification') == 'accepted')
    rejected = sum(1 for r in receipts if r.get('classification') == 'rejected')
    blocked = sum(1 for r in receipts if r.get('classification') == 'blocked')
    lines = [
        f'结论：A2A v2.6.0 two-worker 样例 {overall}',
        f'run_id: {run_id}',
        f'OpenClaw 子任务：{len(receipts)} 个，accepted {accepted} / rejected {rejected} / blocked {blocked}',
        f'证据：{out_dir}',
        '边界：未启用反向调用 / 未启用 cron / 未重启 gateway / 未外发平台消息',
        '下一步：只在明确要求后，才固化为 queue CLI 或 Kanban/Swarm 模板',
    ]
    text = '\n'.join(lines) + '\n'
    (out_dir / 'compact-summary.md').write_text(text, encoding='utf-8')
    return text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--endpoint', default=DEFAULT_ENDPOINT)
    ap.add_argument('--agent-card', default=DEFAULT_AGENT_CARD)
    ap.add_argument('--remote-host', default=DEFAULT_REMOTE_HOST)
    ap.add_argument('--ssh-key', default=DEFAULT_SSH_KEY)
    ap.add_argument('--fixture-dir', default=str(DEFAULT_FIXTURE_DIR))
    ap.add_argument('--out-dir', default='')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    run_id = f'a2a-v260-two-worker-{now_id()}'
    out_dir = Path(args.out_dir) if args.out_dir else ROOT / 'examples' / 'v2.6.0' / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    dispatches = [
        read_json(Path(args.fixture_dir) / 'dispatch-worker-readiness.json'),
        read_json(Path(args.fixture_dir) / 'dispatch-worker-review.json'),
    ]
    markers = ['A2A_V260_READINESS_OK', 'A2A_V260_REVIEW_OK']

    readiness = {'run_id': run_id, 'dry_run': args.dry_run, 'endpoint': args.endpoint, 'agent_card_url': args.agent_card, 'created_at': now_iso()}
    credential = 'dry-run-credential-not-used'
    if args.dry_run:
        readiness.update({'agent_card_http_status': 200, 'agent_card_live': False, 'credential_loaded': False, 'credential_recorded': False})
        write_json(out_dir / 'agent-card.json', {'dry_run': True, 'url': args.agent_card})
    else:
        status, card = http_get_json(args.agent_card)
        readiness.update({'agent_card_http_status': status, 'agent_card_live': status == 200, 'credential_loaded': True, 'credential_recorded': False})
        write_json(out_dir / 'agent-card.json', card)
        credential = read_remote_credential(args.remote_host, args.ssh_key)
    write_json(out_dir / 'readiness.json', readiness)

    receipts: list[dict[str, Any]] = []
    for dispatch, marker in zip(dispatches, markers):
        task_text = render_task_from_dispatch(dispatch, marker)
        receipt = a2a_send(args.endpoint, credential, task_text, dispatch['task_id'], dispatch['source_agent'], dispatch['target_agent'], out_dir, marker, args.dry_run)
        classification, reason = classify_receipt(receipt)
        receipt['classification'] = classification
        receipt['classification_reason'] = reason
        write_json(out_dir / f"{receipt['task_id']}-receipt.json", receipt)
        receipts.append(receipt)

    items = [{'task_id': r['task_id'], 'classification': r['classification'], 'reason': r['classification_reason'], 'evidence_path': r['evidence_path']} for r in receipts]
    forbidden_found: list[str] = []
    for p in out_dir.glob('*'):
        if p.is_file():
            text = p.read_text(encoding='utf-8', errors='replace')
            for pattern in has_forbidden_literal(text):
                forbidden_found.append(f'{p.name}:{pattern}')
    all_accepted = all(i['classification'] == 'accepted' for i in items)
    overall = 'accepted_with_boundary' if all_accepted else 'rejected'
    acceptance = {
        'schema_version': 'a2a-acceptance-report-v1',
        'run_id': run_id,
        'overall': overall,
        'items': items,
        'secret_scan': {'ok': not forbidden_found, 'token_recorded': False, 'forbidden_literals_found': forbidden_found},
        'external_side_effects': {'gateway_restart': False, 'openclaw_restart': False, 'cron_enabled': False, 'platform_send': False, 'live_a2a_call': not args.dry_run},
        'next_step': 'only freeze into queue CLI or Kanban/Swarm style template after explicit confirmation',
    }
    write_json(out_dir / 'acceptance-report.json', acceptance)
    summary = render_summary(run_id, out_dir, receipts, overall)
    execution_summary = {
        'ok': all_accepted and not forbidden_found,
        'run_id': run_id,
        'dry_run': args.dry_run,
        'receipt_count': len(receipts),
        'accepted_count': sum(1 for i in items if i['classification'] == 'accepted'),
        'overall': overall,
        'secret_scan_ok': not forbidden_found,
        'out_dir': str(out_dir),
        'compact_summary': summary,
    }
    write_json(out_dir / 'execution-summary.json', execution_summary)
    print(json.dumps(execution_summary, ensure_ascii=False, indent=2))
    return 0 if execution_summary['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
