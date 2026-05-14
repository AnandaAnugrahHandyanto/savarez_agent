# Competitive Analyst — Handoff Matrix

**Purpose:** Map competitive findings to the right specialist skill. The competitive analyst is DIAGNOSE-ONLY — it identifies competitive pressure and traces it to business KPI impact, then routes to the skill that can act on it.

**When to use:** Phase 3, after the constraint cascade determines root cause.

---

## By finding type

### Budget-Constrained IS Loss

| Finding | Handoff | Why |
|---------|---------|-----|
| CA-D02: Budget-lost IS dominant (>15%) | `/budget-specialist` | Budget is the binding constraint — reallocate or increase before touching bids or keywords |
| CA-D02: Budget-lost IS + IS declining (CA-D01) | `/budget-specialist` → then re-audit | Budget constraint is causing the IS trajectory decline; fixing budget may resolve D01 |

### Rank/Quality-Driven IS Loss

| Finding | Handoff | Why |
|---------|---------|-----|
| CA-D02: Rank-lost IS dominant (>15%) | `/keyword-auditor` (QS check) → `/ad-copy-specialist` (CTR) → `/lp-auditor` (LP experience) | Rank loss = Ad Rank problem = Quality Score components |
| CA-D05: Top-of-page rate declining | `/bidding-specialist` for bid target review | Position decline may indicate bid strategy needs adjustment |
| CA-D08: Keyword IS <30% with rank-lost >40% | `/keyword-auditor` for deep-dive on flagged keywords | Keyword-level competitive pressure — may need QS improvement or bid adjustment |

### Competitive Entry / CPC Pressure

| Finding | Handoff | Why |
|---------|---------|-----|
| CA-D11: Strong negative CPC-IS correlation (r < -0.5) | `/bidding-specialist` for bid strategy review | New competition driving up CPCs — bid strategy may need adjustment |
| CA-D11: CPC rising >15% with IS declining | `/competitor-ads` for competitor ad copy intelligence | Understand what competitors are doing before reacting with bids |
| CA-D08: Multiple high-spend keywords under pressure | `/competitor-ads` → `/ad-copy-specialist` | Competitive pressure at keyword level — understand competitor messaging |

### Shopping-Specific Findings

| Finding | Handoff | Why |
|---------|---------|-----|
| CA-D09: Isolated ad group IS decline | Investigate product category → `/product-optimizer` (feed quality) | Category-specific competition — check product data, pricing, feed quality |
| CA-D09: Severe isolated decline (>10pp) | `/product-optimizer` + review bids for that ad group | Urgent: new competitor in a specific product segment |

### KPI Impact

| Finding | Handoff | Why |
|---------|---------|-----|
| CA-D13: Estimated conversion loss <2% | Note in report, deprioritize | Immaterial — competitive pressure exists but isn't hurting the business meaningfully |
| CA-D13: Estimated conversion loss 2-10% | Prioritize IS recovery via budget/bid/quality | Material but manageable — address through normal optimization |
| CA-D13: Estimated conversion loss >10% | `/performance-reviewer` for strategic discussion | Severe — needs strategic response, not just tactical fixes |

### Competitor Intelligence Enrichment

| Finding | Handoff | Why |
|---------|---------|-----|
| No `/competitor-ads` data exists | Suggest: "Run `/competitor-ads` for competitor ad copy analysis" | Competitor ad intelligence enriches the audit but is not scored |
| `/competitor-ads` data exists | Include insights in report Section 10 | Show what competitors are saying — informs ad copy and offer strategy |

---

## Constraint Cascade (Phase 1.5)

Walk this cascade to determine root cause before recommending action:

### Step 1: Is it a budget problem?
**Check:** CA-D02 — is budget-lost IS the dominant loss type?

- Yes → Route to `/budget-specialist` for reallocation or increase
- **Do NOT recommend bid changes if budget is the constraint** — raising bids with insufficient budget just shifts the problem

### Step 2: Is it a rank/quality problem?
**Check:** CA-D02 — is rank-lost IS dominant? CA-D05 — top-of-page declining?

- Yes → Check if QS data available from `/keyword-auditor`
- Route to `/keyword-auditor` (QS), then `/ad-copy-specialist` (CTR), `/lp-auditor` (LP experience)

### Step 3: Is it competitive entry?
**Check:** CA-D11 — CPC pressure signal? CPC rising with IS declining?

- Yes → Route to `/bidding-specialist` for bid strategy review
- Route to `/competitor-ads` for ad copy intelligence

### Step 4: Is the impact material?
**Check:** CA-D13 — estimated conversion loss

- <2% → note but deprioritize. Don't over-react to small competitive shifts
- 2-10% → standard optimization priority
- >10% → escalate to `/performance-reviewer`

---

## Sequencing Rule

When multiple findings are active, sequence handoffs by constraint cascade, not by severity:

1. **First** — Budget fixes (CA-D02 budget-lost dominant)
2. **Then** — Quality/rank fixes (CA-D02 rank-lost, CA-D05, CA-D08)
3. **Then** — Competitive intelligence (CA-D11 CPC pressure → `/competitor-ads`)
4. **Then** — Shopping-specific (CA-D09 isolated declines)
5. **Then** — Strategic escalation if KPI impact material (CA-D13 >10%)

Never present the Phase 3 offer as a flat list. Always frame it as a sequence with dependencies.
