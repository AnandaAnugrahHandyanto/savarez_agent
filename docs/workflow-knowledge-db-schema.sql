-- Workflow Knowledge DB schema draft
--
-- Status: docs-only proposal. Do not run this file as a migration.
-- The executable migration version should be created later under supabase/migrations/
-- after architecture, access model, and RLS policy review.

-- Optional future extensions:
-- create extension if not exists pgcrypto;
-- create extension if not exists pg_trgm;
-- create extension if not exists vector;

create type workflow_review_status as enum (
  'draft',
  'pending',
  'approved',
  'rejected',
  'needs_redaction',
  'needs_more_evidence',
  'superseded',
  'deprecated',
  'archived'
);

create type workflow_knowledge_type as enum (
  'principle',
  'workflow_rule',
  'project_context',
  'decision',
  'failure_lesson',
  'human_correction',
  'review_lesson',
  'handoff_note',
  'risk_rule',
  'eval_case'
);

create type workflow_sensitivity as enum (
  'public_internal',
  'internal',
  'restricted',
  'confidential_redacted'
);

create type workflow_source_type as enum (
  'work_log',
  'meeting_note',
  'review_comment',
  'pull_request',
  'incident_note',
  'handoff',
  'manual_note',
  'other'
);

create table workflow_sources (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null,
  project text not null default 'global',
  source_type workflow_source_type not null,
  source_ref text,
  title text not null,
  summary text not null,
  redaction_status workflow_review_status not null default 'pending',
  sensitivity workflow_sensitivity not null default 'internal',
  source_created_at timestamptz,
  captured_by text,
  captured_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb,
  search_text tsvector generated always as (
    to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(summary, ''))
  ) stored
);

create table workflow_knowledge (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null,
  project text not null default 'global',
  knowledge_type workflow_knowledge_type not null,
  title text not null,
  body text not null,
  tags text[] not null default '{}',
  source_ids uuid[] not null default '{}',
  sensitivity workflow_sensitivity not null default 'internal',
  review_status workflow_review_status not null default 'approved',
  owner text,
  approved_by text not null,
  approved_at timestamptz not null default now(),
  supersedes_id uuid references workflow_knowledge(id),
  created_by text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb,
  search_text tsvector generated always as (
    to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(body, '') || ' ' || array_to_string(tags, ' '))
  ) stored,
  constraint workflow_knowledge_only_approved check (review_status in ('approved', 'deprecated', 'archived', 'superseded'))
);

create table workflow_improvement_candidates (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null,
  project text not null default 'global',
  source_id uuid references workflow_sources(id),
  candidate_type workflow_knowledge_type not null,
  title text not null,
  proposed_body text not null,
  evidence_summary text not null,
  tags text[] not null default '{}',
  sensitivity workflow_sensitivity not null default 'internal',
  review_status workflow_review_status not null default 'pending',
  reviewer_notes text,
  rejection_reason text,
  approved_knowledge_id uuid references workflow_knowledge(id),
  created_by text not null,
  created_at timestamptz not null default now(),
  reviewed_by text,
  reviewed_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  search_text tsvector generated always as (
    to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(proposed_body, '') || ' ' || coalesce(evidence_summary, '') || ' ' || array_to_string(tags, ' '))
  ) stored
);

create table workflow_skills (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null,
  name text not null,
  version text not null,
  status workflow_review_status not null default 'approved',
  purpose text not null,
  applies_to text[] not null default '{}',
  inputs jsonb not null default '{}'::jsonb,
  procedure jsonb not null default '[]'::jsonb,
  constraints text[] not null default '{}',
  output_contract jsonb not null default '{}'::jsonb,
  checklist jsonb not null default '[]'::jsonb,
  failure_handling jsonb not null default '{}'::jsonb,
  related_knowledge_tags text[] not null default '{}',
  owner text,
  approved_by text not null,
  approved_at timestamptz not null default now(),
  supersedes_id uuid references workflow_skills(id),
  created_by text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb,
  unique (org_id, name, version),
  constraint workflow_skills_only_approved check (status in ('approved', 'deprecated', 'archived', 'superseded'))
);

