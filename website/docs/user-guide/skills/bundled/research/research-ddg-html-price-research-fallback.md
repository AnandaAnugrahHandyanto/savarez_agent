---
title: "Ddg Html Price Research Fallback"
sidebar_label: "Ddg Html Price Research Fallback"
description: "Use DuckDuckGo HTML search and lightweight scraping to gather current consumer hardware pricing when direct retailer sites or browser automation are blocked ..."
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# Ddg Html Price Research Fallback

Use DuckDuckGo HTML search and lightweight scraping to gather current consumer hardware pricing when direct retailer sites or browser automation are blocked by Cloudflare or browser startup failures.

## Skill metadata

| | |
|---|---|
| Source | Bundled (installed by default) |
| Path | `skills/research/ddg-html-price-research-fallback` |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that Hermes loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

# When to use
Use this when you need current-ish price guidance for consumer products (especially PC parts) and:
- browser automation fails to start, or
- retailer/aggregator pages like PCPartPicker are blocked by Cloudflare, or
- direct scraping of store pages is unreliable.

Typical case: user wants a build recommendation plus target buy prices.

# Workflow
1. **Try the obvious source first**
   - Attempt browser navigation to the canonical site (e.g. PCPartPicker guide page).
   - If browser daemon fails or the site returns a Cloudflare challenge, switch immediately to the fallback below.

2. **Use DuckDuckGo HTML search as the discovery layer**
   - Query `https://html.duckduckgo.com/html/?q=...` with a normal desktop User-Agent.
   - Parse `<a rel="nofollow" class="result__a" ...>` results.
   - Use this to find:
     - product pages on Amazon / Newegg / Best Buy
     - review pages from Tom's Hardware / TechPowerUp
     - deal pages (e.g. Slickdeals) for recent low prices

3. **Use retailer search/listing pages instead of exact PDP scraping when needed**
   - For Newegg, product-listing/search pages often expose enough price strings even when structured parsing is messy.
   - Pull multiple price samples from the HTML and filter to a plausible range for the category.
   - Do **not** overclaim precision; present ranges and "do not pay over" thresholds.

4. **Cross-check with at least one review source for performance comparisons**
   - Example for GPUs: use Tom's Hardware/TechPowerUp search results to confirm relative raster / RT positioning.
   - Quote only what was actually found, e.g. "snippet says 7–10% slower/faster" rather than inventing exact benchmark averages.

5. **Convert findings into shopping guidance**
   - Provide:
     - recommended part
     - good price range
     - ceiling price (`don't pay over`)
     - estimated whole-build midpoint total
   - For marketplace buys (Taobao / Alibaba / AliExpress), separate:
     - safer parts to buy there (CPU, motherboard, RAM, cooler)
     - higher-risk parts to prefer from trusted sellers (GPU, PSU, SSD)

# Example commands/snippets
## Fetch DDG HTML results in Python
```python
import requests, urllib.parse, re
q = 'Ryzen 5 7600 price Newegg Amazon'
url = 'https://html.duckduckgo.com/html/?q=' + urllib.parse.quote(q)
html = requests.get(url, headers={'User-Agent':'Mozilla/5.0'}, timeout=20).text
for m in re.finditer(r'<a rel="nofollow" class="result__a" href="(.*?)">(.*?)</a>', html):
    title = re.sub('<.*?>', '', m.group(2))
    href = m.group(1)
    print(title, href)
```

## Pull rough Newegg price samples
```python
import requests, re
html = requests.get(url, headers={'User-Agent':'Mozilla/5.0'}, timeout=20).text
prices = [float(x.replace(',','')) for x in re.findall(r'\$(\d+[\d,]*\.\d{2})', html)]
prices = [p for p in prices if 200 <= p <= 1200]  # adjust bounds per category
```

# Pitfalls
- PCPartPicker may present Cloudflare "Just a moment..." pages to simple HTTP requests.
- Browser automation can fail before page load; have the terminal fallback ready.
- Search-result snippets are useful but are **not** the same as full benchmark tables.
- Retail listing pages contain noise prices from accessories/bundles/refurbs; filter aggressively and present ranges, not exact claims.
- Avoid pretending marketplace prices are verified if you only have general US street-price data.

# Output style
For shopping advice, prefer a concise table:
- Part
- Good price
- Don't pay over

Then add a short recommendation section like:
- best pure 1440p gaming choice
- feature/RT choice
- what to buy from Taobao vs trusted local retailers

# Verification checklist
Before finalizing:
- Did direct browsing fail or get blocked? Mention that only implicitly if relevant; don't overfocus on tooling issues.
- Did you back performance claims with at least one review source snippet?
- Are prices framed as approximate current ranges rather than exact verified offers?
- Did you clearly separate marketplace risk guidance from pure performance advice?
