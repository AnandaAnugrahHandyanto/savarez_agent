# AGENT-DISCIPLINE — Motion Granted Citation Database

**Authority:** `binding/v7.2.md`. **Owner:** Clay Tanner (architectural). **Operator:** Porter (engineering execution).

This file binds every agent session that touches this repository. Read it first; read the relevant `.claude/rules/*.md` next; cite v7.2 in every load-bearing claim.

---

## 1. Zero-Inference Discipline

### 1.1 The failure mode it prevents

**Count-gap inference.** A prior session in this repo hallucinated four `al_treatment_type` values by reasoning from a count delta — observing that v1's archive taxonomy listed 15 lowercase values and v7.2 §12 ratifies 16 UPPERCASE values, the agent invented four candidate values to "explain the +1." The correct list lives at v7.2 §12 lines 960–967, exhaustive and verbatim. The agent's invented values were not in v7.2. The error was caught only by direct cross-reference against the spec.

This failure mode is forbidden in every future session.

### 1.2 The rules

1. **Quoted or line-cited.** Every value emitted in any output file (SQL, Markdown, JSON, code) must be quoted verbatim from an authoritative source with a section + line cite. Never inferred.
2. **Counts are reporting facts.** A count delta between two sources is a reporting fact, never a license to invent content. If v1 has N values and v7.2 has N+K, the K extra values come from reading v7.2's enumeration — not from filling the gap with generated content.
3. **Names are grep-verified.** Table names, column names, ENUM type names, ERRCODEs, index names, migration numbers, section numbers — every identifier emitted in scaffold output must be confirmed against the authoritative source via grep before writing.
4. **Triple-checkpoint verification** (per session mission §3.4) governs sessions that produce schema or contract output:
   - **Checkpoint 1 — DISCOVER:** authoritative-list extraction emits direct v7.2 quotes + line-cites; any disagreements with secondary sources surface as `PRODUCER-SPEC-MISMATCH` and halt downstream phases.
   - **Checkpoint 2 — per-file write:** as each file is written, inline comments cite v7.2 line ranges per CREATE / ALTER / constraint. The author re-reads the authoritative list output before each file.
   - **Checkpoint 3 — pre-commit self-audit:** every output token is grepped against the authoritative list; unmatched tokens (not adjacent to `-- v7.2 silent`) quarantine the offending file. A second pass checks banned patterns (e.g. `created_at` in promotion ORDER BY violates I-6b; missing `cardinal_sin_source_missing` fail-closed path violates §12).
5. **"Claude's recommendation" in v7.2 is advisory, not ratified.** When v7.2 surfaces a Claude rec adjacent to a Clay-rules-required item (R-1 Option A vs B; R-3 option (a) vs (b)), draft per the rec, tag the artifact `PENDING`, emit the reverse option commented adjacent so flipping is a single-line edit. Do not pre-decide the ruling.

### 1.3 The doctrine

**Silence in v7.2 is a gap, not a default.** If a scenario isn't covered and you can't find it via grep, log `-- v7.2 silent; chose <X> per minimal-assumption default` inline AND surface it for operator review. Do not fill silence from training-data convention.

---

## 2. Authority hierarchy

When sources disagree, this hierarchy decides:

1. **`binding/v7.2.md`** — the one ratified architectural baseline. 2214 lines, §0 through §29, ADRs 0001–0007. Schema, invariants, taxonomy, roles, tiers, MCP surface, migration order, retention posture, acknowledged gaps. Wins all conflicts.
2. **Ratified producer artifacts** — committed Python contracts on `overnight/producer-port-2026-04-22` (e.g. `producer/pipeline/contracts/{treatment,jurisdiction,derivation}.py`). Used as **tie-breaker** for categories A (treatment_type), B (severity_rank), C (jurisdiction_scope), I (invariants). Disagreement with v7.2 raises `PRODUCER-SPEC-MISMATCH`.
3. **`reports/` and `worktree-session/swarm-raw/`** — informational, treat with skepticism. Re-verify before reuse. Reports may be stale the day after they were written. The cautionary tale of §1.1 came from over-trusting an early report.
4. **Pre-Clay HTMLs and `archive/`** — historical/working material. Useful for context, never authoritative. When archive disagrees with v7.2, v7.2 wins silently.

---

## 3. The A–L category table — high-hallucination-risk categories

Any token written in these categories must match an authoritative source verbatim or carry an inline `-- v7.2 silent; chose <X> per minimal-assumption default` comment.

