# Workflow Knowledge DB Access Model

## Status

This is a docs-only access model. It defines intended roles and boundaries before migrations, APIs, or UI are implemented.

## Actors

### Internal member

A normal employee or collaborator using approved workflow context.

Allowed:

- read approved Knowledge,
- read approved Skills,
- request Resolver recommendations,
- create improvement candidates,
- create Skill candidates when they discover a reusable procedure gap.

Not allowed:

- approve candidates,
- mutate approved Knowledge or Skills,
- mutate Resolver rules,
- access backend-only elevated keys,
- store credential material.

### AI assistant / work support tool

A tool that helps with research, review, development, operations, or summarization.

Allowed:

- read approved Knowledge,
- read approved Skills,
- request Resolver recommendations,
- create improvement candidates,
- create Skill candidates.

Not allowed:

- update approved Knowledge,
- update approved Skills,
- update Resolver rules,
- approve or reject candidates,
- write production data outside candidate tables,
- execute automatically based on Resolver output,
- access backend-only elevated keys.

### Improvement extraction tool

A narrow tool that processes redacted logs or review notes to propose reusable lessons.

Allowed:

- read approved context needed for deduplication,
- create improvement candidates,
- create Skill candidates,
- write audit rows through the approved API boundary.

Not allowed:

- promote candidates,
- modify approved records,
- store raw transcripts by default,
- store credential material.

### Reviewer

A human reviewer responsible for candidate triage.

Allowed:

- read approved Knowledge, Skills, Resolver rules, and candidates,
- approve candidates through the approval workflow,
- reject candidates with reason,
- request more evidence or redaction,
- create audit-visible review notes.

Not allowed:

- bypass audit logging,
- expose backend-only elevated keys,
- approve records without sufficient evidence or redaction.

### Admin

A human administrator or system owner.

Allowed:

- manage access policies,
- manage approved Knowledge and Skill records,
- manage Resolver rules,
- read audit logs,
- manage export mirrors,
- run maintenance workflows.

Required:

- use audited APIs for normal operations,
- keep backend-only elevated access out of client and AI-assisted tool contexts,
- preserve candidate/approved separation.

### Backend-only service role

Server-side capability used by Edge Functions or controlled backend jobs.

Allowed:

- perform transactional promotions,
- write audit rows,
- generate approved export mirrors,
- run maintenance tasks.

Not allowed:

- be exposed to browser clients,
- be exposed to AI assistants,
- be pasted into chat,
- be used from local ad hoc scripts without approval and audit.

## Permission model

### Knowledge

- Internal member: read approved.
- AI assistant: read approved.
- Improvement extraction tool: read approved for deduplication.
- Reviewer: read approved and review candidate promotions.
- Admin: full management.
- Backend-only service: backend transaction support only.

### Skill

- Internal member: read approved.
- AI assistant: read approved.
- Improvement extraction tool: read approved and create candidates.
- Reviewer: read approved and review Skill candidates.
- Admin: full management.
- Backend-only service: backend transaction support only.

### Resolver

- Internal member: request recommendations.
- AI assistant: request recommendations.
- Improvement extraction tool: request recommendations for routing.
- Reviewer: inspect recommendations and rule effects.
- Admin: manage rules.
- Backend-only service: backend transaction support only.

### Candidate tables

- Internal member: create candidates and read own candidates.
- AI assistant: create candidates and read own candidates.
- Improvement extraction tool: create candidates.
- Reviewer: approve, reject, or request changes.
- Admin: full management.
- Backend-only service: transactional promotion support.

### Audit

- Normal actors: append via API only.
- Reviewer: read relevant review audit as needed.
- Admin: read organization audit logs.
- Backend-only service: append transactional audit rows.

## Approval requirements

A candidate can become approved Knowledge only when:

- the content is reusable,
- evidence is sufficient,
- sensitivity is acceptable,
- redaction is complete,
- duplicate approved Knowledge has been checked,
- a human reviewer approves it.

A Skill candidate can become an approved Skill only when:

- the procedure is reusable,
- the scope is clear,
- inputs and outputs are explicit,
- constraints and failure handling are defined,
- a human reviewer approves it,
- versioning is assigned.

A Resolver rule can become approved only when:

- match conditions are specific enough,
- returned Skills and Knowledge are appropriate,
- high-risk approval requirements are represented,
- recommendation-only behavior is preserved,
- a human reviewer or admin approves it.

## Candidate rejection reasons

Rejected candidates should preserve a reason. Common reasons:

- information is vague,
- evidence is insufficient,
- one-off lesson with low reuse value,
- sensitive material requires redaction,
- duplicates existing Knowledge,
- proposed rule is too strong,
- proposed Skill is too heavy,
- Resolver condition is ambiguous.

## Safety boundaries

- Approved state is read-only for AI-assisted tools.
- Candidate generation is allowed; promotion is not automatic.
- Resolver output is recommendation-only at first.
- High-risk tasks should include human approval requirements.
- Raw transcript storage is out of scope by default.
- Credential material is never stored.
- All writes are audit-visible.

## GitHub and Notion mirrors

GitHub and Notion are optional mirrors, not the primary authority.

- GitHub mirror: approved artifacts exported as Markdown or JSONL for backup and review.
- Notion mirror: optional human-friendly browsing layer.
- Supabase remains the primary source of truth unless a later design explicitly changes that.