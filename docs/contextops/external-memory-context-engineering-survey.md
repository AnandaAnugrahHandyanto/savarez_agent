# External memory/context-engineering survey for ContextOps/ESE

> **Lane anchor:** This is a `#contextops` research note. It is documentation-only and does not add runtime behavior, mutation paths, gateway hooks, prompt-builder changes, or Hermes upstream obligations.
>
> **Purpose:** Translate external memory/context-engineering methods into concrete Epistemic State Engine (ESE) design implications while preserving the ContextOps distinction: ESE restores an unfinished epistemic state, not just retrieved facts.

## Executive conclusion

Most external systems improve agent memory by deciding what to store, retrieve, consolidate, or inject. ContextOps/ESE should borrow their operational mechanisms, but not their framing. The core ESE question is:

```text
What unfinished cognitive phase should the next answer resume, and what must it avoid flattening?
```

That means `active_thread`, `cognitive_phase`, `unresolved_tensions`, `safe_refs`, a `versioned state contract`, a temporal provenance graph, explicit state lifecycle rules, and fail-closed compaction are first-class design objects — not add-ons to generic RAG.

## Source map

| Method family | Source URLs | Useful pattern | ContextOps/ESE translation |
| --- | --- | --- | --- |
| MemGPT / Letta | https://arxiv.org/abs/2310.08560, https://docs.letta.com/guides/core-concepts/stateful-agents/ | Virtual context management: working memory, archival memory, paging, and self-editing memory for long-running agents. | Treat ESE state as paged cognitive state: small `context_pack` in working context, larger archival evidence behind `safe_refs`, and explicit self-edit operations gated by provenance. |
| LangMem | https://langchain-ai.github.io/langmem/ | Separates semantic, episodic, and procedural memory; supports hot/background memory and prompt refinement loops. | Map memory types to ESE roles: semantic facts stay background, episodic events become provenance, procedural preferences become response-policy hints; `active_thread` is selected by unresolved cognitive pressure, not semantic similarity alone. |
| Zep / Graphiti | https://help.getzep.com/overview, https://github.com/getzep/graphiti, https://arxiv.org/abs/2501.13956 | Temporal knowledge graph over episodes, facts, invalidation, and provenance. | Build a temporal provenance graph for `threads`, `tensions`, and `state_deltas`: preserve when a claim was true, superseded, contradicted, or low-confidence. |
| OpenAI context engineering / personalization | https://developers.openai.com/cookbook/examples/agents_sdk/context_personalization, https://developers.openai.com/cookbook/examples/agents_sdk/session_memory, https://developers.openai.com/cookbook/examples/agents_sdk/building_reliable_agents_memory_compaction | State object, memory selection, distillation, consolidation, session memory, and context shaping. | Use an explicit `versioned state contract` and context-shaping step: choose only the fields needed to restore `cognitive_phase`; compaction must include `restore` and `avoid`, not just summary text. |
| Agentic Memory / AgeMem | https://arxiv.org/abs/2601.01885, https://github.com/y1y5/AgeMem | Memory operations are agent policy decisions, not passive storage calls. | Make state operations explicit actions: create/update/suppress/archive/reactivate `active_thread` and `unresolved_tensions`, each with evidence refs, confidence, and review policy. |
| Working-memory limits, proactive interference, lost-in-the-middle | Ambiguous user shorthand: no verified paper titled exactly `Working Memory Limits in LLMs`. Closest match: *Unable to Forget: Proactive Interference Reveals Working Memory Limits in LLMs Beyond Context Length* — https://arxiv.org/abs/2506.08184. Related: *Self-Attention Limits Working Memory Capacity of Transformer-Based Models* — https://arxiv.org/abs/2409.10715; *Working Memory Capacity of ChatGPT* — https://arxiv.org/abs/2305.03731; *Lost in the Middle: How Language Models Use Long Contexts* — https://arxiv.org/abs/2307.03172. | Long context can behave like unstable working memory; extra retrieved context can interfere; mid-context information is underused. | Do not equate large context with continuity. Prefer small phase-restoration packets, adversarial exclusion of stale/conflicting memory, and fail-closed compaction when provenance or authority is ambiguous. |

## What ContextOps should borrow

### 1. Virtual memory, but for cognitive phase

MemGPT/Letta's useful insight is not merely "more memory". It is that agents need operating-system-like control over what is in the limited working context and what stays paged out. For ContextOps:

- Working context should contain only the current `cognitive_phase`, selected `active_thread`, live `unresolved_tensions`, and a few `restore` / `avoid` instructions.
- Archival evidence should stay outside the prompt behind `safe_refs` unless exact wording is necessary.
- Paging decisions should be auditable: why this thread entered the context pack, why another was excluded, and which evidence refs support the selection.
- Self-editing memory is allowed only as a proposed `state_delta`; raw event evidence remains append-only.

### 2. Memory taxonomy, but not taxonomy-first routing

LangMem's semantic/episodic/procedural split is useful, but ESE should not route from taxonomy alone.

- Semantic: stable facts and definitions. These should rarely dominate `cognitive_phase`.
- Episodic: event traces and decisions. These become provenance and temporal anchors.
- Procedural: style, safety, and workflow tendencies. These become policy hints.
- ESE-specific: `active_thread` and `unresolved_tensions`. These preserve unfinished thought-lines that may cross topics and memory classes.

Design implication: the router must score unresolvedness, contradiction density, explicit reactivation, lane ownership, and contamination risk alongside semantic similarity.

### 3. Temporal graph, but with epistemic invalidation

Zep/Graphiti points toward a graph whose edges and facts have time, source, and episode provenance. ContextOps should use this idea for epistemic state, not just facts:

- `thread` nodes: durable cognitive lines.
- `tension` nodes: live unresolved pressure.
- `state_delta` nodes: proposed changes after a turn.
- `evidence` nodes: safe references to raw events, not raw transcript dumps.
- temporal edges: created, reinforced, contradicted, reframed, resolved, archived, reactivated.

This temporal provenance graph should support invalidation: a previous context pack or compaction can be marked stale, superseded, contaminating, or low-authority without deleting the raw evidence.

### 4. Context shaping, but under a versioned state contract

OpenAI's context-engineering cookbooks reinforce that useful memory is selected and shaped, not blindly appended. ESE should make this a formal contract:

```yaml
ese_state_contract:
  schema_version: contextops.ese.v0
  active_thread:
    id: string
    evidence_refs: [safe_ref]
  cognitive_phase:
    mode: string
    confidence: low | medium | high
  unresolved_tensions:
    - id: string
      unresolved_core: string
      pressure: 0.0-1.0
      evidence_refs: [safe_ref]
  restore:
    - string
  avoid:
    - string
  exclusions:
    - ref: safe_ref
      reason: stale | contaminating | low_score | wrong_lane | superseded
```

The contract is intentionally smaller than transcript history. Its job is to restore the response starting point and prevent contamination.

### 5. Memory operations as policy actions

Agentic Memory/AgeMem reframes memory management as an agent policy. ESE should make state changes explicit, reviewable operations:

- `create_thread`
- `reactivate_thread`
- `update_tension`
- `reframe_tension`
- `resolve_tension`
- `archive_thread`
- `suppress_candidate_context`
- `propose_long_term_memory_candidate`

Each operation needs operation type, evidence refs, confidence, authority tier, and lifecycle impact. Low-confidence extraction should produce `NEEDS_REVIEW`, not a silent state mutation.

### 6. Working-memory limits as a safety requirement

The working-memory and lost-in-the-middle literature is a warning against assuming that larger context windows solve continuity. The shorthand "Working Memory Limits in LLMs" is ambiguous: this survey did not verify a paper with that exact title. The nearest match and related evidence should be cited claim-by-claim:

- *Unable to Forget: Proactive Interference Reveals Working Memory Limits in LLMs Beyond Context Length* supports the stale-state interference claim: outdated or overwritten values can keep influencing answers even when newer values are present near the query.
- *Self-Attention Limits Working Memory Capacity of Transformer-Based Models* supports the capacity/attention-dispersion claim: information being inside the context does not guarantee stable manipulation as working memory load rises.
- *Working Memory Capacity of ChatGPT* supports the empirical working-memory-limit claim: LLM-style systems can show capacity-limit patterns even under direct task prompting.
- *Lost in the Middle: How Language Models Use Long Contexts* supports the context-burial claim: relevant information placed in the middle of a long context can be underused.

ESE should treat oversized context as a failure mode:

- More retrieved text can increase proactive interference.
- Compactions can fossilize outdated interpretations.
- Mid-context details can be ignored even when present.
- Long summaries can flatten active tension into stale topic labels.

Design implication: fail-closed compaction. If a compaction cannot preserve unresolved pressure, authority ranking, and exclusions, it should not be used for hydration.

## ESE design implications

### Required state fields

