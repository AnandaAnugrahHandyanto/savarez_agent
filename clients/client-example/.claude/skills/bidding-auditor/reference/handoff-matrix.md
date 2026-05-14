# Bidding Auditor — Handoff Matrix

9-layer routing table. Layers are ordered by priority — Measurement > Business > Volume > Efficiency > Conversion > Budget > Competitive > Structural > Traffic.

**Before using this table for a handoff, run Phase 3.5 (Peer Report Lookup)** — if a peer skill has a fresh report at the path below, quote its findings instead of asking the user to re-run.

| Layer | Type | Trigger | Handoff (peer skill) | Existing report to check first | Fresh window |
|---|---|---|---|---|---|
| **M — Measurement** | BLOCKING | BID-D26 fires; tracking gaps on flagged campaigns; M1 hypothesis active | `/tracking-specialist` | `context/analysis/tracking-audit.md` | ≤ 30 days |
| **B — Business** | BLOCKING for target validation | break-even missing/placeholder; primary KPI undefined | `/strategy-audit --execute unit-economics` | `context/analysis/strategy-audit.md` | ≤ 30 days |
| **Vol — Conversion Volume** | Sequenced (sub-cascade with options menu) | BID-D03 below volume threshold | Self-resolve via `/bidding-optimizer setup`, OR `/keyword-auditor expand`, OR `/budget-optimizer raise`, OR wait | `context/analysis/keyword-audit.md` (for expand path) | ≤ 7 days |
| **Eff — Efficiency Recovery** | Sequenced | Eff1/Eff2/Eff3 hypotheses active | `/search-term-auditor`, `/keyword-auditor`, `/quality-score-auditor`, `/rsa-maker` | `search-term-audit.md`, `keyword-audit.md`, `quality-score-audit.md` | ≤ 7 days each |
| **Conv — Conversion** | Sequenced | Low CVR | `/lp-auditor`, `/offer-auditor` | `lp-audit.md` (≤14d), `offer-audit.md` (≤30d) | see ref |
| **Bud — Budget peer** | Sequenced | budget-lost IS > 30%; BID-D17 conflict | `/budget-auditor` (lost share); `/bidding-optimizer fix-shared-portfolio` (D17) | `context/analysis/budget-audit.md` | ≤ 7 days |
| **Comp — Competitive** | Informational | BID-D22 / BID-D23 | `/competitive-analyst` | `context/analysis/competitive-audit.md` | ≤ 14 days |
| **Struct — Structural** | Informational | BID-D11 / BID-D14 | `/account-changelog`, `/account-auditor` | `context/analysis/account-audit.md` | ≤ 30 days |
| **T — Traffic (own optimizer)** | Last | Cascade cleared OR all higher layers explicitly overridden | `/bidding-optimizer ...` | n/a | n/a |

**Handoff phrasing rules** (Phase 4 applies these):

- Fresh peer report exists → "Review the existing {date} {peer} report at `{path}` — top finding: {one-line}. Re-run only if you want fresh data."
- Stale peer report exists → "A previous {peer} report from {date} is {N} days old — re-run via `/{peer-skill}` for current state."
- No peer report → "Run `/{peer-skill}` first."

## Per-diagnostic handoff routing

| Diagnostic | Handoff (in cascade order) |
|---|---|
| BID-D01 mismatch | `/bidding-optimizer setup` (after Vol cleared) |
| BID-D02 manual on volume | Manual: Google Ads UI → Drafts & Experiments (50/50, 14–30d, promote on KPI win) |
| BID-D03 below volume | Vol options menu |
| BID-D04 INFO | none |
| BID-D05 / BID-D06 break-even | B → `/strategy-audit`; T → `/bidding-optimizer adjust-targets` |
| BID-D07 PAR | T → `/bidding-optimizer adjust-targets` |
| BID-D08 deviation | Eff → search-term/QS/LP first; T → optimizer |
| BID-D09 starvation | Bud (if also budget-limited); T → `/bidding-optimizer adjust-targets --rationale=starvation-recovery` |
| BID-D10 / D13 learning | none — wait |
| BID-D11 changes during learning | none — wait, hard refuse on optimizer |
| BID-D12 exclusion gap | `/tracking-specialist` |
| BID-D14 mixed portfolio | Struct → `/account-auditor` |
| BID-D15 / D16 cap | T → `/bidding-optimizer cpc-cap` |
| BID-D17 shared+portfolio | T → `/bidding-optimizer fix-shared-portfolio` |
| BID-D18–D21 modifiers | T → `/bidding-optimizer remove-adjustments` (mCPC) or `/bidding-optimizer modifiers` |
| BID-D22 / D23 CPC | Comp → `/competitive-analyst` |
| BID-D24 simulator gap | T → `/bidding-optimizer scale` paired with `/budget-optimizer raise` |
| BID-D25 unused value rules | T → `/bidding-optimizer value-bidding` |
| BID-D26 rules vs tracking | M → `/tracking-specialist` (blocking) |
