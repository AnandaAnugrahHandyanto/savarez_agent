# capability-manifest-verifier

Opt-in evaOS policy plugin for Hermes. When enabled, the plugin verifies a
broker-issued HS256 capability-manifest JWT and enforces its tool grants through
Hermes' `pre_tool_call` hook before any tool executes.

It does not add tools, shell access, generic RPC, or a control socket.

## Configuration

Enable the plugin in `config.yaml`:

```yaml
plugins:
  enabled:
    - capability-manifest-verifier
  entries:
    capability-manifest-verifier:
      agent_id: agent-1
      manifest_path: ~/.hermes/evaos/capability.jwt
      secret_env: EVAOS_CAPABILITY_MANIFEST_SECRET
```

The JWT can also be supplied by environment variable, which takes precedence
over `manifest_path`:

```bash
export EVAOS_CAPABILITY_MANIFEST_JWT="..."
export EVAOS_CAPABILITY_MANIFEST_SECRET="..."
```

Secrets should come from the environment, not `config.yaml`.

## Manifest Shape

The JWT must use HS256 and include:

- `iss: evaos-broker`
- `aud: evaos-runtime`
- `exp`
- optional `agent_id`, `runtime_id`, or `sub` matching the configured
  `agent_id`
- `tool_grants` or `grants`, keyed by Hermes tool name

Example grant payload:

```json
{
  "tool_grants": {
    "read_file": {"decision": "allow"},
    "terminal": {"decision": "deny", "reason": "shell unavailable"},
    "write_file": {"decision": "requires_approval"},
    "*": {"decision": "deny", "reason": "default deny"}
  }
}
```

`allow` passes through. `deny` and missing grants block. `requires_approval`
also blocks for now because this plugin's hook can only allow or block; routing
those requests into an evaOS Approval Center queue is a later integration slice.
