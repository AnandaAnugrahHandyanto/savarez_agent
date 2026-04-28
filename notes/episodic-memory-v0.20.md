# Episodic Memory v0.20 Release Ledger

Date: 2026-04-28
Release: `v0.20`
Previous tagged baseline: `v0.19` (`810805c2`)

## Scope

This release records the validation and runtime promotion of the user-installed episodic memory plugin living at:

- `~/.hermes/plugins/episodic/`

The plugin is operationally decoupled from the `~/.hermes/hermes-agent` git worktree, so this ledger file exists to keep the repository in sync with the runtime release decision.

## v0.20 changes promoted to runtime

- repaired `~/.hermes/plugins/episodic/journal.py` so `write_session_journal` imports and executes cleanly
- added loud-failure handling in `~/.hermes/plugins/episodic/provider.py`
  - durable artifacts under `~/.hermes/tmp/episodic-failures/`
  - best-effort Telegram alerting via `TELEGRAM_BOT_TOKEN` + `TELEGRAM_ALLOWED_USERS`
  - reconciliation scan for JSONL sessions missing a matching journal artifact
- added regression tests in `~/.hermes/plugins/episodic/tests/test_journal_alerting.py`
- updated runtime plugin manifest to `version: 0.20.0`

## Validation evidence

### Focused verification
- `source ~/.hermes/hermes-agent/venv/bin/activate && python -m pytest tests/test_journal_alerting.py -q`
- result: `2 passed`
- `source ~/.hermes/hermes-agent/venv/bin/activate && python -c "import episodic.provider, episodic.journal; print('ok')"`
- result: `ok`

### Repo regression coverage
- `source venv/bin/activate && python -m pytest tests/agent/test_memory_provider.py tests/run_agent/test_run_agent.py -q`
- result: `359 passed`

### Organic session-finalization proof
- JSONL: `~/.hermes/memory/sessions/20260428_064238_57eb8dc7.jsonl`
- journal: `~/wiki/session-recordings/2026-W18/2026-04-28_20260428_064238_57eb8dc7.md`
- verified parity:
  - `10` user turns
  - `10` assistant turns
  - `11` tool calls
  - `~59 min` duration

## Operational note

This release confirms that the earlier missing-journal behavior was consistent with restart-interrupted session finalization, not a persistent failure in the normal journal path.

## Follow-up recommended

For stronger long-term source control hygiene, migrate or mirror the live plugin tree into a tracked repository path so future runtime-only changes cannot drift silently.
