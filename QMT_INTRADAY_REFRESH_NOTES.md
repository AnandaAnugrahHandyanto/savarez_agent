# QMT 盘中刷新能力说明

## 本轮已完成
1. 新增 `qmt_intraday_refresh.py`
2. 新增 `qmt_intraday_state_matrix.py`
3. 增强 `qmt_intraday_snapshot_and_refresh.py`
4. 支持比较两版候选池 JSON：
   - 上一版
   - 当前版
5. 支持同日多快照连续状态迁移分析：
   - 自动识别主轴稳定性 / 最强切换 / 焦点切换
   - 对单票输出升级 / 降级 / 重排 / 重评
   - 生成自动动作（继续主攻 / 重写主攻 / 仅留备选 / 仅观察 / 全部回避）
6. 支持自动链路：
   - 复制 `auction_candidates_main_board_non_st.json` 为 `auction_candidates_main_board_non_st_HHMM.json`
   - 自动刷新二快照报告 `intraday_refresh_report.txt`
   - 自动刷新多快照轨迹 `intraday_timeline_report.txt`
   - 自动刷新状态迁移报告 `intraday_state_matrix_report.txt`
   - 自动写状态文件 `intraday_refresh_last.json`
   - VM watchdog `qmt_intraday_refresh_watchdog.ps1` 保留 Python 富状态，不再覆盖成旧简版 JSON
7. 输出：
   - 当前是否有主攻
   - 最强备选/主攻
   - 关键个股升级/降级变化
   - 当前动作建议
8. 新增本机同步/验收链路：
   - `qmt_sync_intraday.py` 拉回 VM 盘中状态与三类报告
   - `qmt_intraday_acceptance.py` 校验同步结果是否齐全
9. 新增自动推送链路：
   - `qmt_intraday_push_change_guard.py` 做盘中状态迁移报告去重
   - `~/.hermes/scripts/qmt_intraday_report_commit_state.py` 仅在成功投递后提交基线
   - `~/.hermes/scripts/qmt_intraday_push_context.py` 为 cron 注入同步/验收/guard 上下文
   - cron job `qmt-intraday-to-origin`（job id `2957d10faeda`）已创建，并显式投递到当前 Feishu DM

## 当前输入
```bash
python qmt_intraday_refresh.py PREV.json CURR.json --out intraday_refresh_report.txt
python qmt_intraday_state_matrix.py qmt_sync/reports/20260414 --out intraday_state_matrix_report.txt
python qmt_intraday_snapshot_and_refresh.py qmt_sync/reports/20260414 qmt_sync/reports/20260414 --tag 2200
python qmt_sync_intraday.py --date 20260414
python qmt_intraday_acceptance.py --date 20260414 --out qmt_sync/reports/20260414/intraday_acceptance.txt
```

## 当前产物
- `qmt_sync/reports/20260414/intraday_refresh_report.txt`
- `qmt_sync/reports/20260414/intraday_timeline_report.txt`
- `qmt_sync/reports/20260414/intraday_state_matrix_report.txt`
- `qmt_sync/reports/20260414/intraday_acceptance.txt`
- `qmt_sync/intraday_refresh_last.json`
- `qmt_sync/status_panel.txt`

## 当前边界
- `qmt_intraday_refresh.py` 仍是“二快照对比版”
- `qmt_intraday_state_matrix.py` 已支持同日多快照连续状态迁移，但仍是离线分析，不是实时订阅
- `qmt_intraday_snapshot_and_refresh.py` 已支持自动多时间点落盘 + 三类报告刷新，但当前依赖外部调度触发，不是常驻 watcher
- 连续状态机当前已基于候选池快照序列识别封单/回封/炸板/承接转强/承接转弱，但仍不是 tick 级实时订阅

## 已验证
1. 使用真实当日 JSON + 一份模拟早盘快照，已成功生成盘中刷新报告。
2. 使用 `qmt_sync/reports/20260414/` 真实双快照（09:26 / 21:51），已成功生成状态迁移报告。
3. 使用 `qmt_intraday_snapshot_and_refresh.py qmt_sync/reports/20260414 qmt_sync/reports/20260414 --tag 2200`，已成功：
   - 落盘新快照 `auction_candidates_main_board_non_st_2200.json`
   - 刷新 `intraday_refresh_report.txt`
   - 刷新 `intraday_timeline_report.txt`
   - 刷新 `intraday_state_matrix_report.txt`
4. `pytest tests/test_qmt_report_upgrade.py -q` 已通过，覆盖：
   - 盘中轨迹稳定性指标
   - 自动状态迁移决策引擎输出
   - 自动快照链路产物与状态文件
   - 本机盘中同步脚本
   - 本机盘中验收脚本
   - 升级轨迹文案（如 备选 → 主攻）
5. 已完成真实 VM live 验收：
   - 远端已注册 `QMTIntradayRefresh` / `QMTStatusPanel`
   - 已手工触发 watchdog
   - 已本机执行 `qmt_sync_intraday.py --date 20260418`
   - 已本机执行 `qmt_intraday_acceptance.py --date 20260418`
   - 当前结果为 `PASS`

报告能输出：
- 当前无主攻，仅保留备选观察 / 仅观察 / 重写主攻等自动动作
- 个股动作变化（如回避 → 备选、备选 → 主攻）
- 当前最强候选、主轴稳定性与切换次数

## 下一步
1. 把 VM 导出改为多时间点落盘
2. 本机循环拉取最新快照并自动生成状态迁移报告
3. 若继续增强，升级为更高频成交/逐笔级盘中流，而不只是快照序列事件层
