# Alert Remediation Pipeline Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Turn monitoring cron/webhook alerts into safe, policy-governed remediation by Hermes agents, escalating to Kanban only when durable follow-up or human approval is needed.

**Architecture:** Monitoring jobs emit structured alert envelopes. A deterministic alert router validates and deduplicates events, loads a remediation policy, and chooses one outcome: `noop`, `notify_only`, `auto_remediate`, `triage_readonly`, `kanban_task`, `approval_required`, or `critical_page`. Safe remediations execute only through named runbooks with allowlisted commands and mandatory verification; unresolved or durable work becomes Kanban cards with evidence and idempotency keys.

**Tech Stack:** Python stdlib, Hermes cron jobs, Hermes webhook adapter, Hermes Kanban CLI/DB, Telegram gateway delivery, YAML/JSON policy files, pytest.

---

## Phase 0 — Operating Rules

- Default to read-only triage unless a rule explicitly allows mutation.
- Every mutation needs a policy rule, evidence capture, and verification step.
- Reboots, destructive commands, DNS/LVS routing changes, database restarts, and package upgrades require approval unless Tom later grants a specific exception.
- Kanban is the escalation/durable-work layer, not the destination for every transient alert.
- Every alert needs a stable `dedupe_key` so retries do not spam Telegram or duplicate Kanban tasks.
- Routine OK/noop updates go to Update Stream; critical alerts stay in the alert topic.

## Event Contract v1

Every monitoring source should produce one JSON object:

```json
{
  "schema_version": "alert.remediation/v1",
  "source": "wireguard-watchdog",
  "event_id": "optional-uuid-or-source-id",
  "dedupe_key": "wireguard:do-wireguard-01:stale-handshake",
  "severity": "critical",
  "service": "wireguard",
  "host": "do-wireguard-01",
  "symptom": "peer handshake stale > 15m",
  "first_seen": "2026-06-08T10:00:00Z",
  "last_seen": "2026-06-08T10:05:00Z",
  "count": 2,
  "evidence": [
    {"type": "text", "label": "wg show", "value": "..."}
  ],
  "runbook": "wireguard_stale_handshake",
  "suggested_action": "auto_remediate",
  "links": [
    {"label": "ServerMon node", "url": "https://..."}
  ]
}
```

## Policy Contract v1

Policy rules live in YAML:

```yaml
schema_version: alert-remediation-policy/v1
routes:
  routine_updates: "telegram:-1003939486586:4913"
  critical_alerts: "telegram:-1003939486586:7"

defaults:
  action: triage_readonly
  create_kanban_after_failures: 2
  dry_run: false

rules:
  wireguard_stale_handshake:
    match:
      service: wireguard
      symptom_contains: "handshake stale"
    severity: critical
    action: auto_remediate
    assignee: sysadmin
    allowed_runbooks:
      - wireguard_restart_and_verify
    notify: critical_alerts
    kanban_on_failure: true

  gpu_transcoder_intake_failure:
    match:
      tags_any: [gpu, transcode]
      symptom_contains: "new jobs fail"
    severity: high
    action: triage_readonly
    assignee: sysadmin
    notify: critical_alerts
    kanban_on_failure: true
    forbidden_without_approval:
      - reboot
      - driver_reload

  db_backup_failed:
    match:
      service: db-backup
    severity: high
    action: triage_readonly
    assignee: sysadmin
    notify: critical_alerts
    kanban_on_failure: true
```

---

## Task 1: Add Event and Policy Schema Documentation

**Objective:** Document the alert event and policy formats so cron jobs can be migrated one by one.

**Files:**
- Create: `docs/alert-remediation/event-schema-v1.md`
- Create: `docs/alert-remediation/policy-schema-v1.md`
- Test: documentation review only

**Step 1: Create event schema doc**

Include:
- required fields
- optional fields
- severity enum
- action enum
- evidence object examples
- dedupe key guidance
- invalid examples

