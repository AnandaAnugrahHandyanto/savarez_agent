<!-- BEGIN HERMES CODEX CODING DISCIPLINE -->
## Codex Coding Discipline

Apply these rules whenever Codex writes, fixes, refactors, reviews, or explains
code. They adapt the `karpathy-coding` discipline for a tool-using Codex
runtime: inspect the codebase first, edit files directly, and verify real
behavior where practical.

Core tension: trade a little speed for fewer rewrites. For obvious one-liners,
typos, and simple explanation questions, skip the ceremony and answer directly.

### Pre-flight

Before changing code, know what "done" looks like in verifiable terms:

| Vague request | Verifiable criterion |
|---|---|
| "fix the login bug" | Correct password logs in; wrong password is rejected. |
| "make it faster" | The target operation stays under an agreed threshold. |
| "add validation" | Named invalid inputs raise the expected error or response. |

If the done condition is unclear and a wrong guess would cause a rewrite, ask a
short clarifying question before editing. If there are multiple plausible
interpretations, name them and ask the user to choose.

State load-bearing assumptions early. Examples: runtime version, persistence
behavior, whether a setting is local-only or cross-surface, and whether a plugin
change may touch core.

### Implementation Rules

- Prefer the smallest change that satisfies today's request.
- Match surrounding style exactly; avoid drive-by formatting, renames, and
  unrelated refactors.
- Do not add abstractions, optional parameters, config keys, logging, or broad
  error handling unless the task needs them now.
- Every changed line should trace back to the user's request or to verification
  required by that request.
- Use structured parsers and existing helpers instead of ad hoc string handling
  when the codebase already has the right tool.
- Keep comments rare and useful: explain non-obvious decisions, not what each
  line does.

For non-trivial tasks, work from a short plan with explicit checks:

```text
Plan:
1. Change X -> verify with test Y or command Z.
2. Update affected surface A -> verify behavior B.
```

### Delegation Contract

Use subagents only when the user explicitly asks for delegation, parallel
agents, or subagent work. Delegation is for bounded side work that can progress
in parallel with the main path; do the immediate blocking investigation or edit
locally.

When delegating:

- Give each subagent a concrete, self-contained task.
- Assign clear ownership of files, modules, or read-only questions.
- Tell workers they are not alone in the codebase and must not revert or
  overwrite unrelated edits.
- Do not duplicate work between the parent and subagents.
- Prefer disjoint write sets for parallel workers.
- Continue useful non-overlapping work locally while subagents run.
- Review returned changes before integrating or reporting them.

### Verification

Run the narrowest meaningful verification first: targeted test, typecheck,
lint, or an executable reproduction. Broaden only when the change touches shared
contracts, cross-module behavior, CLI/gateway surfaces, or user-facing flows.

If verification is impossible or too expensive for the current turn, say exactly
what was not run and why. Do not imply unrun tests passed.
<!-- END HERMES CODEX CODING DISCIPLINE -->
