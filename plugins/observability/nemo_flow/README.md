# NeMo Relay Observability

Optional Hermes observability plugin that maps Hermes observer hooks to
NeMo Relay scopes, LLM spans, tool spans, marks, ATOF, and ATIF.

Enable it with:

```bash
hermes plugins enable observability/nemo_flow
```

The plugin fails open when `nemo-relay` is not installed. Install and test it
against the renamed NeMo Relay 0.3 package line:

```bash
pip install "nemo-relay>=0.3"
```

Configure export through NeMo Relay's agent-agnostic plugin file. By default,
the Hermes plugin reads `.nemo-relay/plugins.toml` from the current working
directory. Set `NEMO_RELAY_PLUGINS_TOML` only when the config lives elsewhere.

```toml
version = 1

[[components]]
kind = "observability"
enabled = true

[components.config.atof]
enabled = true
output_directory = ".nemo-relay/atof"
filename = "events.jsonl"
mode = "overwrite"

[components.config.atif]
enabled = true
output_directory = ".nemo-relay/atif"
filename_template = "trajectory-{session_id}.json"
subagent_export_mode = "embedded"
```

## Adaptive Execution PoC

By default, this plugin is passive: it observes Hermes hooks and emits
NeMo Relay lifecycle events without changing execution. When the same
`plugins.toml` contains an enabled `adaptive` component, the plugin also routes
Hermes tool/provider callbacks through NeMo Relay's managed `tools.execute()`
and `llm.execute()` helpers when those APIs are available.

```toml
[[components]]
kind = "adaptive"
enabled = true

[components.config]
version = 1

[components.config.state.backend]
kind = "in_memory"

[components.config.tool_parallelism]
mode = "observe_only"
```

This enables NeMo Relay request intercepts and execution intercepts to run at the
Hermes tool and LLM boundaries while preserving the raw Hermes provider response
for the agent loop. Treat this as an opt-in integration boundary for validating
adaptive behavior before making NeMo Relay a default runtime backend.

## ATOF Mapping

The plugin keeps NeMo Relay's native event model:

- Hermes sessions map to `agent` scopes.
- Hermes API request hooks map to `llm` scope start/end events.
- Hermes tool hooks map to `tool` scope start/end events.
- Turn, approval, subagent, and diagnostic fallback events map to `mark`
  events.

For subagent correlation, mark metadata includes parent and child session IDs,
subagent IDs, role/status fields when present, and derived
`parent_trajectory_id` / `child_trajectory_id` values. This keeps the ATOF
stream lossless for later ATIF conversion that can compact subagents into
separate trajectories.

For ATIF output, NeMo Relay's ATIF exporter embeds subagent trajectories in the
parent trajectory by default under `subagent_trajectories`.
