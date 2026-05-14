# Conversion Volume Thresholds (mirror)

Authoritative source: `/sops/Conversion Volume Thresholds Reference.md`. Defaults below are baked into `lib.js → getConvVolumeThreshold(channel, strategy)`. Update both when the SOP changes.

| Channel | Strategy | Absolute | Functional | Recommended |
|---|---|---|---|---|
| SEARCH | TARGET_CPA / MAXIMIZE_CONVERSIONS | 15 | 30 | 50+ |
| SEARCH | TARGET_ROAS / MAXIMIZE_CONVERSION_VALUE | 30 | 50 | 50+ |
| SHOPPING | TARGET_ROAS | 30 | 50 | 50+ |
| PERFORMANCE_MAX | TARGET_CPA | 15 | 30 | 50+ |
| PERFORMANCE_MAX | TARGET_ROAS | 30 | 50 | 50+ |
| DISPLAY | TARGET_CPA / MAXIMIZE_CONVERSIONS | 15 | 30 | 50+ |
| DISPLAY | TARGET_ROAS | 30 | 50 | 50+ |
| VIDEO (Demand Gen replacement) | TARGET_CPA | 15 | 30 | 50+ |
| DEMAND_GEN | TARGET_CPA | 15 | 30 | 50+ |
| DEMAND_GEN | TARGET_ROAS | 30 | 50 | 50+ |

Manual CPC, Maximize Clicks, Target CPM, Max CPV, Target Impression Share — no conversion-based threshold. Skipped at the diagnostic level.

## When the threshold doesn't apply

For non-conversion-based strategies, BID-D03 returns SKIP. Channel-strategy combinations not listed above (e.g. PERFORMANCE_MAX + MAXIMIZE_CONVERSIONS without target) also return SKIP because no minimum is defined.
