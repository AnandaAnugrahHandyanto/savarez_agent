# Alert Remediation Policy Schema v1

The policy is the safety boundary between monitoring alerts and agent action. Alert payloads may suggest actions, but only policy rules can authorize remediation.

## Top-Level Shape

```yaml
schema_version: alert-remediation-policy/v1
routes:
  routine_updates: "telegram:-1003939486586:4913"
  critical_alerts: "telegram:-1003939486586:7"

defaults:
  action: triage_readonly
  create_kanban_after_failures: 2
  dry_run: false

dangerous_actions:
  approval_required:
    - reboot
    - package_upgrade
    - database_restart
    - data_delete
    - dns_or_lvs_routing_change

rules:
  example_rule:
    match:
      service: example
    severity: high
    action: triage_readonly
    assignee: sysadmin
    notify: critical_alerts
    kanban_on_failure: true
```

## Required Top-Level Fields

- `schema_version`: must be `alert-remediation-policy/v1`.
- `routes`: named notification destinations.
- `defaults`: fallback behavior for unmatched alerts.
- `rules`: named remediation rules.

## Route Aliases

Routes are symbolic names resolved by the router/reporting layer.

For Hippo Host:

- `routine_updates`: `telegram:-1003939486586:4913`
- `critical_alerts`: `telegram:-1003939486586:7`

Rules should reference aliases where possible so topic moves require one edit.

## Match Fields

A rule may match on:

- `source`: exact string.
- `service`: exact string.
- `host`: exact string.
- `severity`: exact string.
- `runbook`: exact string.
- `symptom_contains`: case-insensitive substring.
- `tags_any`: event must contain at least one listed tag.
- `tags_all`: event must contain all listed tags.

All provided match predicates must pass.

## Rule Fields

- `severity`: severity to use for the decision. Defaults to event severity.
- `action`: one of the action enum values.
- `assignee`: Kanban/Hermes profile for escalations.
- `notify`: route alias or explicit delivery target.
- `allowed_runbooks`: list of runbook keys authorized for `auto_remediate`.
- `readonly_runbooks`: list of runbooks/checks authorized for `triage_readonly`.
- `kanban_on_failure`: whether failed remediation should open a Kanban task.
- `initial_status`: Kanban initial status, for example `running` or `blocked`.
- `forbidden_without_approval`: mutation classes that force `approval_required`.

## Valid Actions

- `noop`: do nothing.
- `notify_only`: send a concise notification.
- `auto_remediate`: run an explicitly allowlisted remediation and verify.
- `triage_readonly`: collect read-only evidence and report/escalate.
- `kanban_task`: create or reuse a Kanban card.
- `approval_required`: request approval before any mutation.
- `critical_page`: immediately notify critical alert route.

## Approval Gates

The router must downgrade any requested or matched mutation to `approval_required` if the action intersects `dangerous_actions.approval_required`, unless a future rule explicitly grants an exception.

Default approval-required classes:

- `reboot`
- `package_upgrade`
- `database_restart`
- `data_delete`
- `dns_or_lvs_routing_change`
- `firewall_change`
- `credential_rotation`
- `kernel_or_driver_reload`

## Example: WireGuard Auto-Remediation

```yaml
wireguard_stale_handshake:
  match:
    service: wireguard
    symptom_contains: "handshake stale"
  severity: critical
  action: auto_remediate
  assignee: sysadmin
  notify: critical_alerts
  allowed_runbooks:
    - wireguard_restart_and_verify
  kanban_on_failure: true
```

This is acceptable only because the operator has already authorized automatic WireGuard investigation/restarts when unhealthy.

## Example: GPU Transcoder Read-Only Triage

```yaml
gpu_transcoder_intake_failure:
  match:
    tags_any: [gpu, transcode]
    symptom_contains: "new jobs fail"
  severity: high
  action: triage_readonly
  assignee: sysadmin
  notify: critical_alerts
  readonly_runbooks:
    - gpu_supervisor_logs
    - gpu_job_intake_state
  forbidden_without_approval:
    - reboot
    - kernel_or_driver_reload
  kanban_on_failure: true
```

This encodes the current preference: inspect latest supervisor logs and job-intake state first; do not mutate the host before approval.

## Example: Approval Required

```yaml
host_reboot_needed:
  match:
    symptom_contains: "reboot required"
  severity: high
  action: approval_required
  assignee: sysadmin
  notify: critical_alerts
  initial_status: blocked
```

The generated report must include active workload/job count before asking for approval.
