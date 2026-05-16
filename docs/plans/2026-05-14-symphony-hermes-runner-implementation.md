# Symphony Hermes Runner Implementation Plan

> **For implementer:** Use TDD throughout. Write failing test first. Watch it fail. Then implement.

**Goal:** Build `hermes symphony`, a Symphony-style Linear issue orchestrator that uses Hermes agent as the runner and prepares PR-ready evidence artifacts such as screenshots.

**Architecture:** Add a new `symphony/` package with strict layer boundaries: workflow/config, tracker, workspace, runner, orchestrator, observability, optional server. Ship Hermes runner first, defaulting to subprocess mode for workspace isolation, with an in-process runner path reserved for later hardening.

**Tech Stack:** Python stdlib, `pyyaml`/`ruamel.yaml`, `jinja2.StrictUndefined`, existing Hermes CLI/AIAgent/toolsets, mocked HTTP/subprocess tests, optional stdlib/FastAPI HTTP surface.

**Design doc:** `docs/plans/2026-05-14-symphony-hermes-runner-design.md`

---

## Phase 0: Guardrails

### Task 0.1: Confirm test harness and package import path

**Files:**
- Test: `tests/symphony/test_imports.py`

**Step 1: Write failing test**

```python
def test_symphony_package_imports():
    import symphony
    assert symphony is not None
```

**Step 2: Run test — confirm failure**

Command:

```bash
./venv/bin/python -m pytest tests/symphony/test_imports.py -q -o 'addopts='
```

Expected: FAIL because `symphony` package does not exist.

**Step 3: Minimal implementation**

Create `symphony/__init__.py`:

```python
"""Symphony-style issue orchestration for Hermes."""

__all__ = []
```

**Step 4: Run test — confirm pass**

Same command. Expected: PASS.

**Step 5: Commit**

```bash
git add symphony/__init__.py tests/symphony/test_imports.py
git commit -m "feat: add symphony package skeleton"
```

---

## Phase 1: CLI Surface

### Task 1.1: Add `hermes symphony validate --help`

**Files:**
- Create: `symphony/cli.py`
- Modify: `hermes_cli/main.py`
- Test: `tests/symphony/test_cli.py`

**Step 1: Write failing test**

Use subprocess against module entrypoint:

```python
import subprocess
import sys


def test_symphony_help_lists_validate():
    result = subprocess.run(
        [sys.executable, "-m", "hermes_cli.main", "symphony", "--help"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    assert "validate" in result.stdout
```

**Step 2: Run test — confirm failure**

```bash
./venv/bin/python -m pytest tests/symphony/test_cli.py::test_symphony_help_lists_validate -q -o 'addopts='
```

Expected: FAIL because `symphony` command is unknown.

**Step 3: Minimal implementation**

Add parser builder with subcommands:

- `validate [workflow] [--json]`
- `run [workflow] [--once] [--port PORT] [--json]`
- `state [workflow] [--json]`

Do not implement full behavior yet; return clear placeholder errors for unsupported execution.

**Step 4: Run test — confirm pass**

Same command. Expected: PASS.

**Step 5: Commit**

```bash
git add symphony/cli.py hermes_cli/main.py tests/symphony/test_cli.py
git commit -m "feat: add symphony cli skeleton"
```

### Task 1.2: Implement missing workflow validation error from CLI

**Files:**
- Modify: `symphony/cli.py`
- Create: `symphony/errors.py`
- Test: `tests/symphony/test_cli.py`

**Behavior:**

`hermes symphony validate /missing/WORKFLOW.md --json` exits nonzero and prints:

```json
{"ok": false, "error": {"code": "missing_workflow_file", "message": "..."}}
```

---

## Phase 2: Workflow Loader

### Task 2.1: Load markdown without front matter

**Files:**
- Create: `symphony/workflow.py`
- Test: `tests/symphony/test_workflow.py`

**Test behavior:**

```python
def test_load_workflow_without_front_matter(tmp_path):
    path = tmp_path / "WORKFLOW.md"
    path.write_text("Do work.\n", encoding="utf-8")

    workflow = load_workflow(path)

    assert workflow.config == {}
    assert workflow.prompt_template == "Do work."
```

### Task 2.2: Load YAML front matter

**Behavior:** config is parsed as a root map and body is trimmed.

