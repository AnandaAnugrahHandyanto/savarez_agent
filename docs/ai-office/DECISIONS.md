# Hermes AI Office — DECISIONS

This file records decisions for the Hermes AI Office / Pixel-Agent Dashboard project.

## Decision format

Each decision should include:

```md
## D### — Title

Date:
Status: proposed | accepted | superseded

Decision:

Rationale:

Implications:

Supersedes:
```

---

## D001 — Start with planning before implementation

Date: 2026-05-08
Status: accepted

Decision:

The project will begin with detailed planning, staged research, product requirements, and architecture design. No dashboard implementation will begin until the user explicitly approves an implementation stage.

Rationale:

The domain is large and spans agent observability, browser UI, Telegram topic provenance, Kanban, cron, gateway routing, and possible pixel/game visualization. Implementing too early risks building the wrong abstraction.

Implications:

- Stage 0–5 are planning/research/design first.
- Stage 6 is the earliest read-only implementation stage.
- Code changes, dependency additions, and service restarts require explicit approval.

---

## D002 — Use external handoff documents for `/new` continuity

Date: 2026-05-08
Status: accepted

Decision:

The project will preserve context across `/new` sessions using at least `STATUS.md` and `NEXT.md` under `docs/ai-office/`.

Rationale:

Hermes `/goal` is session-scoped. A fresh `/new` helps keep work clean, but it also risks losing project context unless the state is externalized.

Implications:

- Before `/new`, update `STATUS.md` and `NEXT.md`.
- After `/new`, read `NEXT.md` and `STATUS.md` first.
- The suggested `/goal` text is stored in `NEXT.md`.

---

## D003 — Build Hermes-native observability before pixel UX

Date: 2026-05-08
Status: accepted

Decision:

The first functional MVP should be a read-only Hermes-native dashboard using Kanban, cron, gateway/topic, and session/provenance data. Pixel-office visualization should come after the data layer is trustworthy.

Rationale:

Pixel UX is valuable only if it represents real operational state accurately. Hermes already has task/cron/gateway data, but provenance and APIs need to be designed first.

Implications:

- Read-only dashboard MVP is Stage 6.
- Pixel visualization MVP is Stage 8.
- Pixel Agents/Smallville research informs UX but does not drive early data architecture.

---

## D004 — Treat Pixel Agents and Smallville as references pending audit

Date: 2026-05-08
Status: accepted

Decision:

Pixel Agents, Pixel Agents standalone/Codex forks, and Smallville/Generative Agents will be audited before any adoption decision. No code will be copied, vendored, or forked until license and architecture are reviewed.

Rationale:

Search results suggest Pixel Agents is directly relevant, but Hermes has a different architecture and source of truth. Smallville is conceptually relevant but likely not directly reusable.

Implications:

- Stage 1 research must include license, stack, architecture, and adopt/reject matrix.
- Direct code adoption remains unapproved.

---

## D005 — Keep early dashboard read-only and localhost-first

Date: 2026-05-08
Status: accepted

Decision:

Early AI Office surfaces should be read-only and localhost-first. Browser control actions and remote access are deferred.

Rationale:

The dashboard may expose operational state and could eventually mutate tasks/services. Starting read-only reduces risk and makes security review simpler.

Implications:

- No reclaim/reassign/retry/approve actions in MVP.
- No public binding or remote exposure by default.
- Security review is required before any control layer.

---

## D006 — Use Pixel Agents as reference, not implementation base

Date: 2026-05-08
Status: accepted

Decision:

Stage 1 research concludes that `pablodelucca/pixel-agents` and `rolandal/pixel-agents-standalone` are strong UX/architecture references, but Hermes will not vendor/fork/copy them before a later explicit implementation approval. The MVP remains Hermes-native read-only observability.

Rationale:

Pixel Agents is MIT-licensed and relevant, but its core lifecycle is VS Code/Claude oriented. The standalone fork proves browser feasibility but uses a parallel Express/WebSocket server and Claude file watchers. Hermes already has a dashboard and real Kanban/cron/gateway/session state.

Implications:

- Stage 2 proceeds to Hermes data-source audit.
- Pixel renderer reuse is deferred to Stage 8 review.
- Asset licensing must be audited separately before any visual asset reuse.

---

## D007 — Use `/goal` as a session guardrail, not durable project state

Date: 2026-05-08
Status: accepted

Decision:

Use Hermes `/goal` at the start of bounded AI Office work sessions to constrain scope, judge completion, and prevent drift into unapproved implementation or service/config mutations. Continue to use `STATUS.md`, `NEXT.md`, `DECISIONS.md`, `OPEN-QUESTIONS.md`, and stage documents as the durable cross-session memory.

Rationale:

`/goal` is useful for one session's operating contract and progress loop, but it is session-scoped. The AI Office project intentionally spans many `/new` sessions, so durable state must remain in repository documents. Explicit approval is still required for mutating actions.

