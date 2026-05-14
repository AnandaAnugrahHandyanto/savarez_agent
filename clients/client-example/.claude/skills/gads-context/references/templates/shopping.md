# Shopping/Product Data - {Account Name}

**If shopping CSVs are empty (0 rows):** Output only the header + "No Shopping campaigns or Merchant Center not linked to this account." + timestamp footer.

**If data exists:**

## Summary
- {N} products with traffic (shopping_performance_view)
- {M} products in feed (shopping_product)
- {P} product groups configured
- Total shopping spend: ${total_cost}

## Product Eligibility

Use the `shopping_product.issue_codes` column (pipe-separated error codes) to categorize NOT_ELIGIBLE products by root cause.

**IMPORTANT:** `not_eligible_in_any_campaign` means the product is NOT targeted by any Shopping/PMax campaign — this is a campaign structure choice, NOT a feed problem. Do not flag this as a critical issue.

| Status | Count | % |
|--------|-------|---|
| ELIGIBLE | {n} | {%} |
| ELIGIBLE_LIMITED | {n} | {%} |
| NOT_ELIGIBLE — not in any campaign | {n} | {%} |
| NOT_ELIGIBLE — feed issues | {n} | {%} |

**How to categorize using `shopping_product.issue_codes`:** Products where issue_codes is exactly `not_eligible_in_any_campaign` (no other codes) count as "not in any campaign." Products with additional codes (e.g. `not_eligible_in_any_campaign | invalid_upc`) count as "feed issues."

## Feed Issues

**Only list issues OTHER than `not_eligible_in_any_campaign`.** If no real feed issues exist, write "No feed issues found — all NOT_ELIGIBLE products are simply not targeted by campaigns."

| Issue | Affected Products | Severity |
|-------|-------------------|----------|
| ...   | ...               | ...      |

## Top Products by Spend

| Product ID | Title | Brand | Category | Impr | Clicks | Cost | Conv | ROAS |
|-----------|-------|-------|----------|------|--------|------|------|------|
| ...       | ...   | ...   | ...      | ...  | ...    | ...  | ...  | ...  |

## Product Groups (by spend)

| Campaign | Ad Group | Group Type | Brand/Category | Impr | Clicks | Cost | Conv |
|----------|----------|-----------|----------------|------|--------|------|------|
| ...      | ...      | ...       | ...            | ...  | ...    | ...  | ...  |

## Insights
- [Products with spend but no conversions]
- [Feed issues — only flag real feed problems, NOT "not in any campaign"]
- [If most products are "not in any campaign": note how many of {total} products are actively advertised]

---
*Last updated: {timestamp}*
