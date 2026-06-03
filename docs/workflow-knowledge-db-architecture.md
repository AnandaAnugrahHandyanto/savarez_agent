# 社内ワークフロー改善DB アーキテクチャ

## Status

This is a **docs-only architecture proposal** for a Supabase-backed internal workflow knowledge database.
It does not create a Supabase project, run migrations, implement Edge Functions, connect any AI assistant, store credentials, or write production data.

## Executive summary

The Workflow Knowledge DB centralizes approved business knowledge, reusable workflow skills, resolver rules, and audit evidence so internal members and AI-assisted tools can reuse context without starting from zero each time.

The goal is **not** to make an AI agent autonomously rewrite its own behavior. The goal is to improve:

- reproducibility of internal workflows,
- handoff quality,
- review quality,
- speed of repeated work,
- discoverability of prior decisions and failure lessons.

The platform manages three related layers:

1. **Knowledge**: approved project context, decisions, rules, human corrections, review lessons, failure lessons, and handoff notes.
2. **Skill**: approved procedures, checklists, review rubrics, and work templates.
3. **Resolver**: read-only selection logic that recommends relevant Knowledge and Skill for a given task.

## Problems addressed

### Scattered knowledge

Important decisions and lessons currently live across chat, meetings, PRs, individual notes, and ad hoc review comments. This makes it hard to answer:

- why a decision was made,
- where similar work previously failed,
- which review feedback mattered,
- which workflow checklist should apply,
- what to avoid next time.

### Person-dependent procedures

Review, research, release checks, meeting notes, handoffs, and redaction workflows become inconsistent when each person remembers a different procedure. Capturing procedures as approved Skills makes quality more repeatable.

### Growing retrieval burden

As Knowledge and Skills grow, manually finding the right material becomes its own cost. Resolver rules reduce that burden by selecting relevant approved material for a task context.

## Terminology

Use internal implementation terms sparingly in employee-facing documents. Prefer the employee-facing terms below.

- GBrain: 社内ワークフロー改善DB
- Dream Cycle: 業務改善ループ
- Memory: ナレッジ
- Memory candidate: 改善候補 / ナレッジ候補
- Production memory: 承認済みナレッジ
- Skill: 業務手順 / 作業テンプレート
- Resolver: 必要情報の選択・取得ロジック
- Agent: AIアシスタント / 業務補助ツール

## Core flow

```text
業務ログ / 会議メモ / レビュー指摘 / 失敗事例
  ↓
改善候補・Skill改善候補の抽出
  ↓
人間レビュー
  ↓
承認済みKnowledge / Skillへ昇格
  ↓
Resolverが作業内容に応じて必要情報を取得
  ↓
次回以降の業務で活用
```

Important invariant: automated tools may create candidates, but they must not directly update approved Knowledge, approved Skill, or Resolver rules. Promotion to approved status requires human review.

## Architecture

```text
                 ┌─────────────────────────────┐
                 │ Supabase Postgres            │
                 │ Workflow Knowledge DB        │
                 └──────────────┬──────────────┘
                                │
           ┌────────────────────┼────────────────────┐
           │                    │                    │
   ┌───────▼───────┐    ┌───────▼───────┐    ┌───────▼───────┐
   │ Knowledge      │    │ Skill Registry │    │ Resolver Rules │
   │ approved info  │    │ procedures     │    │ selection logic │
   └───────┬───────┘    └───────┬───────┘    └───────┬───────┘
           │                    │                    │
           └────────────────────┼────────────────────┘
                                │
                         ┌──────▼──────┐
                         │ Resolver     │
                         │ context load │
                         └──────┬──────┘
                                │
      ┌─────────────────────────┼─────────────────────────┐
      │                         │                         │
┌─────▼─────┐             ┌─────▼─────┐             ┌─────▼─────┐
│ 人間       │             │ AI補助     │             │ 管理者     │
│ メンバー   │             │ ツール     │             │ 承認者     │
└───────────┘             └───────────┘             └───────────┘
```

## Why Supabase

Supabase Postgres is a good primary database because it supports:

