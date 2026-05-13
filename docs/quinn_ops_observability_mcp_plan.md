# Observability MCP Integration Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Add an observability MCP that helps Quinn understand Hermes health trends from logs and runtime metadata without exposing raw private content.

**Architecture:** Build a local stdio MCP server focused on aggregation. It reads approved local telemetry sources, produces counts/trends/windows, and never returns full raw logs by default. Version 1 is read-only and metadata-first; any future log-tail or snippet output must be explicitly gated and sanitized.

**Tech Stack:** Python 3.11, MCP SDK, pathlib/json/re/datetime, pytest with temp log fixtures, subprocess only for whitelisted status probes.

---

## Security Contract

- Read-only in v1.
- No platform/channel history access.
- No session transcript reads.
- No full raw log line output by default.
- No environment dumps.
- No process command lines except whitelisted service identity fields already exposed by Quinn Ops.
- All strings are sanitized before return.
- Time windows and counts are preferred over text snippets.
- Optional future snippets require an explicit env gate and short redacted excerpts only.

## Proposed Files

- Create: `scripts/mcp/quinn_observability_server.py`
- Create: `tests/test_quinn_observability_mcp.py`
- Create: `docs/quinn_observability_mcp.md`
- Optional live copy after approval: `/home/quinn/.hermes/mcp/quinn_observability_server.py`

## Data Sources v1

Approved local sources:

- `$HERMES_HOME/logs/agent.log`
- `$HERMES_HOME/logs/errors.log`
- `$HERMES_HOME/logs/gateway.log`
- `$HERMES_HOME/cron/output/` metadata only: file counts, mtimes, sizes; no output body reads in v1
- systemd user service status for `hermes-gateway` via whitelisted fields only
- optional Quinn Ops overview snapshot metadata, if present

Non-sources in v1:

- Discord/Telegram/channel history
- session transcript content
- auth files
- raw config values
- arbitrary filesystem logs

## Tool Set v1

1. `healthcheck()` — server readiness, log paths present, readable-source counts.
2. `get_log_inventory()` — known log file exists/size/mtime metadata.
3. `get_error_trends(window_minutes: int = 60)` — counts by source/category over a recent window.
4. `get_error_bursts(window_minutes: int = 60, bucket_minutes: int = 5)` — bucketed error/warning counts to spot spikes.
5. `get_component_health_summary()` — combines gateway active/running metadata with recent log severity counts.
6. `get_recent_categories(limit: int = 20)` — category names and counts only, no raw lines.
7. `get_cron_output_inventory()` — cron output file metadata only.
8. `get_observability_snapshot()` — current aggregate-only telemetry snapshot.
9. `compare_observability_snapshots(update_baseline: bool = False)` — optional aggregate baseline under `$HERMES_HOME/mcp/quinn_observability_state/`.

## Snapshot Boundary

Allowed write path, only if snapshot/diff is implemented:

- `$HERMES_HOME/mcp/quinn_observability_state/observability_snapshot.json`

Snapshot contents must be aggregate-only:

- schema version
- timestamp
- log file metadata
- counts by source/category/bucket
- gateway service summary fields
- no raw log lines
- no session contents
- no config values

## Task 1: Add Failing Sanitization and Inventory Tests

**Objective:** Prove the server will not leak raw private strings and only inventories approved paths.

**Files:**
- Create: `tests/test_quinn_observability_mcp.py`

**Tests:**
- `sanitize()` redacts private-looking values in nested data.
- `get_log_inventory()` reports metadata only for temp fixture logs.
- Inventory does not read or return log body contents.
- Unknown arbitrary paths are rejected/not scanned.

**Verification:**
```bash
venv/bin/python -m pytest tests/test_quinn_observability_mcp.py -q
```

Expected: FAIL until server exists.

## Task 2: Scaffold Server and Source Registry

**Objective:** Create importable server and strict source registry.

**Files:**
- Create: `scripts/mcp/quinn_observability_server.py`
- Modify: `tests/test_quinn_observability_mcp.py`

**Implementation requirements:**
- `get_hermes_home()` compatible path resolution.
- `KNOWN_LOGS = {agent, errors, gateway}` registry.
- `response()`, `sanitize()`, `file_meta()` helpers.
- No dependency on MCP SDK for import-time tests.

**Verification:**
```bash
python3 -m py_compile scripts/mcp/quinn_observability_server.py tests/test_quinn_observability_mcp.py
venv/bin/python -m pytest tests/test_quinn_observability_mcp.py -q
```

## Task 3: Parse Log Categories Without Returning Lines

**Objective:** Convert log files into safe aggregate counts.

