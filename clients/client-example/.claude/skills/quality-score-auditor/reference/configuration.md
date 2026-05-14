# Quality Score Auditor — Configuration Reference

Every value the skill reads or writes in `config/ads-context.config.json`.

---

## Top-level shared keys

| Key | Type | Description |
|---|---|---|
| `accountCurrency` | string (ISO-4217) | Currency for all money formatting in the report and analyzer outputs (`USD`, `EUR`, `GBP`, …). Shared with `budget-auditor` and other peers — write at the top level, never inside `qualityScoreAudit`. Defaults to `USD` with a one-line warning if missing. Phase 0.0 Branch B prompts for it; analyzer scripts resolve it via `scripts/lib.js → resolveAccountCurrency`. |

---

## Owned keys (written by this skill — Phase 0.0)

### `qualityScoreAudit`

```json
{
  "qualityScoreAudit": {
    "primaryKPI": "cpa | roas",
    "competitorCampaigns": ["Conquest - CRM", "..."],
    "competitorBrands": ["hubspot", "salesforce"],
    "evaluationPeriod": 30,
    "historicalPeriod": 180,
    "thresholds": {
      "impressionWeightedQsFail": 5.0,
      "impressionWeightedQsWarn": 6.9,
      "lowQsKeywordPct": 10,
      "highSpendPercentile": 80,
      "nullQsWarnPct": 30,
      "dominantComponentPct": 50,
      "qsTrendWarnPoints": 1,
      "qsTrendFailPoints": 2,
      "lostIsRankThresholdPct": 15,
      "lostIsRankQsCeiling": 6,
      "cpcPremiumPct": 30,
      "minImpressionsForStableQs": 1000,
      "brandLowQsCeiling": 8,
      "minWeeksForTrend": 4,
      "minImpressionsPerWeek": 25,
      "modernSearchMinWeeklyImpressions": 300
    },
    "lastConfirmed": "YYYY-MM-DD",
    "businessMdHash": "first-16-chars-of-sha256"
  }
}
```

| Key | Source | Purpose |
|---|---|---|
| `primaryKPI` | Reused from `keywordAudit.primaryKPI` if present; else Phase 0.0 interview | Context for bidding-mode severity; QS fixes are framed against CPA or ROAS targets |
| `competitorCampaigns` | Phase 0.0 interview (campaign-name scan + confirmation) | Classifier assigns `class=COMPETITOR` — suppresses AR Below-Avg findings |
| `competitorBrands` | Phase 0.0 interview | Optional — kept for future keyword-text-level competitor detection |
| `evaluationPeriod` | User-confirmed (30 / 60 / 90; default 30) | Point-in-time period for M1/M2/M4 |
| `historicalPeriod` | User-confirmed (default 180) | M3 trend window |
| `thresholds.*` | Phase 0.0 review of SOP defaults; user can override | All diagnostic cut-points |
| `thresholds.modernSearchMinWeeklyImpressions` | Modern Search SOP — default 300 weekly impressions per AG | Volume gate for structural-split recommendations. Below this, Google AI features (Smart Bidding, RSA asset selection) lose learning signal — the Headline Test must not recommend splitting AGs below this threshold; recommend keyword-level customizers, DKI, or tighter copy themes instead. |
| `lastConfirmed` | Phase 0.0 | Triggers re-interview after 60 days |
| `businessMdHash` | Phase 0.0 | Triggers re-interview when business.md changes |

---

## Reused keys (read — never written)

| Key | Source skill | Usage |
|---|---|---|
| `googleAds.customerId` | `/gads-context` | Query identity |
| `googleAds.loginCustomerId` | `/gads-context` | MCC login context |
| `googleAds.conversionActions` | `/gads-context` | Reported in Phase 0.0 context (not used directly for QS) |
| `googleAds.dateRange` | `/gads-context` | Default period fallback |
| `searchTermAnalysis.brandedCampaigns` | `/search-term-auditor` Phase 0 | Classifier BRANDED class |
| `searchTermAnalysis.conversionLagDays` | `/search-term-auditor` Phase 0 | Lag offset for period pulls |
| `keywordAudit.primaryKPI` | `/keyword-auditor` Phase 0.0 | Pre-fill KPI during Phase 0.0 |

---

## Branch logic (Phase 0.0)

**Branch A — cached AND fresh:**

- `qualityScoreAudit.lastConfirmed` is < 60 days old
- `qualityScoreAudit.businessMdHash` matches current `business.md` SHA-256 (first 16 chars)

→ Show one-line reconfirmation:

> "Using cached QS context: primary KPI **{primaryKPI}**, competitor campaigns **{list or 'none'}**, eval period **{n}d**, history **{n}d**. Last confirmed {date}. Proceed? (y / update)"

**Branch B — first run, stale, or user requested `--reconfirm`:**

1. Read `business.md` + existing `config`.
2. Scan campaign names in `campaigns-settings.csv` for competitor signals: `conquest`, `competitor`, `conquesting`, known rival brand names from `business.md`.
3. Present step-through interview:
   - **Primary KPI** — pre-filled from `keywordAudit.primaryKPI` if present
   - **Evaluation period** — default 30, options 30 / 60 / 90
   - **Historical period** — default 180
   - **Thresholds** — show SOP defaults, allow override per field
   - **Competitor campaigns** — present scanned candidates: *"Found these that look like conquesting — confirm or correct: [list]"*
   - **Competitor brands** — *"List competitor brand names (or 'none')"*
4. Write `qualityScoreAudit` block with `lastConfirmed = today` and `businessMdHash = first16(sha256(business.md))`.

---

## No-values-available case

If the user cannot confirm competitor campaigns (genuinely unknown), save:

```json
"competitorCampaigns": [],
"competitorBrands": []
```

The classifier will then treat all keywords as GENERIC. The report MUST carry a banner:

> *"No competitor campaigns configured. If your account runs conquesting / competitor-targeting campaigns, their AR Below-Avg findings below may be structurally expected — re-run Phase 0.0 to classify them correctly."*
