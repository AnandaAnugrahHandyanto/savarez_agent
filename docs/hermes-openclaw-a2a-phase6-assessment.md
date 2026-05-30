# Hermes ↔ OpenClaw A2A Phase 6 Assessment

## 结论

验收分类：`accepted_with_boundary`

当前已经验证的是 **Hermes 控制的 bounded two-turn A2A 对话**：Hermes 派发第 1 轮，验收 receipt；再基于第 1 轮摘要派发第 2 轮，继续验收 receipt，并由 Hermes 承载当前通道回流。

当前**不默认进入 OpenClaw 主动反向调用 Hermes / autonomous loop 实现**。

## 判断

- Hermes 仍然是 controller、任务派出者和最终验收者。
- OpenClaw 已能作为 bounded worker/peer 返回可验收结果。
- Phase 1 的 live run 已证明两轮 A2A 交流可完成。
- Phase 3 已证明失败路径与安全拦截可工作。
- Phase 4 已证明小批量 queue runner 可工作。
- Phase 5 已确认 recurring cron 模板存在并保持 paused。

## 不进入默认反向实现的原因

1. 反向调用会扩大信任边界。
2. 需要防循环、max_rounds、dedupe ledger、reverse action allowlist。
3. 需要明确 OpenClaw 能请求什么，不能请求什么。
4. 需要先验证 reverse path 的 origin dry-run 和 unsafe classification。
5. 用户当前要求是推进到 Phase 6 评估，不是直接启用 autonomous bidirectional daemon。

## 若以后进入反向实现，必须先补齐

- max_rounds / loop guard。
- reverse callback dedupe ledger。
- reverse request schema。
- strict allowed_actions / forbidden_actions。
- current-channel dry-run before send。
- unsafe / blocked / rejected 分类。
- secret scan。
- evidence manifest。

## 证据路径

- Phase 0：`docs/hermes-openclaw-a2a-current-state.json`
- Phase 1：`examples/live-phase1`
- Phase 3：`examples/v1.1.0`
- Phase 4：`examples/live-phase4-run`
- Phase 5 cron job：`170596628792`，当前 paused
- Phase 5 docs：
  - `docs/hermes-openclaw-a2a-v240-recurring-cron-template.md`
  - `docs/hermes-openclaw-a2a-v250-cron-monitor-race-hardening.md`

## Side effects

本 Phase 6 只做评估文档落盘。

未执行：

- 未开启反向自动调用。
- 未启用 daemon。
- 未启用 cron。
- 未重启 Hermes gateway。
- 未重启 OpenClaw。
