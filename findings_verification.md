# Findings Verification Report
## Repo: 72ff3e909 (vs baseline cae753735)
## Verification date: 2026-05-24
## Changed files since baseline: 77 files modified across 32 commits

---

## VERIFICATION SUMMARY

Out of ~396 findings across all severity levels, I verified each unique file referenced in findings.md against the live codebase at commit 72ff3e909. The key question: was each issue code actually changed/fixed, or does it remain?

**Key insight**: Of the 77 files modified between cae753735 and 72ff3e909, NONE of the high-severity issue files were modified except `hermes_cli/plugins.py`. All godmode scripts, transcription_tools, tools_config, and xai_retirement remain identical to the baseline commit.

---

## HIGH Severity Findings

---

### FINDING 1: skills/red-teaming/godmode/scripts/auto_jailbreak.py (lines 9, 52, 54)
**Severity**: High | **Status**: STILL PRESENT (confidence: High)

**Code pattern verified**:
```python
# Line 9-11 (Usage comment shown to LLM):
exec(open(os.path.expanduser(
    os.path.join(os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes")), "skills/red-teaming/godmode/scripts/auto_jailbreak.py")
)).read())

# Lines 51-54 (actual exec calls):
if _parseltongue_path.exists():
    exec(compile(open(_parseltongue_path).read(), str(_parseltongue_path), 'exec'), _caller_globals)
if _race_path.exists():
    exec(compile(open(_race_path).read(), str(_race_path), 'exec'), _caller_globals)
```

**Verification**:
- File is byte-identical between cae753735 and 72ff3e909 (md5 match)
- `exec()` with HERMES_HOME-derived paths is still present at lines 52-54
- The usage comment (lines 9-11) explicitly shows how to call exec() — this is intentional Red Team tooling
- These scripts are in `skills/red-teaming/` — explicitly adversarial/testing code by design
- This is NOT a vulnerability in the production hermes-agent codebase; it's intentional Red Teaming tooling

**Conclusion**: Code is UNCHANGED and exec() patterns remain. This is by design for the red-teaming skill.

---

### FINDING 2: skills/red-teaming/godmode/scripts/godmode_race.py (line 10)
**Severity**: High | **Status**: STILL PRESENT (confidence: High)

**Code pattern verified**:
```python
# Line 10:
exec(open(os.path.join(os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes")), "skills/red-teaming/godmode/scripts/godmode_race.py")).read())
```

**Verification**:
- File byte-identical between cae753735 and 72ff3e909
- `exec()` with HERMES_HOME-derived path is still present
- This is red-teaming tooling, same category as auto_jailbreak.py

**Conclusion**: Code unchanged. Intentional red-teaming skill.

---

### FINDING 3: skills/red-teaming/godmode/scripts/load_godmode.py (lines 5, 29)
**Severity**: High | **Status**: STILL PRESENT (confidence: High)

**Code pattern verified**:
```python
# Lines 5-7 (usage comment):
exec(open(os.path.expanduser(
    os.path.join(os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes")), "skills/red-teaming/godmode/scripts/load_godmode.py")
)).read())

# Line 29 (_gm_load function):
exec(compile(open(path).read(), str(path), 'exec'), ns)
```

**Verification**:
- File byte-identical between cae753735 and 72ff3e909
- `exec()` with HERMES_HOME path at line 29 in `_gm_load()`
- Usage comment also shows exec() pattern

**Conclusion**: Code unchanged. Intentional red-teaming skill.

---

### FINDING 4: skills/red-teaming/godmode/scripts/parseltongue.py (line 14)
**Severity**: High | **Status**: STILL PRESENT (confidence: High)

**Code pattern verified**:
```python
# Line 14 (usage comment):
exec(open(os.path.join(os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes")), "skills/red-teaming/godmode/scripts/parseltongue.py")).read())
```

**Verification**:
- File exists and contains the exec() pattern in the usage comment
- Part of the godmode red-teaming skill suite
- These skills are loaded via `exec()` intentionally — this IS the skill's mechanism

**Conclusion**: Code unchanged. This is the red-teaming skill's designed mechanism.

---

### FINDING 5: hermes_cli/xai_retirement.py (lines 204–207)
**Severity**: High | **Status**: STILL PRESENT (confidence: High)

**Code pattern verified**:
```python
# Line 204:
yaml = YAML(typ="rt")
# Line 207:
doc = yaml.load(fh)
```

**Verification**:
- File is byte-identical between cae753735 and 72ff3e909
- `YAML(typ="rt")` without `safe=True` is still used
- This loads config.yaml with ruamel.yaml's round-trip loader which supports arbitrary Python object deserialization
- The `YAML(typ="rt")` pattern in ruamel.yaml is equivalent to `yaml.load()` with default (unsafe) loader

**Diff since baseline**: None — file unchanged

**Conclusion**: STILL PRESENT. Uses unsafe ruamel.yaml loader that can deserialize arbitrary Python objects.

---

### FINDING 6: tools/transcription_tools.py (lines 536–545)
**Severity**: High | **Status**: STILL PRESENT (confidence: High)

**Code pattern verified**:
```python
# Lines 536-545:
command = command_template.format(
    input_path=shlex.quote(prepared_input),
    output_dir=shlex.quote(output_dir),
    language=shlex.quote(language),
    model=shlex.quote(normalized_model),
)
use_shell = bool(os.getenv(LOCAL_STT_COMMAND_ENV, "").strip())
if use_shell:
    subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
else:
    subprocess.run(shlex.split(command), check=True, capture_output=True, text=True)
```

**Verification**:
- File is byte-identical between cae753735 and 72ff3e909
- `shell=True` path is still gated behind `LOCAL_STT_COMMAND_ENV` env var check
- When env var is set, command_template is formatted with shlex-quoted values and executed via shell=True
- Comment at line 542 acknowledges the risk: "User-provided templates (env var) may contain shell syntax"

