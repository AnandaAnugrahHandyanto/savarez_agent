---
title: "Hermes Agent Skill Authoring — Author in-repo SKILL"
sidebar_label: "Hermes Agent Skill Authoring"
description: "Author in-repo SKILL"
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# Hermes Agent Skill Authoring

Author in-repo SKILL.md: frontmatter, validator, structure.

## Skill metadata

| | |
|---|---|
| Source | Bundled (installed by default) |
| Path | `skills/software-development/hermes-agent-skill-authoring` |
| Version | `1.0.0` |
| Author | Hermes Agent |
| License | MIT |
| Platforms | linux, macos, windows |
| Tags | `skills`, `authoring`, `hermes-agent`, `conventions`, `skill-md` |
| Related skills | [`writing-plans`](/docs/user-guide/skills/bundled/software-development/software-development-writing-plans), [`requesting-code-review`](/docs/user-guide/skills/bundled/software-development/software-development-requesting-code-review) |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that Hermes loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

# Authoring Hermes-Agent Skills (in-repo)

## Overview

There are two places a SKILL.md can live:

1. **User-local:** `~/.hermes/skills/<maybe-category>/<name>/SKILL.md` — personal, not shared. Created via `skill_manage(action='create')`.
2. **In-repo (this skill is about this case):** `/home/bb/hermes-agent/skills/<category>/<name>/SKILL.md` — committed, shipped with the package. Use `write_file` + `git add`. `skill_manage(action='create')` does NOT target this tree.

## When to Use

- User asks you to add a skill "in this branch / repo / commit"
- You're committing a reusable workflow that should ship with hermes-agent
- You're editing an existing skill under `/home/bb/hermes-agent/skills/` (use `patch` for small edits, `write_file` for rewrites; `skill_manage` still works for patch on in-repo skills, but not for `create`)

## Contract

1. **Runtime surface:** Treat `SKILL.md` as executable agent guidance; put must-follow rules where the model will see them early.
2. **Scope boundary:** Keep in-repo skills concise and peer-matched; split bulky operator config, maintainer notes, or concepts into linked files or docs.
3. **Provenance law:** Any external pattern graft must name source, license/access, adapted subset, rejected subset, safety impact, and verification evidence.
4. **Solution-note law:** Reusable procedural lessons belong in structured solution notes or skills with verification and drift signals, not in durable personal memory.
5. **Verification law:** Before shipping, validate frontmatter/size, update generated docs when applicable, run targeted checks, and record review evidence.

## Required Frontmatter

Source of truth: `tools/skill_manager_tool.py::_validate_frontmatter`. Hard requirements:

- Starts with `---` as the first bytes (no leading blank line).
- Closes with `\n---\n` before the body.
- Parses as a YAML mapping.
- `name` field present.
- `description` field present, ≤ **1024 chars** (`MAX_DESCRIPTION_LENGTH`).
- Non-empty body after the closing `---`.

Peer-matched shape used by every skill under `skills/software-development/`:

```yaml
---
name: my-skill-name               # lowercase, hyphens, ≤64 chars (MAX_NAME_LENGTH)
description: Use when <trigger>. <one-line behavior>.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [short, descriptive, tags]
    related_skills: [other-skill, another-skill]
---
```

`version` / `author` / `license` / `metadata` are NOT enforced by the validator, but every peer has them — omit and your skill sticks out.

## Size Limits

- Description: ≤ 1024 chars (enforced).
- Full SKILL.md: ≤ 100,000 chars (enforced as `MAX_SKILL_CONTENT_CHARS`, ~36k tokens).
- Peer skills in `software-development/` sit at **8-14k chars**. Aim for that range. If you're pushing past 20k, split into `references/*.md` and reference them from SKILL.md.

## Peer-Matched Structure

Every in-repo skill follows roughly:

```
# <Title>

## Overview
One or two paragraphs: what and why.

## When to Use
- Bulleted triggers
- "Don't use for:" counter-triggers

## <Topic sections specific to the skill>
- Quick-reference tables are common
- Code blocks with exact commands
- Hermes-specific recipes (tests via scripts/run_tests.sh, ui-tui paths, etc.)

## Common Pitfalls
Numbered list of mistakes and their fixes.

## Verification Checklist
- [ ] Checkbox list of post-action verifications

## One-Shot Recipes (optional)
Named scenarios → concrete command sequences.
```