**Files:**
- Modify: `scripts/mcp/quinn_observability_server.py`
- Modify: `tests/test_quinn_observability_mcp.py`

**Implementation requirements:**
- Parse timestamps when present; otherwise classify as `unknown_time`.
- Categories: `error`, `warning`, `exception`, `traceback`, `failed`, `timeout`, `rate_limit`, `auth`, `network`, `other`.
- Return counts by source/category.
- Track latest timestamp per source/category.
- Do not include raw line text.

**Tests:**
- Fixture logs produce expected category counts.
- Private strings in fixture logs do not appear in output.
- Window filtering excludes old entries.

## Task 4: Add Burst Bucketing

**Objective:** Identify spikes without exposing content.

**Files:**
- Modify: `scripts/mcp/quinn_observability_server.py`
- Modify: `tests/test_quinn_observability_mcp.py`

**Implementation requirements:**
- Bucket counts by `bucket_minutes`, clamped to `1..60`.
- Clamp `window_minutes` to a safe range, e.g. `5..10080`.
- Return bucket start/end ISO timestamps and counts.
- Include `peak_bucket` metadata.

**Tests:**
- Multiple entries in the same bucket aggregate.
- Limits clamp.
- No raw lines returned.

## Task 5: Component Health Summary

**Objective:** Combine service state and recent log signals into a compact health verdict.

**Files:**
- Modify: `scripts/mcp/quinn_observability_server.py`
- Modify: `tests/test_quinn_observability_mcp.py`

**Implementation requirements:**
- Whitelisted `systemctl --user show hermes-gateway` fields only.
- Verdicts: `healthy`, `degraded`, `critical`, `unknown`.
- Critical if service inactive/dead.
- Degraded if recent errors exceed threshold.
- Include evidence counts, not raw lines.

**Tests:**
- Active service + low errors -> healthy.
- Active service + high errors -> degraded.
- Inactive service -> critical.

## Task 6: Cron Output Inventory

**Objective:** Show scheduled-job output health without reading contents.

**Files:**
- Modify: `scripts/mcp/quinn_observability_server.py`
- Modify: `tests/test_quinn_observability_mcp.py`

**Implementation requirements:**
- Inventory files under `$HERMES_HOME/cron/output/` only.
- Return file count, newest mtime, largest file size, extension counts.
- Do not read output body.

**Tests:**
- Temp output files produce expected metadata.
- Body content does not appear.

## Task 7: Optional Aggregate Snapshot/Diff

**Objective:** Support trend comparison between checks without raw data storage.

**Files:**
- Modify: `scripts/mcp/quinn_observability_server.py`
- Modify: `tests/test_quinn_observability_mcp.py`

**Implementation requirements:**
- `get_observability_snapshot()` returns aggregate-only current state.
- `compare_observability_snapshots(update_baseline=False)` compares to previous aggregate snapshot.
- Atomic writes with mode `0600` when updating baseline.
- Default does not mutate.

**Tests:**
- Missing baseline behavior.
- `update_baseline=False` does not write.
- Snapshot file contains no raw fixture line text.
- Count increases produce warning severity.

## Task 8: Register MCP Tools and Docs

**Objective:** Make the server usable and documented without enabling it live.

**Files:**
- Modify: `scripts/mcp/quinn_observability_server.py`
- Create: `docs/quinn_observability_mcp.md`

**Implementation requirements:**
- Add `TOOL_FUNCTIONS` and MCP stdio startup.
- Document data sources, non-sources, security boundary, tools, config snippet, and verification.

**Verification:**
```bash
python3 -m py_compile scripts/mcp/quinn_observability_server.py tests/test_quinn_observability_mcp.py
venv/bin/python -m pytest tests/test_quinn_observability_mcp.py -q
```

## Live Promotion Gate

Do not promote automatically. Before live use:

1. Frank approval.
2. Repo tests pass.
3. Backup existing live server, if any.
4. Copy repo server to live MCP path.
5. Add MCP config only if approved.
6. Restart gateway.
7. Verify `hermes mcp test quinn_observability`.
8. Verify native calls show aggregate-only data and no raw log content.

## Acceptance Criteria

- All outputs are aggregate metadata by default.
- No raw log lines, session text, or platform history appear.
- Known logs are parsed into trends and buckets.
- Gateway health is summarized from whitelisted service fields and counts.
- Cron output inventory is metadata-only.
- Optional snapshot/diff stores aggregate-only JSON with mode `0600`.

## Open Questions Requiring Frank

1. Should observability live as its own MCP, or eventually merge into `quinn_ops`?
2. Should raw sanitized snippets ever be allowed behind an env gate, or should this MCP stay counts-only forever?
3. What error-count thresholds should trigger degraded vs critical?
