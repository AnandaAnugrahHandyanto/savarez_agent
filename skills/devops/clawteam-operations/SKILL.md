---
name: clawteam-operations
description: Operate and verify ClawTeam teams, inboxes, QA handoffs, and Hermes plugin integration.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [clawteam, multi-agent, qa, inbox, teams, hermes-plugin]
---

# ClawTeam Operations

Use this skill when asked to check ClawTeam status, run a ClawTeam smoke test, coordinate teams/inboxes, verify QA verdict handoffs, inspect the Hermes ClawTeam plugin, or complete/review/ship GitHub issue or PR work where QA must be auditable.

## Non-negotiable QA gate

For GitHub issue, PR, code review, or shipping work, QA is not optional:

1. Discover teams first with `clawteam_team_discover` when the Hermes tools are available.
2. Ensure the long-lived `qa-validation` team exists. If it is absent, create it with `clawteam_team_spawn(name="qa-validation", description="Cross-issue QA verdicts", leader_name="leader")`.
3. Use a per-issue team such as `issue-NN-fix` for implementation/build-log messages when doing tracked issue work.
4. Before any “done”, “shipped”, “merged”, “complete”, `ALL_DONE`, or contract line, post a QA verdict to `qa-validation` with `clawteam_inbox_send`.
5. Prefer `clawteam_inbox_peek` for audits so evidence remains available.

Verdict format:

```text
Issue #N QA verdict: PASS|FAIL. Checked: <bullets>. Findings: <list or none>.
```

If the verdict is `FAIL`, do not ship. Fix and re-run QA, or report the blocker.

## Core workflow

1. **Discover current teams first.**
   - Use Hermes ClawTeam tools when available: `clawteam_team_discover`, `clawteam_team_status`, `clawteam_inbox_peek`.
   - If using the CLI directly, prefer JSON output for deterministic parsing.

2. **Check the long-lived QA team separately.**
   - The expected long-lived team is `qa-validation`; per-issue teams are temporary and should be cleaned up after shipping/review.
   - Peek rather than receive when auditing.

3. **Run a reversible smoke test for core functionality when validating setup.**
   - Create a temporary team.
   - Check team status.
   - Send a message to the leader.
   - Peek the leader inbox and verify the message is present.
   - Clean up the temporary team.
   - Discover teams afterward to verify cleanup removed the smoke-test team.

4. **Verify the Hermes plugin surface if relevant.**
   - Plugin files live under `plugins/clawteam/`.
   - Compile plugin Python files with `python -m py_compile plugins/clawteam/*.py plugins/clawteam/dashboard/*.py`.
   - Expected tools include team discover/status/spawn and inbox send/peek.

5. **Report with evidence, not intuition.**
   - Include what was checked, what passed/failed, and caveats.
   - Distinguish “core CLI/inbox flow works” from “full autonomous spawned-agent runtime was tested.”

6. **When an actionable issue is found, create and execute a tracked ticket.**
   - Create a GitHub issue, branch as `fix/<issue>-<slug>`, fix surgically, verify locally, push, and open a PR whose body includes `Closes #<issue>`.
   - Post the QA verdict to `qa-validation` before pushing/opening/finalizing the PR workflow.
   - If GitHub reports no checks for the branch, say so explicitly and use local test output as verification evidence.
   - Leave unrelated untracked workspace files untouched.

## CLI pitfalls

- `--json` is a global ClawTeam option. Put it before the subcommand:
  - Correct: `clawteam --json team discover`
  - Wrong: `clawteam team discover --json`
- Team creation uses `--agent-name` for the leader name, not `--leader-name`:
  - `clawteam --json team spawn-team my-team --description "..." --agent-name leader`
- For cleanup, use the command-specific force flag:
  - `clawteam --json team cleanup my-team --force`
- Prefer `inbox peek` for audits so evidence remains available.

## Smoke-test recipe

```bash
team="hermes-smoke-test"
clawteam team cleanup "$team" --force >/dev/null 2>&1 || true
clawteam --json team spawn-team "$team" --description "Hermes smoke test" --agent-name leader
clawteam --json team status "$team"
clawteam --json inbox send "$team" leader "smoke ping" --from hermes-smoke
clawteam --json inbox peek "$team" --agent leader
clawteam --json team cleanup "$team" --force
clawteam --json team discover
```

Pass criteria:
- spawn/status/send/peek/cleanup all exit 0;
- peek output contains the smoke message;
- final discover output does not include the smoke-test team.