Not every section is mandatory, but `Overview` + `When to Use` + actionable body + pitfalls are the minimum for the skill to feel like a peer.

## Top-Loaded Runtime Contract

Treat `SKILL.md` as the runtime contract the agent will actually read, not as passive documentation. Long skills should put the laws that must survive truncation, skimming, and tool pressure near the top, immediately after `Overview` / `When to Use` and before detailed recipes.

Use a short `## Contract` or `## Non-Negotiable Rules` section when the skill has safety, output, or workflow constraints that are more important than examples:

```markdown
## Contract

1. **Scope boundary:** Use this skill only for <trigger>. Do not use it for <near-miss>.
2. **Safety law:** Never <dangerous action> without <approval / verification>.
3. **Output law:** Final output must include <required fields / artifact / evidence>.
4. **Verification law:** Before reporting DONE, run <specific checker/test> or state why it is not applicable.
```

Keep the contract brief: 4-7 bullets, imperative, and specific enough to audit. Put nuance, examples, and operator background later. If a rule is merely helpful advice, it belongs in `Workflow` or `Common Pitfalls`, not in the top-loaded contract.

## Structured Solution Notes

When a task produces a reusable postmortem, procedural lesson, or fix pattern, prefer a structured solution note or a promoted skill over durable personal memory. Memory is for stable user/environment facts; solution notes are for reusable engineering knowledge with provenance and verification.

Use this template for a lightweight note under a relevant repo docs, `references/`, or project artifact directory:

```markdown
---
title: <short solution title>
status: draft | verified | deprecated
source: <issue/task/source artifact/repo URL>
provenance: <commit, task id, artifact path, retrieval method, or rationale>
applies_to: [<skill>, <tool>, <repo area>]
last_verified: YYYY-MM-DD | not-yet-verified
---

# <Solution title>

## Problem
What recurring failure or decision this note resolves.

## Contract / Laws
- Non-negotiable constraints that must be followed when reusing this solution.

## Procedure
1. Exact steps, commands, or file edits.

## Verification
- Command/checker/test to run.
- Expected result or acceptance evidence.

## Provenance
- Source artifact, upstream license/access note, adaptation summary, and known risks.

## Retirement / Drift Signals
- Conditions that mean this note is stale and should be revised or deleted.
```

Promote a solution note to a full skill when it becomes a repeatable workflow with a clear trigger, tools, pitfalls, and verification checklist.

## Provenance for Pattern Grafts

This contract-and-solution-note pattern was grafted from the Spearhead `last30days-skill` source spike (`/home/filip/spearhead-execution/20260528-source-spikes/last30days-skill/closure-summary.md`, source repo `mvanhorn/last30days-skill` commit `1e03af19e0ad435ee6d227a3593b0c6e5d2ecbe8`, MIT). The adopted subset is procedural only:

- `SKILL.md` as runtime contract/product surface;
- top-loaded non-negotiable laws for long skills;
- structured solution notes instead of dumping procedural lessons into memory;
- contract/checker mindset for metadata, drift, install/update surfaces, and removed legacy paths.

Do not copy the source's monolithic skill style wholesale. Hermes should keep skills concise, split operator config / maintainer docs / concepts where useful, and require separate security review before adopting any auth, browser-cookie, or social/search behavior from external sources.

## Directory Placement

```
skills/<category>/<skill-name>/SKILL.md
```

Categories currently in repo (confirm with `ls skills/`): `autonomous-ai-agents`, `creative`, `data-science`, `devops`, `dogfood`, `email`, `gaming`, `github`, `leisure`, `mcp`, `media`, `mlops/*`, `note-taking`, `productivity`, `red-teaming`, `research`, `smart-home`, `social-media`, `software-development`.

Pick the closest existing category. Don't invent new top-level categories casually.

## Workflow

1. **Survey peers** in the target category:
   ```
   ls skills/<category>/
   ```
   Read 2-3 peer SKILL.md files to match tone and structure.
