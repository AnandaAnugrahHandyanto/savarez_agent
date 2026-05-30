# Hermes ↔ OpenClaw A2A v2.6.4 Runbook Closure Plan

## 目标
收口 v2.6.x 本地验证链路的入口账本与运行手册，让后续会话不需要翻聊天记录即可复跑与判断当前边界。

## 版本判断
- 版本：v2.6.4
- 类型：patch
- 理由：只补 runbook、文件清单和账本同步，不改变能力边界，不新增运行时能力。

## 范围
1. 新增 `docs/hermes-openclaw-a2a-runbook-v2.6.4.md`。
2. 新增 `docs/hermes-openclaw-a2a-file-inventory-v2.6.x.md`。
3. 更新 `docs/hermes-openclaw-a2a-worklog-and-architecture.md`，补入 v2.6.4 runbook 入口。
4. 复跑一键 verify，确认 runbook 命令仍为 PASS。

## 非范围
- 不提交 git commit。
- 不启用 cron / daemon / webhook。
- 不重启服务。
- 不新增 live A2A call。
- 不平台外发。
- 不启用 OpenClaw 反向调度。

## 验收标准
- runbook 文件存在并包含一键 verify 命令。
- 文件清单文件存在并列出当前 v2.6.x 新增/修改文件。
- 主入口文档包含 v2.6.4 Runbook Closure 段落。
- `python3 scripts/verify_a2a_v263_chain.py --skip-dry-run-runner` 返回 PASS。
- 回读验证关键 marker 通过。
