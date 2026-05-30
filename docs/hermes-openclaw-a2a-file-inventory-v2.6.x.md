# Hermes ↔ OpenClaw A2A v2.6.x File Inventory

## 生成时间
本文件由 v2.6.4 runbook closure 阶段生成，用于记录当前工作区内 v2.6.x 相关新增/修改文件。

## Git 工作区清单
```text
M docs/hermes-openclaw-a2a-worklog-and-architecture.md
?? docs/hermes-openclaw-a2a-live-validation-v2.6.0.md
?? docs/hermes-openclaw-a2a-phase6-review-v2.6.0.md
?? docs/hermes-openclaw-a2a-review-v2.6.0.md
?? docs/hermes-openclaw-a2a-review-v2.6.1.md
?? docs/hermes-openclaw-a2a-review-v2.6.2.md
?? docs/hermes-openclaw-a2a-review-v2.6.3.md
?? docs/hermes-openclaw-a2a-task-plan-v2.6.0.md
?? docs/hermes-openclaw-a2a-task-plan-v2.6.1.md
?? docs/hermes-openclaw-a2a-task-plan-v2.6.2.md
?? docs/hermes-openclaw-a2a-task-plan-v2.6.3.md
?? docs/hermes-openclaw-a2a-validation-v2.6.0.md
?? docs/hermes-openclaw-a2a-validation-v2.6.1.md
?? docs/hermes-openclaw-a2a-validation-v2.6.2.md
?? docs/hermes-openclaw-a2a-validation-v2.6.3.md
?? scripts/hermes_openclaw_v260_two_worker.py
?? scripts/validate_a2a_v260_evidence.py
?? scripts/validate_a2a_v260_mock.py
?? scripts/validate_a2a_v260_negative.py
?? scripts/verify_a2a_v263_chain.py
```

## v2.6.x 核心脚本
- `scripts/hermes_openclaw_v260_two_worker.py`：v2.6.0 two-worker runner，支持 dry-run 与受控 live 模式。
- `scripts/validate_a2a_v260_mock.py`：v2.6.0 mock fixture validator。
- `scripts/validate_a2a_v260_evidence.py`：v2.6.1 positive evidence validator。
- `scripts/validate_a2a_v260_negative.py`：v2.6.2 negative failure-path validator。
- `scripts/verify_a2a_v263_chain.py`：v2.6.3 一键 verify chain。

## v2.6.x 核心文档
- `docs/hermes-openclaw-a2a-task-plan-v2.6.0.md`
- `docs/hermes-openclaw-a2a-validation-v2.6.0.md`
- `docs/hermes-openclaw-a2a-review-v2.6.0.md`
- `docs/hermes-openclaw-a2a-live-validation-v2.6.0.md`
- `docs/hermes-openclaw-a2a-phase6-review-v2.6.0.md`
- `docs/hermes-openclaw-a2a-task-plan-v2.6.1.md`
- `docs/hermes-openclaw-a2a-validation-v2.6.1.md`
- `docs/hermes-openclaw-a2a-review-v2.6.1.md`
- `docs/hermes-openclaw-a2a-task-plan-v2.6.2.md`
- `docs/hermes-openclaw-a2a-validation-v2.6.2.md`
- `docs/hermes-openclaw-a2a-review-v2.6.2.md`
- `docs/hermes-openclaw-a2a-task-plan-v2.6.3.md`
- `docs/hermes-openclaw-a2a-validation-v2.6.3.md`
- `docs/hermes-openclaw-a2a-review-v2.6.3.md`
- `docs/hermes-openclaw-a2a-runbook-v2.6.4.md`
- `docs/hermes-openclaw-a2a-file-inventory-v2.6.x.md`

- `docs/hermes-openclaw-a2a-precommit-audit-v2.6.x.md`

## 当前边界
- v2.6.0 包含一次历史受控 live two-worker evidence。
- v2.6.1/v2.6.2/v2.6.3/v2.6.4 不新增 live call。
- 当前未启用 cron / daemon / webhook / reverse loop。
- 当前没有提交 git commit。