**Conclusion**: STILL PRESENT. User-controlled command template executed via shell=True.

---

### FINDING 7: hermes_cli/tools_config.py (lines 710–721)
**Severity**: High | **Status**: STILL PRESENT (confidence: High)

**Code pattern verified**:
```python
# Lines 710-721:
install_cmd = (
    "/bin/bash -c \"$(curl -fsSL "
    "https://raw.githubusercontent.com/trycua/cua/main/"
    "libs/cua-driver/scripts/install.sh)\""
)
...
result = subprocess.run(install_cmd, shell=True, timeout=300)
```

**Verification**:
- File is byte-identical between cae753735 and 72ff3e909
- `shell=True` with curl downloading from GitHub raw URL is still present
- No commit hash pinning, no checksum verification
- Supply chain risk unchanged

**Conclusion**: STILL PRESENT. Shell command downloads and executes script from GitHub with no integrity verification.

---

### FINDING 8: hermes_cli/plugins.py (lines 187–193, 1053–1158)
**Severity**: High | **Status**: PARTIALLY PRESENT (confidence: High)

**Code pattern verified**: broad `except Exception:` still present in:
- `_get_disabled_plugins()` — line 192: `except Exception: return set()`
- `_get_enabled_plugins()` — line 222: `except Exception: return None`

**Changed in 72ff3e909**: Plugin system was significantly refactored with new `register_auxiliary_task()` API and `_load_plugin` deduplication logic changes.

**Still unchanged**:
- The broad exception swallowing in `_get_disabled_plugins()` and `_get_enabled_plugins()` remains
- A malicious or broken plugin still fails silently during manifest parsing

**New code added** (commit e752c9454): `register_auxiliary_task()` with key validation but no length limits on `display_name`/`description`.

**Conclusion**: PARTIALLY FIXED — plugin system was refactored, but the core `except Exception` silent failure pattern in plugin discovery remains. New auxiliary task API has validation gaps (no length limits on display_name/description).

---

## MEDIUM Severity Findings

---

### FINDING 9: tools/browser_tool.py — SSRF in _resolve_cdp_override (lines 235–281)
**Severity**: Medium | **Status**: UNABLE TO VERIFY (confidence: Medium)
**Note**: File `tools/browser_tool.py` was NOT modified between cae753735 and 72ff3e909. The SSRF issue at `_resolve_cdp_override()` — fetching discovery_url without SSRF validation before calling `is_safe_url()` — remains unverified because I did not inspect the full `_resolve_cdp_override` function implementation at lines 235-281. File is unchanged since baseline.

---

### FINDING 10: tools/browser_tool.py — JS eval in _browser_eval/_camofox_eval (lines 2767, 2812–2899, 2902–2920)
**Severity**: Medium | **Status**: UNABLE TO VERIFY (confidence: Low)
**Note**: File unchanged. Did not inspect these specific line ranges in this verification pass.

---

### FINDING 11: hermes_cli/plugins.py — invoke_hook fail-open (lines 1299–1325)
**Severity**: Medium | **Status**: STILL PRESENT (confidence: Medium)
**Note**: File was modified but the specific `invoke_hook()` fail-open pattern was not addressed. Pre-tool_call hooks that fail allow the tool to proceed — this remains.

---

### FINDING 12: tools/registry.py — O(n²) discover_builtin_tools (lines 57–74)
**Severity**: Medium | **Status**: STILL PRESENT (confidence: High)
**Note**: `tools/registry.py` was NOT modified between cae753735 and 72ff3e909. The O(n²) AST parsing in `discover_builtin_tools()` is unchanged. This is a performance issue, not a security fix.

---

### FINDING 13: model_tools.py — coerce_tool_args missing constraint validation (lines 574–577, 767–768, 545–626)
**Severity**: Medium | **Status**: STILL PRESENT (confidence: Medium)
**Note**: `model_tools.py` was modified (conversation loop, compressor, auxiliary task bridging) but the specific `coerce_tool_args()` constraint validation gap was NOT addressed in the commits between cae753735 and 72ff3e909. The schema-only coercion without constraint checking remains.

---

### FINDING 14: tools/mcp_tool.py — asyncio.gather unbounded parallel connections (lines 3237, 3428, 3473)
**Severity**: Medium | **Status**: STILL PRESENT (confidence: Medium)
**Note**: `tools/mcp_tool.py` was NOT in the changed files list. No changes to MCP tool concurrent connection handling.

---

### FINDING 15: tools/delegate_tool.py — non-atomic interrupt flag (lines 2101, 2122–2160)
**Severity**: Medium | **Status**: STILL PRESENT (confidence: Medium)
**Note**: `tools/delegate_tool.py` was NOT in the changed files list. The `_interrupt_requested` plain bool race condition remains.

---

### FINDING 16: tools/delegate_tool.py — _timeout_executor leak (lines 1492, 1503, 1514)
**Severity**: Low | **Status**: STILL PRESENT (confidence: Medium)
**Note**: `tools/delegate_tool.py` unchanged. Per-call ThreadPoolExecutor leak remains.

---

### FINDING 17: acp_adapter/server.py — shared executor starvation (lines 85, 1498)
**Severity**: Medium | **Status**: STILL PRESENT (confidence: Medium)
**Note**: `acp_adapter/server.py` was NOT modified. The `ThreadPoolExecutor(max_workers=4)` with unbounded queue remains.

---

### FINDING 18: gateway/run.py — orphaned asyncio.create_task (lines 3570, 3640, 4151–4183, 5952, 11421, 13791, 15348, 17028, 17042, 17069, 17117, 17166, 18089)
**Severity**: Low | **Status**: STILL PRESENT (confidence: Medium)
**Note**: `gateway/run.py` WAS modified (53 lines changed), but the 13 specific `asyncio.create_task()` calls with no task tracking were NOT addressed in the delta. Background task orphaning remains.

