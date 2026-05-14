# Competitive Analyst — Report Template

**Purpose:** Shape the Phase 3 report around the hypothesis list produced by `synthesis-playbook.md` and the peer findings produced by Phase 2.5, not around the flat diagnostic list. The reader must see the **Executive read** and **strategic verdict** before the evidence tables, and **actions** must be segmented by economic viability — not presented as a flat fix-it list.

The report is **explain-then-action**: a reader who only reads the Executive Read at the top should still leave with the right next move. Tables and module breakdowns are reference material for when the reader wants to dig in.

## Full report: `context/analysis/competitive-audit.md`

```markdown
# Competitive Position Audit — {client_name}
**Date:** {date} | **Period:** {start} → {end} ({period} days, {lag}-day conversion lag)
**Campaigns:** {count} Search, {count} Shopping | **Keywords:** {count} | **Flags:** {count}

---

## Executive read

{Prose only, no bullet lists, ≤300 words. Direct, confident, plain language. Cover all 6 slots in order:}

{**Slot 1 — Score meaning.** State what the score means in plain language for this account, not just the band name. "62/100 — Needs Attention" tells the reader nothing; "62/100 means three campaigns are losing two-thirds of their impressions to competitors who are bidding harder, but the path back depends on whether the rank loss is a QS problem or a bid problem" tells them what to do. Name the dominant pattern: rank-lost-IS spike, a new auction entrant on branded, a top-of-page rate gap, IS trajectory degrading on Shopping, etc.}

{**Slot 2 — 1–3 things to do this week, ranked, each with the *why*.** Prose form. Name the lever, name the evidence, name the expected impact. Example: "First, confirm whether the rank loss on Campaign X is QS-driven by checking ad relevance and LP experience — if it is, fixing QS gains IS without raising CPC, the cheapest win available." If the audit found nothing actionable: "Nothing urgent this week — competitive position is stable and economics support current bids."}

{**Slot 3 — What is NOT a problem** (so red text below doesn't waste attention). Call out SKIPs (e.g., "PMax campaigns don't expose IS — that's not a tracking gap, it's an API limitation"), deliberate-but-flagged choices (Max Conv intentionally trading IS for efficiency), and false-alarm risks. If no false-alarm risks: "No red findings worth ignoring — every flagged item is real."}

{**Slot 4 — Inline-quoted fresh peer findings from Phase 2.5.** Quote the peer's score, date, and the specific top-line finding when one overlaps a flagged campaign or keyword. Especially important for QS / budget / bidding peers — competitive findings are typically *explainers*, and a fresh peer report often rewrites the diagnosis. Example: "A fresh quality-score audit from {date} ({N} days old) flagged Campaign X with QS 4/10 driven by Landing Page Experience — the rank-lost IS we're seeing is QS-driven, not bid-driven. The action is to fix LP experience, not to raise bids." Or: "A {date} bidding audit shows tCPA was tightened 3 days ago on Campaign Y — the rank loss is intentional, not a problem to solve." If no peers were fresh, omit this slot.}

{**Slot 5 — One line on how to read the rest.** "The Diagnosis section names the strategic verdict; Business Economics Context shows whether each campaign can afford more IS; the Actions section sequences fixes by economic viability."}

{**Slot 6 — Score trend.** "Score: 62/100 — down from 71/100 last run. The drop is driven by Module 2 (Competitive Position) — rank-lost IS climbed on non-branded campaigns." Read from `competitive-audit-log.md` to compute. If no prior entry: "Baseline run — no prior score to compare against."}

---

## 1. Score Summary

| Overall | Grade |
|---------|-------|
| **{score} / 100** | **{grade}** |

| Module | Points | Max | Score | Grade | Key Finding |
|--------|--------|-----|-------|-------|-------------|
| IS Health & Trends | {x} | 30 | {pct}% | {grade} | {1-line} |
| Competitive Position | {x} | 35 | {pct}% | {grade} | {1-line} |
| Competitive Impact | {x} | 35 | {pct}% | {grade} | {1-line} |

---

## 2. Diagnosis

{1-2 paragraphs — the root-cause hypothesis, NOT a symptom list. This is the reader's biggest takeaway. Written as business advice, not a diagnostic readout.

Start with the strategic verdict from SA3: "Compete aggressively" / "Fix economics first" / "Selective competition" / "Structural challenge."

Then connect the dots between IS data, business economics, and QS/rank findings. Example:

"**Verdict: Fix economics first.** Non-branded campaigns are losing 88-90% of impressions to rank, but CPA is already $390 — nearly 2x your $200 target and 5x the $78 break-even. Gaining IS through higher bids would accelerate losses, not growth. At 6.1% CVR and $5.30 avg CPC, the implied CPA floor is $87, already above break-even. The competitive pressure is real, but the path to more IS runs through conversion economics (better QS, LP, and offer), not through higher bids. Fix what converts, then compete for more traffic."

Contrast this with the OLD approach (never do this): "All five campaigns lose IS to rank. Route to /keyword-auditor for QS check. Route to /ad-copy-specialist for CTR. Route to /lp-auditor for LP."}

**Top hypothesis ({layer} layer):** {name}
**Confidence:** {high / medium / low}
**Strategic verdict:** {verdict from SA3}

**Secondary hypotheses:**
- {H2 — one-liner}
- {H3 — one-liner}

---

## 3. Business Economics Context

{This section is NEW — it did not exist in the old report. It connects competitive findings to business reality.}

| Metric | Value | Source |
|--------|-------|--------|
| Primary KPI | {CPA or ROAS} | config / business.md |
| Break-even {CPA/ROAS} | {value} | business.md unit economics |
| Target {CPA/ROAS} | {value} | business.md goals |
| Growth mode | {yes/no} | business.md goals |

### Campaign Economics

| Campaign | Spend | Conv | CPA | Target | Headroom | Implied CPA Floor | Viable? |
|----------|-------|------|-----|--------|----------|-------------------|---------|
| {name} | ${x} | {n} | ${cpa} | ${target} | ${headroom} | ${floor} | {Yes/No/Marginal} |

{For each campaign, one line explaining the economic reality:
- "CPA $42 vs $200 target — $158 headroom. IS recovery via bids is economically viable."
- "CPA $390 vs $200 target — $190 over target. Cannot afford to bid higher. Fix conversion economics first."}

### Keyword Economics (top 20)

| Keyword | Campaign | Spend | CPA | IS | Rank-Lost | CTR | Economic Status |
|---------|----------|-------|-----|----|-----------|-----|-----------------|
| {kw} | {camp} | ${x} | ${cpa} | {is}% | {rl}% | {ctr}% | {BID-CONSTRAINED / QS-CONSTRAINED / HIGH-VALUE-TARGET / FIX-ECONOMICS-FIRST} |

{Economic status labels from QS2 in synthesis playbook. Each keyword gets a label that tells the reader what to do with it.}

---

## 4. Evidence Ladder

Grouped by cascade layer. Only layers with active hypotheses appear.

### Data Validation {check or warning}
- **DV1 — Campaign maturity:** {findings or "all campaigns have sufficient data"}
- **DV2 — Bidding strategy context:** {note that Max Conv/tCPA strategies may intentionally trade IS for efficiency}
- **DV3 — Conversion sufficiency:** {any low-conv campaigns flagged}

### Business Economics {check or warning}
- **BE1 — CPA/ROAS headroom:** {per-campaign headroom analysis. THIS IS THE KEY EVIDENCE.}
- **BE2 — Implied CPA floor:** {floor vs break-even per campaign}
- **BE3 — Budget headroom:** {cross-reference with CA-D02 budget-lost IS}
- **BE4 — IS recovery ROI:** {marginal CPA estimate for recovered IS}

### QS & Rank Diagnosis {check or warning}
- **QS1/QS2 — QS assessment:** {direct QS from keyword audit, or CTR/CPA proxy analysis}
- **QS3 — Data gap:** {recommend /keyword-auditor if QS data would sharpen diagnosis}

### Strategic Assessment
- **SA1 — Campaign prioritization:** {ranked list of where to invest IS recovery effort}
- **SA2 — Competitive entry response:** {branded CPC pressure response if CA-D11 active}
- **SA3 — Market position verdict:** {the verdict with reasoning}

---

## 5. IS Trend Dashboard

{Same as before — campaign-level trajectory table. This is reference data, no longer the lead section.}

| Campaign | Type | Bidding | Days | F30 IS | L30 IS | 30d Delta | Trajectory |
|----------|------|---------|------|--------|--------|-----------|------------|
| ... | ... | ... | ... | ... | ... | ... | ... |

---

## 6. IS Loss Decomposition

{Same table as before, but now with economic context added.}

| Campaign | Budget-Lost | Rank-Lost | Combined | Dominant | CPA | Can Afford More IS? |
|----------|------------|-----------|----------|----------|-----|---------------------|
| ... | ... | ... | ... | ... | ... | {Yes/No + reason} |

{The "Can Afford More IS?" column is the synthesis column — it connects the IS finding to business reality. Example: "No — CPA $390 already 2x target" or "Yes — CPA $42, $158 headroom."}

---

## 7. Top-of-Page Position Analysis

{Same as before — per-campaign abs-top IS table.}

---

## 8. Keyword Competitive Pressure

{Same top-20 table as before, but with economic status column added from Section 3.}

---

## 9. Shopping Ad Group Breakdown

{Same as before — conditional on Shopping campaigns.}

---

## 10. CPC-Competition Correlation

{Same as before — per-campaign correlation analysis. But now with SA2 competitive entry response included inline for branded campaigns.}

---

## 11. KPI Impact Estimate

{Same metric tree as before, BUT with economic reality check added:}

**Total estimated impact: ~{N} conversions lost, ~${value}**

| Campaign | IS Gap | Lost Conv | Lost Value | Current CPA | Recovery CPA | Viable? |
|----------|--------|-----------|-----------|-------------|-------------|---------|
| ... | ... | ... | ... | ... | ... | ... |

{Recovery CPA = estimated CPA to capture those lost conversions (from BE4). If Recovery CPA > target CPA, note: "Recovering these conversions at current economics would cost ${recovery_cpa}/conv — above the ${target_cpa} target. Fix conversion economics before chasing IS."}

---

## 12. Skipped Diagnostics

{Same as before.}

---

## 13. Competitor Ad Copy Insights

{Same as before — conditional on /competitor-ads data.}

---

## 14. Actions — segmented by cascade state

{NEVER a flat table. Always segmented by economic viability and cascade layer.}

### Investigate first (resolve before acting)

{Populated when Layer 1 or Layer 3 raises unresolved questions.}

| # | Action | Skill | Why this first |
|---|--------|-------|----------------|
| 1 | {description} | `{/skill}` | {what it resolves and what it unblocks} |

### Fix economics first (structural — before any IS recovery)

{Populated when BE1 headroom is negative. This is the KEY DIFFERENCE from the old report.}

| # | Action | Skill | What it fixes | Expected impact |
|---|--------|-------|---------------|-----------------|
| 1 | Improve QS on {N} flagged keywords — QS gains raise IS without increasing CPC | `/keyword-auditor` | Rank loss via ad relevance | IS improvement + lower CPC |
| 2 | Audit LP conversion rate on {campaigns} | `/lp-auditor` | CVR improvement lowers CPA, creates bid headroom | CPA reduction |
| 3 | Audit offer quality — competitor messaging winning on {angle} | `/offer-auditor` | CVR improvement | CPA reduction |
| 4 | Review campaign targets vs business economics | `/strategy-specialist` | Validate whether targets are achievable | Strategic clarity |

{Frame these as: "Fix what converts, THEN compete for more traffic."}

### Compete where viable (tactical IS recovery)

{Populated ONLY for campaigns/keywords where BE1 headroom > 0 or where QS improvement path is clear.}

| # | Action | Scope | Skill | Rationale |
|---|--------|-------|-------|-----------|
| 1 | {description} | {campaigns/keywords} | `{/skill}` | CPA ${x} with ${y} headroom — can afford to compete |

### Strategic discussion (escalation)

{Populated when SA3 verdict is "fix economics first" or "structural challenge" AND CA-D13 > 10%.}

| # | Action | Skill | Context |
|---|--------|-------|---------|
| 1 | {N} conversions at risk but CPA is {X}x target — this needs strategic discussion, not tactical fixes | `/strategy-specialist` | {summary} |

### Monitor (stable, no action needed)

{Populated for findings that are stable or immaterial (<2% impact).}

- {finding — why no action needed}
```

