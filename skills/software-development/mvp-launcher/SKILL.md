---
name: mvp-launcher
description: Use when orchestrating an end-to-end MVP website launch from PRD to scaffold, build loop, private preview, gated domain/DNS setup, and production promotion.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [mvp, launch, website, prd, deployment, domain]
    related_skills: [mvp-build-loop, domain-launch-operations, preview-deployment, self-hosted-service-operations]
---

# MVP Launcher

## Overview

MVP Launcher is an umbrella workflow that composes three focused skills:

- `mvp-build-loop` — PRD parsing, project scaffold, implementation, deterministic audits, and tests.
- `preview-deployment` — private preview deployment and smoke/browser checks.
- `domain-launch-operations` — domain research, registration, Cloudflare DNS/SSL, and production cutover safety gates.

Use this skill for orchestration and decision sequencing. Load the focused skill before performing each phase.

## When to Use

- The user wants to go from product idea/PRD/research document to a deployed MVP website.
- The launch includes domain selection/registration and production DNS.
- You need a repeatable PRD → build → preview → production workflow.

Do not use this for a simple static mockup, a one-off code edit, or unattended bulk domain purchasing.

## Phase Model

1. **Plan / PRD intake**
   - Read the PRD/research document.
   - Extract scope, target audience, must-have features, data requirements, and deployment constraints.
   - Define a minimal launchable vertical slice.

2. **Domain research** — load `domain-launch-operations`
   - Generate and check candidate domains.
   - Report availability/prices.
   - Stop before purchase unless the user explicitly approves exact domain and charge.

3. **Build loop** — load `mvp-build-loop`
   - Create workspace.
   - Generate design brief.
   - Build app with a configurable agent backend.
   - Run deterministic audits and tests.

4. **Preview deployment** — load `preview-deployment`
   - Deploy to configured private preview backend.
   - Run smoke checks and browser validation.
   - Fix issues before production.

5. **Production promotion**
   - Confirm production target and domain.
   - Configure DNS/Cloudflare/Ingress.
   - Deploy only after explicit user approval.
   - Verify HTTPS and public route.

6. **Launch report**
   - Summarize URLs, commit/build ID, domain/DNS state, test results, open risks, and rollback notes.

## Safety Rules

Never perform these without explicit approval:

- domain registration or paid purchase
- nameserver changes
- domain deletion/cancellation/autorenew changes
- public DNS cutover
- production deployment
- exposing a private preview publicly

Approval should include exact target values, not vague consent.

## Reworked Repo Notes

The original standalone `batumilove/mvp-launcher` repo was a flat OpenClaw/Clawd-style skill. Its scripts and references are preserved under this skill as support material, but reusable Hermes guidance is split into focused skills. Treat the copied scripts as adaptation helpers, not authoritative Hermes runtime APIs, until they are hardened for `$HERMES_HOME`, configurable preview targets, and backend-agnostic agent execution.

Known original assumptions to avoid reintroducing:

- hardcoded `/home/exedev` or `~/clawd` paths
- sibling `claude-code/scripts/run.py` dependency
- hardcoded preview host/domain
- docs claiming browser E2E when only HTTP checks ran
- references to missing `final-audit.py`

## Verification Checklist

- [ ] Loaded focused skill for the active phase.
- [ ] Used dry-run/discovery before side effects.
- [ ] User approved every billing/DNS/prod action explicitly.
- [ ] Preview passed smoke/browser checks before production.
- [ ] Final launch report includes verified URLs and open risks.
