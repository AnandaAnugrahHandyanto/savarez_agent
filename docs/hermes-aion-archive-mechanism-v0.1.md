# AION × Hermes 归档机制 v0.1

> 目标：让项目越来越多以后，AION 仍能被 AI 高效调用、低 token 检索、精确追溯。Hermes 原生归档负责“移出活跃视图”；AION 归档负责“可审计、可召回、可汇总”。

## 1. Hermes 现有归档能力盘点

Hermes 已有多类归档/清理机制：

| 类型 | Hermes 机制 | 特点 | AION 使用方式 |
| --- | --- | --- | --- |
| Kanban task archive | task 状态变为 `archived`；默认不显示，可通过 include archived 查看 | 不删除数据库记录，只移出默认看板 | 用作“移出主战场”，不是最终档案 |
| Kanban board archive | 删除 board 默认移动到 `boards/_archived/`，可恢复 | 项目级看板归档 | 用作项目看板冷归档 |
| Kanban gc | 清理 archived task workspace、旧 events、旧 logs | 偏存储清理 | 只能在确认 AION 档案已入账后使用 |
| Session export/prune | `hermes sessions export` / `sessions prune` | 导出 JSONL、清理旧会话 | 只做会话备份/清理，不能当任务正本 |
| Profile export/import | `hermes profile export`，不包含 `.env`/`auth.json` |  profile 备份，排除凭据 | 用作 GM/007/审计环境备份，不存 secret |
| Skill curator archive | 技能移动到 `.archive/`，可 restore | 可恢复，不直接删除 | 用作过期技能归档，不等于项目档案 |
| Cron local output | cron 输出默认保存本地文件 | 可查调度结果 | 只存摘要索引，不把长输出塞进看板 |

结论：Hermes 原生归档偏“收纳/隐藏/恢复”，AION 还需要一层“任务正本索引 + 精准摘要 + 证据链”。

## 2. AION 归档原则

1. **GitHub 仍是正本**：issue、PR、commit、CI、review、comment 是最终证据。
2. **Factory Report 是账本**：保存健康、吞吐、证据索引、完成趋势。
3. **Hermes Kanban 是作战视图**：显示当前状态，不承载长历史。
4. **归档不是删除**：主战场减负，但必须可恢复、可检索、可追溯。
5. **AI 优先读取短索引**：默认读取精简 JSON/Markdown 索引；只有需要时再打开长文、PR、日志。
6. **禁止归档未闭环任务**：缺 GitHub evidence、缺审计、缺 ledger 的任务不能归档为“已完成”。
7. **高风险单独留痕**：涉及 production/payment/credits/webhook/DB/customer data/legal 的任务必须保留授权证据链接。

## 3. AION 档案层级

建议采用四层结构：

```text
Level 0: Live 看板
  当前活跃任务，只放短字段。

Level 1: Index 索引
  AI 默认读取；每条任务 10-20 行以内。

Level 2: Packet 完成包
  单任务完整收口：目标、范围、PR、测试、审计、风险、AAR。

Level 3: Evidence 原始证据
  GitHub issue/PR/comment/CI/log/report/截图链接，不复制长内容。
```

## 4. 推荐目录结构

在 AION governance repo 中建议新增：

```text
factory/archive/
  index.json
  index.md
  projects/
    <project_id>/
      project-index.json
      project-index.md
      tasks/
        <task_id>.json
        <task_id>.md
      prs/
        pr-<number>.json
        pr-<number>.md
      aar/
        <date>-<task_id>-aar.md
```

其中：

- `index.json`：机器优先读取。
- `index.md`：人类快速查看。
- `task_id.json`：短、结构化、AI 友好。
- `task_id.md`：完成包，可读版本。
- 不把大日志全文塞进去，只保存链接和摘要。

## 5. 单任务归档字段

```yaml
archive_packet:
  schema_version: aion.archive.v0.1
  project_id:
  task_id:
  title_cn:
  status: completed | archived | blocked | superseded | abandoned
  owner:
  auditor:
  risk_level: L0 | L1 | L2 | L3 | L4
  monarch_required: true | false
  github:
    repo:
    issue:
    pr:
    head_sha:
    merge_commit:
    ci_runs:
    review_comments:
  evidence:
    status: present | missing
    links:
    summary:
  audit:
    verdict: pass | fail | fallback | retrospective | pending
    auditor:
    comment_url:
  factory_report:
    report_url:
    evidence_index_path:
  kanban:
    board:
    card_id:
    final_state:
    archived_at:
  aar:
    what_was_expected:
    what_happened:
    lessons:
    followups:
  retrieval:
    keywords:
    one_line_summary:
    token_budget: short
```

## 6. 归档门槛

任务从 `已完成` 进入 `已归档` 前必须满足：

- ✅ 有 GitHub 正本链接。
- ✅ 有 PR/commit/CI/review/comment 等 evidence。
- ✅ 有审计或 GM2 low-risk verdict。
- ✅ 有 completion packet。
- ✅ 有 AAR/经验教训，哪怕很短。
- ✅ 已写入 AION archive index。

不满足时：

- 缺 evidence：停在 `待补证据`。
- 缺审计：停在 `待审计`。
- 高风险缺授权：停在 `待君主拍板`。
- 缺 completion packet：停在 `待入档`。

## 7. 看板归档规则

Hermes Kanban 中的 `archived` 只表示“移出主战场”，不等于 AION 归档完成。

推荐状态：

```text
已完成 → 待入档 → 已归档
```

v0.1 如果不新增列，可以用卡片字段：

```yaml
evidence_status: present
archive_status: pending | indexed | archived
```

## 8. AI 检索策略

AI 调用时按顺序读取：

1. `factory/archive/index.json`：找项目、任务、PR。
2. `project-index.json`：找项目内相关任务。
3. `<task_id>.json`：读取短结构化事实。
4. 必要时才打开 `<task_id>.md`。
5. 最后才访问 GitHub PR/issue/log 原文。

这样避免每次把长 PR、长日志、长会话塞进上下文。

## 9. PR / 完成任务入档要求

所有完成 PR 必须能整理入档：

- PR 标题中英文双语。
- PR body 含验收、测试、风险、回滚/恢复、审计请求。
- merge 后生成或更新 archive packet。
- Factory Report evidence index 加一条短索引。
- Kanban card 最终状态改为 `已归档` 前必须能反查 archive packet。

## 10. v0.1 实施建议

本次 Hermes AION Kanban PR 先做：

1. 文档定义归档机制。
2. Kanban AION payload 增加 `archive_status` 概念。
3. 卡片显示“是否已入档”。
4. 测试覆盖：没有 evidence/audit/archive packet 的任务不能显示为真正归档完成。

后续 AION governance repo 再落地真实 `factory/archive/` schema、checker、fixtures、Factory Report 入口。
