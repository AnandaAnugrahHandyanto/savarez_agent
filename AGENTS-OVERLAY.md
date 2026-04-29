> **This is a methodology overlay file** maintained alongside upstream Hermes' AGENTS.md.
> Upstream Hermes contributor guidance lives in [AGENTS.md](AGENTS.md).
> This file extends the agent harness with mode-switching (DISCOVERY/AUDIT/IMPLEMENT), parallel-agent rules, GitNexus mandates, operator-only boundaries, doc-routing rules, and the legal-tech-coding profile.
> Both files apply.

# AGENTS.md - Motion Granted Citation Database

Context for Codex when working in this repository. Claude Code uses
`CLAUDE.md`; Codex uses this file. Both harnesses coexist and must honor the
same authority hierarchy, operator boundaries, and Zero-Inference discipline.

## Session Mode

Declare one mode at the start of a session:

| Mode | Trigger | Behavior |
|---|---|---|
| DISCOVERY | New codebase, setup, mapping | Read, inventory, document. No production edits. |
| AUDIT | Explicit audit/review request or Chen-style investigation | Read-only findings with grep/file evidence. Await operator approval before fixes. |
| IMPLEMENT | Approved coding/setup task | Edit within declared scope, verify after changes, stop before merge/push. |

Switching from AUDIT to IMPLEMENT requires explicit operator approval such as
`proceed`, `implement`, or `go ahead`. Discovery produces a written report
before implementation unless the mission already contains an approved plan.

## Authoritative Spec

`binding/v7.2.md` is the sole ratified architectural authority for the Motion
Granted Authority Layer. Every factual claim about schema, invariants,
Cardinal Sin, STOP Gate, ordering, MCP, roles, tiers, taxonomy, migration order,
or retention must cite v7.2 by section and line. Do not answer AL factual
questions from memory; grep v7.2.

When v7.2 conflicts with archive material, reports, or summaries, v7.2 wins.
When v7.2 is silent, treat silence as a gap, not a default.

## Binding Discipline

Read `AGENT-DISCIPLINE.md` before schema, contract, scaffold, producer, or
operator-facing work.

### Zero-Inference

Never invent values, versions, counts, citations, or structures. High-risk
categories must be grep-verified before they are written:

- Treatment types: 16 UPPERCASE values, v7.2 §12 L960-L967.
- Jurisdiction scopes: range shorthand in v7.2 §7 L444-L452; producer-port is the tie-breaker for silent USPS expansion.
- Invariants: I-1 through I-10 (v7.2 §1 L135-L191) plus I-6a/I-6b/I-6c (v7.2 §6 L407-L409).
- ERRCODEs and SQLSTATE names, including `CS001`, `OV001`, and `NI001`-`NI005`.
- Migration filenames and sequence 001-015.
- v7.2 line citations.
- Access-control roles: 12 per v7.2 §13 L1015-L1028, including `platform_admin`. If `CLAUDE.md` says 11, treat that as stale.
- Event classes: 11 per v7.2 §14 L1071-L1075.
- Severity ranks: 1=POSITIVE, 2=NEUTRAL, 3=CAUTION, 4=STOP per v7.2 §12 L969-L971.
- §16 test IDs, CHECK values, and primary-key compositions.

Named failure mode: count-gap inference. Seeing a count delta and filling the
gap with generated content is forbidden. Specific enumerations beat summary
counts.

### Operator-Only Boundaries

Codex agents do not perform these actions:

- `gh pr merge`
- `git push origin main`
- `git push --force origin main`
- direct commits to `main`
- applying Clay-binding rulings per §24 without a signed/operator-provided ruling
- executing staging DB DDL or DML
- applying migrations with `psql`, `supabase db push`, `supabase migration up`, or equivalent
- editing `binding/v7.2.md`, `AGENT-DISCIPLINE.md`, `CLAUDE.md`, or `archive/rulings/*`
- destructive deletion of protected paths such as `rm -rf binding/`

Route operator-only work to logs, checklists, or backlog items for Porter.

### Triple Safety Net

1. Read before replace on every edit.
2. Grep-verify A-L categories before any write that references them.
3. Review output against v7.2 before calling work complete.

Self-audit alone is insufficient.

## Workflow

Default session pattern:

1. Porter provides mission.
2. Codex reads relevant sources.
3. Codex states mode and plan when the work is nontrivial.
4. Porter approves any plan gate.
5. Codex executes within scope.
6. Porter reviews before merge.

Branch check first: run `git branch --show-current` before any edit. Do not
push production branches without explicit operator instruction.

When running beside another Codex or Claude Code session, isolate with a
worktree such as:

```bash
git worktree add ../Case-Database-<session-name>
```

Keep two to three parallel sessions maximum across all harnesses combined.

Commit format when the operator asks Codex to prepare a commit:

```text
<scope>(<area>): <summary> per <authority>

Co-Authored-By: Codex <noreply@openai.com>
```

Every fix cites a severity label and authority. Codex may stage or commit only
when explicitly authorized for that action.

## Current Readiness State

As of Phase 2 verification on 2026-04-23, operator-provided state is:
Clay/operator handling has unblocked the §24 decision items R-1/R-3/N-2, but
Tier A is not yet reached. v7.2 §18 L1296 defines Tier A as reached when the
six §24 blockers are resolved and migrations 001-012 apply cleanly with correct
constraints and triggers; staging apply, S-5 audit/tag, operator review, and
empirical prerequisites remain pending. Do not describe the system as live,
customer-facing, Tier A reached, or Tier B/C/D.