**Step 2: Create policy schema doc**

Include:
- route aliases
- match fields
- allowed actions
- runbook references
- approval gates
- forbidden command classes
- notification routing

**Step 3: Verify docs render as plain Markdown**

Run:

```bash
python - <<'PY'
from pathlib import Path
for p in [Path('docs/alert-remediation/event-schema-v1.md'), Path('docs/alert-remediation/policy-schema-v1.md')]:
    text = p.read_text()
    assert '# ' in text
    assert '```' in text
print('docs ok')
PY
```

Expected: `docs ok`

**Step 4: Commit**

```bash
git add docs/alert-remediation docs/plans/2026-06-08-alert-remediation-pipeline.md
git commit -m "docs: plan alert remediation pipeline"
```

---

## Task 2: Add a Local Policy Example for Hippo Host

**Objective:** Create a concrete starter policy that encodes current Hippo Host safety preferences without enabling broad mutations.

**Files:**
- Create: `docs/alert-remediation/examples/hippo-host-policy.yaml`
- Test: `tests/alert_remediation/test_policy_examples.py`

**Step 1: Write failing test**

```python
from pathlib import Path
import yaml


def test_hippo_host_policy_loads():
    policy = yaml.safe_load(Path('docs/alert-remediation/examples/hippo-host-policy.yaml').read_text())
    assert policy['schema_version'] == 'alert-remediation-policy/v1'
    assert policy['routes']['routine_updates'] == 'telegram:-1003939486586:4913'
    assert policy['routes']['critical_alerts'] == 'telegram:-1003939486586:7'
    assert 'wireguard_stale_handshake' in policy['rules']


def test_dangerous_actions_default_to_approval():
    policy = yaml.safe_load(Path('docs/alert-remediation/examples/hippo-host-policy.yaml').read_text())
    dangerous = policy['dangerous_actions']
    assert 'reboot' in dangerous['approval_required']
    assert 'database_restart' in dangerous['approval_required']
    assert 'dns_or_lvs_routing_change' in dangerous['approval_required']
```

**Step 2: Run test to verify failure**

```bash
python -m pytest tests/alert_remediation/test_policy_examples.py -q
```

Expected: fail because files do not exist.

**Step 3: Add policy file**

Include rules for:
- `wireguard_stale_handshake`: `auto_remediate` allowed for approved WG restart/verify runbook
- `db_backup_failed`: `triage_readonly`
- `gpu_transcoder_intake_failure`: `triage_readonly`, no reboot/driver reload
- `lvs_backend_unhealthy`: `triage_readonly`, no routing change without approval
- `disk_pressure`: `notify_only` below critical, `triage_readonly` above critical

**Step 4: Run test to verify pass**

```bash
python -m pytest tests/alert_remediation/test_policy_examples.py -q
```

Expected: pass.

**Step 5: Commit**

```bash
git add docs/alert-remediation/examples/hippo-host-policy.yaml tests/alert_remediation/test_policy_examples.py
git commit -m "docs: add hippo host remediation policy example"
```

---

## Task 3: Implement a Pure Alert Router Library

**Objective:** Add deterministic routing logic with no side effects.

**Files:**
- Create: `alert_remediation/__init__.py`
- Create: `alert_remediation/models.py`
- Create: `alert_remediation/router.py`
- Test: `tests/alert_remediation/test_router.py`

**Step 1: Write failing tests**

Test cases:
- missing required event fields raises validation error
- unknown event uses default action
- WireGuard stale handshake routes to `auto_remediate`
- GPU intake failure routes to `triage_readonly`
- dangerous requested action downgrades to `approval_required`
- repeated event uses same dedupe key

**Step 2: Run test to verify failure**

```bash
python -m pytest tests/alert_remediation/test_router.py -q
```

Expected: import failure.

**Step 3: Implement models**

Use dataclasses and stdlib only:

```python
@dataclass(frozen=True)
class AlertEvent:
    schema_version: str
    source: str
    dedupe_key: str
    severity: str
    service: str
    symptom: str
    host: str | None = None
    evidence: list[dict[str, Any]] = field(default_factory=list)
    runbook: str | None = None
    suggested_action: str | None = None
