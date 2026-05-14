# Handoff Matrix — Search Term Optimizer

This optimizer mutates the live account. Unlike audit-only skills, the handoff is enforced as a **pre-flight gate** before operations are generated, plus an **enrichment layer** on the dry-run output. Two modes:

- **Mode 1 — Pre-flight gate.** Hard-block on dirty Measurement (M) or Business (B) layers. Hard-warn on data-discontinuity peer activity. Soft-warn on cohort-shifting peer activity.
- **Mode 2 — Enrichment.** Surface fresh peer findings on the campaigns / ad groups being mutated inside the dry-run "Cross-skill context" section. The user sees what other skills know about the same surfaces before approving the apply.

The cascade order is **Measurement → Business → Conversion → Traffic → Creative** — fixes upstream of where this skill mutates always take precedence.

---

## Peer Freshness Table (10 peers — excludes `/search-term-auditor`, which is the upstream input)

The optimizer reads each peer's report header date as the canonical freshness signal. If the file is missing or the header date is older than the window, the peer is treated as **stale (no signal)** — neither block nor warn, just absent from the cross-skill context. Never use file mtime — the header date is canonical.

| Peer skill | Report file | Fresh window | Layer |
|---|---|---|---|
| `/quality-score-auditor` | `context/analysis/quality-score-audit.md` | ≤ 7 days | Creative |
| `/keyword-auditor` | `context/analysis/keyword-audit.md` | ≤ 7 days | Traffic |
| `/budget-auditor` | `context/analysis/budget-audit.md` | ≤ 7 days | Traffic |
| `/bidding-auditor` | `context/analysis/bidding-audit.md` | ≤ 7 days | Traffic |
| `/competitive-analyst` | `context/analysis/competitive-audit.md` | ≤ 14 days | Competitive |
| `/lp-auditor` | `context/analysis/lp-audit.md` | ≤ 14 days | Conversion |
| `/offer-auditor` | `context/analysis/offer-audit.md` | ≤ 30 days | Conversion |
| `/tracking-specialist` | `context/analysis/tracking-audit.md` | ≤ 30 days | **M — hard-block if dirty** |
| `/strategy-specialist` | `context/analysis/strategy-audit.md` | ≤ 30 days | **B — hard-block if dirty** |
| `/account-auditor` | `context/analysis/account-audit.md` | ≤ 30 days | Structure |

### Freshness rule

1. The **header date** in each peer report is canonical. Parse it; never substitute file mtime.
2. If the header date is within the fresh window, the peer signal is **active**. Surface it.
3. If the header date is older than the fresh window, the peer signal is **stale** — do not surface as fresh, do not block. The user can choose to re-run that peer.
4. If the header date contradicts other dating in the report body (e.g. body cites pulls from a different date), surface the contradiction in the Cross-skill context section. Never auto-defer to either date — let the user decide.
5. Never auto-run a peer skill from inside the optimizer. Only suggest.

---

## Mode 1 — Pre-Flight Gate

Run before Phase 1 generates `operations.json`. The gate produces one of three outcomes: **proceed**, **proceed-with-soft-warn**, **hard-block / hard-warn**.

### Hard-block (M and B layers)

| Trigger | Action |
|---|---|
| `tracking-audit.md` is fresh AND module score < 70 on attribution / OCT / consent / completeness | **HARD-BLOCK.** Tell the user: "Tracking audit shows {module} at {score}/100. Negating terms while attribution is broken can delete converting traffic. Resolve via `/tracking-specialist` first." Do not generate operations. |
| `tracking-audit.md` missing or stale (> 30 days) | **HARD-BLOCK.** Tell the user: "No fresh tracking audit. Run `/tracking-specialist` first — search-term mutations depend on trustworthy conversion data." |
| `strategy-audit.md` is fresh AND `target_source=fallback` on any campaign in the mutation scope | **HARD-BLOCK.** Tell the user: "Campaign {name} has no real target ({target_source}). Negating traffic without a target compresses the account but does not fix the math. Run `/strategy-specialist` first." |
| `strategy-audit.md` is fresh AND module score < 70 on targets / unit economics | **HARD-BLOCK.** Same template — fix Business layer first. |
| `strategy-audit.md` missing or stale (> 30 days) | **HARD-BLOCK.** "No fresh strategy audit. Run `/strategy-specialist` first — promotions and negations need calibrated targets." |

The user can override a hard-block only by explicit acknowledgment ("proceed despite tracking-dirty"). Never bypass silently.

### Hard-warn (data discontinuity)

| Trigger | Action |
|---|---|
| `account-audit.md` flags a campaign restructure within 14 days on any campaign in mutation scope | **HARD-WARN.** "Campaign {name} was restructured {N} days ago. Performance data on the new structure is not stable — negating or promoting terms based on pre-restructure cohorts will misfire. Recommend deferring this surface for {14-N} more days." Require explicit confirmation. |

