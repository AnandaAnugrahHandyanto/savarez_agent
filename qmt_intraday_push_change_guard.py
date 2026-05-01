#!/usr/bin/env python3
"""Detect whether today's synced QMT intraday state-matrix report changed materially.

去重机制说明：
--------------
本脚本通过 decision_hash 指纹防止重复推送相同的交易决策。

核心逻辑：
1. normalized_hash: 对整个报告内容归一化后的 SHA256，用于检测任何内容变化
2. decision_hash: 仅对核心决策字段（自动动作、当前最强、题材判定、动作模板）计算 SHA256
3. 推送判定: 只有当 decision_hash 变化时才标记为 CHANGED，触发推送

示例场景：
- 报告中的时间戳、路径、其他分析内容更新 → content_changed=1, decision_changed=0 → 不推送
- 核心决策从"仅留备选"变为"全部清仓" → decision_changed=1 → 推送
- 首次运行（无历史状态） → decision_changed=1 → 推送

状态持久化：
- 状态文件: qmt_sync/reports/.last_feishu_intraday_state_matrix.json
- 包含字段: date, report_path, normalized_hash, decision_hash, updated_at
- 使用 --commit 参数提交当前状态为已推送基线
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path


STATE_FILENAME = '.last_feishu_intraday_state_matrix.json'


def normalize_report(text: str) -> str:
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        line = re.sub(r'\s+', ' ', line)
        line = re.sub(r'20\d{6}', '<DATE>', line)
        line = re.sub(r'/Users/[^ ]+', '<PATH>', line)
        line = re.sub(r'[A-Za-z]:\\[^ ]+', '<PATH>', line)
        lines.append(line)
    return '\n'.join(lines)


def digest(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def load_state(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}


def write_state(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def build_state(today: str, report_path: Path, normalized_hash: str) -> dict:
    return {
        'date': today,
        'report_path': str(report_path),
        'normalized_hash': normalized_hash,
        'updated_at': datetime.now().isoformat(timespec='seconds'),
    }


def extract_push_summary(report_text: str) -> dict:
    action_line = ''
    best_line = ''
    theme_line = ''
    template_line = ''
    reason_tags: list[str] = []

    in_im_summary = False
    for raw in report_text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith('## '):
            in_im_summary = line == '## IM 极简摘要'
            continue
        if not in_im_summary or not line.startswith('- '):
            continue
        content = line[2:]
        if content.startswith('自动动作：'):
            action_line = content
        elif content.startswith('当前最强：'):
            best_line = content
        elif content.startswith('题材判定：'):
            theme_line = content
        elif content.startswith('动作模板：'):
            template_line = content
            match = re.search(r'标签=([^；）]+)', content)
            if match:
                reason_tags = [tag for tag in match.group(1).split('/') if tag]

    return {
        'action_line': action_line,
        'best_line': best_line,
        'theme_line': theme_line,
        'template_line': template_line,
        'reason_tags': reason_tags,
    }


def detect_status(report_path: Path, state_path: Path) -> tuple[str, str, dict]:
    if not report_path.exists():
        return 'MISSING', '', {}

    report_text = report_path.read_text(encoding='utf-8', errors='replace')
    normalized = normalize_report(report_text)
    current_hash = digest(normalized)
    
    # Extract decision fingerprint (action/best/theme/template)
    summary = extract_push_summary(report_text)
    decision_key = '|'.join([
        summary.get('action_line', ''),
        summary.get('best_line', ''),
        summary.get('theme_line', ''),
        summary.get('template_line', ''),
    ])
    decision_hash = digest(decision_key)
    
    prev = load_state(state_path)
    content_changed = current_hash != prev.get('normalized_hash')
    decision_changed = decision_hash != prev.get('decision_hash')
    
    # Only push if decision changed
    status = 'CHANGED' if decision_changed else 'UNCHANGED'
    
    state = build_state(datetime.now().strftime('%Y%m%d'), report_path, current_hash)
    state['decision_hash'] = decision_hash
    state['content_changed'] = content_changed
    state['decision_changed'] = decision_changed
    
    return status, current_hash, state


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--date', default=datetime.now().strftime('%Y%m%d'))
    parser.add_argument('--commit', action='store_true', help='Persist the current normalized hash as the delivered state')
    args = parser.parse_args()

    report_path = Path('qmt_sync/reports') / args.date / 'intraday_state_matrix_report.txt'
    state_path = Path('qmt_sync/reports') / STATE_FILENAME

    status, current_hash, state = detect_status(report_path, state_path)
    if status == 'MISSING':
        print('STATUS=MISSING')
        print(f'REPORT_PATH={report_path}')
        return 0

    if args.commit:
        write_state(state_path, state)
        print('STATE_COMMITTED=1')
    else:
        print('STATE_COMMITTED=0')

    print(f'STATUS={status}')
    print(f'REPORT_PATH={report_path}')
    print(f'STATE_PATH={state_path}')
    print(f'NORMALIZED_SHA256={current_hash}')
    print(f'DECISION_HASH={state.get("decision_hash", "")}')
    print(f'CONTENT_CHANGED={1 if state.get("content_changed") else 0}')
    print(f'DECISION_CHANGED={1 if state.get("decision_changed") else 0}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
