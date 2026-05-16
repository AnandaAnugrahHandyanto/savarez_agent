# Symphony Hermes Runner Design

**Status:** Draft for approval

**Goal:** Implement OpenAI Symphony-style issue orchestration in Hermes, using Hermes agent as the worker/runner instead of Codex app-server, so Linear issues can be picked up automatically, executed in isolated workspaces, and produce PR-ready evidence such as screenshots.

**Non-goal:** Implement a full Codex app-server client. The Codex-specific protocol surface in upstream `SPEC.md` is treated as one possible runner backend, not the default Hermes implementation path.

---

## 1. Context

OpenAI Symphony `SPEC.md` defines a long-running service that:

- Reads candidate issues from Linear.
- Creates deterministic per-issue workspaces.
- Runs an agent session inside each workspace.
- Reconciles running work against tracker state.
- Retries failures with backoff.
- Exposes logs/status/API for operators.

Hermes already has many pieces that should be reused rather than recreated:

- `AIAgent` and toolsets for execution.
- Gateway and CLI config/profile loading.
- `computer_use` for macOS screenshots and GUI evidence.
- `terminal`/`file`/`browser`/`vision` tools for repo work and PR evidence.
- Existing patterns for cron/kanban-style durable automation.

The main design difference is runner protocol. Upstream Symphony assumes Codex app-server. This project should support `agent.runner: hermes` as a documented extension.

---

## 2. Proposed Approaches

### Approach A: Strict Codex-compatible Symphony implementation

Implement Symphony nearly verbatim, including Codex app-server client, then later add Hermes as another runner.

**Pros:**
- Best upstream spec fidelity.
- Easier to compare behavior against OpenAI reference implementation.

**Cons:**
- Does not solve the user's primary need first.
- Requires Codex app-server protocol work that Hermes does not need.
- Delays screenshot/evidence integration through Hermes tools.

**Verdict:** Not recommended as first implementation.

### Approach B: Hermes-first Symphony with runner abstraction

Implement the orchestration, workflow/config, Linear reader, workspace manager, retry, reload, and observability per spec. Define a `Runner` interface and ship `HermesRunner` first. Keep `CodexRunner` unimplemented or optional.

**Pros:**
- Solves the actual goal first.
- Keeps the core service aligned with Symphony concepts.
- Cleanly separates runner-specific divergence.
- Leaves room for Codex runner later.
- Best fit for PR screenshot/evidence via Hermes `computer_use`.

**Cons:**
- Not fully conformant to Section 10 of upstream spec until Codex runner exists.
- Requires documenting extension semantics clearly.

**Verdict:** Recommended.

### Approach C: Reuse Hermes Kanban as Symphony backend

Map Linear issues into Hermes Kanban tasks and let the existing Kanban dispatcher run workers.

**Pros:**
- Reuses existing Hermes durable board/dispatcher.
- Faster MVP if exact Symphony semantics are relaxed.

**Cons:**
- Symphony has tracker-driven claim/retry/reconciliation semantics that do not map cleanly to Kanban.
- Extra state layer can create confusing ownership between Linear, Symphony, and Kanban.
- Harder to claim SPEC alignment.

**Verdict:** Useful reference, not the primary implementation.

---

## 3. Recommendation

Use **Approach B: Hermes-first Symphony with runner abstraction**.

Implement the core layers as a new `symphony/` package and `hermes symphony` CLI. The runner boundary should be explicit from day one:

```python
class AgentRunner(Protocol):
    async def run_attempt(self, issue, attempt, workspace, prompt, callbacks) -> RunnerResult: ...
```

Ship:

- `HermesRunner` now.
- `CodexRunner` as a future-compatible placeholder only if needed.

This gives us a spec-shaped orchestrator while keeping the execution engine Hermes-native.

---

## 4. Architecture

### 4.1 Package layout