| Field | Why it exists | Borrowed lesson |
| --- | --- | --- |
| `active_thread` | Restores the live cognitive line rather than a topic. | Virtual paging + memory selection. |
| `cognitive_phase` | Restores the stance/mode of reasoning. | Context shaping and personalization. |
| `unresolved_tensions` | Preserves what remains deliberately unresolved. | ESE-specific addition beyond RAG/memory platforms. |
| `safe_refs` | Keeps evidence auditable without leaking raw transcript/path/secret content. | Temporal provenance and fail-closed safety. |
| `versioned state contract` | Prevents ad-hoc prompt packets and schema drift. | OpenAI-style state object + product boundary contract. |
| `temporal provenance graph` | Tracks creation, contradiction, supersession, and reactivation over time. | Zep/Graphiti temporal graph pattern. |
| `state lifecycle` | Distinguishes active, dormant, resolved, archived, stale, and contaminating state. | Agentic memory operations as policy. |
| `fail-closed compaction` | Blocks unsafe summaries from becoming authority. | Working-memory limit and proactive-interference risk. |

### State lifecycle proposal

```text
candidate -> active -> reinforced -> reframed -> dormant -> reactivated
                         |             |          |
                         v             v          v
                    superseded     resolved    archived
                         |
                         v
                  contaminating / suppress
```

Lifecycle transitions must be evidence-backed. `resolved` and `archived` do not erase evidence; they change whether the state is eligible for future context packs. `contaminating` means a previous state packet is known to mislead future responses and should be excluded unless explicitly requested for audit.

### Compaction contract

A ContextOps compaction is acceptable only if it preserves:

1. the current `cognitive_phase`,
2. the `active_thread`,
3. live `unresolved_tensions`,
4. authority ranking and recent user corrections,
5. exclusions / `avoid` items,
6. `safe_refs` to evidence,
7. confidence and lifecycle state.

A summary that says only "we discussed memory systems" is not a compaction. It is flattening contamination.

## How ContextOps differs from generic RAG/memory platforms

Generic RAG/memory platforms optimize for retrieving relevant information. ContextOps/ESE optimizes for resuming an unfinished epistemic state.

| Generic memory/RAG question | ContextOps/ESE question |
| --- | --- |
| What facts are relevant? | What thought-line is still active? |
| Which chunks match the query? | Which tension is being reactivated? |
| What should be summarized? | What cognitive pressure must remain unresolved? |
| How much history fits? | What is the smallest phase-restoration packet? |
| What should be remembered long-term? | What delta changes the next response, and is it safe to promote? |

This difference matters operationally: a retrieved fact can be correct and still damage continuity if it shifts the model into the wrong cognitive phase or prematurely resolves a tension the user intended to keep open.

## Guardrails

- Do not let semantic similarity alone activate a thread.
- Do not inject raw transcripts when a `safe_ref` is enough.
- Do not let old compaction override a newer user correction.
- Do not promote working state to durable memory automatically.
- Do not treat a temporal graph as authority; it is provenance plus candidate state until policy gates approve it.
- Do not let `cognitive_phase` become a tone label. It should encode epistemic stance: exploratory, anomaly-investigation, anti-premature-closure, verification, synthesis, or decision mode.
- Do not use ContextOps docs to imply a Hermes upstream destination; Hermes remains a dogfood adapter/client.

## Recommended next product slice

Title:

```text
Define ESE v0 state contract and lifecycle fixtures
```

Acceptance criteria:

- Add a docs-only or fixture-only `contextops.ese.v0` contract containing `active_thread`, `cognitive_phase`, `unresolved_tensions`, `restore`, `avoid`, `safe_refs`, exclusions, confidence, and lifecycle state.
- Add fixture examples for: normal reactivation, stale compaction suppression, wrong-lane exclusion, temporal contradiction, and unresolved-tension preservation.
- Add a fail-closed review checklist: if a context pack lacks evidence refs, authority ranking, or exclusions, it is rejected.
- Keep runtime behavior unchanged; no gateway integration, prompt-builder mutation, memory writes, or dispatch.

## Review checklist

- [ ] Only `docs/contextops/` documentation changed for this research slice.
- [ ] All source URLs above are present and directly tied to design implications.
- [ ] The note explicitly says ESE restores unfinished epistemic state, not just retrieved facts.
- [ ] Required design terms appear: `active_thread`, `cognitive_phase`, `unresolved_tensions`, `safe_refs`, `versioned state contract`, `temporal provenance graph`, `state lifecycle`, `fail-closed compaction`.
- [ ] The recommended next slice is product/contract work, not runtime mutation.
- [ ] Forbidden paths remain untouched: `gateway/run.py`, `agent/prompt_builder.py`.
