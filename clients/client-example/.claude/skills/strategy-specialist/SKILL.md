---
name: strategy-specialist
description: Audit unit economics and goal/KPI setup for campaign viability across 14 diagnostics in 2 modules. Scores 0-100. Execute mode sets goals, revises targets, and generates viability reports.
argument-hint: "[module] [--execute]"
---

# Strategy Specialist Skill

Audits business fundamentals across 2 modules (14 diagnostics) and executes fixes interactively:

**DIAGNOSE (audit):**

| Module | IDs | Method |
|--------|-----|--------|
| **Unit Economics** | D01-D09 | business.md validation + user interview |
| **Goals & KPIs** | D10-D14 | business.md + campaigns.csv + user interview |

**EXECUTE (fix):**

| Action | ID | What it does |
|--------|-----|-------------|
| Calculate unit economics | E01 | Interactive SOP → calculate → update business.md |
| Set goals and KPIs | E02 | Interactive SOP → define goals → update business.md |
| Recalculate unit economics | E03 | Re-run E01 with existing values shown for comparison |
| Revise targets | E04 | Compare new economics vs current targets → propose revisions |
| Viability report | E05 | Generate stakeholder-facing report |

## Command Format

```
/strategy-specialist                              # DIAGNOSE: runs both modules
/strategy-specialist unit-economics               # DIAGNOSE: D01-D09 only
/strategy-specialist goals                        # DIAGNOSE: D10-D14 only
/strategy-specialist --execute                    # EXECUTE: guided by DIAGNOSE results
/strategy-specialist --execute unit-economics     # EXECUTE: E01 (or E03 if data exists)
/strategy-specialist --execute goals              # EXECUTE: E02 (or E04 if data exists)
/strategy-specialist --execute viability-report   # EXECUTE: E05 — generate report
```

**Examples:**
- `/strategy-specialist` — Full strategy audit across both modules
- `/strategy-specialist unit-economics` — Quick unit economics health check
- `/strategy-specialist goals` — Goal and KPI validation only
- `/strategy-specialist --execute unit-economics` — Calculate/recalculate unit economics interactively
- `/strategy-specialist --execute goals` — Set or revise goals and KPIs interactively
- `/strategy-specialist --execute viability-report` — Generate stakeholder viability report

---

## Data Sources

| File | Required | Purpose |
|------|----------|---------|
| `context/business.md` | Yes | Core input — vertical, unit economics, goals |
| `context/google-ads/data/campaigns.csv` | For D13 | Bid strategy per campaign (auto-pulled if missing) |
| `context/account-changelog.md` | Recommended | Recent target/budget changes |
| `config/ads-context.config.json` | For D13 | Account IDs for campaigns.csv auto-pull |

---

## Process

---

### Phase 0: Prerequisites & Route

1. **Parse subcommand and flags:**
   - `unit-economics` → D01-D09 only
   - `goals` → D10-D14 only
   - No subcommand (default) → run both modules sequentially
   - `--execute` → EXECUTE mode (skip DIAGNOSE, go directly to Phase 6)
   - `--execute unit-economics` → E01/E03 only
   - `--execute goals` → E02/E04 only
   - `--execute viability-report` → E05 only

2. **Load business.md** — extract and display:
   - Vertical (ecommerce / lead gen / SaaS)
   - Unit Economics section (if running unit-economics module)
   - Goals & KPIs section (if running goals module)
   - Last Updated date
   - If business.md is missing or has no vertical set, STOP: tell user to run `/business-context-gatherer` first

3. **Check account-changelog.md** — scan for recent target, budget, or bid strategy changes (last 7 days). If found, display them.

Display configuration:
```
Strategy Audit Configuration:
  Account: {client name}
  Vertical: {vertical}
  Mode: {unit-economics / goals / full}
  Last Updated: {date} ({X} days ago)
```

---

### Phase 1: Vertical Detection & Module Routing

Determine which diagnostics to run based on vertical:

| Vertical | Unit Economics Diagnostics | Skip |
|----------|---------------------------|------|
| Ecommerce | D01, D02, D08, D09 | D03, D04, D05, D06, D07 |
| Lead Gen | D03, D04, D08, D09 | D01, D02, D05, D06, D07 |
| SaaS | D05, D06, D07, D08, D09 | D01, D02, D03, D04 |

Goals module (D10-D14) runs for all verticals.

---

### Phase 2: Run Diagnostics

**Read `reference/diagnostic-rules-shared.md` first.**

**Then read ONLY the module-specific rules for the requested subcommand:**

| Subcommand | Read these reference files |
|---|---|
| `unit-economics` | `diagnostic-rules-unit-economics.md` + `unit-economics-formulas.md` + `viability-thresholds.md` |
| `goals` | `diagnostic-rules-goals-kpis.md` + `kpi-framework.md` + `bid-targets-par.md` + `bid-strategy-alignment.md` + `goal-quality-checklist.md` |
| Default (both) | Run unit-economics first, then goals. Load and release each module's references before loading the next. |

**Important:** When running both modules (default), do NOT load all reference files at once. Run unit-economics first, then goals — loading each module's references fresh for that phase.

**For each diagnostic:**

1. Check if the required data exists in business.md
2. If data exists → evaluate against thresholds → assign PASS / WARN / FAIL
3. If data is missing → assign ASK status
4. If diagnostic doesn't apply to this vertical → assign SKIP

**For D13 specifically:** Check if `context/google-ads/data/campaigns.csv` exists. If not, auto-pull:

```bash
node .claude/skills/gads-context/scripts/query.js \
  --customer-id={customer_id} \
  --login-customer-id={login_customer_id} \
  --query-file=.claude/skills/gads-context/references/campaigns.gaql \
  --days=30 \
  --output=context/google-ads/data/campaigns.csv
```

After running all diagnostics in a module, display results table:

```
Unit Economics Results ({vertical}):
| ID | Diagnostic | Status | Pts | Details |
|----|-----------|--------|-----|---------|
| D05 | LTV:CAC ratio | FAIL | 0/15 | 1.17:1 at $200 CPA — below 3:1 |
| D06 | CAC payback | WARN | 5/10 | 14.3 months — close to 18mo threshold |
...

Module score: X/Y (Z%) — {grade}
```

---

### Phase 2.5: Interview Gate

After initial diagnostic pass, if any diagnostics have ASK status:

1. **Present the batch:** "I found {X} items that need your input. Want to provide the data now, or skip them?"

2. **If user provides data:**
   - Re-run affected diagnostics with new data
   - Ask: "Want me to update business.md with this data?"
   - If yes, update the relevant section of business.md

3. **If user skips:**
   - Mark as SKIP, exclude from scoring denominator

---

### Phase 3: Score & Log

**Scoring:** Same system as tracking-specialist.

| Severity | Points |
|----------|--------|
| Critical | 15 |
| High | 10 |
| Medium | 5 |

SKIP and ASK (unresolved) diagnostics are excluded from the scoring denominator.

**Grade scale:**
- 90-100%: Excellent
- 70-89%: Good
- 50-69%: Needs Attention
- 0-49%: Critical

**Append to log:** Write entry to `context/analysis/strategy-audit-log.md` using format from `reference/report-template.md`.

---

### Phase 3.5: Peer Report Lookup (MANDATORY before writing the report)

**Don't send the user from one door to the other.** Before recommending any peer-skill handoff in Phase 4, check whether that peer has already produced a fresh report — and if so, **read it and integrate its findings into THIS report** instead of asking the user to re-run.

Strategy is the **B (Business) layer** — the second hard-block in every other skill's constraint cascade after Measurement. That makes peer lookup especially load-bearing here: a fresh tracking-audit confirming measurement is clean upstream is what *validates* that strategy-side hypotheses (break-even CPA, LTV inputs, monthly target feasibility) can be acted on at all. Without that confirmation, an "infeasible target" finding from this audit could just be a measurement artifact.

The whole point of cross-skill awareness is that a user who runs `/tracking-audit` last week and then runs `/strategy-audit` this week sees the tracking findings *quoted inside the strategy report*, not a redundant "go run tracking-specialist" instruction.