```

**Step 4: Implement `route_event(event, policy)`**

Return a dataclass:

```python
@dataclass(frozen=True)
class RouteDecision:
    action: str
    severity: str
    notify_target: str | None
    assignee: str | None
    runbooks: list[str]
    kanban_on_failure: bool
    reason: str
```

**Step 5: Run test to verify pass**

```bash
python -m pytest tests/alert_remediation/test_router.py -q
```

Expected: pass.

**Step 6: Commit**

```bash
git add alert_remediation tests/alert_remediation/test_router.py
git commit -m "feat: add pure alert remediation router"
```

---

## Task 4: Add CLI for Dry-Run Routing

**Objective:** Let operators pipe an alert JSON into the router and see the decision without triggering remediation.

**Files:**
- Create: `alert_remediation/cli.py`
- Modify: package entrypoint if this repo uses one, otherwise document `python -m alert_remediation.cli`
- Test: `tests/alert_remediation/test_cli.py`

**Step 1: Write failing CLI test**

Use `subprocess.run` with a temporary event JSON and policy YAML.

**Step 2: Implement CLI**

Command:

```bash
python -m alert_remediation.cli route --policy docs/alert-remediation/examples/hippo-host-policy.yaml --event event.json --json
```

Output:

```json
{
  "action": "auto_remediate",
  "severity": "critical",
  "notify_target": "telegram:-1003939486586:7",
  "assignee": "sysadmin",
  "runbooks": ["wireguard_restart_and_verify"],
  "kanban_on_failure": true,
  "reason": "matched rule wireguard_stale_handshake"
}
```

**Step 3: Run tests**

```bash
python -m pytest tests/alert_remediation/test_cli.py -q
```

Expected: pass.

**Step 4: Commit**

```bash
git add alert_remediation/cli.py tests/alert_remediation/test_cli.py
git commit -m "feat: add alert remediation router cli"
```

---

## Task 5: Add Kanban Escalation Formatter

**Objective:** Convert an alert event and route decision into a Kanban card body with evidence, links, and idempotency key.

**Files:**
- Create: `alert_remediation/kanban.py`
- Test: `tests/alert_remediation/test_kanban_formatter.py`

**Step 1: Write failing tests**

Assert:
- title includes service/host/severity
- body includes symptom, evidence, route reason, requested outcome
- idempotency key is prefixed with `alert:`
- approval-required cards start blocked or clearly request human approval

**Step 2: Implement formatter only**

Do not call the Kanban DB yet. Return:

```python
@dataclass(frozen=True)
class KanbanCardDraft:
    title: str
    body: str
    assignee: str
    idempotency_key: str
    initial_status: str
