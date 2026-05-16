# Agent Orchestration Defaults

> **For Hermes:** Use this as the default pre-flight and role split before dispatching Claude Code, Codex, OpenCode, or Hermes subagents on this repo.

**Goal:** Keep coding-agent work fast, grounded, and non-overlapping by front-loading repo intelligence and assigning explicit roles.

**Architecture:** One controller owns scope, shared context, and verification. Workers receive bounded tasks with exact files, expected tests, and the relevant repo guidance copied into their prompt. Reviewers check spec compliance first, then quality.

**Tech Stack:** Hermes Agent repo, `AGENTS.md`, Graphify detection artifacts, Claude Code, Codex, OpenCode, Hermes `delegate_task`, git worktrees when needed.

---

## Default Pre-flight

1. Read `AGENTS.md` before touching code.
2. Check `git status --short` and identify existing user/agent changes. Do not overwrite unrelated work.
3. Check for Graphify artifacts:
   - If `graphify-out/GRAPH_REPORT.md` or `graphify-out/graph.json` exists, read it before searching broadly.
   - If only `graphify-out/.graphify_detect.json` exists, treat Graphify as detection-only; do not run full extraction blindly on this repo.
4. Check for local agent config:
   - `.opencode/opencode.json`
   - `.opencode/plugins/`
   - project `CLAUDE.md` / `.cursorrules` if later added.
5. Decide role split before dispatching workers.

## Default Role Split

Use this unless the task clearly calls for a different split:

- **Hermes controller:** owns scope, context pack, task sequencing, verification, final summary.
- **Claude Code:** broad implementation, multi-file feature work, large refactors.
- **Codex:** surgical diffs, tests, bug fixes, API/CLI edge cases, final patch tightening.
- **OpenCode:** alternate implementation/review pass, quick independent verification, Graphify-aware exploration.
- **Hermes `delegate_task`:** small bounded subreviews or research where a synchronous fresh context is enough.

## Worker Context Pack

Every worker prompt should include:

- User-visible goal and non-goals.
- Exact files/directories in scope.
- Relevant `AGENTS.md` excerpts, especially testing and pitfall sections.
- Current `git status --short` summary.
- Graphify status:
  - `graphify-out/GRAPH_REPORT.md` / `graph.json` available: summarize findings.
  - detection-only: say extraction is not trusted yet.
- Test command to run, normally `scripts/run_tests.sh ...` for this repo.
- Requirement to report changed files, commands run, and unresolved risks.

## Execution Gates

1. **Pre-flight gate:** no worker starts until repo guidance, git status, and graph status are known.
2. **Spec gate:** after implementation, verify the result matches the original task exactly.
3. **Quality gate:** after spec pass, check maintainability, tests, security, and repo conventions.
4. **Integration gate:** controller runs targeted tests and reviews `git diff --stat` / relevant diffs before reporting done.

## Graphify Policy for This Repo

Current known state:

- `graphify detect` has worked and produced `graphify-out/.graphify_detect.json`.
- Full extraction has previously hung/timed out even on a bounded smoke run.
- Do not block normal development on Graphify extraction until its runtime path is debugged.
- Prefer interactive `/graphify .` in Claude/OpenCode or a tiny isolated repo for future smoke tests.

## Default Verification

For Hermes repo code changes:

```bash
scripts/run_tests.sh <targeted test path> -q
```

Use full `scripts/run_tests.sh` only when scope justifies it. Do not call raw `pytest` unless debugging the test runner itself.

For docs/config-only changes:

- Re-read changed files.
- Check links/paths are exact.
- Verify `git diff --stat` only includes intended files.

## Handoff Format

Worker summaries should be short and structured:

```text
Status: PASS | BLOCKED | NEEDS_REVIEW
Changed files:
- path/to/file
Commands run:
- command -> result
Notes/Risks:
- ...
```
