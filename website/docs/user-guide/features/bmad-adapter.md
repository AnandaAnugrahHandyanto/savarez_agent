---
title: BMAD Adapter
description: Use project-local BMAD-METHOD skills from Hermes without making BMAD global behavior.
---

# BMAD Adapter

Hermes can detect a project-local BMAD-METHOD installation and expose its workflows as project-scoped skills. The adapter is optional: BMAD appears only when the current working directory is inside a project that contains `_bmad/`, or when a caller explicitly asks from that project path.

## What it does

- Detects `_bmad/` by walking upward from the current working directory, stopping at the nearest Git root by default.
- Reads BMAD skills from real BMAD manifests when present (`_bmad/_config/skill-manifest.csv`) and falls back to scanning `_bmad/core/` and `_bmad/bmm/`.
- Shows active BMAD skills in `skills_list` under `bmad-project`.
- Supports `skill_view` identifiers such as `bmad:bmad-help`, including safe linked resource reads from `references/`, `templates/`, `scripts/`, and `assets/`.
- Builds explicit BMAD invocation payloads that label the skill as project-provided and scoped to the current task.

## What it does not do

- It does not turn every Hermes session into a BMAD session.
- It does not inject all BMAD instructions into the system prompt.
- It does not install BMAD for you.
- It does not automatically convert BMAD stories into Kanban tasks.
- Prompt-index exposure is disabled by default and reserved for a later phase after project-aware cache semantics are proven.

## Configuration

```yaml
bmad:
  enabled: true
  auto_detect: true
  expose_in_skill_index: false
  expose_slash_commands: true
  max_indexed_skills: 80
  allowed_roots: []
  disabled_skills: []
```

Set `bmad.enabled: false` to disable the adapter. Use `allowed_roots` to restrict BMAD discovery to approved workspaces, and `disabled_skills` to hide specific BMAD skills.

## Safety model

Project-local BMAD content is treated as semi-trusted project instruction, closer to an `AGENTS.md` file than to a bundled Hermes skill. Hermes does not make it global policy; explicit invocation payloads tell the agent to apply BMAD instructions only to the current task.
