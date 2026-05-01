# Cron 通知去重后置提交机制验收说明

## 范围

本验收覆盖 Hermes cron 通知链路从“检测阶段前滚基线”到“成功投递后再提交基线”的完整改造，重点验证：

1. 去重基线是否已从检测阶段剥离
2. 是否已具备通用的 post-deliver 提交能力
3. QMT Feishu 日报 job 是否已迁移到正式配置
4. 文档是否已固化为后续通知类 cron 的标准接法

## 结论

- **重复推送根因已被结构性消除。** 当前机制不再依赖检测阶段更新 state，而是仅在成功非静默投递后执行基线提交。
- **能力已通用化。** 不再依赖 `qmt-daily-report-to-feishu-home` 之类的 job name 硬编码，任何 cron job 都可以通过 `post_deliver_script` 接入相同模式。
- **QMT job 已正式切流。** `10d8a7b23488 / qmt-daily-report-to-feishu-home` 已持久化声明 `post_deliver_script: qmt_daily_report_commit_state.py`。
- **开发规范已落文档。** 后续所有需要通知去重/基线提交的 cron，都应使用 post-deliver script，而不是在检测阶段写入 state。

## 问题与根因

### 原始问题

QMT Feishu 开盘日报会出现重复/近似内容反复推送，且在“发送失败”场景下存在漏发风险。

### 根因

旧链路存在两个问题：

1. **无变化静默逻辑不稳定**：虽然已有 `[SILENT]` 机制，但缺少可靠的“基于实际已发送版本”的基线管理。
2. **状态提交时机错误**：检测脚本在比较完成后立即写入新 state；若后续平台投递失败，则基线已前滚，下一轮会把同一份未真正送达的内容误判为 `UNCHANGED`。

## 改动点

### 1. 检测 / 提交分离

文件：`qmt_daily_report_change_guard.py`

- 默认运行：只检测，不写 state
- `--commit`：显式提交已成功发送的版本到 state

这保证了“变化检测”与“成功送达后基线提交”分离。

### 2. 通用 post-deliver 能力

文件：`cron/jobs.py`

- job 模型新增 `post_deliver_script`
- 支持持久化存储到 `~/.hermes/cron/jobs.json`

文件：`tools/cronjob_tools.py`

- `cronjob(create/update/list)` 支持 `post_deliver_script`
- 路径校验沿用 `~/.hermes/scripts/` 约束

文件：`cron/scheduler.py`

- 在成功投递且非静默的前提下，执行：
  - `post_deliver_script = job.get("post_deliver_script")`
  - `if success and should_deliver and not delivery_error and post_deliver_script:`
- 若 post-deliver script 执行失败，则记录为 `delivery_error`

### 3. QMT 具体落地

文件：`~/.hermes/scripts/qmt_daily_report_commit_state.py`

- 作为 QMT 日报的 post-deliver 提交脚本
- 通过 importlib 加载仓库内 `qmt_daily_report_change_guard.py`
- 支持 `--commit`

文件：`~/.hermes/cron/jobs.json`

- job `10d8a7b23488` 已写入：
  - `post_deliver_script: "qmt_daily_report_commit_state.py"`

## 验收证据

### 证据 1：调度器已按成功投递后提交执行

文件：`cron/scheduler.py:1125-1142`

关键逻辑：

- 先执行 `_deliver_result(...)`
- 再读取 `post_deliver_script`
- 仅在 `success and should_deliver and not delivery_error` 时执行后置脚本

说明：提交时机已绑定到“真实投递成功”之后。

### 证据 2：QMT job 已持久化声明 post_deliver_script

文件：`~/.hermes/cron/jobs.json:42-78`

关键字段：

- `id: "10d8a7b23488"`
- `name: "qmt-daily-report-to-feishu-home"`
- `post_deliver_script: "qmt_daily_report_commit_state.py"`

说明：不是临时运行态，而是正式配置。

### 证据 3：提交脚本实测可用

实测命令：

```bash
python /Users/zezesun/.hermes/scripts/qmt_daily_report_commit_state.py --commit
python qmt_daily_report_change_guard.py
```

实测结果：

- 第一步输出：`STATE_COMMITTED=1`
- 第二步输出：`STATE_COMMITTED=0` 且 `STATUS=UNCHANGED`

说明：

- 提交动作能真正落盘
- 提交后基线比较会正确变为未变化

### 证据 4：文档规范已落地

- `website/docs/developer-guide/cron-internals.md`
  - 新增 `Post-Delivery Scripts`
- `website/docs/guides/automate-with-cron.md`
  - 新增 `Post-delivery baselines (important)`

说明：后续同类通知 cron 已有统一规范，不再依赖口头约束。

## 标准接法（后续所有通知类 cron）

适用场景：

- 网站/公告/日报/状态变更通知
- 需要“只在变化时通知”的 cron
- 需要防止发送失败后漏发的任何 dedupe 监控链路

标准模式：

1. **检测阶段只判断变化，不提交基线**
   - 可以用 `script`、prompt、或单独 guard 脚本
2. **无变化返回 `[SILENT]`**
3. **有变化时返回完整通知内容**
4. **通过 `post_deliver_script` 在成功投递后提交新基线**
5. **禁止在检测阶段写入“已发送版本”状态**

推荐字段：

- `script`：收集数据 / 预处理 / 检测上下文
- `post_deliver_script`：提交 dedupe baseline / checkpoint

## 已知边界

- 本次环境中 `pytest` 不可用（缺少 pytest 模块），因此未完成自动化测试执行；但关键脚本与配置链路已通过真实命令验证。
- 当前外层平台对 cronjob tool 的描述文档尚未单独补一份 API 级变更公告，但仓库内实现、jobs.json、调度器、文档都已一致。

## 最终验收结论

> Hermes cron 通知链路已完成从“检测阶段前滚基线”的脆弱实现，升级为“成功投递后再提交基线”的通用机制；QMT Feishu 日报已正式迁移到该机制，并具备配置、代码、脚本、文档四层一致性，达到可复用、可扩展、可验收的收口状态。