Tier definitions:

- Tier A: schema scaffold safe to apply after the v7.2 §24 gate set resolves (v7.2 §18 L1296, §29 L2159-L2161).
- Tier B: migrations 013-015 and full promote/recompute/merge implementation (v7.2 §18 L1297).
- Tier C: staging and dual-state validation (v7.2 §18 L1298).
- Tier D: Phase 1D cutover authorized after the §28 criteria hold and Porter/Clay sign off (v7.2 §18 L1299).

## Key Architectural Reminders

### Interpretation A

The Authority Layer owns the schema under Interpretation A (v7.2 §3 L271).
Porter's Data Engine is the derivation producer; the approved AL-side writer
persists `al_treatment_derivation` and `al_stop_gate_result` rows under the
`derivation_writer` role (v7.2 §13 L1020). Producer code itself must not write
`al.` tables. AL promotion owns the sink.
Double namespace is intentional: `al.al_authority`, `al.al_citation_edge`.

### Identity Tuple

The treatment identity tuple is:

```text
(cited_authority_id, citing_authority_id, jurisdiction_scope)
```

Jurisdiction is a first-class primary-key component per I-5 and ADR-0004
(v7.2 §1 L173, §7 L442). Every tuple-scoped MCP/API query must supply
jurisdiction or fail with `400 missing_jurisdiction` (v7.2 §7 L475, §15 L1185).

### Cardinal Sin

A row is refused from `al_effective_treatment` when all three are true:

```text
verification_status = 'VERIFIED'
confidence >= 0.99
source_derivation.produced_by_error_path = TRUE
```

This is the v7.2 precise mapping (v7.2 §12 L883-L901). The single enforcement
point is `al.al_enforce_cardinal_sin`, invoked by
`al_enforce_cardinal_sin_trigger` (v7.2 §12 L901). FK-integrity failure fails
closed with `cardinal_sin_source_missing` (v7.2 §12 L899).

### Ordering Function

The deterministic priority tuple is v7.2 §6 L381-L389:

```text
priority(candidate) = (
  override_present DESC,
  pipeline_run.blessed DESC,
  stop_gate_passed DESC,
  severity_rank DESC,
  confidence DESC,
  pipeline_version DESC,
  derivation_version DESC,
  derivation_content_hash ASC
)
```

No wall-clock field may be an authoritative ordering dimension. `created_at` is
allowed in scan-performance indexes and certain CHECK constraints, but not in
promotion ordering logic.

## Codex Runtime Notes

Verified for this environment:

- Context file: Codex uses `AGENTS.md`. It also supports
  `AGENTS.override.md` and project fallback names if configured.
- Discovery order: global Codex home first, then project root down to current
  directory; closer files appear later and override earlier guidance.
- Subagents: Codex supports custom project agents in `.codex/agents/*.toml`,
  but only spawn subagents when the operator explicitly asks for delegation or
  parallel agent work.
- Built-in agents available in this runtime: `default`, `worker`, `explorer`.
- Current local config marks this repo trusted and uses Windows sandbox
  `elevated`.
- Current session sandbox: workspace-write, network restricted, writable roots
  limited to this repo, approval review set to auto-review.
- Network access for shell commands is not assumed. Use web search only when the
  user asks or the information is time-sensitive/current.
- `.git` and `.codex` are protected paths in default workspace-write semantics;
  git index writes generally require approval/escalation.

Project Codex config lives in `.codex/config.toml`. Command policy hints live in
`.codex/rules/motion-granted.rules`. These are guardrails; AGENTS.md remains the
behavioral contract when a rule language cannot express a distinction such as
read-only SQL versus DDL/DML.

## GitNexus

GitNexus rules apply when GitNexus is connected. If connected, before editing a
code symbol run upstream impact analysis, before renaming use GitNexus rename
preview, and before committing run staged change detection. If GitNexus is not
available, state that structural checks were unavailable and run grep-only
evidence checks.

This setup session verified that GitNexus was not connected through the visible
Codex tool set, and `npx` was not available on PATH.

## Personas

Codex project-scoped custom agents are translated under `.codex/agents/`:

- `architect`: read-only planning, decomposition, worktree/session discipline.
- `chen`: read-only adversarial audit, including spec-to-code delta mode.
- `grep_verifier`: read-only textual/pattern verification.

The Claude `code-reviewer` role is intentionally not translated yet because its
scope overlaps Chen and needs operator clarification.

Subagents are read-only investigators unless Porter explicitly authorizes a
different pattern. The main thread synthesizes findings and owns edits.

## Repo Layout

- `binding/v7.2.md`: authoritative spec.
- `AGENT-DISCIPLINE.md`: binding discipline doctrine.
- `CLAUDE.md`: Claude Code peer context; useful but not superior to v7.2 or `AGENT-DISCIPLINE.md`.
- `.claude/agents/`: Claude agent source material translated for Codex where appropriate.
- `.claude/rules/`: subsystem boundaries for producer, scaffold, and reports.
- `docs/operator/`: operator-facing reference, Chen-verified but not a replacement for v7.2.
- `drafts/scaffold/`: SQL migration drafts; never auto-apply.
- `producer/`: V1 to v7.2 derivation producer boundary.
- `BACKLOG.md`: outstanding operator, Clay, counsel, and Tier B+ work.
- `archive/`: historical material; read-only, never authoritative over v7.2.
