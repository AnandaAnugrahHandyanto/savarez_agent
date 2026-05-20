---
name: methodology-router
description: "Use when choosing the right software-development workflow depth for Hermes: quick edit, bugfix, spec-driven feature, product/SDLC work, or memory/brain changes. Routes to the proper skills and gates."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [methodology, workflow, routing, software-development, skills]
    related_skills: [spec-driven-development, writing-plans, subagent-driven-development, test-driven-development, systematic-debugging, requesting-code-review]
---

# Methodology Router

## Overview

Use this skill to select the minimum effective development methodology before changing code or project state. The goal is not ceremony. The goal is leverage: choose the workflow that prevents avoidable mistakes while staying proportional to task size.

Hermes already has strong primitives — tools, skills, memory, session search, delegation, kanban, cron, and MCP. This router turns those primitives into a consistent development operating system.

## When to Use

Use when:
- The user asks for implementation, architecture, refactoring, debugging, or repository changes.
- The task may need planning, testing, review, subagents, or durable memory.
- You are unsure whether to use quick execution, TDD, spec-driven development, or SDLC/product planning.

Don't use for:
- Pure factual Q&A.
- One-line edits with obvious verification.
- Tasks where the user explicitly asks for no process and the risk is low.

## Workflow Tiers

### Tier 0 — Direct Answer

Use for questions and tiny non-code clarifications.

Signals:
- No repo/file changes.
- No external side effects.
- Answer can be grounded in existing context or one lookup.

Action:
- Answer directly.
- Use tools if the answer depends on current facts, files, git, system state, or arithmetic.

### Tier 1 — Quick Edit

Use for very small, low-risk repo changes.

Signals:
- One or two files.
- No new architecture.
- Existing test coverage is obvious.

Action:
1. Inspect target files.
2. Make minimal patch.
3. Run targeted test/lint if available.
4. Summarize changed paths and verification.

Gate: targeted verification passes.

### Tier 2 — TDD Bugfix or Behavior Change

Use for bugs, regressions, and behavior changes.

Signals:
- Something is broken.
- The correct behavior can be expressed in a test.
- Existing code has unclear failure mode.

Action:
1. Load `systematic-debugging` for root cause work.
2. Load `test-driven-development`.
3. Write/identify a failing regression test first.
4. Fix minimally.
5. Run targeted + relevant broader tests.

Gate: failing test fails for the expected reason before the fix, then passes after.

### Tier 3 — Spec-Driven Feature

Use for medium/large features or anything that affects multiple components.

Signals:
- Multiple files/modules.
- New user-visible behavior.
- Needs acceptance criteria.
- Ambiguity would materially change implementation.

Action:
1. Load `spec-driven-development`.
2. Create/update `.hermes/specs/<feature>/spec.md` or repo-approved equivalent.
3. Create plan and task breakdown.
4. Execute with `subagent-driven-development` when tasks are independent or review quality matters.
5. Use TDD for behavior-producing tasks.

Gates:
- Spec gate: requirements and non-goals are explicit.
- Plan gate: implementation tasks are concrete and ordered.
- Verification gate: tests/checks prove the feature.

### Tier 4 — Product / SDLC Mode

Use for greenfield products, large brownfield initiatives, roadmap work, or cross-functional planning.

Signals:
- PRD, architecture, UX, epics, stories, milestones, or rollout is needed.
- Multiple agents/profiles would materially improve speed/quality.
- Work spans days or persistent kanban tasks.

Action:
1. Use BMAD-inspired roles selectively: analyst, PM, architect, developer, reviewer.
2. Convert strategy into artifacts: PRD, architecture, epics/stories, implementation plan.
3. Use Hermes kanban for durable multi-agent execution.
4. Keep human approval gates for destructive, security, deployment, or cost-bearing actions.

Gate: stakeholder/user approval before irreversible execution.

### Tier 5 — Brain / Memory Architecture Work

Use when changing durable memory, skills, agent behavior, MCP, or project knowledge systems.

Signals:
- Memory provider, skillpack, agent protocol, or long-running behavior is involved.
- Bad design would pollute future sessions.

Action:
1. Load `agent-brain-protocol`.
2. Separate memory classes: user facts, project facts, procedural skills, episodic events, knowledge corpus.
3. Prefer plugin/config/skill changes before core prompt changes.
4. Add validation and rollback path.

Gate: memory writes are scoped, auditable, and not stale task logs.

## Default Stack

Use this default unless the user says otherwise:

1. **AGENTS.md / CLAUDE.md / .hermes/** — project-local instructions and artifacts.
2. **Spec-driven development** — for medium/large feature lifecycle.
3. **Superpowers-style execution discipline** — TDD, systematic debugging, subagent reviews, verification.
4. **Kanban** — for durable multi-agent execution.
5. **Graph/semantic memory** — only for durable facts and relationships, not raw noisy logs.

## Escalation Rules

Escalate one tier when:
- The change touches more files than expected.
- Requirements are ambiguous.
- Tests reveal hidden coupling.
- The task has security, privacy, deployment, or cost impact.
- A subagent/reviewer finds spec gaps.

De-escalate when:
- The task is smaller than expected.
- Existing tests/docs fully constrain the change.
- User asks for speed and risk is low.

## Common Pitfalls

1. **Over-process.** Do not use full SDLC for a typo.
2. **Under-spec.** Do not code multi-file features from vibes.
3. **Skipping RED.** Bug fixes need a failing test or equivalent reproduction first.
4. **Memory pollution.** Do not save PR numbers, transient task state, or stale logs as durable memory.
5. **Core edits before extension points.** Prefer skills, MCP, plugins, config, and user-local providers before changing core prompts/runtime.

## Verification Checklist

- [ ] Chosen tier matches risk and scope.
- [ ] Required related skills were loaded.
- [ ] Tests or verification commands were run when code changed.
- [ ] Durable memory/skills only store reusable or stable facts.
- [ ] Final answer reports concrete changes and verification, not intentions.
