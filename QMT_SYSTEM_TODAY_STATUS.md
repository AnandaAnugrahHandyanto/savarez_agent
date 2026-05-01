# QMT 系统今日闭环说明

## 当前已完成
1. VM QMT REST 数据服务在线
2. 主板非ST候选池自动导出
3. 中文结论版选股输出
4. 日报成品自动生成
5. 日报已可同步到 Hermes 本机目录
6. 盘中多时点快照自动落盘
7. 盘中二快照刷新报告自动生成
8. 盘中全日轨迹报告自动生成
9. 自动状态迁移决策引擎报告自动生成
10. 本机已具备盘中同步脚本与验收脚本
11. 盘中自动推送 cron 已创建，并带 post-deliver 去重提交

## Hermes 本机同步/验收脚本
- `qmt_sync_report.py`
- `qmt_sync_intraday.py`
- `qmt_intraday_acceptance.py`
- `qmt_intraday_push_change_guard.py`

## 自动推送
- cron job: `qmt-intraday-to-origin`
- job id: `2957d10faeda`
- deliver: `feishu:oc_09f8f912151bec1e75b99d7d050109a9`
- schedule: `every 15m`
- script: `qmt_intraday_push_context.py`
- post-deliver script: `qmt_intraday_report_commit_state.py`

## 本机盘中产物落点
- `qmt_sync/intraday_refresh_last.json`
- `qmt_sync/status_panel.txt`
- `qmt_sync/reports/YYYYMMDD/intraday_refresh_report.txt`
- `qmt_sync/reports/YYYYMMDD/intraday_timeline_report.txt`
- `qmt_sync/reports/YYYYMMDD/intraday_state_matrix_report.txt`

## 推荐使用顺序
1. VM 运行 `register_qmt_intraday_task.ps1`
2. VM 运行 `register_qmt_status_panel_task.ps1`
3. VM 用 `check_qmt_tasks.ps1` 确认任务存在
4. VM 按时自动生成盘中产物
5. 本机运行 `python qmt_sync_intraday.py --date YYYYMMDD`
6. 本机运行 `python qmt_intraday_acceptance.py --date YYYYMMDD`
7. 需要盘后日报时，再运行 `python qmt_sync_report.py --date YYYYMMDD`

## 当前缺口
- 题材语义仍偏粗
- 更细粒度盘中流（封单/回封/炸板/承接转强/承接转弱）已接入快照序列事件层，但尚未升级为 tick 级实时订阅
- 当前自动推送 job 已建，但下一次真正非静默推送要等交易时段且内容发生变化
- VM 控制台中文输出仍有乱码，但文件与同步结果已正常
