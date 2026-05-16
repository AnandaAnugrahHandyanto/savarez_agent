# Symphony Hermes Runner

**Status:** MVP documentation for the current `hermes symphony` implementation. This is a Hermes-first extension of OpenAI Symphony concepts with a working Linear → workspace → Hermes runner → Linear comment vertical slice.

## Scope

`hermes symphony` is intended to:

- load a `WORKFLOW.md` file with YAML front matter and a Markdown/Jinja prompt body;
- poll Linear-style issue data through the Symphony tracker layer;
- prepare deterministic per-issue workspaces;
- run Hermes as the worker runner;
- preserve local evidence artifacts such as screenshots for PR or handoff comments;
- expose structured state/event shapes for later operator APIs.

Current MVP reality:

- CLI command shape exists: `hermes symphony validate|run|state`.
- `validate` loads the workflow, validates typed config, and renders the prompt with a sample issue.
- `run --once` performs one real orchestration tick when `tracker.api_key` is configured: fetch candidates from Linear, select dispatchable Todo issues, create per-issue workspace/evidence dirs, claim with a Linear comment, run `hermes chat -q <prompt>` in the workspace, and post a completion/evidence summary comment.
- `run` without `--once` is a long-running polling loop; use `--max-cycles N` for bounded smoke tests.
- Workflow loading, config typing, prompt rendering, workspace path safety, Linear payload normalization/mutations, runner subprocess behavior, retry/reconcile helpers, loop smoke, reload helpers, and state snapshot helpers are covered by targeted unit tests.
- The HTTP status API, durable distributed locking, richer startup cleanup, and GitHub evidence publication are deferred.

## Workflow shape

A Symphony workflow is a Markdown file with optional YAML front matter:

```yaml
---
polling:
  interval_ms: 30000
agent:
  runner: hermes
  max_concurrent_agents: 2
  max_turns: 20
hermes:
  mode: subprocess
  command: hermes
tracker:
  api_key: $LINEAR_API_KEY
workspace:
  root: ./.symphony/workspaces
---
```

The Markdown body is rendered with Jinja `StrictUndefined`. The current prompt context includes:

- `issue`: issue fields normalized from Linear-like payloads, for example `identifier`, `title`, `url`, `state`, `labels`, `priority`, and blocker IDs.
- `attempt`: current attempt number.

The runner prepends a deterministic runtime context with workspace path, evidence directory, optional issue identifier/title, and attempt number before the workflow body.

## Hermes runner extension fields

These fields are Hermes-specific extensions to the upstream Symphony runner model.

- `agent.runner`
  - Value: `hermes` or `codex`.
  - Current default: `hermes`.
  - Current behavior: `hermes` is implemented in the runner layer; `codex` requires `codex.command` and is only a compatibility placeholder.

- `agent.max_concurrent_agents`
  - Integer concurrency limit.
  - Current default: `10`.
  - Current behavior: `run --once` dispatches up to this many eligible issues in one tick; `run` repeats that tick on the configured polling interval.

- `agent.max_turns`
  - Integer turn/session limit.
  - Current default: `20`.
  - Current MVP behavior: for subprocess mode, one Hermes subprocess invocation is one turn. Continuation/retry behavior is modeled by the orchestrator helpers, not a durable production loop yet.

- `hermes.mode`
  - Value: `subprocess` or `in_process`.
  - Current default: `subprocess`.
  - Current behavior: `subprocess` is implemented. `in_process` is feature-gated and raises `unsupported_runner_mode` until cwd/tool scoping is hardened.

- `hermes.command`
  - String command prefix for launching Hermes.
  - Current default: `hermes`.
  - Current behavior: parsed with `shlex.split`, invoked with `shell=False`, then `chat -q <prompt>` is appended. Example: `command: hermes` runs `hermes chat -q <prompt>`.

- `tracker.api_key`
  - String or environment reference.
  - Use only `api_key: $LINEAR_API_KEY` in committed examples. Do not place secrets in workflow files.

- `workspace.root`
  - Root directory for issue workspaces.
  - Relative paths resolve relative to the workflow file directory.

- `codex.command`
  - Compatibility placeholder for `agent.runner: codex`.
  - Not the Hermes MVP path.

## Subprocess MVP behavior

`HermesRunner.run_turn()` currently performs one synchronous Hermes turn:

1. Build command: `[<hermes command>, "chat", "-q", <prompt>]`.
2. Run with `cwd` set to the prepared issue workspace.
3. Run with `shell=False`.
4. Capture stdout/stderr.
5. Map exit status:
   - return code `0` => `turn_completed`;
   - non-zero return code => `turn_failed`;
   - timeout => `turn_timeout`;
   - `OSError` such as missing binary => `turn_failed` result.