```

**Step 3: Run tests**

```bash
python -m pytest tests/alert_remediation/test_kanban_formatter.py -q
```

Expected: pass.

**Step 4: Commit**

```bash
git add alert_remediation/kanban.py tests/alert_remediation/test_kanban_formatter.py
git commit -m "feat: format alert remediation kanban cards"
```

---

## Task 6: Add Safe Kanban Creation Adapter

**Objective:** Create or reuse Kanban tasks for escalations using existing Hermes Kanban CLI/DB semantics.

**Files:**
- Modify: `alert_remediation/kanban.py`
- Test: `tests/alert_remediation/test_kanban_adapter.py`

**Step 1: Write failing tests**

Use a temp Hermes home/kanban DB if existing test helpers support it. Assert duplicate `idempotency_key` reuses the existing card.

**Step 2: Implement adapter**

Preferred implementation options:
1. Import `hermes_cli.kanban_db` directly for in-process creation.
2. If direct DB helper is awkward, shell out to `hermes kanban create ... --json` from the operator script layer, not core library.

**Step 3: Verify with CLI manually**

```bash
python -m alert_remediation.cli escalate --policy docs/alert-remediation/examples/hippo-host-policy.yaml --event fixtures/wireguard-stale.json --dry-run
```

Expected: prints card draft, no DB mutation.

**Step 4: Commit**

```bash
git add alert_remediation/kanban.py tests/alert_remediation/test_kanban_adapter.py
git commit -m "feat: add alert kanban escalation adapter"
```

---

## Task 7: Add Read-Only Triage Prompt Builder

**Objective:** Produce safe agent prompts for Class C alerts without letting alert payloads issue instructions.

**Files:**
- Create: `alert_remediation/prompts.py`
- Test: `tests/alert_remediation/test_prompts.py`

**Step 1: Write failing tests**

Assert prompt:
- wraps alert payload as data, not instructions
- includes safety policy summary
- lists allowed read-only checks
- forbids mutation unless policy allows it
- includes expected output schema

**Step 2: Implement prompt builder**

Prompt sections:
- System intent: read-only triage
- Alert data block
- Policy limits
- Evidence to collect
- Required final response JSON

**Step 3: Run tests**

```bash
python -m pytest tests/alert_remediation/test_prompts.py -q
```

Expected: pass.

**Step 4: Commit**

```bash
git add alert_remediation/prompts.py tests/alert_remediation/test_prompts.py
git commit -m "feat: build safe alert triage prompts"
```

---

## Task 8: Wire Into Cron Script-First Jobs

**Objective:** Let existing monitoring cron scripts pipe alert JSON into the router before deciding whether to notify or spawn an agent.

**Files:**
- Create: `scripts/alert_remediation_router.py`
- Docs: `docs/alert-remediation/cron-integration.md`
- Test: `tests/alert_remediation/test_cron_integration.py`

**Step 1: Implement script wrapper**

Inputs:
- stdin: alert JSON
- env/config: policy path
- flags: `--dry-run`, `--policy`, `--emit-decision-json`

Outputs:
- empty stdout for noop/no alert
- JSON decision for upstream cron context
- nonzero exit only for malformed inputs or internal errors

**Step 2: Add integration doc**

Show a cron script pattern:

```bash
alert_json="$(python check_wireguard.py)"
python scripts/alert_remediation_router.py --policy ~/.hermes/profiles/sysadmin/alert-remediation/hippo-host-policy.yaml <<<"$alert_json"
```

**Step 3: Run tests**

```bash
python -m pytest tests/alert_remediation/test_cron_integration.py -q
```

Expected: pass.

**Step 4: Commit**

```bash
git add scripts/alert_remediation_router.py docs/alert-remediation/cron-integration.md tests/alert_remediation/test_cron_integration.py
git commit -m "feat: add cron alert remediation router wrapper"
```

---

## Task 9: Add Webhook Integration Path

**Objective:** Support near-real-time alert ingestion through Hermes webhook routes after the cron path is stable.

**Files:**
- Docs: `docs/alert-remediation/webhook-integration.md`
- Optional modify: webhook route templates/config examples only
- Test: existing webhook tests if code changes are required

**Step 1: Document webhook route pattern**

Use existing webhook adapter capabilities:
- HMAC secret required
- route-specific prompt/template
- deliver target
- `deliver_only` for low-cost notifications

**Step 2: Add example route config**

Show route that passes payload to alert router, or creates a triage prompt.

**Step 3: Verify against webhook docs/tests**

Run:

```bash
python -m pytest tests/gateway/test_webhook_dynamic_routes.py tests/gateway/test_webhook_signature_rate_limit.py -q
```

Expected: pass if code changed; docs-only otherwise.

**Step 4: Commit**

```bash
git add docs/alert-remediation/webhook-integration.md
git commit -m "docs: add webhook path for alert remediation"
```

---

## Task 10: Pilot One Real Alert Class — WireGuard

**Objective:** Start with the safest already-authorized remediation class.

**Files:**
- Profile-local policy copy: `~/.hermes/profiles/sysadmin/alert-remediation/hippo-host-policy.yaml`
- Existing WG cron/watchdog scripts as applicable
- Docs: `docs/alert-remediation/pilots/wireguard.md`

**Step 1: Dry-run with synthetic event**

```bash
python -m alert_remediation.cli route --policy ~/.hermes/profiles/sysadmin/alert-remediation/hippo-host-policy.yaml --event fixtures/wireguard-stale.json --json
```

Expected: `auto_remediate`, critical alert target.

**Step 2: Add read-only verification command list**

Before mutation:
- `wg show`
- service status
- peer ping if configured
- recent watchdog logs

**Step 3: Add approved remediation command**

Only the already-approved WG restart path.

**Step 4: Verify post-remediation**

Require:
- recent handshake
- peer reachable
- service active

**Step 5: Run one dry-run cron tick**

Expected: no mutation unless synthetic failure is injected.

**Step 6: Enable live policy for WG only**

Keep all other classes as `triage_readonly`.

**Step 7: Commit tracked docs/code only**

Do not commit profile-local operational policy unless explicitly desired.

---

## Task 11: Add Reporting Format

**Objective:** Standardize concise operator-facing status messages.

**Files:**
- Create: `alert_remediation/reporting.py`
- Test: `tests/alert_remediation/test_reporting.py`

**Step 1: Write failing tests**

Cases:
- auto-remediation success
- auto-remediation failed and Kanban opened
- approval required
- read-only triage summary

**Step 2: Implement text formatter**

Format:

```text
Alert remediation: <status>
Host: <host>
Service: <service>
Issue: <symptom>
Action: <action taken or proposed>
Verification: <result>
Next: <noop | Kanban card | approval needed>
```

**Step 3: Run tests**

```bash
python -m pytest tests/alert_remediation/test_reporting.py -q
```

Expected: pass.

**Step 4: Commit**

```bash
git add alert_remediation/reporting.py tests/alert_remediation/test_reporting.py
git commit -m "feat: format alert remediation reports"
```

---

## Acceptance Criteria

- Monitoring jobs can emit structured alert JSON.
- Router can dry-run decisions without side effects.
- Hippo Host policy encodes current safety boundaries.
- Kanban cards are created only for escalations/durable follow-up and deduped by alert key.
- Read-only triage prompts treat alert payloads as untrusted data.
- At least one pilot class, WireGuard stale handshake, is verified end-to-end in dry-run before live mutation.
- Telegram routing respects existing preferences: routine updates to Update Stream; critical alerts to alert topic.
- Dangerous actions require approval by default.

## Verification Commands

Run focused tests during implementation:

```bash
python -m pytest tests/alert_remediation -q
```

Run related integration tests before merge:

```bash
python -m pytest tests/tools/test_cronjob_tools.py tests/tools/test_kanban_tools.py tests/gateway/test_webhook_dynamic_routes.py -q
```

Run broad suite if touching Hermes core routing/gateway/cron internals:

```bash
python -m pytest tests/ -o 'addopts=' -q
```

## Rollout Plan

1. Documentation and schemas only.
2. Router dry-run CLI.
3. Kanban escalation dry-run.
4. WireGuard pilot in dry-run.
5. WireGuard live auto-remediation.
6. Add DB backups as read-only triage + Kanban escalation.
7. Add GPU transcoder incidents as read-only triage only.
8. Review results after one week before enabling more auto-remediation.

## Open Decisions

- Whether alert-remediation belongs as a built-in Hermes package, a sysadmin-profile script suite, or a plugin.
- Whether Kanban task creation should use direct DB helpers or the CLI subprocess boundary.
- Whether webhook ingestion should come before or after the cron-script wrapper.
- Which ServerMon alert classes should be first-class event producers.