```text
symphony/
  __init__.py
  cli.py              # hermes symphony command surface
  errors.py           # typed errors and error codes
  workflow.py         # WORKFLOW.md loader + hot-reload helpers
  config.py           # typed config view + defaults + validation
  prompt.py           # strict Jinja rendering
  models.py           # Issue, Workspace, RunAttempt, RuntimeSnapshot dataclasses
  tracker.py          # tracker interface + Linear implementation
  workspace.py        # workspace path safety + hooks
  runner.py           # AgentRunner protocol + HermesRunner
  orchestrator.py     # poll/reconcile/dispatch/retry state machine
  observability.py    # structured logs, event ring buffer, snapshot helpers
  server.py           # optional HTTP API/dashboard extension
```

### 4.2 Data flow

1. CLI starts with `hermes symphony run [WORKFLOW.md]`.
2. `WorkflowLoader` parses front matter and prompt body.
3. `ConfigView` applies defaults and validates dispatch requirements.
4. `Orchestrator` starts polling.
5. `LinearTracker` fetches candidate issues.
6. `WorkspaceManager` creates/reuses `<workspace.root>/<sanitized_issue_identifier>`.
7. `PromptRenderer` renders issue prompt with strict variables.
8. `HermesRunner` runs an agent in the workspace.
9. Runner emits events to orchestrator.
10. Orchestrator reconciles Linear state, retries, or releases claims.
11. Logs/snapshot/API expose current state and evidence paths.

---

## 5. Hermes Runner Contract

### 5.1 Workflow config extension

```yaml
agent:
  runner: hermes
  max_concurrent_agents: 2
  max_turns: 20
  toolsets: [terminal, file, web, browser, computer_use, vision]
  model: null
  provider: null
  yolo: false

hermes:
  mode: in_process       # in_process | subprocess
  command: hermes chat -q
  profile: null
  evidence_dir: .hermes/evidence
  continuation_prompt: |
    Continue working on this issue. Check the tracker/PR state and either proceed or hand off.
```

### 5.2 Execution modes

#### In-process mode

Instantiate `AIAgent` inside the worker process/task.

**Benefits:** better testability, direct callbacks, fewer shells.

**Risk:** Hermes global state/config and terminal cwd must be scoped correctly. If per-agent workdir cannot be guaranteed safely, do not use this mode first.

#### Subprocess mode

Launch `hermes chat -q <prompt>` with `cwd=workspace.path`.

**Benefits:** simplest isolation, uses existing CLI behavior, easier to reason about cwd.

**Risk:** less structured telemetry and harder token accounting.

### 5.3 Initial implementation choice

Implement both interface paths, but make **subprocess mode the MVP default** unless in-process cwd/tool scoping is proven safe. Add in-process as an optimization after tests prove no cross-workspace leakage.

This is a refinement from the first plan: correctness and workspace isolation matter more than runner elegance.

---

## 6. PR Screenshot / Evidence Design

### 6.1 Evidence directory

For every attempt, create:

```text
<workspace>/<hermes.evidence_dir>/<issue_identifier>/
```

Example:

```text
.../symphony-linear/KATO-123/.hermes/evidence/KATO-123/
```

### 6.2 Environment variables for runner

Set for each Hermes runner invocation:

```text
SYMPHONY_ISSUE_ID
SYMPHONY_ISSUE_IDENTIFIER
SYMPHONY_ISSUE_URL
SYMPHONY_WORKSPACE
SYMPHONY_EVIDENCE_DIR
SYMPHONY_ATTEMPT
```

### 6.3 Prompt prelude

Before the workflow prompt, prepend a small runner-owned context block:

```markdown
# Symphony Runtime Context

- Issue: <identifier>
- Workspace: <path>
- Evidence directory: <path>

If UI evidence is relevant, save screenshots/videos under the evidence directory and mention the file paths in your PR or handoff comment.
```

Keep this prelude deterministic and short.

### 6.4 Upload policy