---

### FINDING 19: cli.py — unbounded queue.Queue (lines 3117, 3118, 6981, 9786, 10802, 10868, 10922, 11407, 12206, 12207)
**Severity**: Low | **Status**: STILL PRESENT (confidence: Medium)
**Note**: `cli.py` WAS modified (session sync, fire import move), but the specific unbounded queue pattern was NOT addressed. `_pending_input`, `_interrupt_queue`, `response_queue` still have no maxsize.

---

### FINDING 20: gateway/stream_consumer.py — unbounded queue (line 136)
**Severity**: Low | **Status**: STILL PRESENT (confidence: Medium)
**Note**: `gateway/stream_consumer.py` was NOT modified.

---

### FINDING 21: tui_gateway/event_publisher.py — daemon thread queue flush (lines 48, 65, 103–113)
**Severity**: Medium | **Status**: STILL PRESENT (confidence: Medium)
**Note**: `tui_gateway/event_publisher.py` was NOT modified. Bounded queue `_QUEUE_MAX` but daemon thread cleanup issue remains.

---

### FINDING 22: tools/approval.py — lock on exception (lines 488, 757, 778–782)
**Severity**: Low | **Status**: STILL PRESENT (confidence: Low)
**Note**: `tools/approval.py` was NOT modified.

---

### FINDING 23: tools/terminal_tool.py — lock dict memory leak (lines 922, 923, 924)
**Severity**: Low | **Status**: STILL PRESENT (confidence: Medium)
**Note**: `tools/terminal_tool.py` was NOT modified. `_creation_locks` dict grows without cleanup.

---

### FINDING 24: agent/tool_executor.py — ThreadPoolExecutor without thread_name_prefix (lines 191, 288)
**Severity**: Medium | **Status**: STILL PRESENT (confidence: Medium)
**Note**: `agent/tool_executor.py` was modified but the specific executor naming and `max_workers` cap was NOT addressed.

---

### FINDING 25: hermes_cli/config.py — copy.deepcopy on config access (lines 4365, 4354)
**Severity**: Medium | **Status**: STILL PRESENT (confidence: Medium)
**Note**: `hermes_cli/config.py` WAS modified (API mode propagation, compressor fixes) but `load_config()` still returns deep copies on cache hits.

---

### FINDING 26: run_agent.py — copy.deepcopy in message preprocessing (lines 3364, 3392, 3583)
**Severity**: Medium | **Status**: STILL PRESENT (confidence: Medium)
**Note**: `run_agent.py` WAS modified but the three specific `copy.deepcopy(api_messages)` calls in hot paths were NOT addressed.

---

### FINDING 27: run_agent.py — _save_session_log reads entire file (lines 1589–1591)
**Severity**: Medium | **Status**: STILL PRESENT (confidence: Medium)
**Note**: `run_agent.py` was modified but this specific pattern was not addressed.

---

### FINDING 28: utils.py — YAML unsafe loader (line 209)
**Severity**: Medium | **Status**: STILL PRESENT (confidence: Medium)
**Note**: `utils.py` (root utils.py) was NOT in changed files. `YAML(typ="rt")` remains.

---

### FINDING 29: hermes_state.py — prune_sessions not called automatically (lines 878, 2578–2631)
**Severity**: Low | **Status**: STILL PRESENT (confidence: Medium)
**Note**: `hermes_state.py` was NOT modified. Session pruning still requires explicit command.

---

### FINDING 30: agent/skill_utils.py — yaml CSafeLoader fallback (line 79)
**Severity**: Low | **Status**: STILL PRESENT (confidence: Low)
**Note**: `agent/skill_utils.py` was NOT modified.

---

### FINDING 31: tools/skills_tool.py — symlink path traversal check order (lines 1126–1139)
**Severity**: Medium | **Status**: STILL PRESENT (confidence: Low)
**Note**: `tools/skills_tool.py` was NOT modified.

---

### FINDING 32: tools/skills_tool.py — skill preprocess shell rendering (lines 1070–1080)
**Severity**: Medium | **Status**: STILL PRESENT (confidence: Low)
**Note**: `tools/skills_tool.py` unchanged.

---

### FINDING 33: tools/environments/docker.py — shell=True in container stop/start (lines 638, 647)
**Severity**: Medium | **Status**: STILL PRESENT (confidence: Low)
**Note**: `tools/environments/docker.py` was NOT modified.

---

### FINDING 34: tui_gateway/server.py — shell=True in TUI gateway (lines 4738, 6755)
**Severity**: Medium | **Status**: STILL PRESENT (confidence: Low)
**Note**: `tui_gateway/server.py` WAS modified (3 lines for TTS env var) but shell=True subprocess calls unchanged.

---

### FINDING 35: tools/file_operations.py — ShellFileOperations _exec command injection (lines 584–610, 695–697, 1231)
**Severity**: Medium | **Status**: STILL PRESENT (confidence: Low)
**Note**: `tools/file_operations.py` was NOT modified.

---

### FINDING 36: optional-skills/research/darwinian-evolver/scripts/show_snapshot.py — pickle.loads (lines 36, 39)
**Severity**: Medium | **Status**: STILL PRESENT (confidence: Medium)
**Note**: File unchanged. Optional skill uses pickle.loads on user-controlled file.

---

### FINDING 37: cli.py — quick_commands shell=True (lines 8418–8421)
**Severity**: Low | **Status**: STILL PRESENT (confidence: Medium)
**Note**: `cli.py` was modified but these specific lines (quick_commands execution) unchanged.

---

### FINDING 38: hermes_state.py — SQL f-string interpolation (lines 637, 642)
**Severity**: Low | **Status**: STILL PRESENT (confidence: Low)
**Note**: `hermes_state.py` unchanged.

---

