# Private skills integration

If you maintain a separate private repo of operator-only skills, integrate via this contract.

## Location

Private skills clone to `~/.claude/skills/private/<name>/SKILL.md` in Claude Code user-global storage. They do not live in this repo.

## Naming

Prefix all private skill names with `private-`.

## Activation

Auto-invoke per their own `description:` frontmatter. No configuration in this repo required.

## Conflict resolution

If a private skill name collides with an overlay skill, the private skill wins. Document the override here with `<skill-name>: private overrides project (reason)`.

## Update path

Porter pushes to private repo; Clay pulls private repo; both machines align independently of the Hermes overlay update path.

## Privacy

Never reference private-skill names from this repo's committed files. Public-fork name leakage is a privacy regression.