Core Symphony should **not** decide how to upload images. It should expose local artifact paths. Project-specific workflow can choose one of:

- Commit evidence files when appropriate.
- Use GitHub-native attachments via browser/computer-use.
- Use `gh` comments with links to committed artifacts.
- Use project-specific storage.

For katohome specifically, prefer local/GitHub-native handoff and avoid third-party image hosts.

---

## 7. State Machine Details

### 7.1 Claims

`claimed` is in-memory only, per spec. A claimed issue is either running or retry queued. Restart recovery comes from polling Linear again and reusing preserved workspaces.

### 7.2 Normal completion

A normal Hermes runner exit does not imply issue is done. It schedules a short continuation retry after ~1 second. On retry, if the issue is still active and slots are available, it can continue.

### 7.3 Max turns

Because a subprocess Hermes run maps more naturally to one turn/session, implement `max_turns` as max worker sessions per orchestrator worker lifetime only if using in-process mode. For subprocess MVP, treat one subprocess invocation as one turn and use continuation retries to continue.

Document this as an MVP limitation if needed.

---

## 8. Dynamic Reload

Use mtime polling at tick boundaries first. Avoid new file watcher dependencies.

On valid reload:

- Apply future poll interval.
- Apply active/terminal states.
- Apply concurrency limits.
- Apply hooks/workspace settings for future attempts.
- Apply prompt template for future attempts.
- Apply runner settings for future attempts.

On invalid reload:

- Keep last known good config.
- Log an operator-visible error.
- Continue reconciliation.
- Skip dispatch only if no valid dispatch config exists.

---

## 9. Testing Strategy

Follow TDD. No production code without a failing test first.

Test groups:

- `tests/symphony/test_workflow.py`
- `tests/symphony/test_config.py`
- `tests/symphony/test_prompt.py`
- `tests/symphony/test_workspace.py`
- `tests/symphony/test_tracker_linear.py`
- `tests/symphony/test_runner_hermes.py`
- `tests/symphony/test_orchestrator.py`
- `tests/symphony/test_reload.py`
- `tests/symphony/test_server.py`
- `tests/symphony/test_evidence.py`

Unit tests should mock Linear and runner processes. Real integration tests should be opt-in and skipped unless explicitly enabled.

---

## 10. Acceptance Criteria

MVP is complete when:

- `hermes symphony validate WORKFLOW.md` validates a Linear + Hermes workflow.
- `hermes symphony run WORKFLOW.md --once` can poll mocked or real Linear candidates and run a Hermes subprocess in the issue workspace.
- Workspace root containment and cwd invariants are enforced.
- Runner receives `SYMPHONY_EVIDENCE_DIR` and creates the directory.
- Normal/abnormal exits produce retry behavior.
- State snapshot includes running/retry/evidence information.
- Invalid `WORKFLOW.md` reload does not crash a running service.

Production-ready when:

- Real Linear smoke test passes with `LINEAR_API_KEY`.
- macOS `computer_use` screenshot workflow is validated in a sample repo/workspace.
- Logs are sufficient to debug stuck/rate-limited/failed workers.
- Docs include a sample `WORKFLOW.md` and safety posture.

---

## 11. Open Questions

1. Should MVP default to `hermes.mode: subprocess` for stronger isolation, even if in-process is planned later?
2. Should Symphony live in core Hermes or as a plugin under `plugins/symphony`?
3. Should Linear writes be exposed as a Hermes tool in the runner, or left entirely to existing CLI/API access from the workflow prompt?
4. Should evidence upload be a generic GitHub extension or katohome-specific workflow logic first?

Recommended answers for MVP:

1. Yes: subprocess default.
2. Core package is acceptable because it adds a CLI/service feature, but plugin is viable if feature-gating is preferred.
3. Start read-only in orchestrator; runner can use existing tools. Add `linear_graphql` extension later if needed.
4. Start with local evidence paths; add GitHub publisher later.
