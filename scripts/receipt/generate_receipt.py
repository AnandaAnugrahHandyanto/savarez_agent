#!/usr/bin/env python3
"""
Hermes 对话小票生成器
在对话结束时自动生成 token 使用小票
"""

import sqlite3
import json
import datetime
import os
from pathlib import Path

def get_session_stats(session_id=None):
    """从数据库获取当前会话统计"""
    db_path = Path.home() / ".hermes" / "state.db"
    
    if not db_path.exists():
        return None
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # 获取最新会话或指定会话
    if session_id:
        cursor.execute('''
            SELECT id, started_at, ended_at, message_count, tool_call_count,
                   input_tokens, output_tokens, estimated_cost_usd, title
            FROM sessions 
            WHERE id = ?
        ''', (session_id,))
    else:
        cursor.execute('''
            SELECT id, started_at, ended_at, message_count, tool_call_count,
                   input_tokens, output_tokens, estimated_cost_usd, title
            FROM sessions 
            ORDER BY started_at DESC 
            LIMIT 1
        ''')
    
    session = cursor.fetchone()
    conn.close()
    
    if not session:
        return None
    
    # 获取消息详情
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute('''
        SELECT role, content, token_count, timestamp
        FROM messages 
        WHERE session_id = ? 
        ORDER BY timestamp
    ''', (session[0],))
    
    messages = []
    for row in cursor.fetchall():
        role, content, token_count, timestamp = row
        # 截断长内容
        if content and len(content) > 200:
            content = content[:197] + "..."
        messages.append({
            "role": role,
            "token_count": token_count,
            "timestamp": datetime.datetime.fromtimestamp(timestamp).strftime('%H:%M:%S')
        })
    
    conn.close()
    
    return {
        "session_id": session[0],
        "started_at": datetime.datetime.fromtimestamp(session[1]).strftime('%Y-%m-%d %H:%M:%S'),
        "ended_at": datetime.datetime.fromtimestamp(session[2]).strftime('%Y-%m-%d %H:%M:%S') if session[2] else "进行中",
        "duration_minutes": round((session[2] - session[1]) / 60, 1) if session[2] else None,
        "message_count": session[3],
        "tool_call_count": session[4],
        "input_tokens": session[5],
        "output_tokens": session[6],
        "total_tokens": (session[5] or 0) + (session[6] or 0),
        "estimated_cost_usd": session[7],
        "title": session[8] or "未命名会话",
        "messages": messages
    }

def generate_receipt(stats, output_dir="~/.hermes/receipts"):
    """生成小票文件"""
    if not stats:
        return None
    
    # 确保输出目录存在
    output_path = Path(output_dir).expanduser()
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 生成文件名
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"hermes_receipt_{timestamp}_{stats['session_id'][:8]}.json"
    filepath = output_path / filename
    
    # 添加生成时间
    stats["receipt_generated_at"] = datetime.datetime.now().isoformat()
    stats["receipt_version"] = "1.0"
    
    # 保存 JSON
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    
    # 生成文本摘要
    txt_filename = f"hermes_receipt_{timestamp}_{stats['session_id'][:8]}.txt"
    txt_filepath = output_path / txt_filename
    
    with open(txt_filepath, 'w', encoding='utf-8') as f:
        f.write(generate_summary(stats))
    
    return str(filepath), str(txt_filepath)

def generate_summary(stats):
    """生成文本摘要"""
    summary = []
    summary.append("=" * 50)
    summary.append("         HERMES AI 对话小票")
    summary.append("=" * 50)
    summary.append(f"会话标题: {stats['title']}")
    summary.append(f"会话ID: {stats['session_id']}")
    summary.append(f"开始时间: {stats['started_at']}")
    summary.append(f"结束时间: {stats['ended_at']}")
    
    if stats['duration_minutes']:
        summary.append(f"持续时间: {stats['duration_minutes']} 分钟")
    
    summary.append("-" * 50)
    summary.append("Token 使用统计:")
    summary.append(f"  输入Token: {stats['input_tokens'] or 0:,}")
    summary.append(f"  输出Token: {stats['output_tokens'] or 0:,}")
    summary.append(f"  总计Token: {stats['total_tokens']:,}")
    
    if stats['estimated_cost_usd']:
        summary.append(f"估算成本: ${stats['estimated_cost_usd']:.6f}")
    
    summary.append("-" * 50)
    summary.append("活动统计:")
    summary.append(f"  消息数量: {stats['message_count']}")
    summary.append(f"  工具调用: {stats['tool_call_count']}")
    
    summary.append("-" * 50)
    summary.append("消息摘要:")
    user_msgs = [m for m in stats['messages'] if m['role'] == 'user']
    assistant_msgs = [m for m in stats['messages'] if m['role'] == 'assistant']
    tool_msgs = [m for m in stats['messages'] if m['role'] == 'tool']
    
    summary.append(f"  用户消息: {len(user_msgs)} 条")
    summary.append(f"  助手回复: {len(assistant_msgs)} 条")
    summary.append(f"  工具调用: {len(tool_msgs)} 次")
    
    summary.append("=" * 50)
    summary.append(f"小票生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    summary.append("=" * 50)
    
    return "\n".join(summary)

def print_receipt(stats):
    """打印小票到控制台"""
    if not stats:
        print("⚠️ 无法获取会话统计信息")
        return
    
    print("\n" + "="*50)
    print("     对话结束 - Token 使用小票")
    print("="*50)
    
    print(f"📝 会话: {stats['title']}")
    print(f"⏱️  时长: {stats['duration_minutes']} 分钟" if stats['duration_minutes'] else "⏱️  进行中")
    
    print("\n📊 Token 统计:")
    print(f"  输入: {stats['input_tokens'] or 0:,}")
    print(f"  输出: {stats['output_tokens'] or 0:,}")
    print(f"  总计: {stats['total_tokens']:,}")
    
    if stats['estimated_cost_usd']:
        print(f"💰 成本: ${stats['estimated_cost_usd']:.6f}")
    
    print(f"\n📨 消息: {stats['message_count']} 条")
    print(f"🔧 工具调用: {stats['tool_call_count']} 次")
    print("="*50)

if __name__ == "__main__":
    # 获取最新会话统计
    stats = get_session_stats()
    
    if stats:
        # 生成并保存小票
        json_path, txt_path = generate_receipt(stats, "~/.hermes/receipts")
        
        # 打印摘要
        print_receipt(stats)
        print(f"\n📁 小票已保存到:")
        print(f"  JSON: {json_path}")
        print(f"  文本: {txt_path}")
    else:
        print("未找到会话数据")