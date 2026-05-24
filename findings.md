---

## Pass #70 – Plugin Lifecycle, Hot-Reload & Dynamic Discovery Deep Dive – 2026-05-25T12:00:00Z

Scope: `hermes_cli/plugins.py` (1725 lines), `hermes_cli/plugins_cmd.py` (1636 lines), `plugins/memory/__init__.py` (407 lines), `plugins/context_engine/__init__.py` (219 lines), `agent/shell_hooks.py`, key call sites in `cli.py`, `gateway/run.py`, `model_tools.py`, `agent/conversation_loop.py`.

---

### P70-1 · No on_load / on_unload lifecycle hooks — plugins register at discover time only — MEDIUM

**File:** `hermes_cli/plugins.py` lines 128-168 (VALID_HOOKS), 1284-1351 (_load_plugin)  
**Severity:** MEDIUM

The plugin lifecycle consists of exactly two transition points:

1. `register(ctx)` is called immediately after the module is imported (`_load_plugin` line 1307).
2. `invoke_hook()` is called for event-driven hooks (session start/end, tool calls, LLM calls).

There is **no `on_load` / `on_unload` hook** and no cleanup when a plugin is reloaded. Specifically:

- `_load_plugin()` calls `register(ctx)` but there is no symmetric `unregister()` or `on_unload()` call.
- When `discover_plugins(force=True)` is called, `self._plugins.clear()` and all `_hooks`, `_plugin_tool_names`, `_cli_commands`, `_plugin_commands`, `_plugin_skills`, `_aux_tasks`, `_context_engine` are cleared (lines 915-923) — but **no hook callbacks are invoked before clearing**, and **no module teardown** is performed.
- `sys.modules` entries for plugins (`hermes_plugins.<slug>`) are **never removed** on reload. A reloaded plugin's new `register(ctx)` runs while the old module still occupies `sys.modules[module_name]`. The module object is replaced in the dict, but any lingering references (e.g., in other modules that imported the plugin) will still see the old version.
- The `LoadedPlugin` objects (line 271-281) track `tools_registered`, `hooks_registered`, `commands_registered` — but there is no `tools_unregister()` / `hooks_unregister()` call when clearing.

**Impact:** State from a previously-loaded plugin (registered tools, hooks, platforms) persists in the registry even after `force=True` reload, because only the lists in `self._plugins` are cleared — not the actual global registries (`tools.registry`, `platform_registry`, etc.).

---

### P70-2 · No plugin code validation — arbitrary code executes at load time — HIGH

**File:** `hermes_cli/plugins.py` lines 1353-1389 (_load_directory_module), 1391-1407 (_load_entrypoint_module)  
**Related:** `plugins/memory/__init__.py` lines 185-285, `plugins/context_engine/__init__.py` lines 100-196  
**Severity:** HIGH

Plugin loading is **not sandboxed** in any way:

1. `_load_directory_module()` (line 1384-1388): Uses `importlib.util.spec_from_file_location` + `spec.loader.exec_module(module)` — this executes the plugin's `__init__.py` directly in the Hermes process with full access to `sys.modules`, the filesystem, network, etc.
2. `_load_entrypoint_module()` (line 1403): Uses `ep.load()` which is equivalent to `importlib.import_module` — same unrestricted execution.
3. For memory providers (`plugins/memory/__init__.py` lines 257-258) and context engines (`plugins/context_engine/__init__.py` lines 168-169): Same pattern — `spec.loader.exec_module(mod)`.
4. The manifest parsing uses `yaml.safe_load()` (line 1174), which is safe for YAML deserialization but does not restrict what the plugin code can do.

**No validation step exists** — there is no:
- AST inspection of the plugin code before execution
- Restricted `__builtins__` or sandboxed `exec()`
- Resource limits (CPU, memory, file I/O) per plugin
- Allowlist of accessible modules

A malicious or buggy plugin can:
- Access `~/.hermes/.env` directly (read env vars)
- Overwrite or patch any Hermes global state
- Import arbitrary system modules (`os`, `subprocess`, `socket`, etc.)
- Modify `sys.modules` to intercept future imports

---

### P70-3 · Hot reload doesn't clean sys.modules or global registries — state leak — MEDIUM