create table workflow_skill_candidates (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null,
  proposed_name text not null,
  proposed_version text not null default '0.1.0',
  purpose text not null,
  applies_to text[] not null default '{}',
  proposed_inputs jsonb not null default '{}'::jsonb,
  proposed_procedure jsonb not null default '[]'::jsonb,
  proposed_constraints text[] not null default '{}',
  proposed_output_contract jsonb not null default '{}'::jsonb,
  proposed_checklist jsonb not null default '[]'::jsonb,
  proposed_failure_handling jsonb not null default '{}'::jsonb,
  related_knowledge_tags text[] not null default '{}',
  evidence_summary text not null,
  review_status workflow_review_status not null default 'pending',
  reviewer_notes text,
  rejection_reason text,
  approved_skill_id uuid references workflow_skills(id),
  created_by text not null,
  created_at timestamptz not null default now(),
  reviewed_by text,
  reviewed_at timestamptz,
  metadata jsonb not null default '{}'::jsonb
);

create table workflow_resolver_rules (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null,
  rule_name text not null,
  status workflow_review_status not null default 'approved',
  priority integer not null default 100,
  match jsonb not null,
  return_config jsonb not null,
  owner text,
  approved_by text not null,
  approved_at timestamptz not null default now(),
  supersedes_id uuid references workflow_resolver_rules(id),
  created_by text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb,
  unique (org_id, rule_name),
  constraint workflow_resolver_rules_only_approved check (status in ('approved', 'deprecated', 'archived', 'superseded')),
  constraint workflow_resolver_rules_object_shape check (jsonb_typeof(match) = 'object' and jsonb_typeof(return_config) = 'object')
);

create table workflow_artifacts (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null,
  project text not null default 'global',
  artifact_type text not null,
  title text not null,
  body text,
  storage_ref text,
  related_knowledge_ids uuid[] not null default '{}',
  related_skill_ids uuid[] not null default '{}',
  related_resolver_rule_ids uuid[] not null default '{}',
  sensitivity workflow_sensitivity not null default 'internal',
  review_status workflow_review_status not null default 'pending',
  created_by text not null,
  created_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb
);

create table workflow_access_audit (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null,
  actor_id text,
  actor_role text not null,
  action text not null,
  table_name text not null,
  record_id uuid,
  request_id text,
  outcome text not null,
  reason text,
  created_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb
);

create index workflow_sources_org_project_idx on workflow_sources (org_id, project, source_type);
create index workflow_sources_search_idx on workflow_sources using gin (search_text);

create index workflow_knowledge_org_project_type_idx on workflow_knowledge (org_id, project, knowledge_type, review_status);
create index workflow_knowledge_tags_idx on workflow_knowledge using gin (tags);
create index workflow_knowledge_search_idx on workflow_knowledge using gin (search_text);

create index workflow_improvement_candidates_review_idx on workflow_improvement_candidates (org_id, review_status, candidate_type);
create index workflow_improvement_candidates_tags_idx on workflow_improvement_candidates using gin (tags);
create index workflow_improvement_candidates_search_idx on workflow_improvement_candidates using gin (search_text);

create index workflow_skills_org_name_idx on workflow_skills (org_id, name, status);
create index workflow_skills_applies_to_idx on workflow_skills using gin (applies_to);
create index workflow_skills_related_tags_idx on workflow_skills using gin (related_knowledge_tags);

create index workflow_skill_candidates_review_idx on workflow_skill_candidates (org_id, review_status, proposed_name);
create index workflow_skill_candidates_applies_to_idx on workflow_skill_candidates using gin (applies_to);

create index workflow_resolver_rules_org_status_priority_idx on workflow_resolver_rules (org_id, status, priority);
create index workflow_resolver_rules_match_idx on workflow_resolver_rules using gin (match jsonb_path_ops);

create index workflow_artifacts_org_project_idx on workflow_artifacts (org_id, project, artifact_type, review_status);
create index workflow_access_audit_org_created_idx on workflow_access_audit (org_id, created_at desc);

-- RLS must be enabled by the migration version. See docs/workflow-knowledge-db-rls-policy.md.
