# Diagnostic Rules — Unit Economics (D01-D09)

Read during Phase 2 when running `/strategy-specialist unit-economics` or `/strategy-specialist` (default).
Read `diagnostic-rules-shared.md` first. Load `unit-economics-formulas.md` and `viability-thresholds.md` alongside this file.

## Module Scoring

| ID | Diagnostic | Severity | Pts | Verticals |
|----|-----------|----------|-----|-----------|
| D01 | Gross margin adequacy | Critical | 15 | Ecommerce |
| D02 | Break-even ROAS calculation | Critical | 15 | Ecommerce |
| D03 | Lead-to-sale rate | Critical | 15 | Lead Gen |
| D04 | Deal value adequacy | High | 10 | Lead Gen |
| D05 | LTV:CAC ratio | Critical | 15 | SaaS |
| D06 | CAC payback period | High | 10 | SaaS |
| D07 | Monthly churn | High | 10 | SaaS |
| D08 | Viability verdict | Critical | 15 | All |
| D09 | Unit economics staleness | Medium | 5 | All |

---

## D01: Gross Margin Adequacy
**Severity:** Critical (15 pts)
**Vertical:** Ecommerce only
**Data:** business.md > Unit Economics > Gross Margin %
**Formula reference:** `unit-economics-formulas.md` > Ecommerce Formulas

**Check:** Is gross margin documented and above minimum threshold for viable Google Ads campaigns?

**PASS:** Gross margin >= 30%. Break-even ROAS <= 333%. Scaling headroom exists.
**WARN:** Gross margin 20-29%. Break-even ROAS 334-500%. "Margins are tight — limited scaling headroom. Consider pricing or COGS optimization."
**FAIL:** Gross margin < 20%. Break-even ROAS > 500%. "Margins likely cannot support profitable Google Ads at scale."
**ASK:** Gross margin not documented in business.md. Ask: "What is your gross margin percentage? (Revenue minus COGS, shipping, and payment fees, divided by revenue)"

**Details to report:** Gross margin %, calculated break-even ROAS, AOV if available.

---

## D02: Break-even ROAS Calculation
**Severity:** Critical (15 pts)
**Vertical:** Ecommerce only
**Data:** business.md > Unit Economics > Break-even ROAS (or calculated from gross margin)
**Formula reference:** `unit-economics-formulas.md` > Ecommerce Formulas

**Check:** Is break-even ROAS explicitly calculated and documented? Is it achievable given market benchmarks?

**PASS:** Break-even ROAS is documented AND is <= 333% (or target ROAS in business.md is above break-even with room).
**WARN:** Break-even ROAS is documented but 334-500%. Or: break-even ROAS not explicitly documented but calculable from gross margin.
**FAIL:** Break-even ROAS > 500%. Or: no margin data exists to calculate break-even.
**ASK:** Neither break-even ROAS nor gross margin is documented. Ask: "What is your gross margin percentage so we can calculate your break-even ROAS?"

**Details to report:** Break-even ROAS, target ROAS (if set), gap between them.

---

## D03: Lead-to-Sale Rate
**Severity:** Critical (15 pts)
**Vertical:** Lead Gen only
**Data:** business.md > Unit Economics > Lead-to-Sale Rate (or equivalent funnel conversion rates)
**Formula reference:** `unit-economics-formulas.md` > Lead Gen Formulas

**Check:** Is the lead-to-sale rate documented and above minimum viable threshold?

**PASS:** Lead-to-sale rate >= 15%. Target CPL has adequate headroom for competitive bidding.
**WARN:** Lead-to-sale rate 10-14%. "Sales conversion is below average — target CPL will be compressed. Monitor closely."
**FAIL:** Lead-to-sale rate < 10%. "Low lead-to-sale rate severely compresses target CPL. Fix sales process before scaling Google Ads."
**ASK:** Lead-to-sale rate not documented. Ask: "What percentage of your leads convert to paying customers? (Closed deals / total leads generated)"

**Details to report:** Lead-to-sale rate, calculated max CPL, deal value used.

---

## D04: Deal Value Adequacy
**Severity:** High (10 pts)
**Vertical:** Lead Gen only
**Data:** business.md > Unit Economics > Average Deal Value + Profit Margin
**Formula reference:** `unit-economics-formulas.md` > Lead Gen Formulas

**Check:** Does the deal value and margin combination support a viable target CPL?

**PASS:** Calculated max CPL > €50 (enough room for competitive Search bidding).
**WARN:** Calculated max CPL €30-50. "CPL ceiling is tight — limited to highly targeted, bottom-of-funnel campaigns only."
**FAIL:** Calculated max CPL < €30. "Deal value and margin cannot support competitive Google Ads CPLs."
**ASK:** Deal value or profit margin missing. Ask: "What is your average deal value and profit margin percentage?"

**Calculation:** Max CPL = Deal Value x Profit Margin % x Lead-to-Sale Rate

