# Hermes ↔ OpenClaw A2A v2.6.1 Task Plan

## 1. 结论

本版为 patch：`2.6.0 → 2.6.1`。

目标不是扩张 A2A 能力边界，而是补齐 v2.6.0 Phase 6 之后最需要的低风险验证能力：**统一校验 mock / dry-run / live two-worker 证据目录**。

## 2. 当前事实

v2.6.0 已完成：

- 本地 mock contract validation。
- dry-run two-worker runner。
- live two-worker A2A 样例。
- Hermes final acceptance report。

Phase 6 审核结论：`accepted_with_boundary`。

## 3. 本版目标

建立一个 stdlib-only evidence validator：

- 对 `examples/v2.6.0/mock-fixtures` 做 mock fixture 校验。
- 对 `examples/v2.6.0/dry-run-two-worker` 做 two-worker run 校验。
- 对 `examples/v2.6.0/live-two-worker` 做 live two-worker run 校验。
- 输出统一 JSON validation summary。
- 保持无外部副作用。

## 4. 范围

### 4.1 本版包含

- 新增 `scripts/validate_a2a_v260_evidence.py`。
- 新增 `examples/v2.6.0/evidence-validation-summary.json`。
- 新增 `docs/hermes-openclaw-a2a-validation-v2.6.1.md`。
- 新增 `docs/hermes-openclaw-a2a-review-v2.6.1.md`。
- 回读验证关键 marker 和 secret scan。

### 4.2 本版不包含

- 不执行新的 live A2A call。
- 不重启 Hermes gateway。
- 不重启 OpenClaw。
- 不启用 cron / daemon / webhook。
- 不固化 queue CLI / Kanban / Swarm 模板。
- 不做 OpenClaw → Hermes 反向调用。

## 5. 验收标准

本版 PASS 条件：

- validator 脚本能通过 `python3 -m py_compile`。
- validator 能同时校验 mock、dry-run、live 三类目录。
- mock summary `ok=true`。
- dry-run summary `ok=true`。
- live summary `ok=true`。
- live acceptance overall 为 `accepted_with_boundary`。
- live two-worker receipt 数为 2，accepted 数为 2。
- secret scan 无 forbidden literal。
- 输出 summary JSON 可回读。
- docs validation/review 存在并包含 v2.6.1 markers。

## 6. Side Effects

本版只读既有证据并写入 validator summary / validation docs。

不会修改生产配置，不会触发新的远端调用，不会重启服务。
