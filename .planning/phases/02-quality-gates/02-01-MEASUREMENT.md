# Phase 02-01: Lint and Type-Check Measurement Report

**Generated:** 2026-04-25  
**Purpose:** Empirical baseline for 02-02 (auto-fix), 02-03 (CI lint gate), and 02-04 (type-check pilot).

---

## Tool versions

| Tool   | Version   | Source                                                            |
|--------|-----------|-------------------------------------------------------------------|
| ruff   | 0.15.11   | `/var/home/denniyahh/.hermes/hermes-agent/venv/bin/ruff`         |
| ty     | 0.0.21    | `/var/home/denniyahh/.hermes/hermes-agent/venv/bin/ty`           |
| Python | 3.11.15   | System Python at time of measurement                              |

**Note:** Tools were sourced from the hermes-agent venv already installed on the host. No temporary venv was created — `ruff >= 0.6` is satisfied by `0.15.11`. The `uv` binary was not available in the CI execution environment, so the installed venv was used directly. This does not affect result reproducibility (see Reproduction Commands below).

**Important — ruff config bypass:** `pyproject.toml` currently has `[tool.ruff] exclude = ["*"]` which globally disables ruff. All ruff measurements in this report use `--isolated` to bypass project configuration and directly measure the codebase. This mirrors exactly what the new config in 02-03 will enable.

**Important — ty config bypass:** `pyproject.toml` has `[tool.ty.src] exclude = ["**"]` which excludes all files. When checking the full `agent/` directory, a temporary `ty.toml` was used that removes this global exclude but keeps the same override rules (unresolved-import, invalid-method-override, invalid-assignment, not-iterable → ignore). Single-file checks bypass the config automatically.

---

## Scope

The lint scope mirrors the `[tool.setuptools.packages.find] include` list from `pyproject.toml`:

```
agent tools hermes_cli gateway tui_gateway cron acp_adapter plugins
```

Out of scope: `tests/`, `skills/`, `scripts/`, `docs/`, top-level entry points (`batch_runner.py`, etc.) not inside the above packages.

---

## Total violations (E, F, I)

**Total violations: 6,809**

Command used:
```bash
ruff check --isolated --select E,F,I --output-format json \
  agent/ tools/ hermes_cli/ gateway/ tui_gateway/ cron/ acp_adapter/ plugins/
```

Per-rule breakdown:

| Rule | Count | Description                                          |
|------|-------|------------------------------------------------------|
| E501 | 6,067 | Line too long                                        |
| I001 |   406 | Import block is un-sorted or un-formatted (isort)   |
| E402 |   178 | Module level import not at top of file               |
| F541 |    61 | f-string without any placeholders                    |
| F401 |    35 | Unused import                                        |
| E741 |    23 | Ambiguous variable name                              |
| F841 |    15 | Local variable is assigned but never used            |
| F821 |    10 | Undefined name                                       |
| F811 |     6 | Redefinition of unused name                          |
| E401 |     3 | Multiple imports on one line                         |
| E731 |     2 | Lambda assignment                                    |
| F823 |     2 | `__all__` contains an undefined name                 |
| F601 |     1 | `in` operator used with a list literal               |
| **Total** | **6,809** |                                              |

**Key observation:** E501 (line too long) dominates at 89.1% of all violations. These are NOT auto-fixable and represent a formatting policy question, not a correctness issue. Excluding E501, the remaining **742 violations** are the actionable set for 02-02.

---

## Auto-fixable split

| Category        | Count | Percentage |
|-----------------|-------|------------|
| Auto-fixable    |   526 |  7.7%      |
| Manual required | 6,283 | 92.3%      |
| **Total**       | **6,809** | 100%   |

**Note:** The 526 auto-fixable violations are primarily I001 (isort), F401 (unused imports), F841 (unused locals), and F811 (redefinitions). Nearly all E501 violations (6,067) are manual-only since ruff cannot shorten long lines without logic knowledge.

---

## Top 20 offending files

