# DECISION JOURNAL

## 2026-04-22 — Build the extract set as vertical slices
**Decision:** Implement ratchet, Spar, judge, scars, campaigns, and the proving matrix as small extensions on top of Hermes' existing checkpoint, tool, and session primitives.
**Why:** Hermes already has the correct seams. Extending them keeps the blast radius lower than importing a second orchestration architecture.
**Alternatives rejected:**
- Replace Hermes checkpointing with a separate ratchet subsystem — rejected because it duplicates working rollback primitives.
- Fold Spar/Judge into MoA — rejected because MoA is consensus reasoning while Spar is an adversarial review gate.
- Add UI work first — rejected because the backend capability is the leverage point and UI would slow the rollout.
**Revisit if:** The new backend features prove valuable enough that Scarf needs first-class controls for them.

## 2026-04-22 — Keep Spar defaults fully direct-provider
**Decision:** Set Spar to `xiaomi/mimo-v2-pro` for building, `minimax/MiniMax-M2.7-highspeed` for review, and `deepseek/deepseek-reasoner` for the independent judge.
**Why:** The user already has direct API access for all three providers, and this keeps Spar aligned with the shipped direct-provider MoA stack while avoiding OpenRouter coupling.
**Alternatives rejected:**
- Reuse MoA's OpenRouter-era routes — rejected because the branch goal is native direct-provider routing.
- Use Xiaomi for both builder and reviewer — rejected because adversarial review benefits from model diversity.
**Revisit if:** Hermes gains a first-class per-profile coding-mode router with configurable build/review/judge roles.
