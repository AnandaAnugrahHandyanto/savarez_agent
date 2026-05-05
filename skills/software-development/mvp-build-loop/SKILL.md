---
name: mvp-build-loop
description: Use when turning a PRD or product brief into an MVP codebase through scaffold, implementation, deterministic audits, tests, and iterative fixes.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [mvp, software-development, audit, testing, prd]
    related_skills: [subagent-driven-development, test-driven-development, requesting-code-review]
---

# MVP Build Loop

## Overview

This skill covers the build phase after a product brief exists: parse requirements, create a project workspace, scaffold the app, implement a thin vertical slice, run deterministic audits, fix issues, and repeat until the MVP is shippable enough for preview deployment.

The loop should be model/tool agnostic. Hermes can use `delegate_task`, `hermes chat -q`, Claude Code, Codex, OpenCode, or manual coding depending on the environment. Do not hardcode a sibling OpenClaw/Clawd skill path.

## When to Use

- The user provides a PRD/research note and wants an MVP codebase.
- A launch workflow needs implementation before preview/prod deployment.
- You need a repeatable audit/fix loop for generated website/application code.

Do not use for one-line fixes in an existing app; use normal TDD/debugging skills.

## Recommended Loop

1. **Input analysis**: Extract project name, features, target users, content/data requirements, tech constraints, and deployment constraints.
2. **Workspace setup**: Create a dedicated project directory with `prd.md`, `project.json`, `src/`, `design/`, `audits/`, and `deploy/`.
3. **Design brief**: Generate brand traits, color palette, typography, page inventory, and content rules.
4. **Implementation**: Build the smallest complete vertical slice first.
5. **Deterministic audit**: Scan for TODOs/placeholders, fake data, secrets, unsafe patterns, broken structure, missing tests, and deploy gaps.
6. **Fix pass**: Prioritize critical/security/data-quality findings before polish.
7. **Verification**: Run unit/build/lint/smoke tests and write an audit report.
8. Repeat within a bounded iteration count.

## Hermes Agent Backend Guidance

Inside a Hermes session, prefer `delegate_task` for isolated implementation/review work:

- builder subagent: scaffold/implement feature slice
- reviewer subagent: inspect code and audit findings
- tester subagent: run/build/debug tests when appropriate

For long autonomous tasks outside the current session, use a separate Hermes process:

```bash
hermes -w chat -q "Build the MVP described in prd.md. Work in this directory. Run tests and summarize changed files."
```

If using Claude Code/Codex/OpenCode, load the corresponding skill and keep the backend configurable.

## Data Quality Rule

If the app displays directories, listings, locations, businesses, people, prices, events, or other real-world data:

- Do not use lorem ipsum, John/Jane Doe, fake emails, placeholder phone numbers, Example Company, or placeholder images.
- Use real researched data with source notes when allowed.
- If real data cannot be collected, explicitly label the app as using sample data and block production launch until replaced.

## Verification Checklist

- [ ] Project workspace contains PRD and metadata.
- [ ] Generated app builds locally.
- [ ] Audits are saved under `audits/` with date/iteration.
- [ ] Critical/security findings are zero or explicitly accepted by the user.
- [ ] Placeholder/fake data scan passes before preview/prod launch.
- [ ] Tests/build commands and results are recorded.