6. Return a `RunnerResult` with timestamps, events, evidence directory, stdout, stderr, and return code.

Environment handling is intentionally narrow. The runner copies only safe base keys (`PATH`, `HOME`, locale/terminal keys) and injects:

```text
SYMPHONY_EVIDENCE_DIR=<prepared evidence directory>
```

The design document reserves additional variables such as issue ID, issue URL, workspace, and attempt; they are not all injected by the current runner implementation yet.

## Safety posture and workspace isolation

Current safety choices:

- Workspaces are one path segment per issue identifier after sanitization.
- Final workspace paths must remain under `workspace.root`; escape attempts raise `invalid_workspace_cwd`.
- Evidence directories are created under the prepared issue workspace.
- Hermes subprocesses run with the issue workspace as `cwd`.
- Runner commands use argument arrays and `shell=False`; the prompt is passed as one argument, not shell-interpolated.
- Secrets are not copied wholesale into the subprocess environment. Only a small allowlist is inherited plus `SYMPHONY_EVIDENCE_DIR`.
- Logs/events redact common secret-looking keys and token patterns in observability helpers.

Limitations to keep in mind:

- The subprocess still runs a real Hermes agent with its enabled tools, so workflow authors must scope tasks carefully.
- `in_process` mode is intentionally disabled until Hermes global state, tool cwd, and per-agent workdir scoping are proven safe.
- Full daemon supervision, remote cancellation, durable claims, and operator authentication are deferred.

## Evidence directory and screenshot workflow

Current prepared evidence path:

```text
<workspace.root>/<sanitized issue identifier>/.symphony/evidence/
```

The runner exposes this path as `SYMPHONY_EVIDENCE_DIR` and also includes it in the runtime prompt context. A workflow should instruct the agent to:

1. Reproduce or inspect the UI change in the issue workspace.
2. Save screenshots, screen recordings, logs, or text evidence under `$SYMPHONY_EVIDENCE_DIR`.
3. Use deterministic names such as:
   - `before.png`
   - `after.png`
   - `responsive-mobile.png`
   - `test-output.txt`
4. Mention evidence file paths in the final handoff or PR body.

Recommended prompt snippet:

```markdown
If UI evidence is relevant, capture screenshots with Hermes computer/browser tools and save them under the evidence directory from the runtime context. Reference those local paths in the PR or Linear handoff. Do not upload to third-party image hosts unless the repository workflow explicitly requires it.
```

The core Symphony layer does not upload artifacts. Upload/attachment policy belongs to the project workflow.

## Real Linear smoke-test steps

Use a disposable/safe Linear project or a test issue. Do not put secrets in files.

1. Ensure `$LINEAR_API_KEY` is set in your shell or local environment outside the repository.

2. Copy the sample workflow:

```bash
cp docs/examples/WORKFLOW.hermes.md ./WORKFLOW.md
```

3. Review the front matter and set a safe local workspace root. Keep:

```yaml
tracker:
  api_key: $LINEAR_API_KEY
```

4. Create or choose a Linear issue in a Todo-like state with a clear, low-risk task.

5. Run the currently available unit-level checks before manual execution:

```bash
./venv/bin/python -m pytest tests/symphony -q -o 'addopts='
```

6. Validate and run a bounded smoke cycle:

```bash
./venv/bin/python -m hermes_cli.main symphony validate ./WORKFLOW.md --json
./venv/bin/python -m hermes_cli.main symphony run ./WORKFLOW.md --once --json
```

For daemon-style operation, omit `--once`:

```bash
./venv/bin/python -m hermes_cli.main symphony run ./WORKFLOW.md
```

Use `--max-cycles 1` or `--max-cycles 2` for bounded smoke tests. If `tracker.api_key` is absent, the run command skips dispatch and reports `skipped: missing_tracker_api_key` instead of contacting Linear.

When a dispatchable issue exists, Symphony posts a claim comment to Linear, runs Hermes in the issue workspace, and posts a completion comment with evidence files found under `.symphony/evidence/`.

## Operational notes

- Prefer small `max_concurrent_agents` values while the daemon is maturing.
- Keep `workspace.root` outside source-controlled directories unless the repository explicitly wants per-issue worktrees there.
- Add project-specific cleanup hooks only after validating they cannot delete paths outside the workspace root.
- Treat all local evidence as potentially sensitive; review before committing or posting.
