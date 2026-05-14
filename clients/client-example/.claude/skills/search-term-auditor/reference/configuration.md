# Configuration Reference — Search Term Auditor

Complete reference for the `searchTermAnalysis` + `ngramAnalysis` blocks of `config/ads-context.config.json`.

## searchTermAnalysis

```json
{
  "searchTermAnalysis": {
    "conversionLagDays": 14,
    "minSpendToFlag": 20,
    "minSpendForInefficient": 50,
    "minClicksForInefficient": 3,
    "inefficientCPAMultiplier": 1.5,
    "inefficientROASMultiplier": 0.7,
    "biddingStrategy": "cpa",
    "excludeBrandedCampaigns": true,
    "brandedCampaigns": [
      "Branded — Exact",
      "Branded — Phrase"
    ],
    "protectedTerms": {
      "neverExclude": ["core product term"],
      "alwaysInclude": ["must-have keyword"]
    },
    "sharedNegativeLists": {
      "primary": "Negative Keywords — Irrelevant",
      "ngramNonConverting": "Negative N-grams — Non-Converting",
      "ngramInefficient": "Negative N-grams — Inefficient",
      "foreign": "Negative Keywords — Foreign Language"
    },
    "negativeMatchType": "Phrase",
    "routingNegatives": ["<term-routed-elsewhere>", "<another-routing-term>"]
  }
}
```

| Field | Default | Description |
|-------|---------|-------------|
| `conversionLagDays` | 14 | Days to shift all search-term date ranges back. Applied at query time via `--lag-offset`. |
| `minSpendToFlag` | 20 | Minimum cost threshold for ST-D02 non-converting flag (currency units). |
| `minSpendForInefficient` | 50 | Minimum cost for ST-D03 underperforming flag. |
| `minClicksForInefficient` | 3 | Minimum clicks for ST-D03 underperforming flag. |
| `inefficientCPAMultiplier` | 1.5 | CPA cutoff = `target × multiplier`. A term with CPA > this value is inefficient. |
| `inefficientROASMultiplier` | 0.7 | ROAS cutoff = `target × multiplier`. A term with ROAS < this value is inefficient. |
| `biddingStrategy` | `"cpa"` | Account-level default strategy. Per-campaign strategy is resolved by the script. |
| `excludeBrandedCampaigns` | `true` | Skip branded campaigns from Module 1–3 analysis. |
| `brandedCampaigns` | `[]` | Explicit list of full branded campaign names (case-insensitive). **Preferred.** When empty, falls back to a name-pattern check. |
| `protectedTerms.neverExclude` | `[]` | Terms that must never be proposed as negatives. |
| `protectedTerms.alwaysInclude` | `[]` | Terms to always force into promotion candidates. |
| `sharedNegativeLists.primary` | `"Negative Keywords — Irrelevant"` | Default shared list for irrelevant terms (ST-E01). |
| `sharedNegativeLists.ngramNonConverting` | `"Negative N-grams — Non-Converting"` | ST-E02 destination for zero-conv n-grams. |
| `sharedNegativeLists.ngramInefficient` | `"Negative N-grams — Inefficient"` | ST-E02 destination for inefficient n-grams. |
| `sharedNegativeLists.foreign` | `"Negative Keywords — Foreign Language"` | ST-E10 destination for foreign queries. |
| `negativeMatchType` | `"Phrase"` | Default match type for created negatives. |
| `routingNegatives` | `[]` | Negative terms (case-insensitive) that should always be treated as intentional traffic routing. Force-flags `likely_routing: true` on matching ST-D09/D10 entries so they are excluded from consolidation handoffs. Use for terms where the auto-heuristic is too weak (e.g. brand routing where the brand is the entire term and there are no positive-keyword matches in other campaigns). |

## ngramAnalysis

```json
{
  "ngramAnalysis": {
    "minImpressions": 100,
    "minClicks": 25,
    "minDistinctTerms": 3,
    "nonConvertingSpendMultiplier": 2.0,
    "inefficientCPAMultiplier": 1.75,
    "inefficientROASMultiplier": 0.7,
    "defaultAOV": 0,
    "stopwords": [],
    "biddingStrategy": "cpa"
  }
}
```

| Field | Default | Description |
|-------|---------|-------------|
| `minImpressions` | 100 | Filter out n-grams below this impression count. |
| `minClicks` | 25 | Filter out n-grams below this click count. |
| `minDistinctTerms` | 3 | Minimum distinct search terms an n-gram must appear in. |
| `nonConvertingSpendMultiplier` | 2.0 | ST-D13 threshold: `spend > target × multiplier`. |
| `inefficientCPAMultiplier` | 1.75 | ST-D14 CPA cutoff. |
| `inefficientROASMultiplier` | 0.7 | ST-D14 ROAS cutoff. |
| `defaultAOV` | 0 | Fallback AOV when conversion-value data is missing (used for ROAS non-converting threshold). |
| `stopwords` | `[]` | Additional words to exclude from n-gram extraction. |
| `biddingStrategy` | inherits `searchTermAnalysis.biddingStrategy` | Account-level default; per-campaign resolved. |

## How the auditor discovers per-campaign targets

The auditor never hardcodes CPA/ROAS. Precedence (handled by `lib.resolveBiddingStrategy`):

1. `campaign.target_cpa` / `campaign.target_roas` (inline) — `target_source=campaign_inline`
2. Portfolio strategy target via `campaign.bidding_strategy` → `bidding-strategies.csv` → `target_source=portfolio`
3. `business.md` target — `target_source=fallback`
4. No target — `target_source=none`

Every flagged record carries `target_source` and `portfolio_name` so the synthesis layer can distinguish real vs inferred targets.
