# Workflow Knowledge DB RLS Policy Draft

## Status

This is a docs-only RLS design. It does not apply policies to any Supabase project.
Executable policies should be created later in `supabase/migrations/create_workflow_rls.sql` after review.

## Goals

Row-level security must enforce these invariants:

- Members and AI-assisted tools can read approved Knowledge, approved Skills, and approved Resolver recommendations for their organization.
- Automated tools can create candidates but cannot approve candidates or mutate approved records.
- Reviewers can approve or reject candidates for their organization.
- Admins can manage approved records, Resolver rules, and candidate lifecycle for their organization.
- Backend-only elevated access is reserved for server code and never exposed to AI-assisted tools or client applications.
- All write operations have audit coverage.

## Assumed JWT claims

The executable implementation should standardize these claims or equivalent server-side role mapping:

- `org_id`: organization identifier.
- `workflow_role`: one of `member`, `assistant`, `improvement_tool`, `reviewer`, `admin`.
- `actor_id`: stable user or tool identifier.

Example helper functions for the migration version:

```sql
create function workflow_current_org_id()
returns uuid
language sql stable as $$
  select nullif(auth.jwt() ->> 'org_id', '')::uuid;
$$;

create function workflow_current_role()
returns text
language sql stable as $$
  select coalesce(auth.jwt() ->> 'workflow_role', 'member');
$$;

create function workflow_current_actor_id()
returns text
language sql stable as $$
  select coalesce(auth.jwt() ->> 'actor_id', auth.uid()::text);
$$;
```

## Enable RLS on every table

The migration version should enable RLS for all workflow tables:

```sql
alter table workflow_sources enable row level security;
alter table workflow_knowledge enable row level security;
alter table workflow_improvement_candidates enable row level security;
alter table workflow_skills enable row level security;
alter table workflow_skill_candidates enable row level security;
alter table workflow_resolver_rules enable row level security;
alter table workflow_artifacts enable row level security;
alter table workflow_access_audit enable row level security;
```

## Read policies

### Approved Knowledge read

Members, AI-assisted tools, improvement tools, reviewers, and admins can read approved Knowledge for their organization.

```sql
create policy workflow_knowledge_read_approved
on workflow_knowledge
for select
using (
  org_id = workflow_current_org_id()
  and review_status in ('approved', 'deprecated', 'archived', 'superseded')
  and workflow_current_role() in ('member', 'assistant', 'improvement_tool', 'reviewer', 'admin')
);
```

### Approved Skill read

```sql
create policy workflow_skills_read_approved
on workflow_skills
for select
using (
  org_id = workflow_current_org_id()
  and status in ('approved', 'deprecated', 'archived', 'superseded')
  and workflow_current_role() in ('member', 'assistant', 'improvement_tool', 'reviewer', 'admin')
);
```

### Approved Resolver rule read

Resolver rules are read as recommendations. They do not authorize execution.

```sql
create policy workflow_resolver_rules_read_approved
on workflow_resolver_rules
for select
using (
  org_id = workflow_current_org_id()
  and status = 'approved'
  and workflow_current_role() in ('member', 'assistant', 'improvement_tool', 'reviewer', 'admin')
);
```

### Candidate read

Reviewers and admins can read all candidates. Candidate creators can read their own candidate records. Normal members and AI-assisted tools should not browse every candidate by default.

```sql
create policy workflow_improvement_candidates_read_review_scope
on workflow_improvement_candidates
for select
using (
  org_id = workflow_current_org_id()
  and (
    workflow_current_role() in ('reviewer', 'admin')
    or created_by = workflow_current_actor_id()
  )
);
```

Apply the same pattern to `workflow_skill_candidates`.

## Candidate creation policies

Automated tools and members can create candidates only. They cannot insert approved records.

```sql
create policy workflow_improvement_candidates_insert
on workflow_improvement_candidates
for insert
with check (
  org_id = workflow_current_org_id()
  and workflow_current_role() in ('member', 'assistant', 'improvement_tool', 'reviewer', 'admin')
  and review_status in ('pending', 'needs_redaction', 'needs_more_evidence')
  and created_by = workflow_current_actor_id()
);
```