- row-level security for per-organization and per-role controls,
- SQL and full-text search,
- future pgvector-based retrieval,
- review status columns and approval workflows,
- audit tables,
- Edge Functions for API boundaries,
- GitHub and Notion mirrors as exports rather than primary state.

Recommended split:

- **Supabase**: primary database and access control source.
- **GitHub**: export, backup, and audit mirror for approved artifacts.
- **Notion**: optional human-friendly mirror after the core workflow is stable.

## Minimum database areas

The first version should contain these areas:

- `workflow_knowledge`: approved knowledge.
- `workflow_improvement_candidates`: knowledge improvement candidates.
- `workflow_skills`: approved Skills.
- `workflow_skill_candidates`: Skill improvement candidates.
- `workflow_resolver_rules`: Resolver recommendation rules.
- `workflow_sources`: redacted source summaries from logs, meetings, PRs, and reviews.
- `workflow_artifacts`: generated reports, proposals, evaluation cases, and mirrors.
- `workflow_access_audit`: access and mutation audit log.

## Knowledge scope

Approved Knowledge can include:

- principles,
- workflow rules,
- project context,
- decisions,
- failure lessons,
- human corrections,
- review lessons,
- handoff notes,
- risk rules,
- evaluation cases.

Raw transcripts should not be stored by default. Store summarized and redacted source records instead.

## Skill scope

Approved Skills are not just prompts. They should include:

- purpose,
- applicability conditions,
- required inputs,
- procedure,
- constraints,
- output contract,
- checklist,
- failure handling,
- related Knowledge tags,
- owner and approval metadata.

## Resolver scope

The Resolver is initially **recommendation only**. It should return required and optional context, not execute actions.

A Resolver result can include:

- required Skills,
- optional Skills,
- required Knowledge tags,
- relevant failure lessons,
- relevant decisions,
- required safety rules,
- output contract,
- approval requirements.

## Security and privacy invariants

- Enable RLS on all workflow tables.
- Normal users and AI-assisted tools read only approved material.
- Automated tools may create candidates only.
- Approved Knowledge, Skill, and Resolver changes require human approval.
- Backend-only elevated keys must never be exposed to assistants or clients.
- Credential material must not be stored.
- Raw transcripts are out of scope by default.
- Write operations are audited.
- Resolver rule changes are approval-gated.

## Rollout plan

### Phase 1: Docs only

Create and review these documents:

- `docs/workflow-knowledge-db-architecture.md`
- `docs/workflow-knowledge-db-schema.sql`
- `docs/workflow-knowledge-db-rls-policy.md`
- `docs/workflow-knowledge-db-access-model.md`
- `docs/workflow-skill-registry.md`
- `docs/workflow-resolver-design.md`

### Phase 2: Supabase schema draft

Create migration drafts only after the docs are reviewed.

### Phase 3: Read-only Resolver API

Implement read-only context APIs such as `POST /workflow-resolve`, `GET /workflow-context`, and `GET /workflow-search`.

### Phase 4: Candidate APIs

Allow tools to create improvement and Skill candidates without updating approved state.

### Phase 5: Human approval flow

Build UI or CLI flows to approve and reject candidates.

### Phase 6: pgvector / RAG

Add vector search only after approval, redaction, and audit boundaries are stable.

### Phase 7: GitHub export mirror

Export approved Knowledge, Skills, and Resolver rules to Markdown or JSONL for backup and review.

### Phase 8: Notion mirror

Optionally publish a human-friendly mirror.

## Initial scope

In scope first:

- development review,
- research notes,
- meeting notes,
- failure lessons,
- work handoffs,
- Skill management,
- Resolver design.

Out of scope first:

- company-wide HR data,
- confidential contracts,
- bulk raw transcript storage,
- automatic approved-Knowledge updates,
- automatic configuration changes by AI-assisted tools,
- automatic execution by Resolver output.

## Direction decision

Adopt Supabase as the primary database. Keep approved and candidate data separate. Treat AI-assisted tools as read-only for approved state and candidate-only for proposed improvements. Use the Resolver as recommendation-only at first. Keep a GitHub export mirror for backup and optional review.