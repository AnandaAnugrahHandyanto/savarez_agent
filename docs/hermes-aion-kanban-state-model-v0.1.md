# Hermes × AION Kanban 状态模型 v0.1

> English: State model for the AION Chinese cockpit layer on top of Hermes native Kanban.

## 1. 状态列

| AION 状态列 | Hermes 基础状态 | 中文定义 | 完成/流转规则 |
| --- | --- | --- | --- |
| 待定性 | triage | 原始想法、子议题、未拆解需求 | 需要 GM/13爷补目标、边界、证据要求。 |
| 待派工 | todo | 已明确目标，但还没有负责人 | 需要指定 owner / assignee。 |
| 待开工 | ready | 已派给角色，等待调度器 tick 或 worker ACK | v0.1 只展示，不自动催动。 |
| 执行中 | running | 007 / GM / Cursor / 13爷等正在处理 | 需要持续留痕。 |
| 待审计 | derived waiting_audit | 执行者声称完成，但没有八府巡按 formal verdict | 有完成声称但缺审计或缺 evidence 时进入。 |
| 阻塞 | blocked | 缺依赖、CI 失败、证据不足、权限不足、任务定义不清 | 必须显示阻塞原因和下一关口。 |
| 待君主拍板 | derived needs_monarch | 涉及真实外部影响或高风险 merge | 不能由普通调度器直接推过。 |
| 已完成 | done | 已有证据、已审计、已写回、可归档 | 没有 GitHub evidence 或 audit verdict 时不得进入真正完成。 |
| 已归档 | archived | 完成超过冷却期后移出主战场 | 保留查询能力。 |

## 2. 最小卡片字段

```yaml
task_id:
title_cn:
repo:
issue:
pr:
owner:
auditor:
risk_level:
state:
monarch_required:
merge_allowed_now:
evidence_status:
latest_evidence:
discord_trace:
next_gate:
age_hours:
sla_status:
```

字段含义：

- `task_id`：Hermes task id 或 AION task id。
- `title_cn`：中文标题优先。
- `repo`：GitHub 仓库。
- `issue`：GitHub issue 链接或编号。
- `pr`：GitHub PR 链接或编号。
- `owner`：负责人，如 007、13爷、GM2、Cursor。
- `auditor`：审计角色，默认八府巡按。
- `risk_level`：L0-L4。
- `state`：AION 状态列。
- `monarch_required`：是否需要君主拍板。
- `merge_allowed_now`：当前是否允许 merge；v0.1 只展示，不执行。
- `evidence_status`：`present` / `missing`。
- `latest_evidence`：最新 GitHub evidence link。
- `discord_trace`：最近 Discord/评论活动摘要。
- `next_gate`：下一关口。
- `age_hours`：等待时长。
- `sla_status`：`ok` / `watch` / `overdue`。

## 3. 风险等级

| 等级 | 定义 | Kanban 行为 |
| --- | --- | --- |
| L0 | 纯信息 / 只读 | 可自动展示，可进入只读状态流。 |
| L1 | 文档 / prepare-only / 低风险 | 可自动推进到待审计，但 v0.1 不写回。 |
| L2 | 可自动执行，但需要留痕 | 必须显示证据和审计关口。 |
| L3 | 准备包可以做，真实执行需审计 | prepare-only 可走，真实执行前阻断。 |
| L4 | 必须君主拍板 | 进入待君主拍板列。 |

以下关键词/语义出现时，v0.1 默认标为高风险或待君主拍板候选：

- production deployment
- prod smoke
- payment
- credits
- webhook
- external executor
- secret / token
- DB mutation
- customer data
- irreversible operation
- merge high-risk PR

注意：AION 总治理仍按“真实财务后果 / 真实法律后果 / 真实外部副作用”判断最终 Monarch gate；Kanban v0.1 为防误推，可以保守展示到 `待君主拍板`。

## 4. 完成判定

不得仅因 worker 声称完成就显示为真正完成。

真正完成至少需要：

1. GitHub evidence link 存在：issue / PR / commit / CI / review。
2. 审计或验收证据存在：八府巡按 formal verdict、CI PASS、GM2 low-risk verdict 等。
3. 已写回正本或账本：GitHub comment / Factory Report evidence index。

缺任一项时：

- 缺 evidence：`待补证据 / Evidence Missing`。
- 缺 audit：`待审计`。
- 高风险缺君主授权：`待君主拍板`。

## 5. 阻塞判定

进入 `阻塞` 的常见原因：

- CI failed。
- 权限不足。
- Command Approval gate 拦截。
- GitHub evidence 缺失。
- 任务定义不清。
- 外部依赖未就绪。

卡片必须显示 `next_gate`，避免只显示“blocked”但不知道谁该动。

## 6. 归档规则

建议：

- 已完成且 evidence/audit/ledger 齐全后进入 `已完成`。
- 冷却期后可归档；默认建议 24-72 小时。
- 已归档任务不显示在主战场，但可通过归档过滤查看。

## 7. 归档状态

AION 不把 Hermes 原生 `archived` 等同于最终归档完成。推荐增加卡片字段：

```yaml
archive_status: none | pending | indexed | archived
archive_packet:
```

含义：

- `none`：还没进入归档流程。
- `pending`：任务完成但还缺入档包、AAR、证据索引或审计链接。
- `indexed`：已写入 AION archive index / Factory Report evidence index，但仍保留在主战场冷却。
- `archived`：已完成、已审计、已入档，可从主战场移出。

详细机制见：`docs/hermes-aion-archive-mechanism-v0.1.md`。

## 8. v0.1 只读门禁

v0.1 中这些 UI 动作必须禁用或只显示提示：

- 拖拽改状态。
- 批量改状态。
- 新建任务并写回。
- Nudge Dispatcher / 催动调度器。
- close issue。
- merge PR。
- production / payment / webhook / external executor。

## 8. 审计验收清单

- 中文为主，英文仅技术辅助。
- GitHub evidence 可点击。
- Discord trace/评论摘要可见。
- 执行完成、待审计、审计通过、已归档可区分。
- 待君主拍板单独成列。
- 当前瓶颈角色可见。
- 阻塞原因和下一关口可见。
- 风险等级可见。
- 缺证据不得显示为真正完成。
- 高风险任务不得被调度器误推进。