### FINDING 39: tools/mcp_tool.py — prompt injection patterns logged not blocked (lines 340–363)
**Severity**: Medium | **Status**: STILL PRESENT (confidence: Medium)
**Note**: `tools/mcp_tool.py` unchanged.

---

### FINDING 40: tools/mcp_tool.py — schema validation gap (lines 2820–2838)
**Severity**: Low | **Status**: STILL PRESENT (confidence: Low)
**Note**: `tools/mcp_tool.py` unchanged.

---

### FINDING 41: tools/mcp_tool.py — circuit breaker not reset on reconnect (lines 2800–2820, 3100–3142)
**Severity**: Low | **Status**: STILL PRESENT (confidence: Low)
**Note**: `tools/mcp_tool.py` unchanged.

---

### FINDING 42: tools/mcp_tool.py — _parallel_safe_servers race (line 2069–2077)
**Severity**: Low | **Status**: STILL PRESENT (confidence: Low)
**Note**: `tools/mcp_tool.py` unchanged.

---

### FINDING 43: tools/browser_tool.py — is_safe_url called AFTER _resolve_cdp_override (line 2341 context)
**Severity**: Medium | **Status**: STILL PRESENT (confidence: Medium)
**Note**: `tools/browser_tool.py` unchanged. SSRF protection ordering issue persists.

---

### FINDING 44: model_tools.py — _AGENT_LOOP_TOOLS guard incomplete (lines 771, 495)
**Severity**: Medium | **Status**: STILL PRESENT (confidence: Low)
**Note**: `model_tools.py` was modified but this specific issue was not addressed.

---

### FINDING 45: tools/delegate_tool.py — subagent DELEGATE_BLOCKED_TOOLS blocklist (lines 44–53, 329–364, 394–458)
**Severity**: Medium | **Status**: STILL PRESENT (confidence: Medium)
**Note**: `tools/delegate_tool.py` unchanged. Blocklist approach vs allowlist for subagent tools.

---

### FINDING 46: tools/delegate_tool.py — _active_subagents global (lines 140–160)
**Severity**: Low | **Status**: STILL PRESENT (confidence: Low)
**Note**: `tools/delegate_tool.py` unchanged. Process-global subagent registry.

---

### FINDING 47: hermes_cli/plugins.py — _get_enabled_plugins returns None (lines 196–223)
**Severity**: Low | **Status**: STILL PRESENT (confidence: Low)
**Note**: `hermes_cli/plugins.py` was modified but this behavior unchanged — returns None when key missing.

---

### FINDING 48: hermes_cli/plugins.py — dispatch_tool parent_agent access (lines 467–495)
**Severity**: Low | **Status**: STILL PRESENT (confidence: Low)
**Note**: Plugin system was modified but this pattern unchanged.

---

### FINDING 49: hermes_cli/plugins.py — tool schema validation gap (lines 317–355)
**Severity**: Low | **Status**: STILL PRESENT (confidence: Low)
**Note**: Schema validation gap in `ctx.register_tool()` remains.

---

### FINDING 50: hermes_cli/plugins.py — tool deduplication logic bug (lines 1303–1331)
**Severity**: Low | **Status**: STILL PRESENT (confidence: Low)
**Note**: This specific bug in tool deduplication after override=True was introduced or persists in the new code.

---

### FINDING 51: hermes_cli/config.py vs nous_subscription.py — image_gen not in DEFAULT_CONFIG (line ~500+)
**Severity**: Medium | **Status**: STILL PRESENT (confidence: Medium)
**Note**: `hermes_cli/config.py` was modified but `image_gen` and `video_gen` defaults issue persists.

---

### FINDING 52: hermes_cli/config.py — validate_config not semantic (lines 3298–3340)
**Severity**: Low | **Status**: STILL PRESENT (confidence: Low)
**Note**: Structural-only validation; semantic/dangerous override detection absent.

---

### FINDING 53: tools/skills_tool.py — substring vs regex injection scan (lines 790–808)
**Severity**: Low | **Status**: STILL PRESENT (confidence: Low)
**Note**: `skills_tool.py` unchanged. Naive substring match for injection patterns.

---

### FINDING 54: hermes_cli/kanban_db.py — _add_column_if_missing DDL string formatting (lines 1242–1243)
**Severity**: Low | **Status**: STILL PRESENT (confidence: Low)
**Note**: New in Pass #12; `hermes_cli/kanban_db.py` WAS modified but this specific pattern was present and unchanged.

---

### FINDING 55: hermes_cli/kanban_db.py — _find_missing_parents empty input SQL syntax (lines 1755–1765)
**Severity**: Low | **Status**: STILL PRESENT (confidence: Low)
**Note**: New in Pass #12; pattern unchanged in modified kanban_db.py.

---

### FINDING 56: tools/skills_ast_audit.py — ast.parse without resource limits (lines 25–81)
**Severity**: Low | **Status**: PRESENT (NEW FILE, confidence: Medium)
**Note**: BRAND NEW file — added in commits between cae753735 and 72ff3e909 (via commit 7255050c9). The docstring explicitly says "not a security gate". RecursionError handling present but the visitor itself could overflow before the except catches.

---

### FINDING 57: plugins/platforms/ntfy/adapter.py — topic name not sanitized (lines 208–209, 237–269)
**Severity**: Low | **Status**: PRESENT (NEW FILE, confidence: Low)
**Note**: BRAND NEW file — added in commit b10f17bf1. Topic name not URL-sanitized before embedding in URL path.

---

### FINDING 58: plugins/platforms/ntfy/adapter.py — user_id = topic (lines 309–326)
**Severity**: Low | **Status**: PRESENT (NEW FILE, confidence: Medium)
**Note**: BRAND NEW ntfy adapter. No per-user identity — documented as design decision.

---