**File:** `hermes_cli/plugins.py` lines 906-924 (discover_and_load force path), 1353-1389  
**Severity:** MEDIUM

When `discover_plugins(force=True)` is called:

1. `self._plugins.clear()` removes the `LoadedPlugin` objects from the manager's dict.
2. `_hooks`, `_plugin_tool_names`, `_cli_commands`, `_plugin_commands`, `_plugin_skills`, `_aux_tasks` are all cleared (lines 917-922).
3. `_context_engine` is set to `None` (line 923).

**However:**
- `sys.modules[module_name]` (the plugin module itself) is **never removed**.
- Global registries (`tools.registry`, `platform_registry`) are **not cleaned** — tools and platforms registered by the old plugin remain registered even after `_load_plugin` runs again.
- `LoadedPlugin.module` references the old module object; when the new module is loaded into `sys.modules[module_name]`, the `LoadedPlugin` for that key is updated — but if any other code holds a reference to the old module object, it persists.

For example, a plugin that registers a tool: the tool name stays in `tools.registry` permanently. On `force=True` reload, the new plugin's `register()` adds the tool again (possibly as a duplicate with different handler). There is no deduplication on re-registration in `tools.registry`.

---

### P70-4 · Two invoke_hook() implementations with inconsistent exception handling — LOW

**File:** `hermes_cli/plugins.py` lines 1413-1447 (PluginManager.invoke_hook), 1521-1526 (module-level invoke_hook)  
**Related:** Findings.md P35-4  
**Severity:** LOW (already documented as P35-4, re-confirmed here)

`PluginManager.invoke_hook()` (instance method, line 1413) wraps each callback in try/except and logs failures (lines 1436-1446). The module-level `invoke_hook()` (line 1521) calls `get_plugin_manager().invoke_hook()` — so it ultimately hits the same instance method.

However, the module-level function is public and could theoretically be called directly with different kwargs. The instance method is the one that matters for exception handling.

**No change** from P35-4 — this remains outstanding.

---

### P70-5 · No plugin signature verification or source authentication — INFO

**File:** `hermes_cli/plugins.py` (discovery), `hermes_cli/plugins_cmd.py` (install), `ENTRY_POINTS_GROUP = "hermes_agent.plugins"`  
**Severity:** INFO

Plugin discovery accepts code from four sources:

1. **Bundled plugins** (`<repo>/plugins/<name>/`) — trusted, shipped with repo.
2. **User plugins** (`~/.hermes/plugins/<name>/`) — user-controlled, unvalidated.
3. **Project plugins** (`./.hermes/plugins/<name>/`) — opt-in, unvalidated.
4. **Pip entry-point plugins** — published to PyPI, unvalidated.

**No signature verification exists** at any level:
- No GPG/signed manifests
- No hash verification of plugin code
- No trusted publisher list
- `hermes plugins install` clones from git (with `_sanitize_plugin_name` path traversal protection, lines 80-133 in `plugins_cmd.py`) but does **not** verify git commit signatures or tags.

