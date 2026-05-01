---
name: find-deals
description: Use when searching for current deals, discounts, or pricing on specific products at local retail stores, particularly cannabis dispensaries. Accepts product name and location to query the web for active promotions and menu pricing.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [shopping, deals, local-search, pricing, retail, dispensaries]
    related_skills: [web-search, maps]
---

# Find Deals

## Overview
This skill locates current deals, promotions, and pricing for specific products at local retail stores, with focused support for cannabis dispensaries in jurisdictions where legal. It formulates targeted web queries from the provided product name and geographic location, then interprets results to surface menu pricing, daily specials, first-time patient discounts, and bulk promotions.

## When to Use
- Searching for current pricing or deals on a specific cannabis product at nearby dispensaries
- Comparing menu prices across local stores before visiting
- Finding limited-time promotions (daily specials, happy hours)
- Researching first-time patient or loyalty program discounts

## How It Works
The skill prompts for a product name and location, then uses web search to find publicly listed menus and deal pages. It summarizes findings with store names, deal descriptions, price points, and direct links where available.

## Parameters
| Parameter | Required | Description |
|-----------|----------|-------------|
| `product` | Yes | Product name, strain, brand, or category (e.g., "Blue Dream", "edibles", "vapes") |
| `location` | Yes | City, neighborhood, or ZIP code |
| `deal_type` | No | Optional filter: `all`, `first-time`, `daily-special`, `loyalty`, `bulk`, `clearance` (default: `all`) |

## Workflow
1. Confirm product name and location if not provided.
2. Construct targeted web query: `"<product> deals <location>"` or `"cannabis dispensary <product> menu <location>"`.
3. Run `web_search` with the query.
4. Summarize top results, extracting store names, prices, and deal details.
5. Present findings in a compact table with links.

## Example Calls
- `find_deals(product="Blue Dream 3.5g", location="Denver, CO")`
- `find_deals(product="edibles", location="Los Angeles, CA", deal_type="daily-special")`

## Common Pitfalls
1. **Location is mandatory.** Cannabis pricing and inventory are hyper-local due to varying state regulations. Always supply a city or ZIP; "near me" fails without geolocation context.
2. **Deal freshness.** Web-cached deals and menu prices may be stale; always confirm directly with the dispensary before visiting.
3. **Legal jurisdiction.** Only valid results from jurisdictions where cannabis retail is legal will be useful. Respect local laws.
4. **Medical vs. recreational.** Some deals apply only to medical cardholders; note this in results when mentioned.

## Verification Checklist
- [ ] Product name and location supplied by user.
- [ ] Web search query constructed and executed.
- [ ] Results parsed for store name, deal description, price, and expiration if listed.
- [ ] User advised to verify deals directly with the retailer before traveling.