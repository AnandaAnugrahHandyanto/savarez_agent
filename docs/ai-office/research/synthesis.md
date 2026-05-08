# Hermes AI Office — Stage 1 Research Synthesis

Last updated: 2026-05-08 11:32 KST
Status: Stage 1 synthesis. Documentation-only; no implementation approved.

## Executive conclusion

The research supports the original planning direction:

1. Build Hermes-native read-only observability first.
2. Use Pixel Agents as the primary UX/renderer inspiration.
3. Use the standalone fork as proof that the browser-dashboard shape is feasible.
4. Use Smallville/Generative Agents only as conceptual inspiration for legibility, memory/reflection/speech bubbles later.
5. Do not vendor, fork, add dependencies, or implement pixel UI until after Hermes data-source audit, product requirements, provenance design, and architecture design are complete.

## Reference ranking

| Rank | Reference | Value for Hermes | Adoption posture |
|---:|---|---|---|
| 1 | `pablodelucca/pixel-agents` | Best pixel-office UX and renderer/state reference | Study now; possible renderer inspiration later |
| 2 | `rolandal/pixel-agents-standalone` | Best browser separation reference | Study now; do not copy parallel server |
| 3 | Agent observability products | Best operational patterns | Adopt concepts for read-only MVP |
| 4 | Smallville / Generative Agents | Best narrative/legibility concepts | Inspiration only; no synthetic simulation |
| 5 | `pixel-agents-codex` fork | Secondary Codex-oriented reference | Low priority |

## Adopt now

Adopt immediately into planning/product language, not code:

- Office metaphor: boards as rooms, assignees as characters, tasks as desks/cards, cron as automation bots.
- Real-time status mapping: running, waiting, permission-needed/blocked, idle, done.
- Browser server/UI separation: Hermes dashboard backend feeds React UI.
- Safe event stream concept: chronological task/automation activity drives details and future speech bubbles.
- Read-only-first safety model.

## Defer

- Pixel renderer implementation.
- PixiJS/Phaser/Canvas dependency decision.
- Direct code reuse from Pixel Agents.
- Asset import or sprite reuse.
- LLM-generated summaries/speech bubbles.
- Browser-side mutation actions.
- Remote dashboard exposure.

## Reject for MVP

- Separate Express/Node server beside Hermes dashboard.
- VS Code extension host integration.
- Claude JSONL watcher as source of truth.
- Synthetic Smallville-style autonomous society.
- Raw transcript browser by default.
- Any UI that fabricates agent intent/state.

## Recommended product order confirmed by research

1. Stage 2: read-only Hermes data-source audit.
2. Stage 3: product requirements and IA.
3. Stage 4: provenance/routing design.
4. Stage 5: technical architecture.
5. Stage 6: read-only dashboard MVP, only after explicit approval.
6. Stage 8: pixel office visualization, only after reliable data exists.

## MVP boundary after research

The first implementation MVP should not be the pixel game. It should be a read-only operational dashboard that answers:

- What is running?
- What is blocked?
- What completed recently?
- Which boards/tasks are active?
- Which cron jobs are healthy or failing?
- Which Telegram topics map to which work streams?
- What safe metadata exists for task/session provenance?

Pixel visualization becomes a second projection over the same `OfficeState` model.

## Main risks surfaced

1. Asset licensing risk from Pixel Agents forks.
2. Architecture mismatch between Hermes dashboard and VS Code/Claude-specific assumptions.
3. Privacy risk from exposing raw prompts/transcripts/tool args.
4. Novelty risk: pixel UI could obscure operational clarity.
5. Parallel-server risk from copying standalone fork too literally.
6. Provenance gap: Hermes tasks may not currently retain Telegram topic/message origin.

## Decision recommendation

Accept D003: “Build Hermes-native observability before pixel UX.”

After this synthesis, proceed to Stage 2: Hermes current-state and data-source audit.