| Rank | Violations | File                                   |
|------|-----------|----------------------------------------|
|  1   |    468    | gateway/run.py                         |
|  2   |    251    | gateway/platforms/feishu.py            |
|  3   |    249    | hermes_cli/gateway.py                  |
|  4   |    229    | gateway/platforms/discord.py           |
|  5   |    188    | hermes_cli/main.py                     |
|  6   |    183    | hermes_cli/config.py                   |
|  7   |    171    | hermes_cli/tips.py                     |
|  8   |    150    | hermes_cli/doctor.py                   |
|  9   |    142    | gateway/platforms/telegram.py          |
| 10   |    124    | hermes_cli/setup.py                    |
| 11   |    121    | tools/terminal_tool.py                 |
| 12   |    120    | gateway/platforms/api_server.py        |
| 13   |    120    | tools/web_tools.py                     |
| 14   |    115    | tools/send_message_tool.py             |
| 15   |    109    | plugins/memory/hindsight/__init__.py   |
| 16   |    103    | hermes_cli/tools_config.py             |
| 17   |    101    | hermes_cli/auth.py                     |
| 18   |    99     | agent/auxiliary_client.py              |
| 19   |    95     | tools/browser_tool.py                  |
| 20   |    94     | hermes_cli/models.py                   |

All top-20 files are dominated by E501 (line-too-long). The actionable (non-E501) violations per file will be much lower.

---

## Per-package breakdown

| Package      | Total | E501  | I001 | E402 | F541 | F401 | E741 | Other |
|--------------|-------|-------|------|------|------|------|------|-------|
| agent        |   631 |   580 |   31 |    3 |    0 |   13 |    0 |     4 |
| tools        | 1,490 | 1,339 |   79 |   56 |    3 |    5 |    4 |     4 |
| hermes_cli   | 1,969 | 1,691 |  141 |   49 |   50 |    7 |   17 |    14 |
| gateway      | 1,938 | 1,746 |  109 |   67 |    2 |    4 |    1 |     9 |
| tui_gateway  |    47 |    26 |   17 |    1 |    0 |    1 |    0 |     2 |
| cron         |    93 |    83 |    8 |    2 |    0 |    0 |    0 |     0 |
| acp_adapter  |    73 |    63 |    8 |    0 |    0 |    1 |    0 |     1 |
| plugins      |   568 |   539 |   13 |    0 |    6 |    4 |    1 |     5 |
| **Total**    | **6,809** | **6,067** | **406** | **178** | **61** | **35** | **23** | **39** |

**Actionable (non-E501) per package:**

| Package     | Non-E501 violations |
|-------------|---------------------|
| hermes_cli  | 278 |
| tools       | 151 |
| gateway     | 192 |
| agent       |  51 |
| plugins     |  29 |
| tui_gateway |  21 |
| cron        |  10 |
| acp_adapter |  10 |

---

## Format-check status

**249 files would be reformatted; 31 files already formatted.**

Command:
```bash
ruff format --check --isolated agent/ tools/ hermes_cli/ gateway/ tui_gateway/ cron/ acp_adapter/ plugins/
```

This means **88.9% of in-scope files** need reformatting. The codebase is NOT format-clean against ruff's defaults.

**Sample format diff (first 60 lines of `ruff format --diff --isolated`):**

```diff
--- acp_adapter/auth.py
+++ acp_adapter/auth.py
@@ -9,10 +9,16 @@
     """Resolve the active Hermes runtime provider, or None if unavailable."""
     try:
         from hermes_cli.runtime_provider import resolve_runtime_provider
+
         runtime = resolve_runtime_provider()
         api_key = runtime.get("api_key")
         provider = runtime.get("provider")
-        if isinstance(api_key, str) and api_key.strip() and isinstance(provider, str) and provider.strip():
+        if (
+            isinstance(api_key, str)
+            and api_key.strip()
+            and isinstance(provider, str)
+            and provider.strip()
+        ):
             return provider.strip().lower()
     except Exception:
         return None

--- acp_adapter/events.py
+++ acp_adapter/events.py
@@ -44,6 +44,7 @@
 # Tool progress callback
 # ------------------------------------------------------------------
 
+
 def make_tool_progress_cb(
     conn: acp.Client,
     session_id: str,
@@ -63,7 +64,13 @@
     ``reasoning.available``) are silently ignored.
     """
 
-    def _tool_progress(event_type: str, name: str = None, preview: str = None, args: Any = None, **kwargs) -> None:
+    def _tool_progress(
+        event_type: str,
+        name: str = None,
+        preview: str = None,
+        args: Any = None,
+        **kwargs,
+    ) -> None:
         # Only emit ACP ToolCallStart for tool.started; ignore other event types
         if event_type != "tool.started":
             return
@@ -92,7 +99,9 @@
 
                 snapshot = capture_local_edit_snapshot(name, args)
             except Exception:
-                logger.debug("Failed to capture ACP edit snapshot for %s", name, exc_info=True)
+                logger.debug(
+                    "Failed to capture ACP edit snapshot for %s", name, exc_info=True
+                )
```