#### Freshness windows

| Peer skill | Report file | Fresh window |
|---|---|---|
| `/quality-score-auditor` | `context/analysis/quality-score-audit.md` | ≤ 7 days |
| `/search-term-auditor` | `context/analysis/search-term-audit.md` | ≤ 7 days |
| `/keyword-auditor` | `context/analysis/keyword-audit.md` | ≤ 7 days |
| `/budget-auditor` | `context/analysis/budget-audit.md` | ≤ 7 days |
| `/bidding-auditor` | `context/analysis/bidding-audit.md` | ≤ 7 days |
| `/competitive-analyst` | `context/analysis/competitive-audit.md` | ≤ 14 days |
| `/lp-auditor` | `context/analysis/lp-audit.md` | ≤ 14 days |
| `/offer-auditor` | `context/analysis/offer-audit.md` | ≤ 30 days |
| `/tracking-specialist` | `context/analysis/tracking-audit.md` | ≤ 30 days |
| `/account-auditor` | `context/analysis/account-audit.md` | ≤ 30 days |

#### Procedure for each peer that the routing would otherwise hand off to

1. **Check if the file exists.** If not → keep the handoff as a plain "run `/peer-skill`" line.
2. **If it exists, check the date in the report header against the freshness window.** The report header date is canonical. mtime is a sanity check — if mtime is *older* than the header date, warn the user that something is off.
3. **If fresh:** open the report and read its **executive read / top findings / module scores**. Pull out the 1–3 findings that overlap with this audit's flagged unit-economics inputs, goals, KPIs, or bid-strategy alignment. Use them to:
   - **Enrich the Executive read at the top of `strategy-audit.md`** — quote the peer's score, the headline finding, and the date inline.
   - **Replace** the routing line "run `/peer-skill`" with: **"Review the existing {date} {peer} report at {path} — top finding: '{one-liner}'. Re-run only if you want fresher data."**
   - In Critical Issues / Recommendations, when a peer handoff is the recommended action, quote the peer's specific finding so the user can act without leaving this report.
4. **If stale:** mention "a previous {peer} report exists from {date} but is {N} days old — recommend re-running before relying on it" and keep the handoff as a re-run.
5. **If missing:** standard "run `/peer-skill`" handoff.

#### When a fresh peer report contradicts a strategy hypothesis

Surface contradictions in the Executive read explicitly — never auto-defer or auto-override. Strategy sits at the B layer, so the contradictions to watch for are upstream-vs-downstream:

- A fresh **tracking-audit shows measurement is clean** for the campaigns this audit names — that *validates* a "monthly target infeasible at current CVR" finding here, because the CVR input is trustworthy. Quote it inline.
- A fresh **tracking-audit shows the conversion event is misfiring** on the very campaigns whose CVR this audit used to declare a target unrealistic — the strategy-side conclusion is then unreliable. The strategy report must say so, not silently propose a target revision built on bad data.
- A fresh **bidding-audit shows tCPA targets above this audit's calculated break-even CPA** — quote it; the bid-strategy fix the user should run is downstream of the unit-economics fix this audit names.
- A fresh **lp-audit or quality-score-audit flagging a CVR ceiling** that contradicts the CVR assumption inside a goal feasibility check — surface both numbers and let the user judge.

That cross-skill validation is the entire reason this phase exists. A strategy audit that ignores a fresh tracking or bidding audit produces a confidently-wrong Go/No-Go verdict.

---

### Phase 4: Write Report

Write full report to `context/analysis/strategy-audit.md` using template from `reference/report-template.md`.

This file is regenerated on each run (overwrites previous). The log file preserves history.

**Lead with the Executive read** — the 6-slot prose contract defined in `reference/report-template.md`. Apply Phase 3.5 lookup results to slot 4 (inline-quoted fresh peer findings) and to every line in Recommendations / Critical Issues that points to a peer skill.

