#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QMT 智能推送 Cron 任务配置
每天早上 9:00 自动运行
"""

import json
from pathlib import Path

HERMES_HOME = Path.home() / ".hermes"
CRON_CONFIG_FILE = HERMES_HOME / "config" / "qmt_smart_push_cron.json"
CRON_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)

cron_config = {
    "name": "QMT 一进二智能推送",
    "schedule": "0 9 * * 1-5",  # 每个工作日早上 9:00
    "command": "cd ~/.hermes/runtime-hermes-agent && python3 qmt_smart_push_master.py",
    "enabled": True,
    "notify_on_complete": True,
    "deliver_to": "lark",  # 推送到飞书
    "description": "每天早上 9:00 抓取新闻、分析消息面、生成一进二候选并推送",
}

with open(CRON_CONFIG_FILE, "w", encoding="utf-8") as f:
    json.dump(cron_config, f, ensure_ascii=False, indent=2)

print(f"✓ Cron 配置已保存: {CRON_CONFIG_FILE}")
print(f"调度: {cron_config['schedule']}")
print(f"命令: {cron_config['command']}")
