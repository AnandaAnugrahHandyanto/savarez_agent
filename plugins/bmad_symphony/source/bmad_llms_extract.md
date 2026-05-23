# BMAD source extract

Source: https://docs.bmad-method.org/llms-full.txt
Fetched: 2026-05-23

This file is the grounding reference for the Hermes BMAD plugin. BMAD-specific terminology and workflow guidance must be derived from this extract or from user-provided context. Do not add new BMAD claims from general knowledge.

## Core workflow model

BMAD organizes development into four phases:

1. Analysis — brainstorming, research, product brief, PRFAQ; optional.
2. Planning — requirements via PRD or spec; required.
3. Solutioning — architecture and technical work breakdown.
4. Implementation — build epic by epic, story by story.

## Planning tracks

- Quick Flow — bug fixes, simple features, clear scope, about 1–15 stories; creates a tech spec only.
- BMad Method — products, platforms, complex features, about 10–50+ stories; creates PRD + Architecture + UX.
- Enterprise — compliance, multi-tenant systems, about 30+ stories; creates PRD + Architecture + Security + DevOps.

Story counts are guidance, not definitions. Choose the track based on planning needs.

## Install and first step

Install from a project directory:

```bash
npx bmad-method install
```

Prerelease channel:

```bash
npx bmad-method@next install
```

When prompted, select the BMad Method module.

The installer creates:

- `_bmad/` — agents, workflows, tasks, and configuration.
- `_bmad-output/` — generated artifacts.

After install, run:

```text
bmad-help
```

BMad-Help detects completed artifacts and recommends the next workflow. Start with `bmad-help` whenever unsure.

## Fresh-chat rule

Use a fresh chat for each workflow to prevent context limitations and contamination.

## Optional project context

Project conventions can be captured in `_bmad-output/project-context.md`, created manually or generated after architecture with:

```text
bmad-generate-project-context
```

## Phase 1 — Analysis workflows

- `bmad-brainstorming` — guided ideation.
- `bmad-market-research` / `bmad-domain-research` / `bmad-technical-research` — market, domain, and technical research.
- `bmad-product-brief` — foundation document when the concept is clear.
- `bmad-prfaq` — Working Backwards challenge to stress-test and forge the product concept.

## Phase 2 — Planning workflows

For BMad Method and Enterprise tracks:

- Run `bmad-prd` in a new chat.
- Output: `prd.md`, `addendum.md`, `decision-log.md`.
- Intents: Create, Update, Validate.

For Quick Flow:

- Run `bmad-quick-dev`; it handles planning and implementation in a single workflow.

If the project has a UI, optionally invoke `bmad-agent-ux-designer` and run `bmad-ux` after creating the PRD.

## Phase 3 — Solutioning workflows

Create architecture:

1. Invoke `bmad-agent-architect` in a new chat.
2. Run `bmad-create-architecture`.
3. Output: architecture document with technical decisions.

Create epics and stories:

1. Invoke `bmad-agent-pm` in a new chat.
2. Run `bmad-create-epics-and-stories`.
3. The workflow uses both PRD and Architecture to create technically-informed stories.

Implementation readiness check is highly recommended:

1. Invoke `bmad-agent-architect` in a new chat.
2. Run `bmad-check-implementation-readiness`.
3. Validates cohesion across planning documents.

## Phase 4 — Implementation workflow

Initialize sprint planning:

- Invoke `bmad-agent-dev` and run `bmad-sprint-planning`.
- Output: `sprint-status.yaml`.

Build cycle for each story, with fresh chats:

1. DEV / `bmad-create-story` — create story file from epic.
2. DEV / `bmad-dev-story` — implement the story.
3. DEV / `bmad-code-review` — quality validation; recommended.

After completing all stories in an epic:

- Invoke `bmad-agent-dev` and run `bmad-retrospective`.
