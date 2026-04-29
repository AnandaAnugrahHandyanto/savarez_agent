# Security

This file states the security posture of the Motion Granted Citation Database: product positioning, schema-level guardrails, supported-version policy, threat model, operator-only boundaries, and vulnerability-reporting channel. Every load-bearing claim cites `binding/v7.2.md` by `§N line M`, or names an authoritative repo path.

This is pre-1.0 scaffold-state tooling. See [`NOTICE.md`](NOTICE.md) for licensing and legal framing; nothing in this file modifies or waives any term in `LICENSE` or `NOTICE.md`.

---

## 1. Scope and posture

The Citation Database is a **research acceleration tool**, not a substitute for professional legal judgment, and not legal advice. Canonical framing, quoted verbatim from `archive/Codebase Doc/6- Pre-Send Audit v7.2.html` line 368:

> "The citator is a research acceleration tool, not a substitute for professional legal judgment. All negative treatment flags include the model's reasoning and proof text for attorney verification."

The schema enforces this framing at the data level: `al_treatment_derivation` stores `proof_text`, `proof_locator`, and `proof_section` on every derivation (v7.2 §12 line 863).

---

## 2. Product positioning (R10 — malpractice discipline)

Pre-Send Audit v7.2 "Issue 10 — The Malpractice Liability Discussion Needs Specifics, Not a Paragraph" (archive lines 353-370; action-list #9 at lines 434-438) prescribes three concrete design decisions for the product's legal positioning:

1. **Confidence floor** (Pre-Send Audit L367). The audit proposes `0.85` as an illustrative threshold: MCP responses below that confidence must carry an uncertainty notice. **v7.2 does not ratify a specific MCP confidence-floor threshold.** The spec's only ratified confidence threshold is the Cardinal Sin contrapositive (`≥ 0.99` required for `VERIFIED` rows on non-error derivation paths, v7.2 §12 line 893-897). Between 0.85 and 0.99 is unspec'd. The 0.85 figure is a cofounder-ratification decision, not engineering-decidable.
2. **Research-tool positioning** (Pre-Send Audit L368). The verbatim sentence in §1 above is the cofounder-audit-approved framing.
3. **Cofounder-authored disclaimer path** (Pre-Send Audit L369). Disclaimer language carried by the MCP envelope is a cofounder-ratification artifact, not an engineering artifact. This repo does not invent disclaimer prose for the MCP envelope.

---

## 3. Supported versions

- **Schema version: pre-1.0.** External MCP consumption against pre-1.0 schemas is **forbidden** (v7.2 §15 line 1181, verbatim): "Pre-Phase-1D, the schema version is `'0.x'` … Schema versions below `'1.0'` must not be consumed by external MCP clients; only internal testing infrastructure may deserialize against pre-1.0 schemas."
- **Spec version: 7.2.** Envelope field per v7.2 §15 line 1164 + line 1175.
- **Phase ladder** (v7.2 §20 line 1424-1432): 1A (Tier A scaffold apply) → 1B (full bodies + 013 roles + 014/015 triggers, Tier B) → 1C (MG CIV reads from AL, Tier C) → 1D (MG CIV writes cut over, Tier D).
- **Tier B PENDING items** gating production: migration 013 (12-role GRANT/REVOKE matrix), migration 014 (full `promote_derivation_to_sink`, `compute_verification_status` body relocation per §12 line 917, `al_merge_authority`, `recompute_sink_for_tuple`, `recompute_sink_for_authority`), migration 015 (`al_scope_lineage` auto-population trigger wiring + body), concrete `al_recompute_queue` DDL.
- **Tier D PENDING items** (v7.2 §29 line 2175-2180): operational P0 runbooks (incident response, deployment strategy), P1 operational documents (performance model, model governance), **legal-counsel ratification of §26 retention numbers**.
- **Producer posture.** Four **strict xfails** track open prompt-layer vulnerabilities as documented open items (not silent known risks): F3 prompt-side jurisdiction request, F5 prompt-side STOP-signal removal, F7 dicta-vs-holding split, F8 prompt-injection defense (BACKLOG.md line 14). Strict mode guarantees CI failure when any closes, forcing operator review.

---

## 4. Schema-level security guardrails

### 4.1 Cardinal Sin (I-6)

Authority: v7.2 §1 line 175-177 (invariant) + §12 line 883-921 (precise mapping).

No row may exist in `al_effective_treatment` with `verification_status = 'VERIFIED'` AND `confidence ≥ 0.99` unless produced by a non-error derivation path. Enforced by DB-level trigger `al_enforce_cardinal_sin_trigger` BEFORE INSERT OR UPDATE (v7.2 §12 line 901).

Three-condition prohibition (v7.2 §12 line 891-897, verbatim):

```
verification_status = 'VERIFIED'
  AND confidence >= 0.99
  AND (lookup of source_derivation.produced_by_error_path) = TRUE
```

A row is refused promotion if and only if all three hold simultaneously. Fail-closed guard (v7.2 §12 line 899): if the source derivation lookup returns NULL (FK integrity failure), the trigger raises `cardinal_sin_source_missing` rather than passing.

- **ERRCODE**: `CS001` (`drafts/scaffold/012_functions_triggers.sql:17-18`; v7.2 silent on specific SQLSTATE — scaffold chose distinct families `CS001`/`SG001`/`OV001`/`NI001-005`/`PP001`/`PR001`/`VS001`).
- **Metric** (v7.2 §14 line 1095): `al.cardinal_sin_rejection_count` target = 0; any non-zero is P0.
- **Alert** (v7.2 §14 line 1103): "Cardinal Sin rejection > 0 / 5min → **P0, page Clay**."
- **Test gate**: T-CS-3 verifies `sink_promoter` cannot DROP the trigger; gated by migration 013 (role creation).

### 4.2 STOP gate (I-7)

Authority: v7.2 §1 line 179-181 + §8 line 485-568 + §12 line 942. No STOP-severity row enters the sink without passing a 5-factor commit gate. Trigger `al_enforce_stop_gate_trigger` BEFORE INSERT OR UPDATE on `al_effective_treatment`. ERRCODE `SG001` (`drafts/scaffold/012_functions_triggers.sql:115-124`).

### 4.3 Two-person STOP override (§9 + §24 N-2)

Authority: v7.2 §9 line 608-641 + §24 N-2 line 1539-1551.

Any override asserting `severity_rank = 4` (STOP) requires a `second_approver_id` distinct from `created_by_user_id`. Trigger drafted in `drafts/scaffold/012_functions_triggers.sql:148-176` with ERRCODE `OV001`. The application-layer feature flag gating STOP-severity override creation stays **OFF** in all environments until (a) the trigger ships in migration 012, (b) test `T-OV-1` verifies single-approver rejection, and (c) Porter + Clay sign off (v7.2 §9 Correction #11, line 612-621). Clay ratified N-2 acknowledgment by email 2026-04-23 1:48 PM; in-repo BACKLOG sync pending.

Threat modeled (v7.2 §9 line 623, verbatim): "A single operator creating a fabricated STOP override (e.g., '*Chevron* is overruled effective tomorrow') would write canonical truth into the sink, bypassing Cardinal Sin … This is the exact 'disgruntled ex-contractor' threat model Attack 5 anticipated."

### 4.4 Append-only history (I-9)

Authority: v7.2 §1 line 187-189, verbatim: "Every state transition in `al_effective_treatment` produces a row in `al_effective_treatment_history`. History is append-only — no UPDATE, no DELETE. Tombstones are represented as new history rows with appropriate `transition_type`."

Derivation-layer append-only posture is a derived consequence of the role matrix: the only UPDATE right on `al_treatment_derivation` is to `quarantine_operator` on a single column (`disposition_status`, v7.2 §13 line 1023).

### 4.5 Deterministic sink + no wall-clock ordering (I-4 + I-6b)

Authority: v7.2 §1 line 167-169 (I-4) + §6 line 380-409 (ordering function + I-6a/b/c).

Sink ordering across candidates is 8 dimensions: `override_present DESC, blessed DESC, stop_gate_passed DESC, severity_rank DESC, confidence DESC, pipeline_version DESC, derivation_version DESC, derivation_content_hash ASC`. **No wall-clock-derived field may appear** as an authoritative ordering dimension (v7.2 §6 line 393-399). Timestamps (`created_at`, `promoted_at`, `transitioned_at`, `evaluated_at`) are observational metadata only. `derivation_content_hash` (SHA-256 over canonical-serialized derivation, CHECK `~ '^[0-9a-f]{64}$'`) is the authoritative final tiebreaker (v7.2 §6 line 413). I-6a Totality, I-6b Determinism, I-6c Monotonicity-under-override at v7.2 §6 line 407-409.

`AGENT-DISCIPLINE.md §7` self-audit includes a banned-pattern check: `created_at` in `ORDER BY` inside promotion-function bodies is a hard block.

### 4.6 Fail-closed (I-8)

Authority: v7.2 §1 line 183-185, verbatim: "On ambiguity, conflict, lock contention, version mismatch, or any precondition failure, the AL rejects the write with an explicit reason. It never writes a best-guess default, never swallows an exception into a success response, never returns 200 on an internal failure."

### 4.7 Reproducibility + prompt integrity (I-10)

Authority: v7.2 §1 line 191-193 (I-10) + §10 line 666-675 + §12 line 865 + `producer/pipeline/prompts/README.md` line 63-66 + BACKLOG.md line 14 + line 69.

- Per-derivation attestation: `al_treatment_derivation` carries `model_ids_jsonb` and `prompt_ids_jsonb` (v7.2 §12 line 865).
- Per-run attestation: `al_pipeline_run` carries `prompt_versions_jsonb` (v7.2 §10 line 666, 675), e.g., `{"flp":"v404","mg":"v83.1"}`.
- Prompt-content hash: every classification record stores a `prompt_hash` = **SHA-256 of the prompt file content** (not a Git commit SHA). `producer/pipeline/prompts/README.md` line 63-66.
- Prompt-file immutability: prompts under `producer/pipeline/prompts/` are **IMMUTABLE** until the four strict xfails (F3, F5, F7, F8) close (BACKLOG.md line 14, line 69). This is a session-level session discipline combined with per-record `prompt_hash` attestation and per-run `prompt_versions_jsonb` version pinning. (No single v7.2 section is labeled "immutable prompts + Git-SHA verification" — the doctrine is distributed across the cites above. v7.2 has no §3.7.)

---

## 5. Access-control defenses

Authority: v7.2 §13 line 1013-1056.

**12 canonical roles** (v7.2 §13 line 1015-1028). CLAUDE.md legacy text and v7.2 §18 line 1330 / §29 line 2170 still reference "11 roles"; the canonical enumeration at §13 is 12 (including `platform_admin`). BACKLOG.md line 71 tracks the reconciliation. This file uses 12.

| # | Role | Kind | Summary |
|---|---|---|---|
| 1 | `source_ingest_writer` | service | INSERT on `al_source_ingest` only |
| 2 | `authority_normalizer` | service | INSERT + UPDATE `al_authority`; calls `al_merge_authority()` |
| 3 | `citation_resolver` | service | INSERT on `al_citation_edge` |
| 4 | `derivation_writer` | service | INSERT on `al_treatment_derivation`, `al_stop_gate_result` |
| 5 | `sink_promoter` | internal | Stored-proc-only; no direct DML on sink/history |
| 6 | `override_operator` | human | INSERT on `al_override`; STOP requires two operators |
| 7 | `quarantine_operator` | human | UPDATE `disposition_status` only |
| 8 | `pipeline_steward` | human | UPDATE `al_pipeline_run.blessed`; two-operator unbless |
| 9 | `consumer_reader` | service | SELECT only on sink, authorities, edges |
| 10 | `mcp_reader` | service | SELECT only on sink + views |
| 11 | `audit_reader` | human | SELECT on `al_audit_event`, history |
| 12 | `platform_admin` | human | Superuser; two-approver break-glass; mandatory post-incident review |

**Sink-ownership rule** (v7.2 §13 line 1030-1032, verbatim): "No role may directly INSERT, UPDATE, or DELETE `al_effective_treatment` or `al_effective_treatment_history`. Even `sink_promoter` operates through stored procedures. `platform_admin` can bypass in break-glass; every bypass is a P1 incident."

**Two-person extensions** (v7.2 §13 line 1034-1040): STOP override creation, `platform_admin` break-glass sessions, unblessing a previously-blessed `pipeline_run`, manual DELETE from `al_audit_event`.

**Secrets posture** (v7.2 §13 line 1052-1056): DB connection strings in environment variables only, never in code; service-account passwords rotated quarterly with audit-event emission; external MCP API keys max TTL 90 days with explicit renewal.

**Current status.** Migration 013 is Tier B / PENDING. Scaffold draft `drafts/scaffold/013_roles_grants.sql` outlines role creation; full GRANT/REVOKE matrix ships at Tier B (v7.2 §13 line 1048-1050, §20 line 1420). Until 013 ships, the DB operates with default Postgres privileges. This is a current security-posture gap, not a defense.

---

## 6. Threat model

Each threat: what, schema defense, residual risk.

### 6.1 Unauthorized sink write (consumer bypass)

Defense: v7.2 §13 line 1030-1032 sink-ownership; I-4 L167-169; role SELECT-only on sink for `consumer_reader` (L1025) + `mcp_reader` (L1026). **Residual**: migration 013 PENDING; until Tier B ships, defense is spec-binding, not DB-enforced.

### 6.2 Ordering-function determinism violation

Defense: v7.2 §6 line 393-399 no-wall-clock; I-6a/b/c at line 407-409; content-hash tiebreaker at line 413; `al_derivation_replay_dedupe_idx` unique on `(citation_edge_id, pipeline_run_id, derivation_content_hash)` at line 417; test T-SINK-3 (§16). `AGENT-DISCIPLINE.md §7` banned-pattern pre-commit block. **Residual**: `promote_derivation_to_sink` full body is Tier B / PENDING; currently raises `NI001` stub.

### 6.3 Prompt injection exfiltration

Defense (partial): producer adapter normalization + `ContractViolation` raise; Python-side Cardinal Sin at `DerivationRecord.__post_init__`; DB-layer Cardinal Sin trigger; prompt-text immutability until xfails close. **Open gaps** (strict xfails, BACKLOG.md line 14):

- **F3** — prompt-side jurisdiction-scope request. Test `test_hf3_irac_prompt_requests_jurisdiction_scope_field` at `producer/tests/adversarial/test_prompt_audit_findings.py:329-343`.
- **F5** — prompt-side STOP-signal removal. Test `test_hf2_irac_prompt_does_not_request_signal_field` at lines 310-326.
- **F7** — dicta-vs-holding split instruction. Test `test_p67_irac_prompt_contains_dicta_vs_holding_instruction` at lines 289-307.
- **F8** — injection-defense clause. Test `test_hf4_irac_prompt_contains_injection_defense_clause` at lines 266-286.

**Residual**: four open gaps tracked as strict xfails, not silent. Strict mode forces CI failure on XPASS.

### 6.4 Confidence inflation → Cardinal Sin attempt

Defense: Cardinal Sin trigger (§4.1); metric target 0 with P0 alert; producer-side Python-layer duplicate defense at record construction. **Residual**: `produced_by_error_path` flag is on honor system from `derivation_writer` (v7.2 §12 line 919); `al.cardinal_sin_rejection_count` rising is the signal that flag accuracy needs investigation. Error-path criteria at v7.2 §28 line 1964-1975; "ambiguous cases default to TRUE — Cardinal Sin bias is 'be conservative.'"

### 6.5 STOP-override abuse (single-operator sign-off)

Defense: §4.3 above; application-layer feature flag OFF until T-OV-1 passes and Clay + Porter sign off. **Residual**: until Clay confirms Porter's trigger restoration (BACKLOG.md line 13), the application-layer flag is the only live defense, and it's a spec contract not a DB constraint.

### 6.6 Replay nondeterminism

Defense: I-10 Reproducibility (v7.2 §1 line 191-193); no-wall-clock ordering (§4.5); content-hash tiebreaker; T-SINK-3; replay-dedupe unique index (v7.2 §6 line 417). **Residual**: I-10 depends on `pipeline_run.blessed` discipline (v7.2 §10 line 664-692); unblessed runs do not promote.

### 6.7 External MCP consumer coupling below 1.0

Defense: v7.2 §15 line 1181 binding-spec forbiddance; envelope carries `al_schema_version` and `al_spec_version` (line 1172-1177); forbidden-ops list at line 1142-1148 (no write, no merge, no override create/revoke on MCP). **Residual**: enforcement depends on external consumers respecting the "must not"; not a DB constraint.

---

## 7. Operator-only boundaries

Authority: `AGENT-DISCIPLINE.md §5` line 82-89. Agents never:

- `git push` to `main` or any protected branch; `gh pr merge`; force-push; tag; release.
- Apply migrations to any database (no `psql`, no Supabase `apply_migration`, no `drafts/scaffold/*.sql` execution) unless the session mission explicitly authorizes staging write.
- Change role grants. The 12-role GRANT matrix is a Tier B item requiring Clay + Porter ratification (v7.2 §13 line 1050; `drafts/scaffold/013_roles_grants.sql`).
- Touch the prompt layer. Prompts under `producer/pipeline/prompts/` are IMMUTABLE per BACKLOG.md line 14.
- Edit `archive/`, `binding/`, `producer/`, `reports/`, `al/` without explicit mission authorization (`AGENT-DISCIPLINE.md §5` line 86-87).
- Produce outputs outside the session's declared workspaces. Any path outside → `SCOPE_CREEP_INFERRED` tripwire (`AGENT-DISCIPLINE.md §5` line 88).

Every scaffold migration file header (e.g., `drafts/scaffold/012_functions_triggers.sql:4`, `drafts/scaffold/013_roles_grants.sql:4`) reinforces with: "OPERATOR MUST REVIEW BEFORE APPLY. NO DB APPLIED IN THIS SESSION."

---

## 8. PII and privacy posture

Authority: v7.2 §28 line 1922-1932.

- **Public-record only.** The corpus is CourtListener bulk-export material; CL upstream redacts per its policy.
- **Known vectors.** Juvenile-court material; sealed sexual-assault cases (where redaction is imperfect); Social Security numbers, financial-account numbers in pro-se filings.
- **Tombstoning procedure.** v7.2 §28 line 1922-1932 defines how flagged PII is removed from the canonical record while preserving the audit trail (history row with appropriate `transition_type`).
- **No attorney-client privilege material** is stored.
- **PII scanner** (§29 item 15): policy stated, code deferred; runs as a Tier B workstream.

---

## 9. Audit surface

Authority: v7.2 §14 line 1071-1107.

- **11 event classes** (v7.2 §14 line 1073): `source_ingest`, `authority`, `citation_resolution`, `derivation`, `stop_gate`, `sink`, `concurrency`, `quarantine_recovery`, `override`, `consumer_api`, `security`.
- **Security sub-types** (v7.2 §28 line 1977-1988): `auth_failure`, `privilege_escalation_attempted`, `break_glass_session_started`, `break_glass_session_ended`, `archival_batch_completed`, `backup_completed`, `pii_concern_raised`, `credentials_rotated`.
- **Alert thresholds** at v7.2 §14 line 1103-1107 (e.g., Cardinal Sin rejection > 0 / 5 min → P0).

---

## 10. Retention and backup — counsel-pending

Authority: v7.2 §26 line 1736-1798.

Per-table retention windows and RPO / RTO / durability numbers are stated in v7.2 §26. v7.2 §26 line 1759 is explicit: "Exact retention numbers are **author's best estimates** and should be ratified by counsel before Phase 1D."

This file does **not** present the retention numbers as ratified. They stand as best-estimate defaults pending counsel sign-off (v7.2 §29 item 11, BACKLOG.md line 44). No operational decision — retention, purge, subject-access-request fulfillment — should cite these numbers as final until counsel has ratified.

---

## 11. Reporting channel — `[OPERATOR DECISION REQUIRED]`

**Currently unresolved.** No `security.txt`, no disclosed vulnerability-reporting channel, and no published coordinated-disclosure policy have been located in `binding/v7.2.md`, `docs/operator/`, repo root, or `archive/`.

Operator to select one of:

1. **Maintainer email** — SECURITY.md points to an email address the operator confirms is monitored. Lightest weight; requires an actually-monitored channel.
2. **`security@` alias** — standard domain-mail pattern with triage rotation. Appropriate for a legal-tech product where bar-rule auditors expect a formal channel.
3. **GitHub private security advisories** — free, accountable, issue-style workflow; requires the repo to remain on GitHub and the feature enabled.
4. **Defer reporting channel until post-Tier-D** — consistent with pre-1.0 state and v7.2 §15 line 1181 "external consumption forbidden." State explicitly: "No external disclosure channel until production release; contact maintainer off-band during pre-1.0 period."

**No email, alias, or URL has been invented in this file.** Inventing a reporting channel creates a legal liability (bar-rule auditors read it as disclosure policy; implies a triage commitment).

This gap is tracked in `worktree-session/DOC-TODOS.md`.

---

## 12. `NOTICE.md` and `LICENSE`

Licensing is governed by [`LICENSE`](LICENSE) (MIT per root file) and [`NOTICE.md`](NOTICE.md) (third-party attributions and product disclaimer). Nothing in this file modifies or waives any term in `LICENSE` or `NOTICE.md`. Disclaimer language shipped with the MCP envelope is a cofounder-ratification artifact (Pre-Send Audit L369) and is not invented in this repo.

---

## 13. Acknowledged gaps

- **Six §24 scaffold blockers** (v7.2 §24 line 1535-1689). Status as of 2026-04-23:
  - **N-1** (ENUM schema-qualifier): baked into `drafts/scaffold/002_enums.sql` with `pg_namespace` idempotency.
  - **N-2** (two-person STOP override trigger): active in `012_functions_triggers.sql`; application feature flag OFF; Clay acknowledged 2026-04-23.
  - **R-1** (three-column authority uniqueness): Clay ratified Option B 2026-04-23.
  - **R-2** (`proof_section` CHECK constraint): restored per v7.2 verbatim 7-value list.
  - **R-3** (proposition-text columns): Clay ratified option (a) 2026-04-23.
  - **S-5** (consumer-tree audit for lowercase `al_treatment_type` literals): operator-owned. Archive-scope in `reports/TAX-15to16-DELTA.md`; live working-tree sweep outstanding.
- **§29 16-item gap list** (v7.2 §29 line 2155-2185; reproduced in BACKLOG.md line 48-65), explicitly including:
  - Item 8 — STOP-override trigger restoration (mapped to N-2 above).
  - Item 11 — legal-counsel ratification of §26 retention numbers.
- **Counsel deliverables pending**: disclaimer language for MCP envelope; §26 retention ratification; bar-rule posture per jurisdiction.

---

## 14. Further reading

- [`binding/v7.2.md`](binding/v7.2.md) — architectural spec (2,214 lines).
- [`AGENT-DISCIPLINE.md`](AGENT-DISCIPLINE.md) — operational doctrine (Zero-Inference, A-L category table, scope rules).
- [`BACKLOG.md`](BACKLOG.md) — ratified open items, Tier B carry-overs, §29 gap list.
- [`NOTICE.md`](NOTICE.md) — third-party attributions, product disclaimer.
- [`CLAUDE.md`](CLAUDE.md) — per-session agent orientation.
- `drafts/scaffold/REBUILD-MANIFEST.md` — scaffold provenance and ERRCODE family register.
- `producer/pipeline/prompts/README.md` — prompt-hash attestation protocol.

Authority: `binding/v7.2.md`. Discipline: `AGENT-DISCIPLINE.md`.