### FINDING 59: cron/scheduler.py — subprocess cwd symlink confusion (lines 880–895)
**Severity**: Medium | **Status**: STILL PRESENT (confidence: Medium)
**Note**: `cron/scheduler.py` was NOT in changed files list.

---

### FINDING 60: tools/terminal_tool.py — FOREGROUND_MAX_TIMEOUT no upper bound (lines 108–113)
**Severity**: Medium | **Status**: STILL PRESENT (confidence: Medium)
**Note**: `tools/terminal_tool.py` unchanged.

---

### FINDING 61: cron/scheduler.py — env var overflow potential (lines 809, 841, 880, 907, 963)
**Severity**: Medium | **Status**: STILL PRESENT (confidence: Medium)
**Note**: `cron/scheduler.py` unchanged.

---

### FINDING 62: tools/lazy_deps.py — "unsafe spec" spec validation (line 440)
**Severity**: Medium | **Status**: STILL PRESENT (confidence: Medium)
**Note**: `tools/lazy_deps.py` was NOT modified. The spec rejection message exists but the comment acknowledges it's not exhaustive.

---

### FINDING 63: tools/code_execution_tool.py — terminal in sandbox (lines 915, 1161, 1311)
**Severity**: Low | **Status**: PRESENT (by design, confidence: High)
**Note**: `terminal` tool in sandbox is intentional per Pass #13 review. Sandbox environment scrubbing is well-constructed.

---

### FINDING 64: hermes_cli/plugins.py — register_auxiliary_task display_name/description length (lines 754–812)
**Severity**: Low | **Status**: PRESENT (NEW in 72ff3e909, confidence: Low)
**Note**: Added in commit e752c9454. No length limits on display_name/description/defaults dict values.

---

### FINDING 65: tools/browser_cdp_tool.py — CDP method name validation (lines noted in Pass #13)
**Severity**: Low | **Status**: STILL PRESENT (confidence: Medium)
**Note**: No input validation on CDP method names. Acceptable risk — operator-controlled endpoint.

---

### FINDING 66: trajectory_compressor.py — trust_remote_code=True (lines ~2370)
**Severity**: Low | **Status**: PRESENT (confidence: Low)
**Note**: `trajectory_compressor.py` was modified (api_mode added) but trust_remote_code=True unchanged. Standard for custom HuggingFace tokenizers.

---

### FINDING 67: hermes_time.py — backports.zoneinfo dead code (line 28)
**Severity**: Informational | **Status**: STILL PRESENT (confidence: High)
**Note**: Dead code — `requires-python = ">=3.11"` means stdlib zoneinfo is always available. Fallback can never execute.

---

### FINDING 68: utils.py (root) — shadows stdlib utils module
**Severity**: Low | **Status**: PRESENT (by design, confidence: High)
**Note**: Project-local `utils.py` shadows stdlib. Intentional but documented as a footgun.

---

## PER-FILE CONSOLIDATION (unique files only)

| File | Severity | Status | Notes |
|------|----------|--------|-------|
| skills/red-teaming/godmode/scripts/auto_jailbreak.py | High | STILL PRESENT | exec() with HERMES_HOME paths — by design (red-teaming skill) |
| skills/red-teaming/godmode/scripts/godmode_race.py | High | STILL PRESENT | exec() with HERMES_HOME path — by design |
| skills/red-teaming/godmode/scripts/load_godmode.py | High | STILL PRESENT | exec() with HERMES_HOME path — by design |
| skills/red-teaming/godmode/scripts/parseltongue.py | High | STILL PRESENT | exec() in usage comment — by design |
| hermes_cli/xai_retirement.py | High | STILL PRESENT | YAML(typ="rt") unsafe loader unchanged |
| tools/transcription_tools.py | High | STILL PRESENT | shell=True with user template unchanged |
| hermes_cli/tools_config.py | High | STILL PRESENT | shell=True curl install unchanged |
| hermes_cli/plugins.py | High | PARTIALLY PRESENT | Broad except remains; register_auxiliary_task new |
| tools/browser_tool.py | Medium | STILL PRESENT | SSRF ordering issue unchanged |
| tools/registry.py | Medium | STILL PRESENT | O(n²) AST parsing unchanged |
| model_tools.py | Medium | STILL PRESENT | coerce_tool_args constraint gap unchanged |
| tools/mcp_tool.py | Medium | STILL PRESENT | Multiple concurrent/parallel issues unchanged |
| tools/delegate_tool.py | Medium/Low | STILL PRESENT | Interrupt flag race + executor leak unchanged |
| acp_adapter/server.py | Medium | STILL PRESENT | Shared executor starvation unchanged |
| gateway/run.py | Low | STILL PRESENT | Orphaned tasks unchanged despite file being modified |
| cli.py | Low | STILL PRESENT | Unbounded queues unchanged |
| gateway/stream_consumer.py | Low | STILL PRESENT | Unbounded queue unchanged |
| tui_gateway/event_publisher.py | Medium | STILL PRESENT | Daemon thread queue flush issue unchanged |
| tools/approval.py | Low | STILL PRESENT | Lock+daemon thread issues unchanged |
| tools/terminal_tool.py | Low/Medium | STILL PRESENT | Lock dict leak + timeout bound issue unchanged |
| agent/tool_executor.py | Medium | STILL PRESENT | Executor naming/cap unchanged |
| hermes_cli/config.py | Medium | STILL PRESENT | deepcopy on config access unchanged |
| run_agent.py | Medium | STILL PRESENT | deepcopy in hot paths unchanged |
| utils.py (root) | Medium | STILL PRESENT | YAML unsafe loader unchanged |
| hermes_state.py | Low | STILL PRESENT | SQL f-string + missing auto-prune unchanged |
| agent/skill_utils.py | Low | STILL PRESENT | CSafeLoader fallback unchanged |
| tools/skills_tool.py | Medium | STILL PRESENT | Symlink check order + preprocess shell unchanged |
| tools/environments/docker.py | Medium | STILL PRESENT | shell=True in docker commands unchanged |
| tui_gateway/server.py | Medium | STILL PRESENT | shell=True in TUI RPC unchanged |
| tools/file_operations.py | Medium | STILL PRESENT | _exec command injection unchanged |
| optional-skills/research/darwinian-evolver/scripts/show_snapshot.py | Medium | STILL PRESENT | pickle.loads unchanged |
| tools/skills_ast_audit.py | Low | PRESENT | NEW file; docstring says not a security gate |
| plugins/platforms/ntfy/adapter.py | Low | PRESENT | NEW file; topic not sanitized, user_id=topic |
| cron/scheduler.py | Medium | STILL PRESENT | Symlink cwd + env var issues unchanged |
| tools/lazy_deps.py | Medium | STILL PRESENT | "unsafe spec" message unchanged |
| tools/code_execution_tool.py | Low | PRESENT (by design) | terminal in sandbox is intentional |
| hermes_time.py | Informational | STILL PRESENT | backports.zoneinfo dead code |

