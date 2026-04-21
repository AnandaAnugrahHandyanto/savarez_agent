# Stale `executing tool: terminal` activity cleanup

## Symptom

Gateway watchdog diagnostics could report a stale tool state like:

- `last_activity=executing tool: terminal`
- `tool=terminal`

…even after the underlying turn was no longer making progress.

This made inactivity timeouts misleading and could leave a session looking like it was still inside a terminal tool call.

## Root cause

Two lifecycle gaps in `run_agent.py` caused the stale state:

1. Tool activity was set before execution started:
   - `_current_tool = function_name`
   - `_touch_activity(f"executing tool: {function_name}")`

2. Cleanup only happened on the normal completion path:
   - `_current_tool = None`
   - `_touch_activity(f"tool completed: …")`

If a tool exited abnormally or raised outside the normal handled path, `_current_tool` could remain stale.

A related asymmetry existed for terminal liveness tracking:

- `tools.environments.base.set_activity_callback(self._touch_activity)` was registered before tool execution
- but there was no matching `set_activity_callback(None)` cleanup at the end of the tool lifecycle

## Fix

The per-tool execution path now uses unconditional cleanup:

- clear the environment activity callback in a `finally` block
- clear `_current_tool` in the same `finally` block
- record a fallback activity message when a tool exits without reaching the normal completion path

## Regression coverage

Added tests in:

- `tests/run_agent/test_run_agent.py`

Coverage includes:

- clearing the terminal activity callback after successful tool completion
- clearing `_current_tool` and callback state even when tool execution aborts with a base exception

## Relevant code

- `run_agent.py`
- `tools/environments/base.py`
- `gateway/run.py`
