# Diagnostic Rules — Goals & KPIs (D10-D14)

Read during Phase 2 when running `/strategy-specialist goals` or `/strategy-specialist` (default).
Read `diagnostic-rules-shared.md` first. Load `kpi-framework.md`, `bid-targets-par.md`, `bid-strategy-alignment.md`, and `goal-quality-checklist.md` alongside this file.

## Module Scoring

| ID | Diagnostic | Severity | Pts | Verticals |
|----|-----------|----------|-----|-----------|
| D10 | Primary KPI definition | Critical | 15 | All |
| D11 | Guardrail KPI definition | High | 10 | All |
| D12 | Target CPA/ROAS feasibility | Critical | 15 | All |
| D13 | Goal-to-bid-strategy alignment | High | 10 | All |
| D14 | Stakeholder alignment | Medium | 5 | All |

---

## D10: Primary KPI Definition
**Severity:** Critical (15 pts)
**Vertical:** All
**Data:** business.md > Goals & KPIs section
**Reference:** `kpi-framework.md` > KPI Tiers, `goal-quality-checklist.md` > KPI Selection

**Check:** Is a primary KPI clearly defined with a measurable target?

**PASS:** All of:
- Primary KPI is explicitly named (CPA, ROAS, POAS, conversions, conversion value, or cost per qualified lead)
- A numeric target is set (e.g., "CPA < $200", "ROAS > 400%")
- Goal type is identified (growth or efficiency)
- The KPI is appropriate for the vertical (see `kpi-framework.md` > Tier 1)

**WARN:** Primary KPI is defined but:
- Missing a numeric target ("improve CPA" without a number)
- Or goal type (growth vs efficiency) is not explicitly stated
- Or KPI is unusual for the vertical (e.g., ROAS for Lead Gen without value tracking)

**FAIL:** No primary KPI defined in business.md Goals section. Or Goals & KPIs section missing entirely.

**ASK:** Goals section exists but is incomplete. Ask: "What is your primary KPI and target? (e.g., CPA under $200, ROAS above 400%)"

**Details to report:** Primary KPI name, target value, goal type (growth/efficiency).

---

## D11: Guardrail KPI Definition
**Severity:** High (10 pts)
**Vertical:** All
**Data:** business.md > Goals & KPIs > Guardrail KPIs / Hard Constraints
**Reference:** `kpi-framework.md` > Tier 2: Guardrail KPIs

**Check:** Are guardrail KPIs set to prevent damage from primary goal pursuit?

**PASS:** All of:
- At least one guardrail KPI is defined with a specific numeric threshold
- Guardrails are the "opposite" type from primary (growth primary → efficiency guardrails, or vice versa)
- Guardrail thresholds are grounded in unit economics (not arbitrary)

**WARN:** Guardrails exist but:
- Thresholds are vague ("keep an eye on CPA")
- Or guardrails don't cover the critical risk (growth goal without max CPA/min ROAS, or efficiency goal without min volume)
- Or guardrails appear arbitrary (not derived from unit economics)

**FAIL:** No guardrail KPIs defined. "Running without guardrails risks unprofitable scaling (growth) or volume starvation (efficiency)."

**Details to report:** List of guardrails with thresholds, whether they match the correct type for the primary goal.

**Cross-reference with unit economics:**
- If primary goal is growth: guardrail CPA/ROAS should align with break-even from D01-D08
- If primary goal is efficiency: guardrail volume should be realistic given campaign data

---

## D12: Target CPA/ROAS Feasibility
**Severity:** Critical (15 pts)
**Vertical:** All
**Data:** business.md > Goals & KPIs > Performance Targets + Unit Economics section
**Reference:** `bid-targets-par.md` > D12 Feasibility Assessment

**Check:** Are the targets grounded in unit economics, not arbitrary? Are they achievable without losing money?

**Step-by-step evaluation:**

1. **Extract the target** from business.md Goals section (Target CPA, Target ROAS, or Target POAS)
2. **Extract the break-even** from business.md Unit Economics section (or calculate from available data)
3. **Calculate implied PAR:**
   - For CPA: PAR = Target CPA / Break-even CPA
   - For ROAS: PAR = Break-even ROAS / Target ROAS
4. **Assess:**

