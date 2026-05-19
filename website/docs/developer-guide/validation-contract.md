---
title: Validation Contract
---

# Validation Contract

Hermes uses a small wrapper around the canonical pytest runner so contributors
and agents have one local entry point before opening a PR:

```bash
scripts/validate_pr.sh
```

The wrapper chooses the smallest useful scope from the files changed against
`origin/main`. It does not own pytest setup. Any scope that runs tests delegates
to `scripts/run_tests.sh`, which is the source of truth for virtualenv selection,
credential scrubbing, timezone and locale pins, and pytest worker count.

## Scopes

```bash
scripts/validate_pr.sh --scope docs
scripts/validate_pr.sh --scope scripts
scripts/validate_pr.sh --scope tests
scripts/validate_pr.sh --scope full
```

Use `--dry-run` to see the selected commands without executing them:

```bash
scripts/validate_pr.sh --scope auto --dry-run
```

| Scope | Intended change | Command contract |
| --- | --- | --- |
| `docs` | Markdown, docs site pages, sidebar entries, `AGENTS.md`, `README.md`, `CONTRIBUTING.md` | Shell syntax-check the wrapper. |
| `scripts` | Validation wrapper or adjacent scripts | Syntax-check the wrapper and canonical test runner, then run `tests/test_validation_contract.py` through `scripts/run_tests.sh`. |
| `tests` | Contract tests for the wrapper | Run `tests/test_validation_contract.py` through `scripts/run_tests.sh`. |
| `full` | Python runtime behavior, packaging, gateway, CLI, providers, plugins, or uncertain scope | Run the full suite through `scripts/run_tests.sh`. |

Before pushing a runtime PR, prefer `scripts/validate_pr.sh --scope full`.
For narrow docs/scripts/tests work, record the exact wrapper command you ran in
the PR body.

## Agent Expectations

Agents working in this repository should:

- Start from a clean branch or worktree based on `origin/main`.
- Avoid reverting unrelated user or contributor edits.
- Keep validation changes in docs, scripts, and tests unless the task explicitly
  asks for runtime behavior.
- Use `scripts/validate_pr.sh --dry-run` when deciding the smallest validation
  scope, then run the selected command.
- Report the command, result, branch, and commit SHA in the PR or handoff.
