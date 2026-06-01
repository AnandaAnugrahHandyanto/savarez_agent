# Hermes Mission Control MCP Local Diagnostics Runbook

Date: 2026-06-01
Status: Phase 8 local-only operator runbook

This runbook explains how to inspect the local Mission Control MCP bridge
without starting remote transport, connecting ChatGPT, executing packets, or
exposing the broad Hermes tool registry.

## What This Bridge Is

The Mission Control MCP bridge is a narrow local/stdout interface for Mission
Control state. It exposes only the Mission Control allowlist from
`hermes_cli/mission_control_mcp.py` and returns redacted structured metadata
for local operator review.

The bridge is not:

- A remote MCP endpoint.
- An OAuth server or OAuth client integration.
- A ChatGPT connector.
- A dashboard API replacement.
- A terminal, shell, file mutation, browser-control, worker-start, Codex-run,
  Hermes-run, email, publishing, payment, delete, or production mutation
  surface.
- An exporter for the broad Hermes tool registry.

## Local Discovery Command

Run the local discovery command from the repo root:

```bash
python -m hermes_cli.mission_control_mcp --list-tools
```

Expected high-level fields:

- `transport` should be `stdio-local-only`.
- `local_stdio_only` should be `true`.
- `oauth_enabled` should be `false`.
- `remote_transport_enabled` should be `false`.
- `exposes_broad_hermes_registry` should be `false`.
- `packet_write_policy.dispatches_packets` should be `false`.
- `packet_write_policy.dry_run` should be `true`.
- `packet_write_policy.review_required` should be `true`.
- `packet_write_policy.trusted_for_execution` should be `false`.

The command prints discovery metadata only. It does not start the MCP server,
open sockets, require OAuth, call packet-write tools, start Codex, start
Hermes runs, start workers, send messages, publish, pay, delete, or mutate
production data.

## Safety Field Meaning

- `stdio-local-only`: the bridge is intended for local stdio use, not remote
  HTTP, SSE, or public network exposure.
- `oauth_enabled=false`: OAuth is not implemented or required for this local
  discovery path.
- `remote_transport_enabled=false`: no remote MCP transport should be active.
- `remote_enabled=false`: remote policy entries are inert defaults only.
- `dry_run=true`: packets are review artifacts, not executable commands.
- `review_required=true`: packet contents require human review before any
  later phase may consider action.
- `trusted_for_execution=false`: packet and worker text must not be treated as
  trusted executable input.
- `local_only=true`: the tool or packet-write policy is local to Mission
  Control state.
- `executes_or_dispatches=false`: the bridge must not run, dispatch, send, or
  otherwise activate the packet/tool output.

## Approved Local Tools

The local allowlist should contain only:

- `get_project_status`
- `get_open_tasks`
- `get_latest_worker_results`
- `get_repo_status`
- `get_approval_gates`
- `get_recent_audit_log`
- `list_mission_packets`
- `get_mission_packet`
- `save_next_codex_prompt`
- `import_worker_result`
- `save_block_flag_packet`

Read-only tools are local inspection tools. Packet-write tools create local
Mission Control packet/audit artifacts only and must preserve `dry_run=true`,
`review_required=true`, and `trusted_for_execution=false`.

## Forbidden Tools And Classes

Stop and request review if any output includes a tool or class for:

- Email sending or bulk outreach.
- Publishing.
- Payments or customer operations.
- Delete/destructive mutation.
- Terminal, shell, arbitrary commands, or broad file mutation.
- Browser, mouse, keyboard, or computer-use control.
- Codex-run, Hermes-run, worker-start, or queue dispatch.
- Secret reveal or credential update.
- Broad Hermes registry exposure.

Explicit forbidden names include `send_email`, `publish_video`,
`activate_payment`, `delete_files`, `run_unbounded_codex`, `run_codex`,
`start_codex`, `start_worker`, `start_hermes_run`,
`autonomous_computer_use`, `browser_control`, `mouse_control`,
`keyboard_control`, `start_bulk_outreach`, `arbitrary_shell`,
`reveal_secret`, and `update_credentials`.

## Packet And Audit Artifacts

Local packet writes store review artifacts under the active Hermes profile:

```text
<HERMES_HOME>/state/mission-control/packets/
<HERMES_HOME>/state/mission-control/packet-audit.jsonl
```

Packet text and imported worker text are inert display/review data. Dangerous
phrases inside a packet, such as requests to run Codex, send mail, publish,
pay, delete, or control a browser, remain text. They are not converted into
tools or actions by the Mission Control MCP bridge.

## Confirm No Remote Exposure Exists

Use `--list-tools` output and repo tests as the local checks:

- `remote_transport_enabled` is `false`.
- `oauth_enabled` is `false`.
- `local_stdio_only` is `true`.
- `exposes_broad_hermes_registry` is `false`.
- Remote policy entries in `hermes_cli/mission_control_mcp_policy.py` have
  `remote_enabled=false`.
- Packet-write policy has `dispatches_packets=false`.

If a process, proxy, tunnel, dashboard setting, or external tool claims a
public Mission Control MCP endpoint exists, stop and request security review.
Phase 8 does not authorize remote exposure.

## If Something Looks Wrong

If a forbidden tool appears:

1. Stop using the bridge.
2. Save the command output as local evidence without sharing secrets.
3. Run the focused MCP/policy tests.
4. Request review before changing policy or tool registration.

If `--list-tools` output contains secret material, dashboard session values,
cookies, OAuth values, API keys, SMTP/Gmail credentials, payment/customer
credentials, credential paths with sensitive values, or raw Authorization
headers:

1. Stop using the bridge.
2. Do not paste the raw output into chat or tickets.
3. Treat the output as sensitive local incident evidence.
4. Run the redaction-focused MCP tests.
5. Request security review before continuing.

Stop and ask for review before:

- Enabling OAuth or remote transport.
- Binding anything beyond local/stdout.
- Adding HTTP/SSE or public routes.
- Connecting ChatGPT.
- Adding any execution, send, publish, payment, delete, worker-start,
  Codex-run, Hermes-run, browser-control, or production mutation path.