**PASS:** Target is documented AND:
- Implied PAR is 20-70% (healthy range — competitive targets with profit retained)
- Target is below break-even CPA or above break-even ROAS (profitable)
- There is documented reasoning linking target to unit economics

**WARN:** Target exists but:
- Implied PAR > 70% (near breakeven, thin profit margin)
- Or target appears to be a round number without documented unit economics basis ("$200 CPA" with no break-even calculation)
- Or break-even data is available but target was not explicitly derived from it

**FAIL:** Any of:
- Target CPA > break-even CPA (spending more than you earn per customer)
- Target ROAS < break-even ROAS (below profitability threshold)
- Target CPA > Max CAC for SaaS (e.g., target $200 but Max CAC = $78)
- Implied PAR > 100% (mathematically losing money on every conversion)

**ASK:** Unit economics exist but no target is set. Or target exists but no unit economics to validate against.

**Details to report:**
- Target value and type
- Break-even value
- Implied PAR and range label
- Gap between target and safe threshold
- Whether target is explicitly linked to unit economics in business.md

---

## D13: Goal-to-Bid-Strategy Alignment
**Severity:** High (10 pts)
**Vertical:** All
**Data:** business.md > Goals & KPIs + `context/google-ads/data/campaigns.csv`
**Reference:** `bid-strategy-alignment.md`

**Prerequisites:**
- Read `context/google-ads/data/campaigns.csv`
- If campaigns.csv does not exist or is older than 14 days, auto-pull:

```bash
node .claude/skills/gads-context/scripts/query.js \
  --customer-id={customer_id} \
  --login-customer-id={login_customer_id} \
  --query-file=.claude/skills/gads-context/references/campaigns.gaql \
  --days=30 \
  --output=context/google-ads/data/campaigns.csv
```

**Check:** Are the bid strategies in active campaigns aligned with the goals in business.md?

**Step-by-step evaluation:**

1. Extract primary goal type (growth/efficiency) and target metric from business.md
2. Read enabled campaigns from campaigns.csv (status = ENABLED)
3. For each campaign, check `campaign.bidding_strategy_type` against alignment rules in `bid-strategy-alignment.md`
4. Check if campaign-level targets match business.md targets (within 30% tolerance)

**PASS:** All enabled campaigns use bid strategies compatible with business.md goals. Campaign-level targets are within 30% of business.md targets.

**WARN:** Minor misalignments:
- One or more campaigns on Maximize Clicks or Manual CPC for 60+ days (should have progressed)
- Campaign-level targets deviate >30% from business.md targets
- Volume campaigns running without an efficiency constraint when business.md specifies one

**FAIL:** Major misalignment:
- Efficiency goal in business.md but campaigns running Maximize Conversions with no target
- Growth goal but all campaigns on very tight Target CPA/ROAS (starvation risk)
- Brand campaigns on aggressive automated bidding (overpaying for brand)

**SKIP:** campaigns.csv not available and auto-pull fails. Suggest running `/gads-context` first.

**Details to report:** Campaign name, bid strategy, target (if any), alignment status, suggested change.

---

## D14: Stakeholder Alignment
**Severity:** Medium (5 pts)
**Vertical:** All
**Data:** business.md > Goals & KPIs section (look for approval markers, stakeholder mentions)

**Check:** Is there evidence that stakeholders agree on goals and measurement methodology?

**PASS:** business.md explicitly states stakeholder-approved goals. Or: review cadence is documented with stakeholder involvement.

**WARN:** Goals are documented but no explicit stakeholder approval noted. Or: review cadence is missing.

**FAIL:** Goals appear to be set unilaterally (no stakeholder mention). Or: conflicting goals detected (e.g., "grow volume AND reduce CPA simultaneously" without acknowledging the trade-off).

**ASK:** Unable to determine stakeholder alignment from business.md. Ask: "Have the stakeholders approved these goals and targets? Is there an agreed review cadence?"

**What to look for in business.md:**
- Phrases like "agreed with client", "stakeholder approved", "confirmed targets"
- A documented review cadence (weekly, monthly, quarterly)
- Consistent goals across sections (no contradictions between Goals and Campaign Priorities)
- Acknowledgment of growth-efficiency trade-off if both are mentioned

**Details to report:** Whether stakeholder approval is documented, review cadence status, any contradictions found.
