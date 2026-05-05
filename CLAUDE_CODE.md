# Claude Code Worktree

This directory is a Claude Code worktree for `hermes-agent-ucpm`.

- **Branch**: `chore/dependabot-gitsubmodule-CHG-0001`
- **Scope**: CHG-0001 — append `gitsubmodule` ecosystem block to `.github/dependabot.yml`.
- **Upstream policy preserved**: the existing `github-actions` block (and the comment block explaining why pip is intentionally excluded under uv.lock pinning) is untouched. Only the new `gitsubmodule` ecosystem is added.
- **Why a fork-only addition**: this fork carries the `tinker-atropos` submodule that upstream's policy doesn't cover.
- **Orchestrator issue**: https://github.com/WanderingStardust79/paperclip-UCPM-orchestrator/issues/2

Do not merge from this worktree directly — review and merge via PR on GitHub.