The `_sanitize_plugin_name()` function in `plugins_cmd.py` provides **path traversal protection** (lines 99-133):
- Rejects `..`, `\`, and `/` (unless `allow_subdir=True`)
- Resolves path and uses `relative_to()` to verify the target is within the plugins directory
- This is good — it prevents writing outside the plugin directory

But the code cloned from git has no cryptographic integrity check.

---

### P70-6 · Memory/context engine providers re-load into sys.modules without cleanup — MEDIUM

**File:** `plugins/memory/__init__.py` lines 185-285, `plugins/context_engine/__init__.py` lines 100-196  
**Severity:** MEDIUM

Memory providers and context engines both follow the same pattern: they use `importlib.util.spec_from_file_location()` to load `__init__.py` directly into `sys.modules` with no sandboxing.

**Memory provider loading** (`plugins/memory/__init__.py`):
- Module name: `plugins.memory.{name}` for bundled, `_hermes_user_memory.{name}` for user-installed (line 196).
- `sys.modules[module_name] = mod` (line 236) — **overwrites any previous module with the same name**.
- On reload of the same provider: the old module is simply replaced in `sys.modules`.
- Submodules are registered as `plugins.memory.{name}.{submodule}` (lines 240-255) — these are **never cleaned up**.

**Context engine loading** (`plugins/context_engine/__init__.py`):
- Same pattern, same lack of cleanup.
- Submodules registered as `plugins.context_engine.{name}.{submodule}` (lines 155-166) — never cleaned up.

The `_ProviderCollector` (memory) and `_EngineCollector` (context engine) are lightweight fake contexts with only a `provider` or `engine` attribute — no tracking of what was registered, no cleanup method.

---

### P70-7 · _scan_directory has no path traversal guard — lower risk but noteworthy — INFO

**File:** `hermes_cli/plugins.py` lines 1078-1157 (_scan_directory / _scan_directory_level)  
**Severity:** INFO

`_scan_directory` uses `path.iterdir()` to discover plugins. It accepts:
- `skip_names` to skip certain top-level directories (used to skip `memory`, `context_engine`, `platforms`, `model-providers`)
- Depth cap of 2 levels to prevent infinite recursion

However, there is **no explicit path traversal check** inside `_scan_directory_level`. A malicious directory structure like `plugins/../../../etc/myplugin/` could theoretically be traversed if the filesystem allows symlinks or unusual permissions.

**Mitigating factors:**
- `Path.iterdir()` follows symlinks by default in Python — but the target must actually be within the repo or home directory to be reachable.
- Project plugins are opt-in (`HERMES_ENABLE_PROJECT_PLUGINS` must be set).
- `_parse_manifest` uses `yaml.safe_load` which is safe.
- The primary attack surface is the install command, which is protected by `_sanitize_plugin_name`.

**Note:** This is lower risk than P70-1 through P70-3 because the directory scanning happens at discover time, not execution time.

---

### P70-8 · Exclusive and model-provider plugin kinds skip loading but still occupy _plugins dict — INFO

**File:** `hermes_cli/plugins.py` lines 1004-1032 (exclusive/model-provider handling)  
**Severity:** INFO

When a plugin's `kind` is `"exclusive"` or `"model-provider"`:

1. The `LoadedPlugin` is created with `enabled=False` (line 1008 or 1026).
2. Error message is set: `"exclusive plugin — activate via <category>.provider config"` or `"model-provider, handled by providers/ discovery"`.
3. The entry is stored in `self._plugins` (line 1012 or 1027).

This is intentional — the plugin manifest is recorded for introspection (`list_plugins()`). However, the design means:
- `list_plugins()` will show exclusive/model-provider plugins as "enabled=False" with an error string — this is informative but could be confusing if the user expects them to be loadable.
- The deduplication logic (`winners` dict) correctly handles multiple sources (bundled/user/project) because it uses the path-derived key, so later sources can override earlier ones.

---

### P70-9 · Hook callback list iteration is not thread-safe during concurrent reload — LOW

**File:** `hermes_cli/plugins.py` lines 1433-1447 (invoke_hook)  
**Severity:** LOW

`invoke_hook()` iterates `self._hooks.get(hook_name, [])` and calls each callback. If `discover_plugins(force=True)` is called concurrently from another thread:

1. `invoke_hook()` holds a reference to the hook list (`[cb1, cb2, cb3]`) from `self._hooks`.
2. Meanwhile, `discover_and_load(force=True)` calls `self._hooks.clear()` (line 917).
3. The list iteration proceeds on whatever list `self._hooks.get()` returned — if `clear()` replaced it with a new empty dict, the old list is still being iterated.

Python GIL protects the immediate dictionary access, but the list reference is captured before iteration begins. If another thread clears `_hooks` and then adds new hooks, the iteration could span old and new hooks unpredictably. This is a race condition.

**Note:** This is only triggered if `discover_plugins(force=True)` is called while hook callbacks are actively firing — which is unlikely in normal operation but possible in long-running gateway processes that also support dynamic plugin updates.

---

## Summary

The plugin system is well-structured with clear separation between bundled/user/project/entrypoint sources, good path traversal protection in the install command, and a comprehensive hook system. However, it has significant gaps in three areas:

**Security (HIGH):** No plugin code validation — arbitrary Python executes in the Hermes process with full system access. No signature verification. No sandboxing.

**Lifecycle/Cleanup (MEDIUM):** No `on_load`/`on_unload` hooks. Hot reload (`force=True`) clears the manager's dicts but leaves `sys.modules` entries, global tool/platform registry entries, and hook registrations untouched. State from previously-loaded plugins leaks into the running process.

**Concurrency (LOW):** Hook callback iteration is not protected against concurrent `force=True` reload.

**Positive notes:**
- `yaml.safe_load` is used correctly for manifest parsing (not `yaml.load`).
- Path traversal protection in `_sanitize_plugin_name` is well-implemented with `relative_to()` checking.
- The `VALID_HOOKS` set is well-defined and hooks are called at appropriate lifecycle points.
- Hook callbacks are individually wrapped in try/except so one plugin's crash doesn't kill the agent loop.
- Memory and context engine plugins use separate discovery paths with their own module namespaces (`_hermes_user_memory.*` vs `plugins.memory.*`).

---

**Files examined in this pass:**  
`hermes_cli/plugins.py` (1725 lines, primary), `hermes_cli/plugins_cmd.py` (1636 lines, install/discover), `plugins/memory/__init__.py` (407 lines), `plugins/context_engine/__init__.py` (219 lines), `agent/shell_hooks.py` (443 lines, hook integration), `cli.py` lines 880-930 (deferred startup), `gateway/run.py` (hook call sites), `agent/conversation_loop.py` (hook call sites), `model_tools.py` (hook call sites).

---

## Pass #70 – Plugin Lifecycle, Hot-Reload & Dynamic Discovery Deep Dive – 2026-05-25T12:00:00Z

Scope: `hermes_cli/plugins.py` (1725 lines), `hermes_cli/plugins_cmd.py` (1636 lines), `plugins/memory/__init__.py` (407 lines), `plugins/context_engine/__init__.py` (219 lines), `agent/shell_hooks.py`, key call sites in `cli.py`, `gateway/run.py`, `model_tools.py`, `agent/conversation_loop.py`.

---

### P70-1 · No on_load / on_unload lifecycle hooks — plugins register at discover time only — MEDIUM

**File:** `hermes_cli/plugins.py` lines 128-168 (VALID_HOOKS), 1284-1351 (_load_plugin)  
**Severity:** MEDIUM

The plugin lifecycle consists of exactly two transition points:

1. `register(ctx)` is called immediately after the module is imported (`_load_plugin` line 1307).
2. `invoke_hook()` is called for event-driven hooks (session start/end, tool calls, LLM calls).

There is **no `on_load` / `on_unload` hook** and no cleanup when a plugin is reloaded. Specifically:

- `_load_plugin()` calls `register(ctx)` but there is no symmetric `unregister()` or `on_unload()` call.
- When `discover_plugins(force=True)` is called, `self._plugins.clear()` and all `_hooks`, `_plugin_tool_names`, `_cli_commands`, `_plugin_commands`, `_plugin_skills`, `_aux_tasks`, `_context_engine` are cleared (lines 915-923) — but **no hook callbacks are invoked before clearing**, and **no module teardown** is performed.
- `sys.modules` entries for plugins (`hermes_plugins.<slug>`) are **never removed** on reload. A reloaded plugin's new `register(ctx)` runs while the old module still occupies `sys.modules[module_name]`. The module object is replaced in the dict, but any lingering references will still see the old version.
- The `LoadedPlugin` objects (line 271-281) track `tools_registered`, `hooks_registered`, `commands_registered` — but there is no cleanup of global registries when these are cleared.

**Impact:** State from a previously-loaded plugin (registered tools, hooks, platforms) persists in the registry even after `force=True` reload, because only the manager's lists are cleared — not the actual global registries (`tools.registry`, `platform_registry`, etc.).

---

### P70-2 · No plugin code validation — arbitrary code executes at load time — HIGH

**File:** `hermes_cli/plugins.py` lines 1353-1389 (_load_directory_module), 1391-1407 (_load_entrypoint_module)  
**Related:** `plugins/memory/__init__.py` lines 185-285, `plugins/context_engine/__init__.py` lines 100-196  
**Severity:** HIGH

Plugin loading is **not sandboxed** in any way:

1. `_load_directory_module()` (line 1384-1388): Uses `importlib.util.spec_from_file_location` + `spec.loader.exec_module(module)` — executes the plugin's `__init__.py` directly in the Hermes process with full `sys.modules`, filesystem, and network access.
2. `_load_entrypoint_module()` (line 1403): Uses `ep.load()` — same unrestricted execution.
3. Memory providers (`plugins/memory/__init__.py` lines 257-258) and context engines (`plugins/context_engine/__init__.py` lines 168-169): Same `spec.loader.exec_module()` pattern.

**No validation step exists** — no AST inspection, no restricted `__builtins__`, no resource limits, no allowlist of accessible modules. A plugin can access `~/.hermes/.env`, modify global state, import `subprocess`/`socket`, etc.

---

### P70-3 · Hot reload does not clean sys.modules or global registries — state leak — MEDIUM

**File:** `hermes_cli/plugins.py` lines 906-924 (discover_and_load force path), 1353-1389  
**Severity:** MEDIUM

When `discover_plugins(force=True)` is called:

1. `self._plugins.clear()` removes the `LoadedPlugin` objects from the manager's dict.
2. `_hooks`, `_plugin_tool_names`, `_cli_commands`, `_plugin_commands`, `_plugin_skills`, `_aux_tasks` are all cleared (lines 917-922).
3. `_context_engine` is set to `None` (line 923).

**However:**
- `sys.modules[module_name]` (the plugin module itself) is **never removed**.
- Global registries (`tools.registry`, `platform_registry`) are **not cleaned** — tools and platforms registered by the old plugin remain registered even after `_load_plugin` runs again.
- If any other code holds a reference to the old module object, it persists.

For example, a plugin that registers a tool: the tool name stays in `tools.registry` permanently. On `force=True` reload, the new plugin's `register()` may add it again or overwrite — but there is no systematic cleanup of the previous registration.

---

### P70-4 · Two invoke_hook() implementations with inconsistent exception handling — LOW (P35-4 re-confirmed)

**File:** `hermes_cli/plugins.py` lines 1413-1447 (PluginManager.invoke_hook), 1521-1526 (module-level invoke_hook)  
**Related:** Findings.md P35-4  
**Severity:** LOW (already documented, re-confirmed outstanding)

`PluginManager.invoke_hook()` (instance method, line 1413) wraps each callback in try/except and logs failures. The module-level `invoke_hook()` (line 1521) delegates to the instance method, so exception handling is consistent via that path. However, no change has been made to address the asymmetry documented in P35-4.

---

### P70-5 · No plugin signature verification or source authentication — INFO

**File:** `hermes_cli/plugins.py` (discovery), `hermes_cli/plugins_cmd.py` (install), `ENTRY_POINTS_GROUP = "hermes_agent.plugins"`  
**Severity:** INFO

Plugin discovery accepts code from four sources: bundled (repo), user (`~/.hermes/plugins/`), project (`./.hermes/plugins/`), and pip entry-point. **No signature verification exists** at any level:

- No GPG/signed manifests
- No hash verification of plugin code
- No trusted publisher list
- `hermes plugins install` clones from git with path traversal protection via `_sanitize_plugin_name()` (lines 80-133 in `plugins_cmd.py`), but does **not** verify git commit signatures or tags.

Positively: `_sanitize_plugin_name()` uses `relative_to()` to verify the resolved target is within the plugins directory (lines 126-131), preventing directory traversal attacks at install time.

---

### P70-6 · Memory/context engine providers re-load into sys.modules without cleanup — MEDIUM

**File:** `plugins/memory/__init__.py` lines 185-285, `plugins/context_engine/__init__.py` lines 100-196  
**Severity:** MEDIUM

Memory providers and context engines both load `__init__.py` via `importlib.util.spec_from_file_location()` into `sys.modules`:

- Memory providers: module name `plugins.memory.{name}` (bundled) or `_hermes_user_memory.{name}` (user-installed), line 196.
- `sys.modules[module_name] = mod` (line 236) **overwrites** any previous module with the same name, but the old module's references may persist elsewhere.
- Submodules are registered as `plugins.memory.{name}.{submodule}` (lines 240-255) — **never cleaned up on reload**.
- Same pattern in context_engine: submodules at `plugins.context_engine.{name}.{submodule}` (lines 155-166) — never cleaned up.

The `_ProviderCollector` / `_EngineCollector` fake contexts track only `provider` or `engine` — no record of what was registered, no cleanup method.

---

### P70-7 · _scan_directory has no explicit symlink traversal guard — INFO

**File:** `hermes_cli/plugins.py` lines 1078-1157 (_scan_directory / _scan_directory_level)  
**Severity:** INFO

`_scan_directory` uses `path.iterdir()` to discover plugins. A malicious directory structure like `plugins/../../../etc/myplugin/` could theoretically be traversed if symlinks allow it. The depth cap of 2 limits recursion depth, and `_parse_manifest` uses `yaml.safe_load`.

**Mitigating factors:**
- Project plugins are opt-in (`HERMES_ENABLE_PROJECT_PLUGINS` must be set)
- Primary install path is protected by `_sanitize_plugin_name`
- No `exec()` or code evaluation during discovery — only manifest parsing

**Risk:** Low in practice, but an explicit `resolve()` + `relative_to()` check before recursing would close this gap.

---

### P70-8 · Exclusive/model-provider plugins skip loading but occupy _plugins dict — INFO

**File:** `hermes_cli/plugins.py` lines 1004-1032  
**Severity:** INFO

When `kind` is `"exclusive"` or `"model-provider"`:

1. `LoadedPlugin` is created with `enabled=False` (line 1008 or 1026).
2. Error string is set explaining the alternative activation path.
3. The entry is stored in `self._plugins` (line 1012 or 1027).

This is intentional for introspection (`list_plugins()` shows all discovered plugins), but the error message assumes the user knows about the category-based activation. Correctly deduplicates multiple sources via path-derived key in `winners` dict.

---

### P70-9 · Hook callback list iteration is not thread-safe during concurrent reload — LOW

**File:** `hermes_cli/plugins.py` lines 1433-1447 (invoke_hook)  
**Severity:** LOW

`invoke_hook()` captures `self._hooks.get(hook_name, [])` and iterates it. If `discover_plugins(force=True)` is called concurrently:

1. `invoke_hook()` captures a reference to the hook list `[cb1, cb2, ...]`.
2. Concurrently, `discover_and_load(force=True)` calls `self._hooks.clear()` (line 917) and rebuilds hooks.

The captured list is iterated independently of the dict mutation. Python GIL protects dictionary access, but the captured list reference persists. If hooks are added/removed during iteration, callbacks may be skipped or called twice. Only triggered if `force=True` is called while hook callbacks are actively firing — unlikely but possible in long-running gateway processes.

---

## Summary

**Positive findings:**
- `yaml.safe_load` is used for manifest parsing — safe YAML deserialization.
- Path traversal protection in `_sanitize_plugin_name` is well-implemented with `relative_to()` checking.
- `VALID_HOOKS` set is well-defined; hooks fire at appropriate lifecycle points (session start/end, tool/LLM calls).
- Hook callbacks are individually wrapped in try/except — one plugin's crash does not kill the agent loop.
- Memory and context engine plugins use separate module namespaces (`_hermes_user_memory.*` vs `plugins.memory.*`) preventing direct collision in `sys.modules`.
- Bundled platform plugins auto-load; bundled backends auto-load; entry-point plugins require pip install.

**Security gaps:**
- No plugin code validation or sandboxing (P70-2, HIGH) — arbitrary Python code executes in the Hermes process.
- No signature/source authentication (P70-5, INFO).

**Lifecycle gaps:**
- No `on_load`/`on_unload` hooks; no cleanup on reload (P70-1, P70-3, MEDIUM).
- `sys.modules` entries persist across hot reload; global registries not cleaned (P70-3, P70-6, MEDIUM).

**Concurrency:**
- Hook iteration races with concurrent `force=True` reload (P70-9, LOW).

**Files examined:** `hermes_cli/plugins.py` (1725 lines, primary), `hermes_cli/plugins_cmd.py` (1636 lines, install/discover), `plugins/memory/__init__.py` (407 lines), `plugins/context_engine/__init__.py` (219 lines), `agent/shell_hooks.py` (443 lines), `cli.py` lines 880-930 (deferred startup), `gateway/run.py` (hook call sites), `agent/conversation_loop.py` (hook call sites), `model_tools.py` (hook call sites).

