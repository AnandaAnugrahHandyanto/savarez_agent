# Episodic Memory Plugin

**Runtime status:** v0.30.0 active candidate with optional skill-candidate workflow

This directory is the live operational runtime for the episodic memory plugin used by Hermes.

## v0.30.0 release summary

v0.30 introduces the staged optional skill-candidate pipeline discussed for episodic memory.

### Included in v0.30.0
- optional skill-candidate config flags and resolver
- SQLite-backed `skill_candidates` persistence
- deterministic JSONL-based recurring-workflow detection
- post-session candidate scan from `on_session_end()`
- candidate review tools:
  - `memory_list_skill_candidates`
  - `memory_get_skill_candidate`
  - `memory_update_skill_candidate`
- candidate drafting and preparation tools:
  - `memory_draft_skill_candidate`
  - `memory_prepare_skill_candidate_for_creation`
- explicit publication marker:
  - `memory_promote_skill_candidate`
- hardened config coercion and status-preserving re-detection

### Workflow shape
1. session ends
2. detector may create/update candidate rows
3. user/agent reviews via list/get/update tools
4. draft is generated explicitly
5. provider can prepare a `skill_manage`-ready payload
6. real skill creation remains intentional and external
7. candidate can then be marked published

### Important boundaries
- no auto-publishing by default
- no implicit real skill creation inside the episodic provider
- `memory_prepare_skill_candidate_for_creation` prepares payload only
- actual skill creation should still go through `skill_manage`

### Validation
- runtime tests:
  - `python -m pytest tests/test_skill_candidates.py -q` → `8 passed`
  - `python -m pytest tests/test_journal_alerting.py tests/test_skill_candidates.py -q` → `10 passed`
- independent re-audit after blocker fixes: **PASS**

## Source-control note

The operational plugin currently lives in `~/.hermes/plugins/episodic/`, outside the `~/.hermes/hermes-agent` git worktree. The mirror under `~/.hermes/hermes-agent/user-plugins/episodic/` should stay aligned with runtime changes.