| | Category | Authoritative source | Producer-port tie-breaker |
|---|---|---|---|
| A | `al_treatment_type` values | v7.2 §12 line 960–967 (16 UPPERCASE) | `producer/pipeline/contracts/treatment.py` |
| B | `al_severity_rank` mapping | v7.2 §12 line 970 + §6 (4 tiers) | `producer/pipeline/contracts/treatment.py` |
| C | `al_jurisdiction_scope` values | v7.2 §7 line 444–452 (range shorthand) | `producer/pipeline/contracts/jurisdiction.py` |
| D | `al_resolution_status` values | v7.2 §12 line 985 (4 lowercase) | — |
| E | `al_disposition_status` values | v7.2 §12 line 989 + §2 line 257 (6 lowercase) | — |
| F | `al_verification_status` values | v7.2 §12 (5 UPPERCASE + 7-row projection rule) | — |
| G | Access-control roles | v7.2 §13 line 1015–1028 (12 roles — including `platform_admin`) | — |
| H | Event classes | v7.2 §14 (11 classes) | — |
| I | Invariants | v7.2 §1 (I-1 through I-10, plus I-6a/I-6b/I-6c at §6) | `producer/pipeline/contracts/derivation.py` |
| J | ADRs | v7.2 §4–§10 (ADR-0001 through ADR-0007) | — |
| K | Migration order + contents | v7.2 §20 line 1408–1426 (15 migrations, 013–015 PENDING) | — |
| L | Table-name variants | v7.2 §11, §12, §24 (`al_override` is canonical; `al_authority_override` has zero matches) | Flag `DISAMBIGUATION_REQUIRED` |

**Precedence for A/B/C/I:** producer-port and v7.2 MUST agree. Disagreement → `PRODUCER-SPEC-MISMATCH`, halts implementation, escalates to operator.

---

## 4. Pending-resolution protocol

| Blocker | Owner | Draft action | Operator review |
|---|---|---|---|
| **R-1** (§24 line 1594–1623, authority-identity) | Clay ruling required | Draft Option B active; Option A commented adjacent. Tag `R-1_PENDING`. | Flip on Clay ruling. Gates Tier A. |
| **R-2** (§24 line 1580–1590, proof_section CHECK) | Porter ratify | Active per §24 verbatim (7-value list). | Confirm only. |
| **R-3** (§24 line 1627–1640, proposition text columns) | Clay ruling required | Draft option (a) active; tag `R-3_PENDING`. | Flip on Clay ruling. Gates Tier A. |
| **N-1** (§24 line 1555–1576, pg_namespace guard) | Porter | Bake `pg_namespace` join into every `CREATE TYPE` idempotency block. | Confirm pattern. |
| **N-2** (§24 line 1539–1551, two-person STOP override trigger) | Porter execute, Clay confirm | Trigger active in scaffold; tag `N-2_PENDING_CLAY_CONFIRM`. Application-layer feature flag stays OFF until T-OV-1 passes. | Confirm. |
| **S-5** (§24 priority 6, consumer-code audit) | Operator | Not scaffold work. Listed in `BACKLOG.md`. | Operator runs grep against MG CIV / Tannerize / Porter trees. |
| **§26 retention numbers** | Counsel | Not scaffold work. | Counsel ratifies before Phase 1D. |

---

## 5. Scope rules

These are session-level discipline rules, not file-level rules (which live under `.claude/rules/`).

- **Reads outside `binding/v7.2.md`, `producer/**` on producer-port branch, and existing harness files at repo root** require explicit operator authorization. Sessions don't go fishing in pre-Clay HTMLs or `archive/` content for "context."
- **Edits to `producer/**`, `reports/**`, `binding/**`, `archive/**`, `al/**`** are forbidden unless the session mission explicitly authorizes them. The producer port has its own ratification flow on `overnight/producer-port-2026-04-22`; the binding spec requires Clay sign-off; archive is by definition read-only.
- **Path scope per session** is set in the session mission. Outputs go to declared workspaces (e.g. `worktree-session/swarm-raw/`, `drafts/scaffold/`, `.claude/rules/`). Any path outside the declared workspaces triggers a scope-creep tripwire — log `SCOPE_CREEP_INFERRED`, quarantine the offending output, continue.
- **No DB apply, no `git push`, no PR creation** unless the session mission explicitly authorizes those actions. Drafts stay drafts until operator review.

