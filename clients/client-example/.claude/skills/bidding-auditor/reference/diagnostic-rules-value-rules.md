# Module 7 — Conversion Value Rules (BID-D25, BID-D26)

Total module weight: 10 points.

## BID-D25 — Rules on Non-Value Campaigns (5 pts)

**Logic:** If `conversion-value-rules.csv` has active rules but the account has zero campaigns on a value-based strategy (TARGET_ROAS / MAXIMIZE_CONVERSION_VALUE), the rules are unused and may indicate a misconfiguration → WARN.

**Verdict map:**

| Active rules | Value-based campaigns | Verdict |
|---|---|---|
| 0 | any | SKIP |
| ≥1 | 0 | WARN |
| ≥1 | ≥1 | PASS |

## BID-D26 — Rules Substituting for Tracking (5 pts)

**Goal:** Detect value rules that look like band-aids for missing tracking — e.g., "boost mobile by 1.5x" that exists only because mobile conversions are under-counted.

**Verdict:** INFO with a high-tone handoff. The auditor cannot conclusively decide; the call is "if these rules correct for under-counted segments instead of true value differences, route to `/tracking-specialist` to fix the source rather than the symptom."

**Routing:** Always offer `/tracking-specialist` when value rules exist. Cascade layer: M (Measurement) — blocking for any optimizer mutation that touches the affected campaigns.