### Soft-warn (cohort signal not stabilized)

Soft-warns surface in the Cross-skill context section and in the apply prompt; they do not require explicit override. The user is expected to read them and decide.

See the **Mutation Sensitivity Matrix** below.

---

## Mutation Sensitivity Matrix (search-term-optimizer)

Maps recent peer activity on the **same campaigns / ad groups** the optimizer is about to mutate. Scope match is at the campaign level for shared-list ops (E01, E02, E07, E10) and at the ad-group level for keyword promotions (E03) and conflict / consolidate ops (E04, E05).

| Recent peer activity | Window | Severity | Why it matters |
|---|---|---|---|
| **Keyword changes** on overlapping ad groups (`/keyword-optimizer` writes to changelog within 7d) | ≤ 7 days | soft-warn | Term cohort is shifting. New keywords pull different queries; negating now may target shadows of the old cohort. |
| **Bid / target adjustments** on overlapping campaigns (`/bidding-optimizer` changelog) | 2–7 days | soft-warn | Negatives shift CPL — a tCPA mid-adjustment will re-learn against a moving target. Stack only if you accept the entanglement. |
| **Ad-copy changes** on overlapping ad groups (`/rsa-maker` or QS optimizer activity within 7d) | ≤ 7 days | soft-warn | CTR signal is mid-test. New copy changes which queries match-and-click; promoting terms based on pre-copy CTR is reading old data. |
| **Self mutations** on the same surfaces (`search-term-changelog.md` within 7d) | ≤ 7 days | soft-warn | Don't stack search-term changes. The previous batch hasn't had time to re-equilibrate impressions and conversions. |
| **Campaign restructure** on overlapping campaigns (account-audit flag) | ≤ 14 days | **hard-warn** | Data discontinuity. Pre-restructure performance does not generalize. |
| **QS optimization activity** on overlapping ad groups (quality-score-audit findings acted on within 7d) | ≤ 7 days | soft-warn | Cohort signal not stabilized — relevance and LP changes shift which terms convert. Promotions especially are noisy here. |

### Severity definitions

- **soft-warn**: surfaced in Cross-skill context section + apply prompt. Does not require explicit override. User decides.
- **hard-warn**: surfaced explicitly. Optimizer prompts: "Recent {activity} on {surface} within {window} — recommend deferring. Proceed anyway? (y/N)". Default is no.
- **hard-block**: refuses to generate operations. Explained above.

---

## Mode 2 — Enrichment (Cross-skill context)

The dry-run output (Phase 2) includes a "Cross-skill context" section that quotes fresh peer findings on the campaigns / ad groups in the mutation scope. Format:

```
## Cross-skill context

Mutation scope: {N} campaigns, {M} ad groups.

Fresh peer signals on this scope:
- /keyword-auditor (3 days old): KW-D04 cannibalization on {ad_group} — promotion ST-E03 here would deepen overlap.
- /bidding-auditor (5 days old): tCPA learning state on {campaign} — soft-warn (negatives shift CPL during learning).
- /quality-score-auditor (2 days old): {ad_group} ad-relevance LOW — negating long-tail here may improve QS within 14d.

Stale peer signals (consider re-running):
- /lp-auditor: report from 22 days ago, fresh window is 14 days.

No fresh signal from: /competitive-analyst, /offer-auditor, /account-auditor.
```

### Quoting rules

- Only surface findings on the same campaigns / ad groups the optimizer will touch. Filter peer reports by scope match.
- Quote one-line summaries per finding — module + diagnostic ID + one-clause why.
- If a peer report is stale, list it as "stale, consider re-running" — do not quote stale findings as fresh.
- If two peer reports contradict (e.g. keyword-auditor says cannibalization, search-term-auditor says safe to promote), surface both and let the user decide. Never auto-defer.

---

## Canonical skill names

Always use these names — no aliases, no abbreviations:

- `/tracking-specialist`
- `/strategy-specialist`
- `/quality-score-auditor`
- `/keyword-auditor`
- `/budget-auditor`
- `/bidding-auditor`
- `/competitive-analyst`
- `/lp-auditor`
- `/offer-auditor`
- `/account-auditor`
- `/search-term-auditor`
- `/search-term-optimizer`

---

## Cascade enforcement

The pre-flight gate enforces Measurement → Business → Conversion → Traffic → Creative. If any layer is dirty:

1. **M dirty** → hard-block, route to `/tracking-specialist`.
2. **B dirty** → hard-block, route to `/strategy-specialist`.
3. **Conversion / Traffic / Creative peer activity recent** → soft-warn or hard-warn per the Mutation Sensitivity Matrix.
4. **All clear** → proceed to Phase 1, attaching Cross-skill context to the dry-run.

The optimizer never auto-runs a peer skill. It only blocks, warns, or quotes.