```sql
create policy workflow_skill_candidates_insert
on workflow_skill_candidates
for insert
with check (
  org_id = workflow_current_org_id()
  and workflow_current_role() in ('member', 'assistant', 'improvement_tool', 'reviewer', 'admin')
  and review_status in ('pending', 'needs_redaction', 'needs_more_evidence')
  and created_by = workflow_current_actor_id()
);
```

## Candidate review policies

Reviewers and admins can move candidates through review states. Promotion to approved Knowledge or Skill should happen inside a transaction or Edge Function that also writes audit rows.

```sql
create policy workflow_improvement_candidates_review_update
on workflow_improvement_candidates
for update
using (
  org_id = workflow_current_org_id()
  and workflow_current_role() in ('reviewer', 'admin')
)
with check (
  org_id = workflow_current_org_id()
  and workflow_current_role() in ('reviewer', 'admin')
  and review_status in ('approved', 'rejected', 'needs_redaction', 'needs_more_evidence', 'superseded')
);
```

Apply the same pattern to `workflow_skill_candidates`.

## Approved record mutation policies

Only admins should directly manage approved Knowledge, Skills, and Resolver rules. Reviewer approval APIs may promote candidates through server-side functions, but client roles should not directly insert approved rows unless explicitly designed and audited.

```sql
create policy workflow_knowledge_admin_write
on workflow_knowledge
for all
using (
  org_id = workflow_current_org_id()
  and workflow_current_role() = 'admin'
)
with check (
  org_id = workflow_current_org_id()
  and workflow_current_role() = 'admin'
);
```

Apply the same admin pattern to:

- `workflow_skills`,
- `workflow_resolver_rules`,
- `workflow_artifacts` when the artifact represents an approved mirror or export.

## Source policies

Sources should contain summarized and redacted source records, not raw transcripts by default.

- Members, assistants, and tools can insert redacted source summaries if the source is within their organization.
- Reviewers and admins can read source records for review.
- Broader source read access should be conservative and sensitivity-aware.

## Audit policies

Audit rows should be append-only from normal application roles.

```sql
create policy workflow_access_audit_insert
on workflow_access_audit
for insert
with check (
  org_id = workflow_current_org_id()
  and actor_role = workflow_current_role()
);
```

Admins can read audit rows for their organization:

```sql
create policy workflow_access_audit_admin_read
on workflow_access_audit
for select
using (
  org_id = workflow_current_org_id()
  and workflow_current_role() = 'admin'
);
```

Do not expose update or delete policies for audit rows to normal client roles.

## Edge Function boundary

Prefer Edge Functions for write workflows that need multiple changes in one transaction, such as:

- approve improvement candidate,
- reject improvement candidate,
- approve Skill candidate,
- reject Skill candidate,
- update Resolver rule after human approval,
- write audit log and approved record together.

The Edge Function should validate:

- actor organization,
- actor role,
- candidate status,
- redaction status,
- approval evidence,
- target record idempotency,
- audit row creation.

## Redaction and sensitivity rules

- `confidential_redacted` records require explicit sensitivity handling.
- Raw transcript ingestion is out of scope by default.
- Candidate extraction must strip credential material and unnecessary personal data before storage.
- If redaction is uncertain, the candidate status should be `needs_redaction`, not `approved`.

## Resolver-specific guardrails

Resolver output is recommendation-only in early phases. RLS should not be treated as an execution approval mechanism. High-risk tasks may include approval requirements in Resolver output, but a separate workflow must enforce those approvals before any external side effect.

## Open questions for implementation review

- Whether `workflow_role` comes from JWT claims, a membership table, or Edge Function middleware.
- Whether source summaries should be readable by normal members or reviewer/admin only.
- Whether candidate creators can update their own pending candidates.
- How to represent cross-project Knowledge that is global within an organization.
- Whether GitHub export mirrors should be stored as artifacts or generated on demand.