---

## 6. File-header conventions

### SQL migration files

```sql
-- MIGRATION <nnn>_<name>.sql
-- PURPOSE: <verbatim §20 purpose text>
-- DRAFTED FROM: binding/v7.2.md §<sections>
-- OPERATOR MUST REVIEW BEFORE APPLY. NO DB APPLIED IN THIS SESSION.
-- DISCIPLINE: Zero-inference; every ENUM/DDL element line-cited to v7.2.
-- SCHEMA: al (Authority Layer)

BEGIN;

-- ... DDL with per-statement line-cite comments ...

-- schema_migrations footer
INSERT INTO public.schema_migrations (version, name, applied_at)
VALUES ('<nnn>', '<name>', NOW()) ON CONFLICT (version) DO NOTHING;

COMMIT;
```

### Test fixture files

```sql
-- TEST FILE <nn>_<name>.sql
-- PURPOSE: <verbatim §16 purpose text>
-- DRAFTED FROM: binding/v7.2.md §16 + Work E fixtures
-- REQUIRES: migrations 001-012 applied (plus specific gates per test)
-- OPERATOR MUST REVIEW BEFORE APPLY. NO DB APPLIED IN THIS SESSION.

BEGIN;

-- ... per-test fixture INSERTs and assertion SELECTs ...

ROLLBACK; -- tests are transactional; no committed state
```

### Markdown artifacts (reports, manifests, summaries)

Open with a title line, then a metadata block stating: session ID, branch, base SHA, date, authority cite. Any claim about schema/invariants/taxonomy carries a v7.2 §X line N cite. Any claim sourced from a swarm sub-agent cites the swarm-raw file path.

### Rule files (`.claude/rules/*.md`)

Follow the template at `.claude/rules/example-rule.md`: `# Rule:` title, `## paths` glob block, `## DO NOT` bulleted list of subsystem prohibitions, `## Architecture Notes`, `## Key Files` table, `## Authority` cite block.

---

## 7. Self-audit rule

Sessions that produce schema or contract output run a Checkpoint 3 self-audit before commit:

**Pass 1 — token audit.** For each A–L category, grep the output tree for tokens; diff against the authoritative list. Unmatched tokens (not adjacent to `-- v7.2 silent`) quarantine the file.

**Pass 2 — banned-pattern audit.** Categorical checks:

- `created_at` I-6b discipline:
  - **ALLOWED:** `created_at` inside `CREATE INDEX` / `CREATE UNIQUE INDEX` (scan-performance territory; v7.2 §12 line 880 explicitly specifies `al_derivation_tuple_scan_idx` with `created_at DESC`).
  - **ALLOWED:** `created_at` in CHECK constraints (e.g. `expiration_at <= created_at + INTERVAL '180 days'` per v7.2 §9 line 603).
  - **BANNED:** `created_at` in any `ORDER BY` inside a SELECT or function body used by promotion logic (the 8-dimension priority function in `promote_derivation_to_sink`).
  - **BANNED:** `created_at` in any materialized view or window function tied to promotion.
- Cardinal Sin trigger body raises `cardinal_sin_source_missing` on FK miss (fail-closed, not silent acceptance).
- Two-person STOP override trigger checks BOTH `second_approver_id IS NOT NULL` AND `second_approver_id != created_by_user_id` with distinct ERRCODEs.
- Every migration file ends with `INSERT INTO public.schema_migrations` footer.
- Every `CREATE TYPE` in migration 002 is wrapped in the `pg_namespace`-aware idempotency block per N-1 (v7.2 §24 line 1555–1576).

Results recorded as `SELF-AUDIT-PASS` or `SELF-AUDIT-QUARANTINE: N files` in the session log; per-file violations enumerated.

---

## 8. Authority cite

- `binding/v7.2.md` — the one ratified architectural baseline.
- `CLAUDE.md` at repo root — project-level orientation, not a discipline document.
- `AGENTS.md` — tanner-stack discipline conventions inherited via flattened harness; this AGENT-DISCIPLINE.md extends those for MG-specific failure modes.
- `.claude/rules/*.md` — per-subsystem path-scoped discipline rules.
- `BACKLOG.md` — open items for Clay rulings, operator confirmations, counsel ratification.

When this file disagrees with `binding/v7.2.md`, v7.2 wins. When this file disagrees with `AGENTS.md`, this file wins (MG-specific extension).
