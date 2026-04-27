# 龙头回调策略 v3.6 验证记录

日期: 2026-04-27

结论: 已通过目标测试与真实脚本 smoke；cron prompt 已是 v3.6，无需更新。

验证命令:
1. `source venv/bin/activate && pytest tests/test_complete_stock_selection_v36.py tests/test_qmt_report_upgrade.py tests/test_cross_theme_mapper.py -q`
   - 结果: 33 passed
2. `python3 -m py_compile qmt_complete_stock_selection_v36.py`
   - 结果: V36_PY_COMPILE_OK
3. `python3 qmt_complete_stock_selection_v36.py`
   - 结果: exit 0；输出包含 v3.6、125分、策略评分≥60分、完整评分表；生成 `qmt_sync/reports/20260427/leader_pullback_selection.json`

关键输出:
- can_enter: 圣阳股份 002580.SZ，strategy_score=69，entry_score=52
- need_wait: 株冶集团/中恒电气/金富科技/美诺华

cron 检查:
- job `8f430cfe82e9` / `龙头回调策略每日选股` prompt preview 已写明 `龙头回调策略v3.6完整选股系统`，schedule `0 19 * * 1-5`，enabled=true。

备注:
- 工作区存在大量既有未提交/未跟踪文件；本次验证未清理这些历史状态。
