---
name: codex-coding-discipline
description: Apply disciplined coding and delegation rules.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [codex, coding, delegation, agents, AGENTS.md]
    category: software-development
    related_skills: [codex, hermes-agent]
---

# Codex Coding Discipline Skill

Use this skill to apply disciplined coding, scoped delegation, and explicit
verification rules to software work. It does not replace project-specific
architecture notes; it supplies a reusable operating contract that can also be
installed into `AGENTS.md` for Codex and other agent runtimes.

## When to Use

- Writing, fixing, refactoring, extending, or reviewing code
- Translating a Hermes skill habit into persistent workspace instructions
- Preparing a repo for Codex app-server or Codex CLI work
- Coordinating subagents or parallel coding workers

Skip the full workflow for obvious one-line fixes, typo corrections, and simple
code explanation questions.

## Prerequisites

- Hermes skill install: `hermes skills install official/software-development/codex-coding-discipline`
- Workspace install: a writable `AGENTS.md` in the target repo, or permission
  to create one

## How to Run

For a Hermes session, install or preload this skill and follow the procedure
below.

For Codex or repo-wide instructions, install the included `AGENTS.md` block:

```bash
python optional-skills/software-development/codex-coding-discipline/scripts/install_agents_block.py AGENTS.md
```

From an installed skill directory, run the same script under
`~/.hermes/skills/software-development/codex-coding-discipline/scripts/`.

To print the block without writing:

```bash
python optional-skills/software-development/codex-coding-discipline/scripts/install_agents_block.py --print
```

## Quick Reference

- Define "done" as a verifiable outcome before editing.
- State load-bearing assumptions early.
- Prefer the smallest change that solves today's request.
- Keep edits surgical and traceable to the task.
- Delegate only bounded side work when delegation is explicitly requested.
- Verify with the narrowest meaningful command first.

## Procedure

1. Convert the request into one or more concrete done criteria.
2. Identify assumptions that would force a rewrite if wrong; ask only about
   blocking ambiguity.
3. Inspect the relevant code before editing.
4. Make the minimum change that satisfies the criteria.
5. If subagents are explicitly requested, assign disjoint ownership and concrete
   outputs before they start.
6. Run targeted verification, then broaden only if the touched surface warrants
   it.
7. Report what changed and what verification did or did not run.

## Pitfalls

- Do not silently choose between multiple valid interpretations.
- Do not add abstractions for one-off code.
- Do not bundle unrelated refactors with a bug fix.
- Do not spawn subagents for immediate blocking work.
- Do not claim tests passed unless they were run.

## Verification

For the skill package itself:

```bash
python optional-skills/software-development/codex-coding-discipline/scripts/install_agents_block.py --print >/tmp/codex-discipline.md
python optional-skills/software-development/codex-coding-discipline/scripts/install_agents_block.py /tmp/AGENTS.md
python optional-skills/software-development/codex-coding-discipline/scripts/install_agents_block.py --check /tmp/AGENTS.md
```
