---
name: skill-creator
description: Hermes-native workflow for creating, validating, updating, and publishing skills using skill_manage, skill_view, skills_list, and repository docs
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [skills, skill-authoring, documentation, self-improvement]
    related_skills: [hermes-agent, writing-plans]
---

# Skill Creator

## When to Use

Use this skill when the task is to:
- create a new Hermes skill from a successful workflow or repeated task
- update an outdated skill after discovering missing steps or pitfalls
- decide whether something should become a skill, tool, or memory
- add references/templates/scripts to support a skill
- prepare a bundled or optional skill for repository inclusion
- audit a skill for quality before relying on it repeatedly

Prefer this skill over ad hoc SKILL.md editing because it gives Hermes a repeatable authoring and verification SOP.

## Core Decision Rules

Before writing anything, decide the correct storage target:

- **Skill** → reusable procedural knowledge: workflows, command sequences, debugging playbooks, integration guides
- **Memory** → compact durable facts: user preferences, environment facts, stable conventions
- **Tool** → capability requiring dedicated runtime integration, precise processing, streaming, auth, or binary handling

If the capability is mostly instructions + existing tools, make it a **skill**.

## Minimal Execution Template

1. Confirm the workflow is reusable, non-trivial, and worth preserving.
2. Search existing skills to avoid duplicates and find the closest pattern.
3. Read the most relevant docs or reference skills before drafting.
4. Choose bundled vs optional vs user-local placement.
5. Create or patch the skill with `skill_manage`.
6. Add supporting references/templates/scripts only if they improve real reuse.
7. Verify the skill is discoverable, accurate, and aligned with current tooling.

## Procedure

### 1. Check if a skill already exists

Use discovery first:
- `skills_list()` for a quick scan
- `skill_view(name)` for likely matches
- `search_files()` in `skills/`, `optional-skills/`, and docs for near-duplicates

Do not create a second skill when patching an existing one is better.

### 2. Gather source material

Collect the real evidence that should become the skill:
- successful command sequences
- files changed and why
- pitfalls discovered during execution
- verification steps that proved the workflow actually worked
- relevant docs pages such as:
  - `website/docs/developer-guide/creating-skills.md`
  - `website/docs/guides/work-with-skills.md`
  - `website/docs/user-guide/features/skills.md`

If the workflow was only partially successful, do not immortalize guesses.

### 3. Choose the right scope

A good skill is narrow enough to trigger reliably and broad enough to be reusable.

Good:
- "webapp smoke testing with browser tools"
- "creating PowerPoint decks with pptxgenjs"
- "requesting code review before merge"

Bad:
- "all frontend work"
- "everything about Python"
- "misc useful commands"

### 4. Pick placement

- `skills/` → bundled, broadly useful, lightweight, generally applicable
- `optional-skills/` → official but heavier, niche, paid, or dependency-rich
- `~/.hermes/skills/` via `skill_manage` → user/local procedural memory

For repo work, mirror the repository’s existing category structure.

### 5. Write the SKILL.md skeleton

A strong skill usually contains:
- YAML frontmatter: `name`, `description`, `version`, optional metadata
- `# Title`
- `## When to Use`
- `## Procedure`
- `## Pitfalls`
- `## Verification`

Useful optional sections:
- `## Quick Reference`
- `## Inputs`
- `## Examples`
- `## Minimal Execution Template`

### 6. Use the right tool for authoring

Preferred operations:
- create a new skill: `skill_manage(action='create', ...)`
- fix or refine a skill: `skill_manage(action='patch', ...)`
- major rewrite only when necessary: `skill_manage(action='edit', ...)`
- add support files: `skill_manage(action='write_file', file_path='references/...')`

Prefer patching over full rewrites to reduce drift.

### 7. Encode pitfalls, not just happy paths

Every worthwhile skill should preserve what can go wrong:
- missing prerequisites
- version-specific breakage
- auth/setup blockers
- tool constraints
- verification traps (command succeeded but outcome wrong)

If a workflow required retries or debugging, capture the actual fix and the observable symptom.

### 8. Add verification that proves usefulness

Verification should confirm the outcome, not merely execution.

Examples:
- skill appears in `skills_list`
- docs/catalog entry exists if repo-visible
- related test or command passes
- produced file/report exists and contains expected content
- workflow can be invoked without hidden assumptions

## Bundled/Repo Integration Checklist

When contributing a repository skill rather than only a local one:

1. Create the skill directory under the correct category.
2. Add supporting files under `references/`, `templates/`, `scripts/`, or `assets/` only.
3. Update the relevant catalog/docs page if the skill should be user-visible.
4. If it changes an existing official capability map or audit doc, update that evidence too.
5. Verify references do not point to non-existent paths.

## Quality Bar

A skill is ready when all are true:
- trigger conditions are obvious
- steps are actionable, not hand-wavy
- pitfalls reflect real failure modes
- verification is concrete
- naming does not duplicate an existing skill confusingly
- placement (bundled vs optional vs local) matches actual intended use

## Pitfalls

- Do not save one-off task history as a skill.
- Do not create a skill before the workflow is actually proven.
- Do not duplicate an existing skill just to rename it without a routing reason.
- Do not omit verification; stale skills usually fail there first.
- Do not put repo-only paths or environment assumptions into a supposedly general skill unless clearly marked.

## Verification

- The skill can be discovered by name or category.
- The SKILL.md structure matches Hermes conventions.
- Any linked files referenced by the skill actually exist.
- If the skill was patched, the missing step/pitfall is now explicitly documented.
- If the skill is repo-visible, catalog/docs references were updated too.
