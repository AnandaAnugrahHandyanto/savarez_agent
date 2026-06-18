# Project Context (bridge to Rosetta)

> Existing-system knowledge is maintained by Rosetta / Rosetta-equivalent AS-IS docs.
> This file points BMad agents at that context and adds implementation rules.
> Keep in sync after each Rosetta refresh.

## Source of truth (Rosetta — AS-IS)

- Tech stack & versions   → see `../TECHSTACK.md`
- File / module map       → see `../CODEMAP.md`
- Dependencies & bounds   → see `../DEPENDENCIES.md`
- Current architecture    → see `../ARCHITECTURE.md`
- Business / domain       → see `../CONTEXT.md`

## Implementation rules (non-obvious, BMAD-specific)

- Follow `AGENTS.md` before changing Hermes Agent source.
- Preserve per-conversation prompt caching; do not mutate system/tool schema mid-conversation unless the explicit task requires it and the impact is documented.
- Preserve strict message role alternation in agent-loop changes.
- Keep the core model tool schema narrow. Prefer existing tools, CLI+skill flows, service-gated tools, plugins, or MCP servers before adding a new core tool.
- Public Hermes Agent source must stay general-purpose. Private deployment or automation policy belongs outside upstream framework code.
- Use profile-safe path helpers such as `get_hermes_home()` instead of hardcoded `~/.hermes` in framework code.
- Tests must not touch the real user's Hermes home; use isolated temp homes and the repository test wrapper where possible.
- For bug fixes, reproduce or locate line-level evidence before implementation. Add regression coverage where practical.
- For behavior changes, use TDD where practical: failing test first, minimal implementation, then verification.
- For source changes, use an isolated git worktree and open a PR for review. Do not auto-merge source changes unless maintainers have explicitly approved that automation policy.

## To-be vs as-is

- BMad PRD / architecture / stories / sprint artifacts = TO-BE design for new work.
- `ARCHITECTURE.md`, `TECHSTACK.md`, `CODEMAP.md`, `DEPENDENCIES.md`, and `CONTEXT.md` = AS-IS current-system context maintained by Rosetta / Rosetta-equivalent refresh.
- Do not overwrite AS-IS docs with TO-BE design. Link to them from BMad artifacts instead.
