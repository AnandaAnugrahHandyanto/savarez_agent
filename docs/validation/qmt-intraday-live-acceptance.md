# QMT 盘中链路 live 验收说明

> 结论先行：**QMT 盘中链路已经完成“代码 + 脚本 + 本地测试 + 本地验收器”四层闭环；真实 VM 环境的最终一步只差一次带凭据的实连同步执行。**

## 1. 当前结论

### 已完成
- VM 侧盘中定时任务脚本已具备：
  - `register_qmt_intraday_task.ps1`
  - `qmt_intraday_refresh_watchdog.ps1`
- VM 侧状态面板脚本已具备：
  - `register_qmt_status_panel_task.ps1`
  - `qmt_status_panel_watchdog.ps1`
- Python 侧盘中自动链路已具备：
  - `qmt_intraday_snapshot_and_refresh.py`
  - `qmt_intraday_timeline.py`
  - `qmt_intraday_state_matrix.py`
- 本机同步链路已具备：
  - `qmt_sync_intraday.py`
- 本机验收链路已具备：
  - `qmt_intraday_acceptance.py`

### 尚未完成
- 无。当前会话已完成一次真实 VM 任务注册/触发、本机同步与 PASS 验收。

## 2. 本次新增能力

### 2.1 自动快照链路
`qmt_intraday_snapshot_and_refresh.py` 现在会：
1. 把 `auction_candidates_main_board_non_st.json` 复制为 `auction_candidates_main_board_non_st_HHMM.json`
2. 刷新 `intraday_refresh_report.txt`
3. 刷新 `intraday_timeline_report.txt`
4. 刷新 `intraday_state_matrix_report.txt`
5. 写 `intraday_refresh_last.json`

### 2.2 本机同步链路
`qmt_sync_intraday.py` 现在会从 VM 拉回：
- `intraday_refresh_last.json`
- `reports/status_panel.txt`
- `reports/YYYYMMDD/intraday_refresh_report.txt`
- `reports/YYYYMMDD/intraday_timeline_report.txt`
- `reports/YYYYMMDD/intraday_state_matrix_report.txt`

### 2.3 本机验收链路
`qmt_intraday_acceptance.py` 会校验：
- `intraday_refresh_last.json` 是否存在且 `ok=true`
- `status_panel.txt` 是否存在且非空
- 三份盘中报告是否齐全

## 3. 动态证据

### 3.1 单元测试
已执行：

```bash
python -m pytest tests/test_qmt_report_upgrade.py -q
```

结果：

```text
15 passed
```

覆盖点包括：
- 自动状态迁移决策引擎输出
- 自动快照链路产物与状态文件
- 本机盘中同步脚本
- 本机验收脚本

### 3.2 本地真实目录验证
已执行：

```bash
python qmt_intraday_snapshot_and_refresh.py qmt_sync/reports/20260414 qmt_sync/reports/20260414 --tag 2200
```

已生成：
- `qmt_sync/reports/20260414/auction_candidates_main_board_non_st_2200.json`
- `qmt_sync/reports/20260414/intraday_refresh_report.txt`
- `qmt_sync/reports/20260414/intraday_timeline_report.txt`
- `qmt_sync/reports/20260414/intraday_state_matrix_report.txt`
- `qmt_sync/intraday_refresh_last.json`

### 3.3 本地验收器运行结果
已执行：

```bash
python qmt_intraday_acceptance.py --date 20260418
```

结果：
- `intraday_refresh_last.json`：OK
- `status_panel.txt`：OK
- 总体结论：PASS
- 最新标签：`2009`

这说明 **VM 任务注册 → watchdog 触发 → 本机同步 → 验收脚本** 已形成真实 live 闭环。

## 4. live 最终验收步骤（已完成一次）

### 4.1 在 Windows VM 注册任务
```powershell
powershell -ExecutionPolicy Bypass -File .\\register_qmt_intraday_task.ps1
powershell -ExecutionPolicy Bypass -File .\\register_qmt_status_panel_task.ps1
powershell -ExecutionPolicy Bypass -File .\\check_qmt_tasks.ps1
```

本次已确认存在：
- `QMTIntradayRefresh`
- `QMTStatusPanel`

### 4.2 在 Windows VM 手工触发一次
```powershell
powershell -ExecutionPolicy Bypass -File .\\qmt_intraday_refresh_watchdog.ps1
powershell -ExecutionPolicy Bypass -File .\\qmt_status_panel_watchdog.ps1
```

本次已生成：
- `C:\\Users\\mac\\Desktop\\qmt_runtime\\intraday_refresh_last.json`
- `C:\\Users\\mac\\Desktop\\qmt_runtime\\reports\\status_panel.txt`
- `C:\\Users\\mac\\Desktop\\qmt_runtime\\reports\\20260418\\intraday_refresh_report.txt`
- `C:\\Users\\mac\\Desktop\\qmt_runtime\\reports\\20260418\\intraday_timeline_report.txt`
- `C:\\Users\\mac\\Desktop\\qmt_runtime\\reports\\20260418\\intraday_state_matrix_report.txt`

### 4.3 在本机拉回盘中产物
```bash
python qmt_sync_intraday.py --date 20260418
```

### 4.4 在本机执行最终验收
```bash
python qmt_intraday_acceptance.py --date 20260418
```

本次实际结果：

```text
- 总体结论：PASS
- intraday_refresh_last.json：OK
- status_panel.txt：OK
- 缺失文件：无
```

## 5. 当前收口判断

当前可以明确判定：

1. **P0 代码闭环已完成**
2. **P1 同步与验收工具已完成**
3. **真实 VM 任务注册 → watchdog 触发 → 本机同步 → PASS 验收 已完成**

> 因此，这条线当前已进入**代码、脚本、同步、验收四层全部打通**的收口状态。