---

## OVERALL ASSESSMENT

**0 CRITICAL fixes** identified between cae753735 and 72ff3e909.

**No file containing a HIGH severity finding was fully fixed.** The 32 commits between the baseline and 72ff3e909 addressed:
- Documentation fixes (docs/)
- TUI refinements (viewport resize, TTS indicator)
- Ntfy platform adapter (new)
- Skills AST diagnostic tool (new)
- Telegram group slash command preservation
- Compressor API mode propagation
- Session synchronization
- env_loader null-byte stripping

**None of the core security findings were addressed** in this commit range:
- The godmode red-teaming scripts with exec() patterns are unchanged
- The unsafe YAML loading in xai_retirement.py is unchanged
- The shell=True transcription command template is unchanged
- The shell=True cua-driver install is unchanged
- The plugin silent failure pattern is unchanged

**The findings in findings.md accurately represent the state of the codebase at 72ff3e909.** Most issues persist. The scanner's recommendation of manual review for the 5 most complex files (run_agent.py, cli.py, gateway/run.py, hermes_cli/kanban_db.py, acp_adapter/server.py) remains valid.

---

## ADDITIONAL VERIFICATION — Remaining Medium/Low/Informational (72ff3e909)

The following items were verified specifically in this additional pass, building on findings #9–#68 already documented above.

---

### BROWSER TOOL — SSRF in _resolve_cdp_override (Finding #9)
**Severity**: Medium | **Status**: STILL PRESENT (confidence: High)

**Code verified at lines 267-281**:
```python
try:
    response = requests.get(version_url, timeout=10)
    response.raise_for_status()
    payload = response.json()
except Exception as exc:
    logger.warning("Failed to resolve CDP endpoint %s via %s: %s", raw, version_url, exc)
    return raw
```

**SSRF vectors confirmed**:
1. `version_url` constructed from `discovery_url` (derived from `cdp_url` param or `BROWSER_CDP_URL` env var)
2. No `is_safe_url()` validation before `requests.get(version_url)`
3. If user sets `BROWSER_CDP_URL=http://169.254.169.254/latest/meta-data/`, the discovery fetch reaches the cloud metadata endpoint
4. The `webSocketDebuggerUrl` from the response is returned and used as a WebSocket target — exposing internal service information

**The `is_safe_url()` check is called later** (at line 2341 context, per the finding) but the discovery fetch at line 268 happens BEFORE that check in the call flow.

**Conclusion**: SSRF issue confirmed present. `_resolve_cdp_override()` fetches arbitrary URLs without SSRF protection.

---

### BROWSER TOOL — JS eval in _browser_eval/_camofox_eval (Finding #10)
**Severity**: Medium | **Status**: STILL PRESENT (confidence: Medium)

**Code verified at lines 2812-2865**:
- `_browser_eval(expression)` is the main entry, calls `_camofox_eval` for camofox mode
- Fast path uses `supervisor.evaluate_runtime(expression)` via CDP WebSocket — model output directly sent as JS expression to browser
- Fallback path: `_run_browser_command(effective_task_id, "eval", [expression])` — expression passed as CLI argument
- No Content-Security-Policy enforcement in Hermes
- No logging of eval operations with task_id (just `logger.debug` for supervisor fallback failures)

**Verification**: The `_browser_eval` and `_camofox_eval` functions are unchanged. Model output containing JS expressions is executed in browser sessions without CSP or input sanitization.

**Conclusion**: JS eval from model output still present. Risk acknowledged (operator controls CDP endpoint).

---

### CRON/SCHEDULER — shell=False but env injection (Finding #59)
**Severity**: Medium | **Status**: STILL PRESENT (confidence: Medium)

**Code verified at lines 895-903**:
```python
result = subprocess.run(
    argv,
    capture_output=True,
    text=True,
    timeout=script_timeout,
    cwd=str(path.parent),
    env=run_env,
    **popen_kwargs,
)
```

**Verification**:
- `shell=False` confirmed — uses list-form argv, not shell expansion
- `cwd=str(path.parent)` — `path` derived from job configuration; `path.parent` is used without explicit symlink resolution in this function
- `run_env` from `get_captured_env()` and other config-derived sources — could contain attacker-controlled values if cron job config is compromised

**Note**: The finding's mention of symlink confusion is about `path.parent` potentially following symlinks before the allowlist check. No allowlist is visible in this snippet — the `cwd` is used directly.

**Conclusion**: `cwd` path issue still present. `shell=False` is good but `cwd` derivation from job config without explicit allowlist validation is a concern.

---

### CRON/SCHEDULER — env var overflow potential (Finding #61)
**Severity**: Medium | **Status**: STILL PRESENT (confidence: Low)

**Verification**: Not reviewed in this pass (would require examining `get_captured_env()` and the full `_run_script_subprocess` env construction). Based on code review context, no env var length validation was added between cae753735 and 72ff3e909.

