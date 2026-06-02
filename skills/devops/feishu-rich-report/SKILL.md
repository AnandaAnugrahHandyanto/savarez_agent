---
name: feishu-rich-report
version: 1.1.0
description: "Side-chain Feishu rich posts via lark-cli; Hermes must ack done."
metadata:
  requires:
    bins: ["lark-cli"]
  tags: [feishu, lark-cli, report, markdown, table]
---

# Feishu 侧链富文本 + Hermes 终态 ack

> **前置：** `~/.claude/skills/lark-shared/SKILL.md`（认证与 `--as`）。
> **SOUL：** `SOUL.md` → **飞书 IM 交付契约**（禁 pipe 表、强制 Phase B ack）。

## 何时用

| 场景 | 用什么 |
| --- | --- |
| Hermes IM 短回复、列表、分段 | **Hermes 正常回复**（禁止 `\|` pipe 表格） |
| 含 pipe 表格 / 长报告 / 正式验收 | **侧链 Phase A** → 本 skill 或 `lark-doc` |
| 侧链成功后 | **Phase B 必做** → Hermes 再发一条终态 IM（见下） |

**禁止**仅跑 `lark-cli` / `terminal` 后结束 turn；用户看不到 Hermes bot 的「已完成」。

## 两阶段闭环（必守）

### Phase A — 侧链交付

```bash
python3 skills/devops/feishu-rich-report/scripts/feishu_rich_send.py \
  --task-label "验收报告" \
  --doc-link "https://xxx.feishu.cn/docx/..." \
  --markdown-file /path/to/REPORT.md
```

- 检查 **exit 0**
- 解析 stdout JSON：`side_delivery.status == "done"`
- 记录 `message_id`、`suggested_chat_reply`

大表优先 **文档侧链**：

1. `lark-doc` 创建/更新文档（表格在 doc 里）
2. Phase A 可选：用本脚本发 **摘要**（小表或无表）+ `--doc-link`
3. 或 Phase A 仅 doc，Phase B 只发链接 + 结论

### Phase B — Hermes 终态 ack（NON-NEGOTIABLE）

**必须**在当前飞书会话再发一条 **Hermes 正常 IM 回复**（assistant 消息，非 terminal 打印）：

- 可直接复制 JSON 里的 `suggested_chat_reply`
- 或按 SOUL 模板：`✅ 已完成` + `📎 链接` + `↪ message_id`

侧链失败时 Phase B 仍要发，说明失败与替代方案。

## 命令示例

```bash
# 当前 Hermes 飞书会话（HERMES_SESSION_CHAT_ID 由 gateway 注入）
python3 skills/devops/feishu-rich-report/scripts/feishu_rich_send.py \
  --task-label "联调结果" \
  --markdown $'## 标题\n\n| 项 | 结果 |\n| --- | --- |\n| A | 通过 |'

# 指定群 + 长报告文件
python3 skills/devops/feishu-rich-report/scripts/feishu_rich_send.py \
  --chat-id oc_xxx \
  --task-label "周报" \
  --markdown-file ./REPORT.md

# 仅打印建议的 Phase B 文案（发送成功后）
python3 skills/devops/feishu-rich-report/scripts/feishu_rich_send.py \
  --chat-id oc_xxx --markdown $'## test' --task-label "测试" \
  --dry-run --suggested-reply-only

# 预览 argv，不发送
python3 skills/devops/feishu-rich-report/scripts/feishu_rich_send.py \
  --chat-id oc_xxx --markdown $'## test' --dry-run
```

工作目录：`hermes-agent` 仓库根，或写脚本绝对路径。

## 输出字段（给 agent 读）

| 字段 | 含义 |
| --- | --- |
| `side_delivery.status` | `done` = 侧链成功；`dry_run` = 未发送 |
| `completion_ack_required` | `true` 时必须 Phase B |
| `suggested_chat_reply` | 建议复制到 Hermes IM 的终态文案 |
| stderr `FEISHU_SIDE_DELIVERY_DONE` | 侧链成功标记（便于日志/监控） |

## 与 Hermes 内置 send 的分工

- Hermes `feishu.py`：**不改**；含 `\|` 表格 → 降级 `text`
- 本 skill：侧链 post，表格正常渲染
- 终态「任务结束」：**永远**以 Hermes Phase B IM 为准

## 参考

- SOUL：`飞书 IM 交付契约`
- 官方行为：`gateway/platforms/feishu.py` `_build_outbound_payload`
- 看板短消息：`kanban-feishu-live/scripts/kanban_feishu_stage_notify.py`（`--text`）
