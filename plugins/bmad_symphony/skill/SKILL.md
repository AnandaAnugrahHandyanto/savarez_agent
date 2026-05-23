---
name: bmad-symphony-workflow
description: Source-grounded BMAD workflow helper for Hermes. Use extracted BMAD docs to choose the next BMAD phase/workflow, then optionally use Hermes delegation as an execution wrapper.
version: 1.1.0
author: NousResearch
license: MIT
platforms:
  - linux
  - macos
metadata:
  hermes:
    category: autonomous-ai-agents
    tags:
      - bmad
      - source-grounded
      - planning
      - implementation
    related_skills:
      - hermes-agent:skills
      - autonomous-ai-agents:plan
---

# BMAD workflow for Hermes

This skill is the playbook for the Hermes BMAD plugin.

## Grounding rule

All BMAD-specific information must be derived from the extracted BMAD source model:

- Source: `https://docs.bmad-method.org/llms-full.txt`
- Local extract: `plugins/bmad_symphony/source/bmad_llms_extract.md`

Do not invent BMAD phases, artifacts, commands, quality gates, or agent roles. If a fact is not in the extracted source model or explicitly provided by the user, label it as an assumption or omit it.

Hermes/Symphony delegation is a Hermes execution wrapper. It is not a BMAD source concept and must be described separately from BMAD guidance.

## Source-derived BMAD model

BMAD organizes development into four phases:

1. Analysis — optional brainstorming, research, product brief, or PRFAQ.
2. Planning — required requirements via PRD or spec.
3. Solutioning — architecture and technical work breakdown.
4. Implementation — build epic by epic, story by story.

Planning tracks:

- Quick Flow — bug fixes, simple features, clear scope; tech-spec only.
- BMad Method — products, platforms, complex features; PRD + Architecture + UX.
- Enterprise — compliance or multi-tenant systems; PRD + Architecture + Security + DevOps.

Track story counts are guidance, not definitions. Choose based on planning needs.

## Required default behavior

1. Start with `bmad-help` whenever the next workflow is uncertain.
2. Use a fresh chat for each BMAD workflow.
3. If BMAD is not installed, install from the project directory with `npx bmad-method install` and select the BMad Method module.
4. Use `_bmad/` for agents/workflows/tasks/configuration and `_bmad-output/` for generated artifacts.
5. Optionally capture technical preferences and rules in `_bmad-output/project-context.md` or generate it after architecture with `bmad-generate-project-context`.

## Phase workflows

### Analysis, optional

- `bmad-brainstorming` — guided ideation.
- `bmad-market-research`, `bmad-domain-research`, `bmad-technical-research` — research.
- `bmad-product-brief` — foundation document when the concept is clear.
- `bmad-prfaq` — Working Backwards stress test.

### Planning, required

For BMad Method and Enterprise:

- Run `bmad-prd` in a fresh chat.
- Outputs: `prd.md`, `addendum.md`, `decision-log.md`.
- Intents: Create, Update, Validate.

For Quick Flow:

- Run `bmad-quick-dev`; it handles planning and implementation in a single workflow.

For UI projects:

- Optionally invoke `bmad-agent-ux-designer` and run `bmad-ux` after creating the PRD.

### Solutioning

Create architecture:

1. Invoke `bmad-agent-architect` in a fresh chat.
2. Run `bmad-create-architecture`.
3. Produce the architecture document with technical decisions.

Create epics and stories:

1. Invoke `bmad-agent-pm` in a fresh chat.
2. Run `bmad-create-epics-and-stories`.
3. Use both PRD and Architecture to create technically-informed stories.

Implementation readiness check, highly recommended:

1. Invoke `bmad-agent-architect` in a fresh chat.
2. Run `bmad-check-implementation-readiness`.
3. Validate cohesion across planning documents.

### Implementation

Initialize sprint planning:

- Invoke `bmad-agent-dev` and run `bmad-sprint-planning`.
- Output: `sprint-status.yaml`.

For each story, repeat with fresh chats:

1. `bmad-create-story` — create story file from epic.
2. `bmad-dev-story` — implement the story.
3. `bmad-code-review` — quality validation, recommended.

After completing all stories in an epic:

- Invoke `bmad-agent-dev` and run `bmad-retrospective`.

## Hermes plugin tools

- `bmad_intake` — create a source-grounded BMAD track/phase/workflow recommendation.
- `bmad_story` — shape the next BMAD handoff/story while preserving the source-derivation rule.
- `symphony_run` — prepare optional Hermes delegation tasks; always separate wrapper behavior from BMAD claims.
- `bmad_proof` — check that the handoff/implementation is grounded in extracted BMAD source facts and user-provided context.
- `bmad_status` — inspect saved workflow state.
- `bmad_reset` — clear saved workflow state.

## Pitfalls

- Do not present Symphony/delegation as part of BMAD.
- Do not add generic agile or AI-agent guidance unless it is present in the extracted source or provided by the user.
- Do not choose a BMAD track purely by story-count guidance.
- Do not skip fresh chats between BMAD workflows.