---

## Append to audit log `context/analysis/competitive-audit-log.md`

Append this entry to the log file. Create the file with `# Competitive Audit Log` header if it doesn't exist.

```markdown
## {YYYY-MM-DD} — Score: {score}% ({grade})

- **Period:** {period} days | **Campaigns:** {count} | **Keywords:** {count}
- **Strategic verdict:** {SA3 verdict — Fix economics first / Compete aggressively / Selective competition / Structural challenge}
- **Top finding:** {1-line — the single most impactful hypothesis or "Clean — competitive position stable"}
- **Fresh peer reports integrated:** {comma-separated list of peer skills + dates whose findings were inline-quoted in this run, e.g., "/quality-score-auditor (2026-04-28), /bidding-auditor (2026-04-30)"; or "none"}
- **Top hypothesis:** {layer} — {name} (confidence {high/medium/low})
- **Key economics:** avg CPA ${x} vs target ${target} (headroom: ${headroom})

| Module | Score | Key Finding |
|--------|-------|-------------|
| IS Health & Trends | {x}/30 | {1-line} |
| Competitive Position | {x}/35 | {1-line} |
| Competitive Impact | {x}/35 | {1-line} |
```

---

## Language rules for the Diagnosis section

The diagnosis MUST read like business advice from a strategist, not a list of diagnostic codes. Rules:

1. **Lead with the verdict** — "Fix economics first" or "Compete aggressively" or "Selective competition" or "Structural challenge." The reader should know what to do before seeing the evidence.

2. **Connect IS to economics** — never say "you're losing 88% of impressions" without immediately saying what that means for the business at current CPA.

3. **Name the trade-off** — "Gaining IS would cost an estimated ${X}/conv; your target is ${Y}. That's the trade-off."

4. **Recommend the sequence, not the tool** — don't say "run /keyword-auditor." Say "check whether QS is driving the rank loss — if it is, fixing QS gains IS without spending more."

5. **Acknowledge growth mode** — if the account is in growth mode with accepted above-break-even CPA, acknowledge it but quantify the cost: "You're in growth mode, but each additional IS point at current economics costs ${X} in CPA margin."

## Anti-patterns (never do these in the report)

- Flat "Recommended Actions" table with equal-weight rows
- "Route to /skill" without explaining what the user gains from running it
- Presenting 1,049 lost conversions as pure opportunity cost without noting the CPA to recover them
- "Fix rank" without saying whether rank loss is QS-driven or bid-driven
- Recommending bid increases when CPA exceeds target
- Listing 5 handoff skills as a menu: "Which would you like to start with?" — instead, give a sequenced recommendation with reasoning
