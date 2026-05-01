#!/usr/bin/env python3
"""
首板盘中推送变更检测 - 判断是否需要推送
"""

import argparse
import hashlib
import json
from pathlib import Path


def compute_event_hash(events_summary: dict) -> str:
    """计算事件摘要的哈希值"""
    # 只关注事件类型和数量，不关注具体时间
    signature = {
        '封板': len(events_summary.get('封板', [])),
        '炸板': len(events_summary.get('炸板', [])),
        '回封': len(events_summary.get('回封', [])),
        '转弱': len(events_summary.get('转弱', [])),
    }
    text = json.dumps(signature, sort_keys=True)
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def load_last_push_state(state_path: Path) -> dict:
    """加载上次推送状态"""
    if not state_path.exists():
        return {}
    try:
        return json.loads(state_path.read_text(encoding='utf-8'))
    except Exception:
        return {}


def save_push_state(state_path: Path, state: dict) -> None:
    """保存推送状态"""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')


def extract_push_summary(report_text: str) -> dict:
    """从报告中提取推送摘要"""
    lines = report_text.split('\n')
    
    # 提取极简摘要部分
    summary_lines = []
    in_summary = False
    for line in lines:
        if line.startswith('## 极简摘要'):
            in_summary = True
            continue
        if in_summary:
            if line.startswith('## '):
                break
            if line.strip():
                summary_lines.append(line)
    
    return {
        'summary': '\n'.join(summary_lines),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description='首板盘中推送变更检测')
    parser.add_argument('--date', required=True, help='交易日 YYYYMMDD')
    args = parser.parse_args()
    
    repo_root = Path(__file__).parent
    reports_root = repo_root / 'qmt_sync' / 'reports'
    state_root = repo_root / 'qmt_sync' / 'state'
    
    report_path = reports_root / args.date / 'first_board_intraday_tracker.txt'
    state_path = state_root / 'first_board_intraday_push_state.json'
    
    # 检查报告是否存在
    if not report_path.exists():
        print('STATUS=MISSING')
        print(f'REPORT_PATH={report_path}')
        return
    
    # 加载报告
    try:
        report_text = report_path.read_text(encoding='utf-8', errors='replace')
    except Exception as e:
        print('STATUS=ERROR')
        print(f'ERROR={e}')
        return
    
    # 提取事件摘要
    summary = extract_push_summary(report_text)
    
    # 如果没有事件，不推送
    if not summary['summary'].strip():
        print('STATUS=UNCHANGED')
        print('REASON=NO_EVENTS')
        return
    
    # 计算事件哈希
    # 简化版：直接用摘要文本作为指纹
    current_hash = hashlib.sha256(summary['summary'].encode()).hexdigest()[:16]
    
    # 加载上次推送状态
    last_state = load_last_push_state(state_path)
    last_hash = last_state.get('last_hash', '')
    last_date = last_state.get('last_date', '')
    
    # 判断是否需要推送
    if last_date == args.date and last_hash == current_hash:
        print('STATUS=UNCHANGED')
        print(f'LAST_HASH={last_hash}')
        print(f'CURRENT_HASH={current_hash}')
        return
    
    # 需要推送
    print('STATUS=CHANGED')
    print(f'REPORT_PATH={report_path}')
    print(f'LAST_HASH={last_hash}')
    print(f'CURRENT_HASH={current_hash}')
    print(f'PUSH_SUMMARY={summary["summary"][:200]}')
    
    # 注意：不在这里更新状态，由 post_deliver_script 完成


if __name__ == '__main__':
    main()
