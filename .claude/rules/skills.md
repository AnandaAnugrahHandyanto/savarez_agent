# Rule: skills

Paths: `skills/`, `optional-skills/`.

DO NOT:
- Hermes runtime skill schema is contract.
- Do not confuse runtime `skills/` with methodology `.claude/skills/`.

Architecture Notes: bundled runtime skills are synced into `~/.hermes/skills/` by setup.

Thresholds: bundled skill edits require `hermes setup` to re-seed runtime skills.

Key Files: `skills/`, `optional-skills/`, `tools/skills_sync.py`.