The format diff is primarily line-length wrapping and argument list reformatting — no logic changes. However, the scope is large (249 files), which constitutes a massive blame-history disruption if done all at once.

---

## Type-check pilot baseline

**Tool used:** ty 0.0.21 (preferred per CONTEXT.md D-E)  
**Pilot scope:** `agent/` and `tools/path_security.py`

**Method note:** The stock `pyproject.toml` sets `[tool.ty.src] exclude = ["**"]` which causes ty to silently pass when checking directories. A temporary `ty.toml` (no global exclude, same override suppression rules) was used for the directory-level check. Single-file checks confirm ty is functional.

**Current state with existing pyproject.toml config:**
```
$ ty check agent/ tools/path_security.py
All checks passed!  (exit 0)
```
This is a false green — the `[tool.ty.src] exclude = ["**"]` setting causes ty to skip all files when invoked via directory path. The override `[[tool.ty.overrides]] include = ["**"]` does not counteract the src exclusion at the directory invocation level.

**Actual baseline (with global exclude removed, override rules preserved):**

| Metric                           | Count |
|----------------------------------|-------|
| Total diagnostics                |   213 |
| Errors                           |   204 |
| Warnings                         |     9 |
| Files with errors                |    17 |
| Files with >5 errors             |     7 |
| tools/path_security.py errors    |     0 |

**Error codes (not silenced by existing overrides):**

| Code                    | Count | Description                                    |
|-------------------------|-------|------------------------------------------------|
| invalid-argument-type   |   126 | Wrong type passed to function argument         |
| invalid-parameter-default | 56  | `None` default on non-Optional typed param     |
| unresolved-attribute    |    17 | Attribute access on type that doesn't have it  |
| invalid-return-type     |     4 | Return type doesn't match annotation           |
| unsupported-operator    |     1 | Operator not valid for given types             |
| **Total errors**        | **204** |                                              |

**Warning codes:**

| Code                         | Count | Description                                      |
|------------------------------|-------|--------------------------------------------------|
| unused-type-ignore-comment   |     9 | `# type: ignore` not needed (ty caught it already)|

**Files with >5 errors:**

| Errors | File                        |
|--------|-----------------------------|
|    116 | agent/auxiliary_client.py   |
|     17 | agent/context_compressor.py |
|     13 | agent/insights.py           |
|     11 | agent/credential_pool.py    |
|     10 | agent/anthropic_adapter.py  |
|     10 | agent/error_classifier.py   |
|      8 | agent/bedrock_adapter.py    |

**Errors NOT silenced by existing overrides:** All 204 errors fall outside the suppressed categories (`unresolved-import`, `invalid-method-override`, `invalid-assignment`, `not-iterable`). The existing overrides were tuned for different error classes; the actual errors are `invalid-argument-type` and `invalid-parameter-default`.

**`tools/path_security.py`:** 0 errors, 0 warnings. This file is type-clean.

**02-04 conclusion:** 02-04 must address **204 errors across 17 files** in `agent/` to get the pilot scope green. The dominant pattern (56 + 126 = 182 violations) is `None`-vs-typed-param mismatches — Python's common antipattern of `def f(x: str = None)` instead of `def f(x: str | None = None)`. Since 204 > 50, **recommend shipping the ty CI step with `continue-on-error: true` for the first merge cycle** per CONTEXT.md D-F.

---

## Reproduction commands

These commands can be re-run in any clone of this repo to verify the numbers. They assume `ruff >= 0.6` and `ty` are installed in a venv at `$RUFF_VENV`.

