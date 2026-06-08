# Alert Remediation Cron Integration

This is the script-first integration path for monitoring cron jobs. Cron jobs keep doing the low-level check they already understand, but when they detect an alert they emit one structured `alert.remediation/v1` JSON object and pipe it into the remediation router.

The router is policy-governed. Alert payload text is evidence only; the policy decides whether the outcome is `noop`, notification, read-only triage, auto-remediation, Kanban escalation, or approval required.

## Wrapper

Use:

```bash
python scripts/alert_remediation_router.py \
  --policy docs/alert-remediation/examples/hippo-host-policy.yaml \
  --emit-decision-json <<<"$alert_json"
```

Inputs:

- `stdin`: one alert JSON object
- `--policy`: remediation policy YAML
- `--dry-run`: print decisions/drafts, never create Kanban cards
- `--emit-decision-json`: emit a machine-readable decision envelope
- `--create-kanban`: create or reuse a Kanban card for escalation actions; ignored with `--dry-run`
- `--board`: optional Hermes Kanban board name

Exit codes:

- `0`: alert parsed and routed successfully, including `noop`
- `2`: malformed JSON, invalid event schema, invalid policy, or I/O error

## Silence semantics

When the policy decision is `noop` and `--emit-decision-json` is not set, the wrapper prints nothing and exits `0`. This keeps script-only cron jobs quiet when there is nothing actionable.

If `--emit-decision-json` is set, even `noop` decisions are printed so tests, dry-runs, or upstream automation can inspect the route.

## Decision envelope

A WireGuard stale-handshake event produces an envelope like:

```json
{
  "dry_run": false,
  "event": {
    "dedupe_key": "wireguard:do-wireguard-01:stale-handshake",
    "host": "do-wireguard-01",
    "service": "wireguard",
    "severity": "critical",
    "source": "wireguard-watchdog",
    "symptom": "peer handshake stale > 15m"
  },
  "decision": {
    "action": "auto_remediate",
    "assignee": "sysadmin",
    "kanban_on_failure": true,
    "matched_rule": "wireguard_stale_handshake",
    "notify_target": "telegram:-1003939486586:7",
    "reason": "matched rule wireguard_stale_handshake",
    "runbooks": ["wireguard_restart_and_verify"],
    "severity": "critical"
  },
  "should_create_kanban": false,
  "should_spawn_triage": false
}
```

## Recommended cron pattern

A cron script should separate detection from routing:

```bash
#!/usr/bin/env bash
set -euo pipefail

policy="${ALERT_REMEDIATION_POLICY:-docs/alert-remediation/examples/hippo-host-policy.yaml}"

alert_json="$(python checks/check_wireguard.py)"
if [[ -z "${alert_json}" ]]; then
  exit 0
fi

python scripts/alert_remediation_router.py \
  --policy "$policy" \
  --emit-decision-json <<<"$alert_json"
```

The checker script should stay quiet when healthy. When unhealthy, it should emit exactly one event JSON object with a stable `dedupe_key`.

## Read-only triage path

For `triage_readonly`, the envelope includes a `triage_prompt` object. Upstream automation can hand this prompt to an agent. The prompt explicitly marks alert payload data as untrusted and forbids mutations unless policy and human approval allow them.

## Kanban escalation path

For `approval_required`, `kanban_task`, and `critical_page`, the envelope includes a Kanban draft. With `--dry-run`, or without `--create-kanban`, this is only a draft:

```bash
python scripts/alert_remediation_router.py \
  --policy docs/alert-remediation/examples/hippo-host-policy.yaml \
  --dry-run \
  --emit-decision-json <<<"$alert_json"
```

To create/reuse a real Kanban card:

```bash
python scripts/alert_remediation_router.py \
  --policy docs/alert-remediation/examples/hippo-host-policy.yaml \
  --create-kanban \
  --emit-decision-json <<<"$alert_json"
```

The Kanban adapter dedupes by `alert:<dedupe_key>`, so repeated cron ticks reuse the existing non-archived card instead of flooding the board.

## Safety boundaries

- Do not pipe raw monitor output directly to an agent as instructions.
- Convert monitor findings to structured alert JSON first.
- Keep mutating remediation behind policy rules and runbooks.
- Reboots, DB restarts, DNS/LVS routing changes, package upgrades, destructive commands, and GPU driver reloads require approval unless Tom grants a narrow future exception.
- Keep routine/noop cron output silent or routed to Update Stream; critical alerts remain in the alert topic.
