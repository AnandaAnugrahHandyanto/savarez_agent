# Governed Memory Context Injection Report — 2026-05-29

## Summary

Implemented a Hermes-core governed memory prefetch path at `MemoryManager.prefetch_all(...)`.

The new implementation supports an optional structured provider capability, `prefetch_candidates(...)`, and applies provider-agnostic governance before automatic memory context is rendered for injection:

- query-token normalization for natural-language relevance;
- profile/scope filtering;
- stale/supersession suppression;
- secret-bearing candidate exclusion;
- trust/relevance reranking;
- best-effort redaction/sanitization for legacy text-only `prefetch(...)` providers.

## Injection Seam

The production pre-turn seam is:

1. `agent/conversation_loop.py` calls `agent._memory_manager.prefetch_all(original_user_message)` once before the tool loop.
2. The returned text is cached in `_ext_prefetch_cache`.
3. On each API call, `build_memory_context_block(_ext_prefetch_cache)` wraps that returned text and appends it to the current user message as ephemeral, non-persisted context.

Governance therefore belongs inside `MemoryManager.prefetch_all(...)`, before `build_memory_context_block(...)` receives memory text.

## Files Changed

- `agent/memory_governance.py` — new pure governance helper module.
- `agent/memory_manager.py` — integrates optional structured candidates and legacy fallback governance at prefetch seam.
- `agent/memory_provider.py` — documents optional `prefetch_candidates(...)` provider capability.
- `tests/agent/test_memory_provider.py` — adds governed injection tests and a synthetic candidate provider.
- `docs/reports/2026-05-29-governed-memory-context-injection-report.md` — this report.

## Behavior Contract

### Structured providers

Providers may optionally implement:

```python
def prefetch_candidates(self, query: str, *, session_id: str = "") -> list[dict]: ...
```

Candidate dicts should include `content` or `text`; useful optional metadata includes `trust_score`, `profile`, `scope`, `status`, and `tags`.

If a provider does not override the base no-op `prefetch_candidates(...)`, Hermes treats the capability as absent and falls back to legacy `prefetch(...)`.

### Legacy providers

Legacy formatted text from `prefetch(...)` remains supported. Hermes applies forced redaction and drops obvious secret-bearing lines, but legacy text lacks enough structure for full profile/stale governance. Full governance requires structured candidates.

## Verification Evidence

### RED failures observed before implementation

New tests initially failed because `MemoryManager.prefetch_all(...)` returned no structured candidate output:

- `test_governed_prefetch_filters_scope_stale_and_secrets` failed: expected governed current fact in result, got `''`.
- `test_governed_prefetch_uses_query_normalization_for_relevance` failed: expected governance fact in result, got `''`.

A follow-up scope test also failed before the profile-scope correction because `default` had been incorrectly treated as a global scope.

### GREEN / regression checks

Focused governed tests:

```bash
venv/bin/python -m pytest \
  tests/agent/test_memory_provider.py::TestMemoryManager::test_governed_prefetch_filters_scope_stale_and_secrets \
  tests/agent/test_memory_provider.py::TestMemoryManager::test_governed_prefetch_uses_query_normalization_for_relevance \
  tests/agent/test_memory_provider.py::TestMemoryManager::test_governed_prefetch_preserves_legacy_text_provider_compatibility \
  tests/agent/test_memory_provider.py::TestMemoryManager::test_governed_candidate_failure_falls_back_to_legacy_prefetch -q
```

Result: `4 passed in 0.07s`.

Scope correction test:

```bash
venv/bin/python -m pytest tests/agent/test_memory_provider.py::TestMemoryManager::test_governed_prefetch_filters_scope_for_non_default_profile -q
```

Result: `1 passed in 0.04s`.

Adjacent memory/run-agent regression suite:

```bash
scripts/run_tests.sh \
  tests/agent/test_memory_provider.py \
  tests/run_agent/test_run_agent.py \
  tests/agent/test_memory_session_switch.py \
  tests/agent/test_memory_user_id.py
```

Result: `452 tests passed, 0 failed`.

Whitespace hygiene:

```bash
git diff --check -- \
  agent/memory_governance.py \
  agent/memory_manager.py \
  agent/memory_provider.py \
  tests/agent/test_memory_provider.py \
  docs/prds/2026-05-29-governed-memory-context-injection-prd.md \
  docs/goals/2026-05-29-governed-memory-context-injection-goal.md
```

Result: passed.

## Safety / Isolation

- No live default Hermes memory DB was used or mutated.
- Tests use synthetic in-memory providers/candidates only.
- No provider/model/config changes were made.
- The live Telegram gateway was not restarted.

## Remaining Limitations

- Full stale/profile governance requires structured provider candidates. Legacy text-only `prefetch(...)` providers only receive best-effort redaction/secret-line filtering.
- The active clean-holographic plugin has not yet been updated to expose `prefetch_candidates(...)`; until then, it continues through the legacy text path.
- No production rollout/restart has been performed in this turn.

## Recommended Follow-Up

- Add `prefetch_candidates(...)` to clean-holographic so Hermes core can apply full governed injection to live clean-holographic recall.
- Consider a small developer doc for provider authors once the structured candidate shape stabilizes across one real provider.