```bash
# Set tool paths (adjust to your installed venv)
RUFF_VENV=/var/home/denniyahh/.hermes/hermes-agent/venv
RUFF=$RUFF_VENV/bin/ruff
TY=$RUFF_VENV/bin/ty
PYTHON=$RUFF_VENV/bin/python3

# Verify versions
$RUFF --version   # should be >= 0.6
$TY --version

# Run from repo root:
cd /path/to/hermes-agent-latest-exec

# === RUFF MEASUREMENT ===

# 1. Total violations with E,F,I (bypasses pyproject.toml exclude = ["*"])
$RUFF check --isolated --select E,F,I --output-format json \
  agent/ tools/ hermes_cli/ gateway/ tui_gateway/ cron/ acp_adapter/ plugins/ \
  > /tmp/ruff-violations.json 2>/tmp/ruff-stderr.txt

# 2. Total + per-rule breakdown
$PYTHON -c "
import json, collections
v = json.load(open('/tmp/ruff-violations.json'))
c = collections.Counter(x['code'] for x in v)
print('total', sum(c.values()))
[print(k, n) for k, n in c.most_common()]
"

# 3. Top 20 offending files
$PYTHON -c "
import json, collections
v = json.load(open('/tmp/ruff-violations.json'))
c = collections.Counter(x['filename'] for x in v)
[print(n, k) for k, n in c.most_common(20)]
"

# 4. Auto-fixable vs manual split
$PYTHON -c "
import json
v = json.load(open('/tmp/ruff-violations.json'))
af = sum(1 for x in v if x.get('fix'))
print('auto-fixable', af, 'manual', len(v) - af)
"

# 5. Format check
$RUFF format --check --isolated \
  agent/ tools/ hermes_cli/ gateway/ tui_gateway/ cron/ acp_adapter/ plugins/ 2>&1 | tail -1

# 6. Format diff sample
$RUFF format --diff --isolated \
  agent/ tools/ hermes_cli/ gateway/ tui_gateway/ cron/ acp_adapter/ plugins/ 2>/dev/null | head -60

# === TY MEASUREMENT ===
# Create a ty.toml without the global exclude (but keeping override suppression rules)
cat > /tmp/ty-measure.toml << 'TOML'
[environment]
python-version = "3.11"

[rules]
unknown-argument = "warn"
redundant-cast = "ignore"

[[overrides]]
include = ["**"]

[overrides.rules]
unresolved-import = "ignore"
invalid-method-override = "ignore"
invalid-assignment = "ignore"
not-iterable = "ignore"
TOML

$TY check --config-file /tmp/ty-measure.toml \
  --python $RUFF_VENV \
  --output-format concise \
  agent/ tools/path_security.py 2>&1 | tee /tmp/ty-pilot.txt

# Summary line
tail -1 /tmp/ty-pilot.txt
```

---

## Implications for 02-02 / 02-03 / 02-04

**02-02 (Auto-fix ruff violations):**

- The 526 auto-fixable violations (I001 + F401 + F841 + F811) are safe to apply with `ruff check --fix --unsafe-fixes=false`.
- The 6,067 E501 violations cannot be auto-fixed and should NOT be addressed in 02-02 per D-C (behavior-touching never). Recommend adding `E501` to the `[tool.ruff] ignore` list in 02-03 OR setting `line-length = 999` as a temporary escape hatch. Given that 89% of violations are E501, the cleanest approach for 02-03 is to **exclude E501 from the enforced ruleset** in this phase and defer line-length enforcement to a future formatting phase.
- Per-package commit strategy: 8 commits (agent, tools, hermes_cli, gateway, tui_gateway, cron, acp_adapter, plugins). The packages with the most actionable violations are hermes_cli (278), gateway (192), and tools (151).

**02-03 (pyproject.toml + CI lint gate):**

- Remove `exclude = ["*"]` from `[tool.ruff]`, set `select = ["E", "F", "I"]`, and add `ignore = ["E501"]` to avoid 6,067 un-actionable violations blocking CI from day one.
- **Recommended:** Ship `ruff format --check` as a **warning-only** or **per-path excluded** step given 249/280 files (88.9%) need reformatting. A blocking format check would fail every PR until a mass-reformat phase ships. Add `[tool.ruff.format] exclude = [...]` listing all 249 files OR ship format-check as a non-blocking annotation.
- Alternative: exclude `hermes_cli/`, `gateway/`, and `tools/` from format-check initially (they account for the bulk of reformatted files), block only on `agent/`, `acp_adapter/`, `cron/`, `tui_gateway/` which are cleaner.

**02-04 (ty type-check pilot):**

- 204 errors across 17 files in `agent/`. `tools/path_security.py` is already clean.
- Ship CI step with `continue-on-error: true` per D-F (N=204 > 50 threshold).
- The fix pattern is mechanical: change `x: str = None` to `x: str | None = None` (Python 3.10+ union syntax). The 56 `invalid-parameter-default` errors are the fastest win.
- `agent/auxiliary_client.py` alone has 116 errors — it should be the primary focus of 02-04 work.
- **Critical:** The `[tool.ty.src] exclude = ["**"]` setting must be removed or scoped for the pilot. The current config silently passes, giving a false green. 02-04 must fix the ty configuration before adding the CI step.
