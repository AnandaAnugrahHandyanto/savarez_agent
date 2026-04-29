# Audit Report — [System / Feature / PR Name]

<!-- provenance: structural template from Motion-Granted-Production/audits/; content is illustrative -->
<!-- Copy this template for any formal audit. Fill in all sections. -->

**Auditor:** [Name or "Claude Code — Chen audit protocol"]
**Date:** YYYY-MM-DD
**Scope:** [What was audited — file paths, features, pipeline stages]
**Method:** [Audit methodology — e.g., Chen adversarial protocol, grep sweep, code review]
**Source version:** [Git SHA or branch]

---

## Executive Summary

**Overall verdict:** [CLEAN / N VIOLATIONS FOUND / INCONCLUSIVE]
**Confidence:** [HIGH (>80% confirmed) / MEDIUM (>50%) / LOW (<50%)]
**Critical findings:** [N]
**Total findings:** [N confirmed + N inferred + N unverified]

---

## Scope

### Files Audited

| File | Lines | Role |
|------|-------|------|
| `{path}` | {N} | {what it does} |

### Not in Scope

- [Explicitly excluded areas and why]

---

## Findings

### Critical (P0 — must fix before ship)

#### Finding 1: [Short title]

**Status:** CONFIRMED / INFERRED / UNVERIFIED
**Location:** `{file}:{line}`
**Evidence:**
```
{grep output or code snippet}
```
**Impact:** [What breaks if this is wrong]
**Fix:** [Specific change needed]

---

### High (P1 — fix in current sprint)

#### Finding 2: [Short title]

**Status:** CONFIRMED / INFERRED / UNVERIFIED
**Location:** `{file}:{line}`
**Evidence:** [grep or file read evidence]
**Fix:** [Specific change needed]

---

### Medium (P2 — fix before next milestone)

_(add as discovered)_

---

### Low / Informational

_(add as discovered)_

---

## False Positives Investigated

List findings that were investigated and ruled out, with the evidence that falsified them. This is as important as confirmed findings — it shows the audit was thorough.

| Candidate Finding | Why It Was Ruled Out | Evidence |
|-------------------|---------------------|----------|
| {description} | {reason} | {file:line or grep} |

---

## Coverage Summary

| Area | Verified | Inferred | Unchecked | Coverage |
|------|----------|----------|-----------|----------|
| Security surface | {N} | {N} | {N} | {N}% |
| Business logic | {N} | {N} | {N} | {N}% |
| Integration wiring | {N} | {N} | {N} | {N}% |
| **Total** | **{N}** | **{N}** | **{N}** | **{N}%** |

---

## Open Questions

Items that require additional investigation or operator decision:

- [ ] **[Question]** — [What needs to be answered, and how to get there]

---

## Recommended Actions

| Priority | Action | Owner | Deadline |
|----------|--------|-------|----------|
| P0 | {action} | {who} | {when} |
| P1 | {action} | {who} | {when} |

---

## Audit Checklist

- [ ] Every finding has evidence (file:line or grep output)
- [ ] Every finding is labeled CONFIRMED / INFERRED / UNVERIFIED
- [ ] False positives investigated and documented
- [ ] Open questions listed
- [ ] No inviolable rules violated in the audited code (per CLAUDE.md)
- [ ] Coverage summary filled in
