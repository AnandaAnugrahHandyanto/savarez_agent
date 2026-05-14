# Handoff Matrix — Search Term Auditor

Maps each finding type to the correct upstream skill. The cascade order is **Measurement → Business → Conversion → Traffic** — the auditor's own execute counterpart (`/search-term-optimizer`) only fires after upstream layers are cleared.

## Routing table

| Finding | Layer | Route to | Why |
|---------|-------|----------|-----|
| Active Measurement hypothesis (tracking-audit score < 70 on attribution/OCT/consent) | Measurement | `/tracking-specialist` | Attribution anomalies can make converting terms look dead. Negating them would delete working traffic. |
| Duplicate criterion_id attribution anomaly | Measurement | `/tracking-specialist` | Double-counting inflates "efficient" terms and hides the real waste. |
| `target_source=fallback` on any flagged campaign | Business | `/strategy-specialist` | Campaign has no real target. The missing target is the issue — negating traffic compresses the account but does not fix the math. |
| Stale targets (strategy-audit score < 70 on targets/unit economics) | Business | `/strategy-specialist` | If unit economics have shifted, "underperforming" is measured against the wrong bar. |
| Core-relevant terms underperforming (B2: term matches core product tokens, yet flagged in ST-D03 or ST-D14) | Conversion | `/lp-auditor`, `/offer-auditor` | These are front-door queries — the problem is conversion, not traffic. |
| Keyword structure overlap caused by promotion (ST-D21 duplicates) | Structural | `/keyword-auditor` | Cannibalization is a keyword-structure issue; promote within existing AG or reorganize. |
| PMax brand cannibalization (ST-D25 > 25%) | Competitive | `/competitive-analyst` | Branded competitive dynamics. Apply brand exclusion via `/search-term-optimizer brand` only after competitive review. |
| PMax / Search overlap (ST-D26) | Structural | `/keyword-auditor` | Owned by keyword-auditor's KW-D12 (Search vs PMax Overlap). Route there for spend-share analysis and remediation (exact match in Search for high-value terms, PMax adjustments). |
| Non-converting terms (ST-D02, D13) on non-core tokens, cascade clear | Traffic | `/search-term-optimizer negate`, `/search-term-optimizer ngrams` | Safe to negate. Shared list by default. |
| Negative conflicts (ST-D08) | Structural | `/search-term-optimizer conflicts` | Always-safe — removing a negative that blocks an active keyword. |
| Consolidation (ST-D09, D10) where `likely_routing === false` | Structural | `/search-term-optimizer consolidate` | Move repeated negatives up the hierarchy. Pass ONLY entries with `likely_routing === false` — entries flagged routing must be excluded from the handoff payload. |
| Routing-flagged repeated negatives (ST-D09, D10 where `likely_routing === true`) | INFO only | (do not route) | Surface in the audit report as informational. Do NOT pass to the optimizer — promoting these to a shared list breaks intentional traffic routing between campaign clusters. Manual review required if the user wants to consolidate anyway. |
| Legacy +modified +broad (ST-D11) | Structural | `/search-term-optimizer negate` (format conversion) | Always-safe — rewrites to current match type. |
| Foreign language terms (ST-D04) | Traffic | `/search-term-optimizer foreign` | Narrow exclusion scope; usually exact match on the foreign queries. |
| Promotion candidates (ST-D20) on non-duplicate terms | Traffic | `/search-term-optimizer promote` | Respects advertiser's existing match-type setup per ad group. |
| Catalog gaps (ST-D12) | Proposal | `/search-term-optimizer catalog` | Propose-only with 365d data validation. |

## Canonical skill names

Always use these names — no aliases, no abbreviations:

- `/tracking-specialist`
- `/strategy-specialist`
- `/lp-auditor`
- `/offer-auditor`
- `/keyword-auditor`
- `/keyword-optimizer`
- `/competitive-analyst`
- `/search-term-optimizer`

## Cascade enforcement

When an upstream hypothesis is active, the Phase 3 handoff offer must lead with that skill — never present `/search-term-optimizer` as the first option. The standard ordering template:

1. Measurement fix (if any)
2. Business fix (if any)
3. Conversion fixes for relevant-but-underperforming terms (if any)
4. Always-safe structural fixes (conflicts, consolidate, legacy format)
5. Traffic negation cycle (negate + ngrams) — only on non-core terms after cascade is clear
6. Promotion candidates — lowest urgency, highest care (match-type respect, no auto-Broad-on-Smart-Bidding)

Only show each step if there are findings to act on. Don't list a step that would produce 0 operations.
