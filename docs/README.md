# 文档索引

## 验收 / 迁移

- [OpenClaw 多智能体团队吸收验收报告](acceptance/openclaw-multi-agent-team-absorption.md)
- [OpenClaw 多智能体团队对外汇报稿](acceptance/openclaw-multi-agent-team-external-brief.md)
- [OpenClaw 多智能体团队能力映射矩阵](architecture/openclaw-team-capability-matrix.md)
- [OpenClaw 剩余可吸收能力审计](architecture/openclaw-remaining-absorption-opportunities.md)
- [OpenClaw 高级多智能体语义边界说明](architecture/openclaw-advanced-multi-agent-semantics.md)
- [OpenClaw 多智能体团队 P1 验收补充](validation/openclaw-team-acceptance.md)
- [QMT 盘中链路 live 验收说明](validation/qmt-intraday-live-acceptance.md)
- [官方 Skills 吸收盘查（本轮）](architecture/hermes-official-skills-absorption-audit-round.md)
- [A股短线高价值官方技能吸收盘查（2026-04-12）](architecture/a-share-official-skills-absorption-audit-2026-04-12.md)
- [A股短线官方技能能力矩阵（2026-04-12）](architecture/a-share-official-skills-capability-matrix-2026-04-12.md)
- [高价值剩余可吸收能力审计（2026-04-12）](architecture/high-value-remaining-absorption-audit-2026-04-12.md)
- [A股短线官方技能动态验收补充（qmd / parallel-cli / cron 闭环）](architecture/a-share-official-skills-absorption-audit-2026-04-12.md)
- [文档生产力吸收审计（DOCX / XLSX / PDF）](architecture/document-productivity-absorption-audit-2026-04-12.md)
- [Migrating from OpenClaw to Hermes Agent](migration/openclaw.md)
- [Honcho Integration Spec](honcho-integration-spec.md)

## 推荐阅读顺序

1. **先看结论**：[`acceptance/openclaw-multi-agent-team-absorption.md`](acceptance/openclaw-multi-agent-team-absorption.md)
2. **再看能力拆解**：[`architecture/openclaw-team-capability-matrix.md`](architecture/openclaw-team-capability-matrix.md)
3. **然后看高级语义边界**：[`architecture/openclaw-advanced-multi-agent-semantics.md`](architecture/openclaw-advanced-multi-agent-semantics.md)
4. **再看 skills 吸收盘查**：[`architecture/hermes-official-skills-absorption-audit-round.md`](architecture/hermes-official-skills-absorption-audit-round.md)
5. **最后看 P1 边界**：[`validation/openclaw-team-acceptance.md`](validation/openclaw-team-acceptance.md)

## CI / Smoke 建议

- 已落地 CI job：
  - `.github/workflows/openclaw-team-absorption-smoke.yml`
  - `.github/workflows/official-skills-absorption-smoke.yml`

- 推荐最小 smoke 子集：

```bash
pytest -q \
  tests/test_openclaw_multi_agent_team_e2e.py \
  tests/test_hermes_team_registry_api.py \
  tests/test_hermes_team_audit_diff.py \
  tests/tools/test_delegate.py \
  tests/agent/test_memory_provider.py
```

- 推荐官方 skills 吸收 smoke 子集：

```bash
python3 website/scripts/extract-skills.py
pytest -q \
  tests/skills/test_telephony_skill.py \
  tests/skills/test_memento_cards.py \
  tests/skills/test_youtube_quiz.py
```

- 建议将上述子集独立为 “OpenClaw Team Absorption Smoke” 与 “Official Skills Absorption Smoke” 两个 CI job，用于快速判断：
  - Hermes-native team registry 是否正常
  - delegate/subagent observability 是否正常
  - 最小 `task -> approval -> cron_upsert -> registry -> list` 链路是否仍通过
  - optional skills 的站点数据构建与关键脚本是否正常

## 对外汇报口径

> Hermes 已完成 OpenClaw 多智能体团队运行底座的吸收与默认写路径切流；task / approval / registry / cron 已 Hermes-native 化并通过动态验收。高级多智能体语义（observer / peerPerspective / agentPeerMap / multi-agent setup 自动迁移）仍属部分吸收，当前不宣称 100% 全量吸收完成。与此同时，官方 Skills 吸收链路已完成一批高价值 optional skills 的目录、文档与 Skills Hub 数据闭环，当前重点转入动态验收与高复用能力补强。