Fill in all sections in this order:
1. **Executive read** (prose, ≤300 words, no bullets) — score meaning, 1–3 priorities w/ why, what's NOT a problem, fresh peer findings inline, how-to-read, score trend.
2. Overall score + grade
3. Viability verdict
4. Unit Economics results
5. Goals & KPIs results
6. Critical Issues — with peer findings integrated when fresh
7. Data freshness
8. Recommendations — apply Phase 3.5 results: every line says either "run /peer" (missing/stale) or "review existing {date} report at {path}" (fresh, with the one-liner finding)

---

### Phase 5: Summary & Next Steps

Already written in Phase 4; Phase 5 is the user-facing presentation. The reader should be able to act from the **Executive read alone** — that's the bar. Everything else is reference material.

Print to user in this order:

1. **Executive read** (the prose section from the report — quote it verbatim, don't re-summarize). It already covers score-meaning, this-week priorities w/ why, what's-NOT-a-problem, fresh peer findings inline, how-to-read, score trend.
2. Overall score and grade, mode, run timestamp.
3. Viability verdict (Go / Conditional Go / No-Go).
4. Top 3 issues (FAIL items first, then WARNs) with specific fix actions.
5. **Recommendations / Routing** — apply Phase 3.5 lookup results to every line. Each peer handoff says either "review existing {date} report at {path} (top finding: ...)" or "run `/peer-skill`".
   - If unit economics FAIL → "Fix unit economics before optimizing campaigns"
   - If goals FAIL → "Define clear goals and KPIs"
   - If bid strategy misaligned → "Adjust bid strategies to match goals"
   - If all PASS → "Business fundamentals are solid — move to next constraint bucket"
6. Note location of full report: `context/analysis/strategy-audit.md`.

**Log to memory:** Append entry to `context/memory/YYYY-MM-DD.md` using format from `reference/report-template.md`.

**DIAGNOSE → EXECUTE bridge:** If DIAGNOSE found FAIL items with corresponding EXECUTE actions, suggest them:

| DIAGNOSE Result | Suggested EXECUTE |
|----------------|-------------------|
| D01-D07 FAIL (unit economics) | "Run `/strategy-audit --execute unit-economics` to calculate/fix" |
| D09 FAIL (stale) | "Run `/strategy-audit --execute unit-economics` to recalculate" |
| D10-D11 FAIL (goals missing) | "Run `/strategy-audit --execute goals` to define goals" |
| D12 FAIL (targets infeasible) | "Run `/strategy-audit --execute goals` to revise targets" |
| Multiple FAILs | Suggest unit economics first (upstream), then goals |

---

### Phase 6: EXECUTE Mode

**Triggered by `--execute` flag.** Skips DIAGNOSE phases (1-5) and goes directly to interactive execution.

**Read `reference/diagnostic-rules-shared.md` first for context.**

**Route based on subcommand:**

| Subcommand | Action | Reference file | Determines E01 vs E03 / E02 vs E04 |
|---|---|---|---|
| `unit-economics` | Calculate/recalculate unit economics | `reference/execute-unit-economics.md` | If business.md has Unit Economics data → E03 (recalculate, show old vs new). If empty → E01 (first-time). |
| `goals` | Set/revise goals and KPIs | `reference/execute-goals-kpis.md` | If business.md has Goals section → E04 (revise). If empty → E02 (first-time). |
| `viability-report` | Generate stakeholder report | `reference/execute-viability-report.md` | Always E05. |
| No subcommand | Ask user what to fix | — | Present options: unit economics, goals, or viability report. |

**For each EXECUTE action, follow the detailed flow in the corresponding reference file.**

**Critical rules for EXECUTE mode:**

1. **Only modify Unit Economics and Goals & KPIs sections** of business.md — never touch other sections
2. **Always ask permission** before writing to business.md
3. **Always update the `Last Updated` date** in the Account section when modifying business.md
4. **Show old vs new comparison** when recalculating (E03/E04)
5. **Preserve existing Conversion Action Values** in the Unit Economics section when updating
6. **Log to memory** after completing any EXECUTE action

**After EXECUTE completes:**
- Suggest running `/strategy-audit` (DIAGNOSE) to verify the fixes
- Log the action to `context/memory/YYYY-MM-DD.md`
