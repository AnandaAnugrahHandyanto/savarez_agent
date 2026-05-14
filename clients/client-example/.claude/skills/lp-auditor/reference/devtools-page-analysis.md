# LP Auditor — Chrome DevTools Page Analysis Guide

Reference for how to use Chrome DevTools MCP to extract page data for structural, technical, and ecommerce diagnostics.

## Navigation & Screenshots

```
# Navigate to target URL
mcp__chrome-devtools__navigate_page(url: "https://example.com")

# Wait for page load
mcp__chrome-devtools__wait_for(selector: "body", timeout: 10000)

# Take full-page screenshot
mcp__chrome-devtools__take_screenshot()

# Take snapshot (DOM state)
mcp__chrome-devtools__take_snapshot()
```

## DOM Content Extraction

### Extract headings and structure
```javascript
// Get all headings
const headings = Array.from(document.querySelectorAll('h1, h2, h3, h4')).map(h => ({
  tag: h.tagName,
  text: h.textContent.trim(),
  rect: h.getBoundingClientRect()
}));
JSON.stringify(headings);
```

### Extract CTA buttons
```javascript
// Get all buttons and prominent links
const ctas = Array.from(document.querySelectorAll('button, a.btn, a.cta, input[type="submit"], [role="button"]')).map(el => ({
  tag: el.tagName,
  text: el.textContent.trim() || el.value || '',
  href: el.href || '',
  rect: el.getBoundingClientRect(),
  isVisible: el.offsetParent !== null
}));
JSON.stringify(ctas);
```

### Extract form fields
```javascript
// Get all form fields
const forms = Array.from(document.querySelectorAll('form')).map(form => ({
  action: form.action,
  method: form.method,
  fields: Array.from(form.querySelectorAll('input, select, textarea')).map(f => ({
    type: f.type,
    name: f.name,
    required: f.required,
    placeholder: f.placeholder
  }))
}));
JSON.stringify(forms);
```

### Extract images
```javascript
// Get all images with sizes
const images = Array.from(document.querySelectorAll('img')).map(img => ({
  src: img.src,
  alt: img.alt,
  width: img.naturalWidth,
  height: img.naturalHeight,
  loading: img.loading
}));
JSON.stringify(images);
```

### Extract links (for one-page-one-goal check)
```javascript
// Get all outbound links
const currentHost = window.location.hostname;
const links = Array.from(document.querySelectorAll('a[href]')).map(a => ({
  text: a.textContent.trim(),
  href: a.href,
  isExternal: !a.href.includes(currentHost),
  isAnchor: a.href.startsWith('#') || a.href.includes(currentHost + '/#'),
  inNav: !!a.closest('nav, header'),
  inFooter: !!a.closest('footer')
}));
JSON.stringify(links);
```

### Check for social proof elements
```javascript
// Look for testimonial/review patterns
const proof = {
  testimonials: document.querySelectorAll('[class*="testimonial"], [class*="review"], blockquote').length,
  logos: document.querySelectorAll('[class*="logo"], [class*="partner"], [class*="client"]').length,
  ratings: document.querySelectorAll('[class*="star"], [class*="rating"]').length,
  badges: document.querySelectorAll('[class*="badge"], [class*="trust"], [class*="seal"]').length
};
JSON.stringify(proof);
```

## Mobile Emulation

```
# Emulate iPhone (375px)
mcp__chrome-devtools__emulate(device: "iPhone 12")

# Check for horizontal overflow
mcp__chrome-devtools__evaluate_script(script: "document.documentElement.scrollWidth > document.documentElement.clientWidth")

# Take mobile screenshot
mcp__chrome-devtools__take_screenshot()

# Reset to desktop
mcp__chrome-devtools__resize_page(width: 1440, height: 900)
```

## Lighthouse Audit

```
# Run Lighthouse performance audit
mcp__chrome-devtools__lighthouse_audit(categories: ["performance"])
```

Extract from results:
- Performance score (0-100)
- LCP (seconds)
- INP (milliseconds) — may show as TBT if INP unavailable
- CLS (score)
- Total page weight
- Specific opportunities (image optimization, render-blocking resources, etc.)

## Network Monitoring

```
# List network requests (after page load)
mcp__chrome-devtools__list_network_requests()
```

Filter for:
- Images >200KB
- Total page weight
- Render-blocking resources
- Redirect chains (3xx responses)

## Section Mapping Strategy

To map page sections to the LP Hierarchy Blueprint:

1. Extract all heading elements (H1-H4) with positions
2. Extract section/div elements with semantic class names
3. Take full-page screenshot
4. Map visual sections to:
   - **Hero:** Above fold content (first viewport)
   - **Benefits:** Section after hero with feature/benefit content
   - **Trust:** Section with logos, badges, credentials
   - **Social Proof:** Section with testimonials, reviews, case studies
   - **Objection Handling:** FAQ section or concern-addressing content
   - **Urgency:** Time-limited offers, countdown timers, stock indicators
   - **CTA:** Button/form placements throughout the page

Use both DOM analysis and visual screenshot analysis for accurate mapping.
