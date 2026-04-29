# Episodic Memory v0.30 Release Ledger

Date: 2026-04-29
Release: `v0.30`
Previous runtime milestone: `v0.20.0`

## Scope

This release advances the live episodic plugin toward the planned optional skill-candidate workflow:

- runtime plugin: `~/.hermes/plugins/episodic/`
- mirror copy: `~/.hermes/hermes-agent/user-plugins/episodic/`

## v0.30 capabilities added

### Optional skill-candidate feature flags
- added config defaults + resolver for:
  - `skill_candidates_enabled`
  - `skill_candidate_mode` (`off | detect-only | draft`)
  - `skill_candidate_auto_publish`
  - `skill_candidate_min_occurrences`
  - `skill_candidate_review_limit`
  - `skill_candidate_scan_source`
  - `skill_candidate_draft_model`

### Candidate persistence
- added `skill_candidates` SQLite table with:
  - fingerprint deduplication
  - occurrence tracking
  - evidence payloads
  - draft markdown storage
  - published skill linkage

### Detection + lifecycle
- deterministic JSONL-based skill-candidate detection
- post-session candidate scan in `on_session_end()`
- preserved non-detected statuses on re-detection
- safe config coercion/fallbacks
- draft timestamp capture

### Review tool surface
- `memory_list_skill_candidates`
- `memory_get_skill_candidate`
- `memory_update_skill_candidate`
- `memory_draft_skill_candidate`
- `memory_prepare_skill_candidate_for_creation`
- `memory_promote_skill_candidate`

## Important behavior boundaries

v0.30 still keeps publication explicit:
- candidate detection does **not** auto-create real skills
- drafting is explicit and separable
- `memory_prepare_skill_candidate_for_creation` returns a `skill_manage`-ready payload
- `memory_promote_skill_candidate` only marks the candidate published after the real skill has been created intentionally

## Validation

### Runtime plugin
```bash
cd ~/.hermes/plugins/episodic
source ~/.hermes/hermes-agent/venv/bin/activate
python -m pytest tests/test_skill_candidates.py -q
python -m pytest tests/test_journal_alerting.py tests/test_skill_candidates.py -q
```

Results:
- `8 passed`
- `10 passed`

### Mirror copy
```bash
cd ~/.hermes/hermes-agent/user-plugins/episodic
source ~/.hermes/hermes-agent/venv/bin/activate
python -m pytest tests/test_skill_candidates.py -q
```

Result:
- `8 passed`

### Independent audit
Auditor re-review verdict after blocker fixes: **PASS**

## Known non-blocking follow-up
- `scan_source=journal|both` is parsed but detection still uses JSONL only
- `auto_publish` and `draft_model` remain exposed but not deeply exercised yet
- README should be expanded to document the review/promotion flow for operators
