# Episodic Memory Plugin

**Runtime status:** v0.20.0 active candidate validated on 2026-04-28

This directory is the live operational runtime for the episodic memory plugin used by Hermes.

## v0.20.0 release summary

v0.20 promotes the journal pipeline from a repaired candidate to a validated release.

### Included in v0.20.0
- repaired `journal.py` import/write path
- successful real-session smoke generation from JSONL
- loud-failure artifacts for journal-write exceptions
- best-effort Telegram alerting for journal failures
- reconciliation scan for orphaned JSONL sessions with no matching journal artifact
- successful organic session-finalization validation

### Live validation
- previous organically closed session JSONL: `~/.hermes/memory/sessions/20260428_064238_57eb8dc7.jsonl`
- matching live journal artifact: `~/wiki/session-recordings/2026-W18/2026-04-28_20260428_064238_57eb8dc7.md`
- verified summary fidelity: `10 user turns, 10 assistant turns, 11 tool calls, ~59 min duration`

### Tests
- `python -m pytest tests/test_journal_alerting.py -q` → `2 passed`
- `python -c "import episodic.provider, episodic.journal; print('ok')"` → `ok`

## Source-control note

The operational plugin currently lives in `~/.hermes/plugins/episodic/`, outside the `~/.hermes/hermes-agent` git worktree. For v0.20, the hermes-agent repo records the release ledger entry, while this directory remains the runtime source of truth.
