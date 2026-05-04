# LangMem eval rubric for Hermes

## Goal

Score Hermes' LangMem behavior in separable layers so failures do not collapse into one vague pass or fail.

The eval harness should report four dimensions per scenario:

- `extraction_score`
- `reconciliation_score`
- `retrieval_score`
- `injection_usefulness_score`

It should also write a machine-readable artifact to `tmp/langmem-eval/latest.json` for quick diffing and human review.

## Scenario families

The first harness covers four deterministic families:

1. **Explicit preference writes**
   - direct `langmem_conclude` writes
   - verifies storage shape and basic recall
2. **Preference correction / supersession**
   - old fact should be retired conservatively and the new fact should dominate recall
3. **Cross-session recall**
   - memory written in one session should remain retrievable in a later session for the same user
4. **Retrieval under lexical ambiguity**
   - when multiple memories partially match the same query, the better-confirmed memory should rank first

## Dimension definitions

### Extraction score

Measures whether the relevant durable fact or episode was actually created in storage.

Count this as a failure when:
- the expected row is missing
- the expected content was not persisted
- the stored shape is malformed enough that later stages cannot trust it

### Reconciliation score

Measures whether Hermes merged or retired memory state correctly.

Count this as a failure when:
- superseded facts remain live when the scenario expects them retired
- metadata needed for later reasoning is missing or wrong
- confirmation counts or session provenance do not reflect repeated evidence

### Retrieval score

Measures whether search or direct lookup returns the right memory for the scenario.

Count this as a failure when:
- the right memory is absent from results
- a stale or irrelevant memory outranks the intended one
- user scoping leaks the wrong user's memory into results

### Injection usefulness score

Measures whether the retrieved output is actually useful for the next turn.

Count this as a failure when:
- the provider returns the wrong fact even if the store contains the right row
- the output contains stale contradictions that would mislead the assistant
- the retrieved result is technically present but not usable as a clean prompt injection

## Failure interpretation

Use this table when reading `latest.json`:

| Failure pattern | Likely cause |
|---|---|
| extraction low, others low | write path or row creation broken |
| extraction high, reconciliation low | merge/delete/session metadata logic broken |
| extraction + reconciliation high, retrieval low | search ranking or lookup path broken |
| retrieval high, injection usefulness low | provider formatting or direct/fallback presentation broken |

## Important guardrails

- Keep this harness deterministic. Do not rely on live LLM calls for the baseline eval.
- Prefer direct store/provider assertions over fuzzy judgments.
- Use this harness to localize failures before considering embeddings or backend changes.
- Do not treat profile lookup as a search problem when the typed profile lane can answer directly.

## Next expansion ideas

Later versions can add:
- typed profile extraction quality checks
- episode-lane usefulness checks
- adversarial lexical collisions
- human-reviewed prompt-injection usefulness samples
- regression snapshots across provider versions