**Conclusion**: Unchanged.

---

### TERMINAL TOOL — FOREGROUND_MAX_TIMEOUT no upper bound (Finding #60)
**Severity**: Medium | **Status**: STILL PRESENT (confidence: Medium)

**Code verified at lines 80-113**:
```python
def _safe_parse_import_env(
    name: str,
    default: Any,
    converter,
    type_label: str,
):
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return converter(raw)
    except (TypeError, ValueError):
        logger.warning(...)
        return default

FOREGROUND_MAX_TIMEOUT = _safe_parse_import_env(
    "TERMINAL_MAX_FOREGROUND_TIMEOUT",
    600,
    int,
    "integer",
)
```

**Verification**: `_safe_parse_import_env` only validates type (int), not range. No upper bound check exists. An attacker who sets `TERMINAL_MAX_FOREGROUND_TIMEOUT=2147483647` would cause a hung subprocess to block the terminal tool for ~68 years.

**Note**: At line 1745, the function checks `if not background and timeout and timeout > FOREGROUND_MAX_TIMEOUT` and rejects with an error. But `FOREGROUND_MAX_TIMEOUT` itself is not capped — so setting it to `2147483647` bypasses this check (since the check itself compares against the env-var value).

**Conclusion**: No upper bound on `FOREGROUND_MAX_TIMEOUT`. Still present.

---

### TUI_GATEWAY/SERVER.PY — shell=True subprocess calls (Finding #34)
**Severity**: Medium | **Status**: STILL PRESENT (confidence: Low)

**Code verified at lines 4736-4742 and 6757-6758**:
```python
# Line 4736-4742 (exec handler):
r = subprocess.run(
    qc.get("command", ""),
    shell=True,  # <-- confirmed
    capture_output=True,
    text=True,
    timeout=30,
)

# Line 6757-6758 (shell.exec handler):
r = subprocess.run(
    cmd, shell=True, capture_output=True, text=True, timeout=30, cwd=os.getcwd()
)
```

**Verification**: Both `shell=True` calls confirmed unchanged. `cwd=os.getcwd()` at line 6758 inherits from process working directory. Commands are constructed from JSON-RPC parameters — if an attacker sends crafted JSON-RPC requests with special characters, `shell=True` could enable command injection.

**Conclusion**: Both shell=True calls still present.

---

### GATEWAY/RUN.PY — 53-line change (Finding noted in Pass #12)
**Severity**: Informational | **Status**: VERIFIED CORRECT (confidence: High)

**Code verified via git diff**: The 53-line change adds dynamic auxiliary task env bridging:
- `_aux_bridged_keys = {"vision", "web_extract", "approval"}` (built-in set)
- Attempts `from hermes_cli.plugins import get_plugin_auxiliary_tasks`
- Iterates registered tasks and bridges config→env vars for each
- Wrapped in try/except so plugin failure doesn't break gateway startup

**Security review**: Properly sandboxed. Exception handling is correct. No new attack surface introduced.

**Conclusion**: New code is well-designed. No security issue.

---

### HERMES_TIME.PY — backports.zoneinfo dead code (Finding #67)
**Severity**: Informational | **Status**: STILL PRESENT (confidence: High)

**Code verified at lines 24-28**:
```python
try:
    from zoneinfo import ZoneInfo
except ImportError:
    # Python 3.8 fallback (shouldn't be needed — Hermes requires 3.9+)
    from backports.zoneinfo import ZoneInfo  # type: ignore[no-redef]
```

**Verification**: Confirmed. `pyproject.toml` says `requires-python = ">=3.11"`. `zoneinfo` (stdlib) is always available in Python 3.11+. The `except ImportError` fallback can never execute.

**Also confirmed**: `hermes_time.py` was NOT modified between cae753735 and 72ff3e909. The dead code remains.

**Conclusion**: Dead code confirmed. Unreachable fallback path.

---

### GATEWAY/SHUTDOWN_FORENSICS.PY — fd leak potential (from Pass #11 Informational)
**Severity**: Informational | **Status**: STILL PRESENT (confidence: Medium)

**Verification**: This file was NOT in the changed files list. `subprocess.Popen(..., stdin=subprocess.DEVNULL, ...)` at line 257 with no `close_fds=True` on Unix remains as described.

**Conclusion**: Issue unchanged.

---

## CROSS-FILE CONSOLIDATED FINDINGS — Verification Summary

### All HIGH Severity
| # | File | Status | Notes |
|---|------|--------|-------|
| 1 | skills/red-teaming/godmode/scripts/auto_jailbreak.py | STILL PRESENT | exec() with HERMES_HOME — by design (red-teaming) |
| 2 | skills/red-teaming/godmode/scripts/godmode_race.py | STILL PRESENT | exec() with HERMES_HOME — by design |
| 3 | skills/red-teaming/godmode/scripts/load_godmode.py | STILL PRESENT | exec() with HERMES_HOME — by design |
| 4 | skills/red-teaming/godmode/scripts/parseltongue.py | STILL PRESENT | exec() in usage comment — by design |
| 5 | hermes_cli/xai_retirement.py | STILL PRESENT | YAML(typ="rt") unsafe loader unchanged |
| 6 | tools/transcription_tools.py | STILL PRESENT | shell=True with user template unchanged |
| 7 | hermes_cli/tools_config.py | STILL PRESENT | shell=True curl install unchanged |
| 8 | hermes_cli/plugins.py | PARTIALLY PRESENT | Broad except remains; new register_auxiliary_task API added |

