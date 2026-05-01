# Hermes Team P4+ Multi-Agent Enhancement Closure

Date: 2026-04-25

## Summary

Hermes Team has been enhanced beyond P3 into a P4+ usable multi-agent runtime closure. The remaining high-value gaps from the previous assessment were implemented or verified:

- Long-task watch/status UI via `team_watch` tool and `/team watch` CLI.
- Cost/time observability via `duration_ms` capture and metrics aggregation.
- Sandbox isolation/audit via `TeamSandboxPolicyEngine`, `team.sandbox_applied`, and `sandbox_audit.json`.
- Bounded dynamic replanning via `TeamReplanner`, `auto_replan`, and `replans.json`.
- Approval audit via `team_approval_audit` and `/team approval-audit`.
- CLI parity for P4 tools: `/team watch`, `/team sandbox`, `/team replans`, `/team approval-audit`.

## Changed runtime files

- `cli.py`
- `hermes_cli/commands.py`
- `hermes_team/metrics.py`
- `hermes_team/runner.py`
- `tests/test_hermes_team_tool.py`
- `tests/cli/test_team_slash_command.py`

The same files were synchronized to source:

- `~/.hermes/runtime-hermes-agent`
- `~/.hermes/hermes-agent`

## Capability details

### Watcher/UI

`team_watch` already persisted snapshots to `HERMES_HOME/state/team/watch.json` and renders text or JSON. CLI now exposes:

- `/team watch [run_id|task_id]`

### Metrics

`TeamDispatcher` records role-level `duration_ms` in each step raw payload. `TeamMetricsStore.snapshot()` now aggregates:

- `total_duration_ms`
- `average_duration_ms`
- `duration_by_role_ms`
- `total_estimated_cost_usd`
- `estimated_cost_by_role_usd`

`TeamRunner` now preserves common cost/token keys from `AIAgent.run_conversation()` into `raw.usage` where present.

### Sandbox

Sandbox policy is derived before dispatch and persisted. Existing audit endpoint remains:

- `team_sandbox_audit`
- `/team sandbox [run_id|task_id]`

### Replanning

`TeamRunSpec.auto_replan=True` triggers bounded replanning only for non-approval failures. Approval gates remain human-controlled and are not bypassed.

### Approval audit

Approval audit is available via:

- `team_approval_audit`
- `/team approval-audit`

## Verification

Runtime targeted verification:

```bash
cd ~/.hermes/runtime-hermes-agent
source venv/bin/activate 2>/dev/null || source .venv/bin/activate
pytest tests/test_hermes_team_tool.py tests/cli/test_team_slash_command.py tests/test_hermes_team_p4_enhancements.py -q
```

Result:

```text
11 passed
```

Final full directed verification should include all team tests in both runtime and source before release/cutover.

## Stop point / value judgment

Further work is now lower marginal value unless Hermes Team becomes a primary production execution substrate. The next useful but non-urgent improvements would be:

1. Real OS/container sandbox enforcement instead of policy/audit only.
2. Streaming per-agent logs into a TUI.
3. Cross-run learning/replanning policy optimization.
4. Distributed worker pool for long-running team jobs.

Current closure is sufficient for Hermes-native multi-agent architecture P4+ local runtime usage.
