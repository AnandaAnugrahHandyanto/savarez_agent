# feat: Configuration-Driven Hooks System (Claude Code Style)

## Summary

This PR introduces a **configuration-driven hooks system** that allows users to define lifecycle event callbacks directly in `config.yaml`. This complements the existing plugin system with a lighter, declarative approach inspired by Claude Code's hooks.

## Motivation

Claude Code users migrating to Hermes often miss the ability to:
1. **Rewrite commands** before execution (e.g., RTK token optimization)
2. **Block dangerous operations** (e.g., accidental config file edits)
3. **Capture observations** for continuous learning
4. **Save state** before context compression

While Hermes has a powerful plugin system, it requires creating a full plugin directory with `plugin.yaml` and Python code. This PR adds a lighter alternative: shell commands defined in config.yaml.

## What's New

### 1. Core Module: `hermes_agent/config_hooks.py`

A new module that manages configuration-driven hooks:

- **`HookConfig`**: Dataclass for individual hook configuration
- **`ConfigHookManager`**: Loads and executes hooks from config
- **Async/sync execution**: Non-blocking async hooks, blocking sync hooks that can modify context
- **Timeout handling**: Hooks respect configurable timeouts
- **Result merging**: Hooks can modify tool args/results via JSON output

### 2. Hook Types

| Hook Type | When Fired | Can Modify |
|-----------|-----------|------------|
| `pre_tool_call` | Before tool execution | ✅ Tool arguments |
| `post_tool_call` | After tool execution | ✅ Tool result |
| `pre_compact` | Before context compression | ❌ (notification only) |
| `on_session_start` | New session begins | ❌ (notification only) |
| `on_session_end` | Session ends | ❌ (notification only) |

### 3. Configuration Format

```yaml
hooks:
  pre_tool_call:
    # RTK token optimization
    - matcher: "Bash"
      command: "node ~/.hermes/hooks/rtk-rewrite.js"
      timeout: 5
      description: "Rewrite git commands with rtk"
    
    # Config file protection
    - matcher: "Write|Edit|MultiEdit"
      command: "python ~/.hermes/hooks/config-guard.py"
      timeout: 10
      description: "Guard sensitive config files"
    
    # Observation capture (async, non-blocking)
    - matcher: "*"
      command: "bash ~/.hermes/hooks/observation.sh"
      async: true
      description: "Capture tool use for learning"

  post_tool_call:
    - matcher: "Bash"
      command: "python ~/.hermes/hooks/pr-log.py"
      description: "Log PR creation"

  pre_compact:
    - command: "bash ~/.hermes/hooks/save-state.sh"
      description: "Save state before compression"
```

### 4. Hook Interface

Hooks receive context as JSON via stdin:

```json
{
  "tool": "Bash",
  "args": {"command": "git status"},
  "task_id": "abc123",
  "session_id": "sess_456"
}
```

They can modify behavior by printing JSON to stdout:

```json
{"args": {"command": "rtk git status"}}
```

### 5. Integration Points

- **`model_tools.py`**: Added config hook calls alongside existing plugin hooks
- **`agent/context_compressor.py`**: Added `pre_compact` hook invocation

## Example Hooks Included

The `examples/hooks/` directory contains reference implementations:

1. **rtk-rewrite.js**: Token-optimizing command rewriter
2. **config-guard.py**: Protects sensitive config files
3. **observation-capture.sh**: Logs tool use for learning
4. **save-state.sh**: Saves snapshots before compression

## Testing

Added comprehensive test suite: `tests/test_config_hooks.py`

```bash
pytest tests/test_config_hooks.py -v
```

Tests cover:
- Hook matching logic (wildcards, multiple tools)
- Sync/async execution
- Timeout handling
- Context modification
- Error resilience

## Migration from Claude Code

For users migrating from Claude Code:

| Claude Code | Hermes (This PR) |
|-------------|------------------|
| `settings.json: hooks.PreToolUse` | `config.yaml: hooks.pre_tool_call` |
| `settings.json: hooks.PostToolUse` | `config.yaml: hooks.post_tool_call` |
| `settings.json: hooks.SessionStart` | `config.yaml: hooks.on_session_start` |
| `settings.json: hooks.PreCompact` | `config.yaml: hooks.pre_compact` |

Hook scripts are compatible with minimal changes (both use stdin/stdout JSON).

## Backward Compatibility

- ✅ Fully backward compatible
- ✅ Hooks are optional (empty by default)
- ✅ Existing plugin hooks continue to work
- ✅ Both systems can be used together

## Future Work

Potential extensions:
1. **Hook chaining**: Allow hooks to depend on other hooks
2. **Conditional hooks**: Execute based on context predicates
3. **Hook marketplace**: Share useful hooks via skills hub
4. **Built-in hooks**: Common hooks shipped with Hermes

## Checklist

- [x] Added `hermes_agent/config_hooks.py`
- [x] Modified `model_tools.py` to invoke config hooks
- [x] Modified `agent/context_compressor.py` for pre_compact hook
- [x] Updated `cli-config.yaml.example` with documentation
- [x] Added example hooks in `examples/hooks/`
- [x] Added comprehensive tests
- [x] Follows Hermes code style
- [x] Cross-platform compatible (no Unix-only dependencies)

---

**Related:** This PR addresses the gap identified in Claude Code harness migration analysis. It provides a migration path for users who rely on config-driven hooks in Claude Code.
