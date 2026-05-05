# Original Repo Adaptation Notes

Source inspected: `github.com/batumilove/mvp-launcher` at commit `2d0d759`.

Hermes migration findings:

- `hermes claw migrate --source <repo> --dry-run --preset full` reports `Nothing to migrate` because this is a flat standalone skill repo, not an OpenClaw home directory.
- `hermes skills tap add batumilove/mvp-launcher` can add the tap but does not expose the root-level `SKILL.md` as a searchable skill.
- Scripts compile, but the original workflow assumes Clawd paths, sibling skills, and Batumi-specific preview infrastructure.

Before using the copied scripts for real launches, harden:

- `$HERMES_HOME`/profile-aware path handling.
- Configurable Porkbun/Cloudflare command integration.
- Configurable preview host/domain/network.
- Backend-agnostic agent execution instead of a sibling `claude-code` skill path.
- Real browser tests if claiming browser E2E.
- Explicit dry-run/phase flags for safe partial execution.