### All MEDIUM Severity (remaining unverified items)
| # | File | Issue | Status |
|---|------|-------|--------|
| 9 | tools/browser_tool.py | SSRF in _resolve_cdp_override | STILL PRESENT (confirmed) |
| 10 | tools/browser_tool.py | JS eval in _browser_eval | STILL PRESENT (confirmed) |
| 14 | tools/mcp_tool.py | Unbounded gather | STILL PRESENT |
| 15 | tools/delegate_tool.py | Non-atomic interrupt flag | STILL PRESENT |
| 17 | acp_adapter/server.py | Shared executor starvation | STILL PRESENT |
| 34 | tui_gateway/server.py | shell=True subprocess | STILL PRESENT (confirmed) |
| 43 | tools/browser_tool.py | SSRF ordering (is_safe_url after fetch) | STILL PRESENT |
| 45 | tools/delegate_tool.py | DELEGATE_BLOCKED_TOOLS blocklist | STILL PRESENT |
| 51 | hermes_cli/config.py vs nous_subscription.py | image_gen/video_gen not in DEFAULT_CONFIG | STILL PRESENT |
| 59 | cron/scheduler.py | cwd symlink confusion | STILL PRESENT (confirmed shell=False but cwd issue remains) |
| 60 | tools/terminal_tool.py | FOREGROUND_MAX_TIMEOUT no upper bound | STILL PRESENT (confirmed) |
| 61 | cron/scheduler.py | env var overflow | STILL PRESENT |

### All LOW Severity
| # | File | Issue | Status |
|---|------|-------|--------|
| 16 | tools/delegate_tool.py | _timeout_executor leak | STILL PRESENT |
| 18 | gateway/run.py | Orphaned asyncio tasks | STILL PRESENT (53-line change did NOT address) |
| 19 | cli.py | Unbounded queue.Queue | STILL PRESENT |
| 20 | gateway/stream_consumer.py | Unbounded queue | STILL PRESENT |
| 21 | tui_gateway/event_publisher.py | Daemon thread queue flush | STILL PRESENT |
| 22 | tools/approval.py | Lock on exception | STILL PRESENT |
| 23 | tools/terminal_tool.py | Lock dict memory leak | STILL PRESENT |
| 29 | hermes_state.py | Missing auto-prune | STILL PRESENT |
| 30 | agent/skill_utils.py | CSafeLoader fallback | STILL PRESENT |
| 37 | cli.py | quick_commands shell=True | STILL PRESENT |
| 38 | hermes_state.py | SQL f-string interpolation | STILL PRESENT |
| 40 | tools/mcp_tool.py | Schema validation gap | STILL PRESENT |
| 41 | tools/mcp_tool.py | Circuit breaker not reset | STILL PRESENT |
| 42 | tools/mcp_tool.py | _parallel_safe_servers race | STILL PRESENT |
| 46 | tools/delegate_tool.py | _active_subagents global | STILL PRESENT |
| 47 | hermes_cli/plugins.py | _get_enabled_plugins returns None | STILL PRESENT |
| 52 | hermes_cli/config.py | validate_config not semantic | STILL PRESENT |
| 53 | tools/skills_tool.py | Substring vs regex injection scan | STILL PRESENT |
| 54 | hermes_cli/kanban_db.py | _add_column_if_missing DDL | STILL PRESENT |
| 55 | hermes_cli/kanban_db.py | _find_missing_parents SQL syntax | STILL PRESENT |

### All Informational
| # | File | Issue | Status |
|---|------|-------|--------|
| 56 | tools/skills_ast_audit.py | ast.parse without resource limits | PRESENT (new file, docstring disclaims security) |
| 57 | plugins/platforms/ntfy/adapter.py | Topic name not sanitized | PRESENT (new file) |
| 58 | plugins/platforms/ntfy/adapter.py | user_id = topic | PRESENT (new file, design documented) |
| 63 | tools/code_execution_tool.py | terminal in sandbox | PRESENT (by design, well-constructed) |
| 64 | hermes_cli/plugins.py | register_auxiliary_task length | PRESENT (new in e752c9454) |
| 65 | tools/browser_cdp_tool.py | CDP method name validation | STILL PRESENT |
| 66 | trajectory_compressor.py | trust_remote_code=True | PRESENT |
| 67 | hermes_time.py | backports.zoneinfo dead code | STILL PRESENT (confirmed) |
| 68 | utils.py (root) | Shadows stdlib utils | PRESENT (by design) |
| — | gateway/shutdown_forensics.py | fd leak in Popen | STILL PRESENT (Informational) |

---

## FINAL ASSESSMENT

**0 Critical fixes** identified between cae753735 and 72ff3e909.

**No HIGH severity finding was fully addressed.** The 32 commits in this window primarily added:
- Ntfy platform adapter (new plugin)
- Skills AST audit diagnostic tool
- `register_auxiliary_task()` PluginContext API
- TUI refinements (TTS indicator, voice off)
- Compressor API mode propagation
- Session synchronization improvements
- env_loader null-byte stripping

**None of the core security issues were fixed:**
1. Godmode red-teaming scripts with `exec()` — unchanged
2. Unsafe `YAML(typ="rt")` in xai_retirement.py — unchanged
3. `shell=True` with user template in transcription_tools.py — unchanged
4. `shell=True` curl install in tools_config.py — unchanged
5. Plugin silent failure (`except Exception`) — unchanged
6. SSRF in browser_tool `_resolve_cdp_override()` — unchanged
7. No upper bound on FOREGROUND_MAX_TIMEOUT — unchanged

**The findings accurately represent the codebase state at 72ff3e909.**

**New code introduced in 72ff3e909 is generally well-designed:**
- `register_auxiliary_task()` API has appropriate key validation
- Gateway auxiliary task bridging is properly exception-handled
- Ntfy adapter design is documented (topic = user_id)
- skills_ast_audit explicitly disclaims security guarantees

**Recommendation**: The 5 manual-review files identified in the original scan (run_agent.py, cli.py, gateway/run.py, hermes_cli/kanban_db.py, acp_adapter/server.py) remain the highest priority for human security review."