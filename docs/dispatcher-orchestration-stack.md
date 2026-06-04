# Dispatcher Orchestration Stack

This document defines the **current dispatcher-style orchestration convention** used in this checkout when documenting or operating Hermes as a role-routed control plane.

It is intentionally narrower than the public product docs:

- Hermes core primitive: `delegate_task`
- Dispatcher compatibility layer: `delegate_role_task(role, goal, context)`
- Workflow style: **GStack-inspired gates** around triage, context packing, verification, and learning capture

Use this file when auditing docs for drift. If another doc conflicts with this one for dispatcher-style workflows, update that doc or add a scope note.

## 1. Canonical Mental Model

Hermes is the execution substrate. The dispatcher is the policy layer on top of it.

- `delegate_task` = low-level isolated child-agent spawn
- `delegate_role_task(...)` = stable routing contract for specialist roles
- Kanban / cron / gateway hooks = durable orchestration surfaces
- Skills / AGENTS.md / role prompts = behavioral policy and operating doctrine

For dispatcher-facing docs, **prefer the policy layer** over raw primitive examples unless the doc is explicitly teaching core Hermes internals.

## 2. Stable Role Matrix

Recommended dispatcher roles:

- `architect`
  - decomposition
  - architecture decisions
  - acceptance criteria
  - risk mapping
  - TZ/spec matching
- `coder`
  - Python code
  - refactors
  - tracebacks
  - data-flow and bug fixes
- `infra`
  - Docker / docker-compose
  - systemd / nginx / Ubuntu services
  - deployment and runtime health
- `logic`
  - n8n JSON
  - webhook schemas
  - payload mapping
  - JS expressions in automation nodes

If a doc tells the dispatcher to improvise specialist identities ad hoc, that doc is a drift candidate.

## 3. GStack-Inspired Workflow Gates

The preferred lifecycle is:

1. **Triage**
2. **Context Packet**
3. **Specialist Execution**
4. **Verification Gate**
5. **Documentation Sync**
6. **Learning Capture**

### Required operating rules

- **Spec/autoplan for vague work**
  - Broad or ambiguous asks should be decomposed before execution.
- **Investigate before fix**
  - Error work starts from logs, repro, and root-cause hypotheses.
- **Review before done**
  - Non-trivial code/config changes should pass a review gate before being declared complete.
- **Infra requires health + rollback**
  - Infra tasks should end with:
    - `HEALTH_CHECK`
    - `ROLLBACK_NOTE`

## 4. Context Packet Standard

Subagents start with fresh context. Every dispatcher packet should include, when applicable:

- absolute paths
- exact error text / stack trace
- relevant logs
- constraints / non-goals
- acceptance criteria
- verification commands
- side-effect boundaries
- output format requirement

Bad packet:

```text
Fix the deployment.
```

Good packet:

```text
Project: /srv/myapp
Failing service: systemd unit myapp-worker.service
Observed error: ModuleNotFoundError: redis.asyncio
Recent log excerpt: ...
Constraints: do not modify nginx or postgres config
Acceptance: service reaches active(running), health endpoint returns 200
Verification: systemctl status myapp-worker --no-pager; curl -f http://127.0.0.1:8000/health
Rollback: restore previous requirements.txt and restart previous unit env
```

## 5. Documentation Hygiene Rules

When auditing docs, treat the following as likely stale or incomplete:

### A. Raw delegation without routing intent

If a dispatcher-oriented doc only says “use `delegate_task`” but omits role selection, context-packet requirements, or verification gates, it should be updated or scoped as low-level guidance.

### B. Fix-first language

Docs that imply “just patch it” for failures should be updated to require investigation first.

### C. Infra docs without closeout requirements

Infra runbooks are incomplete if they do not require both:

- post-change health verification
- rollback note

### D. OpenClaw references outside historical or migration scope

OpenClaw references are acceptable only when they are:

- migration docs
- historical release notes
- archived user quotes / compatibility notes

If an active operating doc still presents OpenClaw as the current orchestration surface, that is stale.

### E. Missing learning capture

For difficult fixes or reusable workflows, docs should point toward:

- `skill_manage` for procedural reuse
- documentation updates when conventions changed

## 6. How This Maps to Public Hermes Docs

Use these rules when choosing doc style:

- **Core product docs** may teach raw `delegate_task`.
- **Dispatcher / orchestration docs** should show role wrappers and gates.
- **Migration docs** may mention OpenClaw, but should be clearly scoped as migration-only.
- **Historical artifacts** (release notes, user quotes, archives) should usually remain untouched.

## 7. Audit Checklist

Use this checklist during cleanup:

- [ ] Does the doc describe the current role-routed orchestration model?
- [ ] Does it distinguish Hermes core primitives from dispatcher wrappers?
- [ ] Does it require context packets for delegated work?
- [ ] Does it require investigate-before-fix for debugging?
- [ ] Does it require review/verification before “done”?
- [ ] For infra: does it require health check + rollback note?
- [ ] Are OpenClaw mentions clearly historical/migration-scoped?
- [ ] Should the learned procedure be promoted into a skill?

## 8. Notes from the June 2026 Audit

Initial cleanup in this checkout:

- Added dispatcher-style orchestration guidance to `AGENTS.md`
- Added this canonical stack document so future audits have a single source of truth
- Left historical OpenClaw references in release notes, migration docs, and user-story JSON untouched because they are still contextually correct

If future docs diverge from this contract, update them here first, then cascade the wording outward.