**Details to report:** Deal value, profit margin, max CPL, max CAC.

---

## D05: LTV:CAC Ratio
**Severity:** Critical (15 pts)
**Vertical:** SaaS only
**Data:** business.md > Unit Economics > LTV, CAC (or Target CPA used as proxy)
**Formula reference:** `unit-economics-formulas.md` > SaaS Formulas

**Check:** Is the LTV:CAC ratio documented and above the 3:1 golden rule?

**PASS:** LTV:CAC >= 3:1. Healthy, sustainable scaling.
**WARN:** LTV:CAC 2:1 - 3:1. "Warning zone — thin margins. Reduce CAC or improve retention."
**FAIL:** LTV:CAC < 2:1. "Danger zone — barely breaking even or losing money per customer."
**ASK:** LTV or CAC not documented. Ask: "What is your LTV and current CAC? (Or provide ARPU, churn rate, and gross margin so we can calculate)"

**If business.md has a Target CPA but no actual CAC:** Calculate LTV:CAC using Target CPA as the denominator. Note: "Using target CPA as CAC proxy — actual CAC may differ."

**Details to report:** LTV, CAC (or target), LTV:CAC ratio, max CAC (LTV/3).

---

## D06: CAC Payback Period
**Severity:** High (10 pts)
**Vertical:** SaaS only
**Data:** business.md > Unit Economics > CAC Payback (or calculable from ARPU, margin, CAC)
**Formula reference:** `unit-economics-formulas.md` > SaaS Formulas

**Check:** Is the CAC payback period within acceptable range?

**PASS:** CAC payback < 12 months. Good — standard SaaS benchmark.
**WARN:** CAC payback 12-18 months. "Cash flow pressure — payback is slow. Monitor carefully and consider reducing CAC."
**FAIL:** CAC payback > 18 months. "Problematic — liquidity risk. Customer lifetime may not justify acquisition cost."
**ASK:** Payback not documented and cannot be calculated from available data. Ask: "What is your ARPU and gross margin percentage?"

**Calculation:** CAC Payback = CAC / (ARPU x Gross Margin %)

**Details to report:** CAC payback in months, ARPU, gross margin %, CAC used.

---

## D07: Monthly Churn
**Severity:** High (10 pts)
**Vertical:** SaaS only
**Data:** business.md > Unit Economics > Monthly Churn Rate
**Formula reference:** `unit-economics-formulas.md` > SaaS Formulas

**Check:** Is monthly churn documented and below the 5% threshold?

**PASS:** Monthly churn < 5%. Average or better retention.
**WARN:** Monthly churn 5-8%. "Below average retention — customer lifetime is compressed, which limits LTV and max CAC."
**FAIL:** Monthly churn > 8%. "Critical retention problem — fix product before scaling acquisition. Customer lifetime: {1/churn} months."
**ASK:** Churn not documented. Ask: "What is your monthly customer churn rate?"

**Details to report:** Monthly churn rate, calculated customer lifetime, impact on LTV.

---

## D08: Viability Verdict
**Severity:** Critical (15 pts)
**Vertical:** All
**Data:** Results of D01-D07 (whichever are applicable for the vertical)
**Reference:** `viability-thresholds.md`

**Check:** Overall advertising viability assessment based on aggregated unit economics diagnostics.

This is a **composite diagnostic** — it reads the results of D01-D07 and produces an overall verdict.

**Logic:**

1. Collect results of all active (non-SKIP) unit economics diagnostics for this vertical
2. If any ASK diagnostics remain unanswered: verdict = "Incomplete — missing data"
3. Apply viability thresholds from `viability-thresholds.md`

**PASS (Go):** All active vertical diagnostics PASS. Business fundamentals fully support advertising.
**WARN (Conditional Go):** At least one WARN, no FAILs. "Viable with known risks." List the risk factors.
**FAIL (No-Go):** Any FAIL on a Critical-severity diagnostic. "Business fundamentals may not support profitable Google Ads."

**If business.md already has a Viability Assessment section:** Compare your verdict with the existing one. If they disagree, note the discrepancy and explain why.

**Details to report:**
- Verdict: Go / Conditional Go / No-Go
- Contributing factors (which diagnostics drove the verdict)
- Risk factors (what could worsen the verdict)
- Required changes (what the client needs to fix for the verdict to improve)

---

## D09: Unit Economics Staleness
**Severity:** Medium (5 pts)
**Vertical:** All
**Data:** business.md > Account > Last Updated field

**Check:** Were unit economics reviewed within the last 90 days?

**PASS:** Last Updated date is within 30 days. Unit economics are fresh.
**WARN:** Last Updated date is 31-90 days ago. "Unit economics should be reviewed soon — inputs may have changed."
**FAIL:** Last Updated date is > 90 days ago or missing. "Unit economics are stale — recalculate before making decisions based on these numbers."

**Calculation:** Compare today's date against the "Last Updated" field in business.md > Account section.

**Details to report:** Last updated date, days since update.
