#!/usr/bin/env python3
"""Generate a local-only Hermes Ops weekly review artifact."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/Users/travis/.hermes/hermes-agent')
REPORTS = Path.home() / '.hermes' / 'reports'


def run(cmd: list[str], cwd: Path = ROOT) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, cwd=str(cwd), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
        return p.returncode, p.stdout.strip()
    except Exception as exc:
        return 1, str(exc)


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime('%Y-%m-%d')
    out = REPORTS / f'hermes_ops_weekly_review_{today}.md'
    generated = datetime.now(timezone.utc).isoformat()

    git_code, git_out = run(['git', 'status', '--short'])
    smoke_code, smoke_out = run([str(ROOT / 'venv/bin/python'), 'scripts/run_william_smoke_prompts.py'])
    mcp_code, mcp_out = run([str(ROOT / 'venv/bin/python'), 'scripts/mcp_inventory.py'])

    benchmark_json = REPORTS / 'document_pipeline_benchmark.json'
    benchmark_summary = 'not found'
    if benchmark_json.exists():
        try:
            rows = json.loads(benchmark_json.read_text(encoding='utf-8'))
            benchmark_summary = f"{sum(1 for r in rows if r.get('ok'))}/{len(rows)} conversions passed"
        except Exception as exc:
            benchmark_summary = f'present but unreadable: {exc}'

    lines = [
        '# Hermes Ops Weekly Review', '',
        f'Generated: {generated}', '',
        '## Git dirty summary', '',
        f'Exit code: `{git_code}`', '',
        '```text', git_out or '(clean)', '```', '',
        '## Smoke prompt suite', '',
        f'Exit code: `{smoke_code}`', '',
        '```json', smoke_out, '```', '',
        '## MCP inventory', '',
        f'Exit code: `{mcp_code}`', '',
        '```json', mcp_out, '```', '',
        '## Document pipeline benchmark', '',
        f'- Artifact: `{benchmark_json}`',
        f'- Status: {benchmark_summary}', '',
        '## Recommended next actions', '',
        '- Keep weekly review delivery local unless explicitly promoted to Hermes Telegram.',
        '- Treat dirty working tree entries as review items before upstream sync.',
        '- Re-run full test shards after any source/test changes.', '',
        'Privacy: no plaintext credentials included; credential-like values are redacted by helper scripts.', ''
    ]
    out.write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps({'ok': smoke_code == 0 and mcp_code == 0 and git_code == 0, 'output': str(out), 'git_exit': git_code, 'smoke_exit': smoke_code, 'mcp_exit': mcp_code}, indent=2))
    return 0 if smoke_code == 0 and mcp_code == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