### Task 2.3: Reject non-map front matter

**Behavior:** raises `SymphonyError(code="workflow_front_matter_not_a_map")`.

### Task 2.4: Resolve default `./WORKFLOW.md`

**Behavior:** explicit path wins; otherwise `cwd / "WORKFLOW.md"`.

---

## Phase 3: Typed Config and Validation

### Task 3.1: Apply core defaults

**Files:**
- Create: `symphony/config.py`
- Test: `tests/symphony/test_config.py`

**Default assertions:**

- `polling.interval_ms == 30000`
- `agent.max_concurrent_agents == 10`
- `agent.max_turns == 20`
- `agent.runner == "hermes"`
- `hermes.mode == "subprocess"` for MVP isolation

### Task 3.2: Resolve `$VAR` only when explicitly referenced

**Behavior:**

- `tracker.api_key: $LINEAR_API_KEY` resolves from env.
- Missing env raises `missing_tracker_api_key` during dispatch validation.
- Literal values are preserved and redacted in logs.

### Task 3.3: Normalize workspace root relative to workflow directory

**Behavior:** relative `workspace.root` resolves relative to `WORKFLOW.md` parent.

### Task 3.4: Validate Hermes-vs-Codex runner requirements

**Behavior:**

- `agent.runner: hermes` does not require `codex.command`.
- `agent.runner: codex` requires non-empty `codex.command`.
- Unsupported runner raises `unsupported_agent_runner`.

---

## Phase 4: Strict Prompt Rendering

### Task 4.1: Render issue and attempt

**Files:**
- Create: `symphony/prompt.py`
- Test: `tests/symphony/test_prompt.py`

**Behavior:**

```python
render_prompt("{{ issue.identifier }} / {{ attempt }}", issue={"identifier": "KATO-1"}, attempt=2)
# => "KATO-1 / 2"
```

### Task 4.2: Unknown variables fail

**Behavior:** unknown names raise `template_render_error`.

### Task 4.3: Add deterministic runtime prelude

**Behavior:** final runner prompt starts with workspace/evidence context, then the rendered workflow body.

---

## Phase 5: Workspace Manager

### Task 5.1: Sanitize issue identifiers

**Files:**
- Create: `symphony/workspace.py`
- Test: `tests/symphony/test_workspace.py`

**Behavior:** `ABC/123: x` becomes `ABC_123__x` or another documented deterministic sanitized key matching `[^A-Za-z0-9._-] -> _`.

### Task 5.2: Enforce workspace root containment

**Behavior:** path traversal cannot escape `workspace.root`; launching runner with invalid workspace raises `invalid_workspace_cwd`.

### Task 5.3: Run hooks with correct fatality

**Behavior:**

- `after_create` failure is fatal.
- `before_run` failure is fatal.
- `after_run` failure is logged and ignored.
- `before_remove` failure is logged and ignored.

### Task 5.4: Create evidence directory

**Behavior:** `workspace.evidence_dir` exists before runner starts.

---

## Phase 6: Linear Tracker Client

### Task 6.1: Normalize candidate issue payloads

**Files:**
- Create: `symphony/models.py`
- Create: `symphony/tracker.py`
- Test: `tests/symphony/test_tracker_linear.py`

**Behavior:** mocked GraphQL payload becomes `Issue` with lowercase labels, integer/null priority, and blocker refs.

### Task 6.2: Candidate query uses project `slugId` and active states

**Behavior:** mocked transport captures query/variables and asserts:

- `project: { slugId: { eq: $projectSlug } }`
- active states passed from config
- pagination variables are used

### Task 6.3: State refresh uses `[ID!]`

**Behavior:** `fetch_issue_states_by_ids([id])` sends a GraphQL variable type compatible with `[ID!]`.

### Task 6.4: Error mapping

**Behavior:** transport error, non-200, GraphQL errors, and malformed payload map to documented `SymphonyError` codes.

---

## Phase 7: Hermes Runner MVP

### Task 7.1: Define runner protocol and fake runner test

**Files:**
- Create: `symphony/runner.py`
- Test: `tests/symphony/test_runner_hermes.py`

**Behavior:** orchestrator-facing result includes status, events, started/ended times, and evidence path.

### Task 7.2: Subprocess runner sets cwd and env

**Behavior:** injected subprocess factory receives:

- `cwd == workspace.path`
- env includes `SYMPHONY_EVIDENCE_DIR`
- command uses configured `hermes.command`
- prompt passed safely without shell injection when possible

**Implementation note:** Prefer `subprocess.create_subprocess_exec` for arguments. If using `bash -lc`, quote prompt via temp file or stdin, not shell interpolation.

### Task 7.3: Timeout and nonzero exit mapping

**Behavior:**

- timeout -> `turn_timeout`
- nonzero -> `turn_failed`
- success -> `turn_completed`

### Task 7.4: In-process runner is feature-gated

**Behavior:** `hermes.mode: in_process` raises `unsupported_runner_mode` until cwd/tool scoping is implemented, or is implemented behind tests proving cwd isolation.

---

## Phase 8: Orchestrator

### Task 8.1: Dispatch sort order

**Files:**
- Create: `symphony/orchestrator.py`
- Test: `tests/symphony/test_orchestrator.py`

**Behavior:** priority ascending, created_at oldest, identifier tie-break.

### Task 8.2: Eligibility and blockers

**Behavior:** Todo issue with non-terminal blockers is skipped; terminal blockers allow dispatch.

### Task 8.3: Running/claimed state prevents duplicate dispatch

**Behavior:** same issue is never dispatched twice in one orchestrator state.

### Task 8.4: Normal exit continuation retry

**Behavior:** clean runner exit schedules retry attempt `1` with ~1s delay.

### Task 8.5: Abnormal exit exponential retry

**Behavior:** delay is `min(10000 * 2^(attempt - 1), max_retry_backoff_ms)`.

### Task 8.6: Reconciliation stops runs on state changes

**Behavior:**

- terminal state -> terminate runner + cleanup workspace
- non-active non-terminal -> terminate runner without cleanup
- active -> update running issue snapshot

---

## Phase 9: Dynamic Reload

### Task 9.1: Detect mtime change at tick boundary

**Files:**
- Modify: `symphony/orchestrator.py`
- Test: `tests/symphony/test_reload.py`

**Behavior:** valid file changes update future config/prompt.

### Task 9.2: Invalid reload keeps last good config

**Behavior:** invalid YAML logs visible error, does not crash, does not replace active config.

---

## Phase 10: Observability and State API

### Task 10.1: Structured event ring buffer

**Files:**
- Create: `symphony/observability.py`
- Test: `tests/symphony/test_observability.py`

**Behavior:** events contain issue/session context when available and truncate large messages.

### Task 10.2: Snapshot shape

**Behavior:** `orchestrator.snapshot()` returns:

- counts
- running rows
- retrying rows
- totals
- latest errors
- evidence directory per issue when known

### Task 10.3: Optional HTTP API

**Files:**
- Create: `symphony/server.py`
- Test: `tests/symphony/test_server.py`

**Endpoints:**

- `GET /api/v1/state`
- `GET /api/v1/<issue_identifier>`
- `POST /api/v1/refresh`
- `GET /`

---

## Phase 11: Docs and Sample Workflow

### Task 11.1: Add user docs

**Files:**
- Create: `docs/symphony-hermes-runner.md`
- Create: `docs/examples/WORKFLOW.hermes.md`

**Must document:**

- Hermes runner extension fields.
- Subprocess MVP behavior.
- Safety posture and workspace isolation.
- Evidence directory and screenshot workflow.
- Real Linear smoke-test steps.

### Task 11.2: Add conformance checklist

**Files:**
- Create: `docs/plans/2026-05-14-symphony-hermes-runner-conformance.md`

**Behavior:** map each SPEC Section 17/18 bullet to `implemented`, `extension`, `deferred`, or `not applicable`.

---

## Final Verification

Run targeted tests:

```bash
./venv/bin/python -m pytest tests/symphony -q -o 'addopts='
```

Run nearby regression tests:

```bash
./venv/bin/python -m pytest tests/hermes_cli tests/tools -q -o 'addopts='
```

Manual smoke test with a safe workflow:

```bash
./venv/bin/python -m hermes_cli.main symphony validate docs/examples/WORKFLOW.hermes.md --json
./venv/bin/python -m hermes_cli.main symphony run docs/examples/WORKFLOW.hermes.md --once --json
```

Real integration is opt-in only and requires `LINEAR_API_KEY` plus a test Linear project.