Implications:

- Each fresh Stage 3–5 planning session can start with a stage-specific `/goal`.
- Stage 6+ implementation sessions should use `/goal` only after the user approves the implementation slice.
- `/goal` should not be used as a replacement for handoff docs, Kanban tasks, cron jobs, or explicit mutation approval.

---

## D008 — Define OfficeState as read-only redacted projection

Date: 2026-05-08
Status: accepted

Decision:

The AI Office data contract should use a normalized `OfficeState` projection over real Hermes state. `OfficeState` is read-only, redaction-first, and not a new source of truth.

Rationale:

Stage 2 showed useful state is spread across Kanban SQLite boards, cron JSON jobs/output files, session SQLite metadata/messages, gateway Telegram runtime source objects, cron delivery strings, and handoff docs. A browser office UI needs one consistent DTO, but copying raw source data directly into the UI would leak private transcripts, prompts, tool outputs, cron scripts, and secrets.

Implications:

- Future implementation should add serializers/adapters that project safe fields into `OfficeState`.
- Missing provenance must be represented as `unknown`, not inferred or fabricated.
- Tests should verify redaction boundaries before user-visible rollout.
- Pixel renderer, if added later, must consume `OfficeState` rather than reaching into Kanban/cron/session internals directly.

---

## D009 — Keep Stage 6 MVP operational-map-first, not pixel-first

Date: 2026-05-08
Status: accepted

Decision:

The first read-only MVP should be an operational map/table/card view over rooms, work items, automations, topics, events, and provenance. Pixel/game visualization remains deferred until data APIs and provenance are trustworthy.

Rationale:

Stage 3 user stories and IA prioritize blocked work, failed automation, source health, redaction, and missing provenance. Pixel UI is still valuable, but it can obscure operational clarity if introduced before exact safe metadata exists.

Implications:

- Stage 5 technical architecture should design non-pixel components first.
- Stage 8 remains the pixel office visualization stage.
- Acceptance criteria for Stage 6 do not require sprites, PixiJS, Phaser, Canvas, or copied Pixel Agents assets.


---

## D010 — Use a profile-local topic registry/projection for topic labels

Date: 2026-05-08
Status: accepted

Decision:

Telegram topic labels for AI Office should come from a profile-local registry/projection with explicit source and confidence, not from hardcoded product constants or raw Telegram API objects.

Rationale:

Stage 2 found topic context exists in gateway runtime source objects, cron delivery strings, home-channel config, and planning memory, but no clean canonical topic registry. Stage 4 needs topic display to be useful while preserving privacy and avoiding fabricated labels.

Implications:

- Stage 5 should choose JSON-file vs SQLite-table storage for the registry.
- Known local topic ids are planning seed candidates only.
- Unknown topics must render as unknown/id-safe fallback.
- Future registry editing is a mutation feature and is not part of the read-only MVP.

---

## D011 — Separate origin provenance from delivery/subscription routing

Date: 2026-05-08
Status: accepted

Decision:

AI Office provenance should model origin relations such as `created_from` separately from delivery/subscription relations such as `delivered_to` and `subscribed_to`.

Rationale:

Cron delivery targets and Kanban notification subscriptions tell where output/updates go; they do not prove where a task or session originated. Conflating destination with origin would fabricate context.

Implications:

- `OfficeState.provenance` should include relation type and confidence.
- Existing tasks can have known delivery but unknown origin.
- UI should be able to say “destination known, origin unknown.”

---

## D012 — Backfill only from structural metadata, never from content inference

Date: 2026-05-08
Status: accepted

Decision:

Legacy provenance backfill should use safe structural fields only and must not infer source/topic/session links from raw prompts, Telegram message text, task body/result, session snippets, logs, or tool output.

Rationale:

Content inference risks privacy leaks and false provenance. Stage 2 showed many schemas lack first-class provenance, so honest `unknown` is safer than plausible guesses.

Implications:

- Backfilled rows need `confidence` and `missing_reason`.
- Session `source=telegram` can prove platform, but not topic/thread when no field exists.
- Kanban legacy tasks without source fields remain `unknown_provenance`.
- Redaction tests should include negative cases for fabricated links.

---

## D013 — Treat local internal ids as mode-dependent display, not public data

Date: 2026-05-08
Status: accepted

Decision:

Chat ids, thread ids, message ids, session ids, task ids, and local paths are internal routing/debug metadata. A localhost MVP may show some of them with clear internal labeling, but future remote mode should hash, hide, or label-only them after security review.

Rationale:

These identifiers are not credentials, but they reveal private infrastructure and context. Stage 3 already established localhost-first posture, and Stage 4 privacy classification makes remote display stricter.

Implications:

- Stage 5 should define display modes and defaults.
- Serializers should separate internal join ids from browser display ids.
- Remote mode is deferred and should not be accidentally enabled by Stage 6.