2. **Check validator constraints** in `tools/skill_manager_tool.py` if unsure.
3. **Draft** with `write_file` to `skills/<category>/<name>/SKILL.md`. If the skill has non-negotiable safety/workflow/output constraints, add a top-loaded `Contract` / `Non-Negotiable Rules` section before detailed recipes.
4. **Capture reusable lessons** as a structured solution note or a promoted skill, not as durable personal memory, when the lesson is procedural and source-specific.
5. **Validate locally**:
   ```python
   import yaml, re, pathlib
   content = pathlib.Path("skills/<category>/<name>/SKILL.md").read_text()
   assert content.startswith("---")
   m = re.search(r'\n---\s*\n', content[3:])
   fm = yaml.safe_load(content[3:m.start()+3])
   assert "name" in fm and "description" in fm
   assert len(fm["description"]) <= 1024
   assert len(content) <= 100_000
   ```
6. **Git add + commit** on the active branch.
7. **Note:** the CURRENT session's skill loader is cached — `skill_view` / `skills_list` will not see the new skill until a new session. This is expected, not a bug.

## Cross-Referencing Other Skills

`metadata.hermes.related_skills` unions both trees (`skills/` in-repo and `~/.hermes/skills/`) at load time. You CAN reference a user-local skill from an in-repo skill, but it won't resolve for other users who clone the repo fresh. Prefer referencing only in-repo skills from in-repo skills. If a frequently-referenced skill lives only in `~/.hermes/skills/`, consider promoting it to the repo.

## Editing Existing In-Repo Skills

- **Small fix (typo, added pitfall, tightened trigger):** `skill_manage(action='patch', name=..., old_string=..., new_string=...)` works fine on in-repo skills.
- **Major rewrite:** `write_file` the whole SKILL.md. `skill_manage(action='edit')` also works but requires supplying the full new content.
- **Adding supporting files:** `write_file` to `skills/<category>/<name>/references/<file>.md`, `templates/<file>`, or `scripts/<file>`. `skill_manage(action='write_file')` also works and enforces the references/templates/scripts/assets subdir allowlist.
- **Always commit** the edit — in-repo skills are source, not runtime state.

## Common Pitfalls

1. **Using `skill_manage(action='create')` for an in-repo skill.** It writes to `~/.hermes/skills/`, not the repo tree. Use `write_file` for in-repo creation.

2. **Leading whitespace before `---`.** The validator checks `content.startswith("---")`; any leading blank line or BOM fails validation.

3. **Description too generic.** Peer descriptions start with "Use when ..." and describe the *trigger class*, not the one task. "Use when debugging X" > "Debug X".

4. **Forgetting the author/license/metadata block.** Not validator-enforced, but every peer has it; omitting makes the skill look half-finished.

5. **Writing a skill that duplicates a peer.** Before creating, `ls skills/<category>/` and open 2-3 peers. Prefer extending an existing skill to creating a narrow sibling.

6. **Expecting the current session to see the new skill.** It won't. The skill loader is initialized at session start. Verify in a fresh session or via `skill_view` using the exact path.

7. **Linking to skills that don't exist in-repo.** `related_skills: [some-user-local-skill]` works for you but breaks for other clones. Prefer only in-repo links.

8. **Burying the laws below examples.** If the skill has non-negotiable safety/output/workflow constraints, place them before long recipes so they survive truncation and model attention drift.

9. **Saving procedural lessons as memory.** Reusable fix patterns, postmortems, and checker rules belong in solution notes or skills with provenance and verification, not in personal memory entries that will be injected forever without context.

## Verification Checklist

- [ ] File is at `skills/<category>/<name>/SKILL.md` (not in `~/.hermes/skills/`)
- [ ] Frontmatter starts at byte 0 with `---`, closes with `\n---\n`
- [ ] `name`, `description`, `version`, `author`, `license`, `metadata.hermes.{tags, related_skills}` all present
- [ ] Name ≤ 64 chars, lowercase + hyphens
- [ ] Description ≤ 1024 chars and starts with "Use when ..."
- [ ] Total file ≤ 100,000 chars (aim for 8-15k)
- [ ] Structure: `# Title` → `## Overview` → `## When to Use` → body → `## Common Pitfalls` → `## Verification Checklist`
- [ ] Long/safety-sensitive skills top-load a short `Contract` / `Non-Negotiable Rules` section before detailed recipes
- [ ] Reusable procedural lessons are captured as solution notes or skills with source, provenance, verification, and drift/retirement signals
- [ ] External pattern grafts record source, license/access, adapted subset, rejected subset, safety impact, and tests/checks run
- [ ] `related_skills` references resolve in-repo (or are explicitly OK to be user-local)
- [ ] `git add skills/<category>/<name>/ && git commit` completed on the intended branch
