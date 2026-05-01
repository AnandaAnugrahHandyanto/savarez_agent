# Hermes Skill Portfolio Segmentation

> Generated to reduce skill sprawl by separating **core operating skills**, **professional specialist skills**, and **long-tail / incubating skills** before any physical directory moves.

## Canonical counts

| Scope | Count | Meaning |
|---|---:|---|
| Repo bundled (`skills/`) | 84 | Built-in skills shipped by default |
| Repo optional (`optional-skills/`) | 44 | Official optional skills shipped in-repo |
| Repo official total | 128 | Built-in + optional |
| Runtime effective catalog | 156 | Current active / discoverable runtime pool |
| Runtime archived-disabled | 19 | `openclaw-imports/.lark-*.disabled` compatibility remnants |
| Runtime physical `SKILL.md` files | 175 | Effective runtime pool + archived-disabled |

## Operating decision

We should **not** start by physically moving or deleting skill folders. The right first move is:

1. add portfolio metadata (`tier`, `status`, `source`, `duplicate_of` where needed)
2. change the docs / catalog UX to emphasize **starter/core** views
3. isolate OpenClaw compatibility skills from the main product narrative
4. archive disabled remnants explicitly

## Portfolio layers

### 1. Core
Small set of skills we actively want users and routing logic to see first.

Target size: **15–20**

Current core candidates:

- `systematic-debugging`
- `test-driven-development`
- `subagent-driven-development`
- `requesting-code-review`
- `github-pr-workflow`
- `github-code-review`
- `github-auth`
- `docker-management`
- `native-mcp`
- `mcporter`
- `hermes-agent`
- `codex`
- `claude-code`
- `honcho`
- `docx`
- `xlsx`
- `notion`
- `google-workspace`
- `himalaya`
- `domain-intel`

### 2. Professional
Useful, supported, and valuable — but not part of the default hero shelf.

Examples:
- most GitHub / MCP / DevOps skills
- document productivity skills
- research and domain investigation skills
- selected data / automation specialist skills

### 3. Long-tail
Lower-frequency, niche, experimental, or domain-specific skills.

Examples:
- most optional `mlops/*`
- blockchain / health niche skills
- specialty creative skills
- migration and compatibility-heavy legacy items

## Status layers

Every skill should also expose a lifecycle status:

- `active` — supported, recommended, routable
- `incubating` — useful but specialist / still proving value
- `deprecated` — replaced by another canonical skill or alias
- `archived` — retained only for compatibility / history

## OpenClaw compatibility policy

The current runtime contains a large `openclaw-imports` footprint. That footprint should be treated as a **compatibility layer**, not as equal first-class product surface.

### Effective runtime split

- Effective runtime pool: **156**
- Archived disabled OpenClaw remnants: **19**
- Physical runtime files: **175**

### Decision

- keep compatibility skills loadable when needed
- remove them from primary catalog / homepage emphasis
- list disabled `.lark-*.disabled` skills as `archived`
- present imported / compatibility variants under a compatibility section instead of the main catalog

## P0 actions

1. **Add portfolio metadata** to generated skill indexes and docs outputs.
2. **Add starter / core view** to the website skills page.
3. **Separate official built-in vs optional vs external/community** more clearly.
4. **Mark long-tail ML and migration-heavy skills as secondary in the UI**.
5. **Document runtime compatibility layer explicitly** so users stop confusing product skills with imported remnants.

## P1 actions

1. Add `duplicate_of` / alias metadata for imported variants.
2. Add role-based shelves (`Coding`, `Docs`, `Research`, `Infrastructure`, `Communication`).
3. Add lifecycle views (`Active`, `Incubating`, `Archived`).
4. Later, consider physical directory cleanup only after routing and docs are already stable.
