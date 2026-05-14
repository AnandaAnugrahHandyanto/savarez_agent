# LP Optimizer -- Page Speed Improvement (LP-E07)

Used by: `/lp-optimizer speed`

## Investigation Steps

### 1. Run Lighthouse Audit via Chrome DevTools

```
mcp__chrome-devtools__lighthouse_audit
```

Capture:
- Performance score (mobile + desktop)
- LCP (Largest Contentful Paint) -- target < 2.5s
- INP (Interaction to Next Paint) -- target < 200ms
- CLS (Cumulative Layout Shift) -- target < 0.1
- Total page weight
- Number of requests

### 2. Identify Bottlenecks

Monitor network requests to find specific issues:

```
mcp__chrome-devtools__list_network_requests
```

**Check for each bottleneck category:**

| Category | What to look for | Impact |
|----------|-----------------|--------|
| Large images | Any image > 200KB, uncompressed formats (BMP, TIFF) | High |
| Render-blocking resources | JS/CSS in `<head>` without defer/async | High |
| Unoptimized fonts | Multiple font weights loaded, no font-display: swap | Medium |
| Server response time (TTFB) | > 600ms | High |
| Third-party scripts | Analytics, chat widgets, ad pixels blocking render | Medium |
| Total page weight | > 3MB total | High |
| Too many requests | > 50 HTTP requests | Medium |

### 3. Image Analysis

For each large image found:
- Current size and format
- Recommended format (WebP for photos, SVG for icons)
- Target size after compression
- Whether lazy loading should be applied (below-fold images)

### 4. JavaScript Analysis

- Count render-blocking scripts
- Identify which can be deferred or async
- Check for unused JavaScript (coverage analysis)
- Identify third-party scripts and their load impact

## Fix Patterns

### Quick Wins (P1)

| Fix | Implementation | Expected Impact |
|-----|---------------|-----------------|
| Compress images | Use WebP format, resize to display dimensions, quality 80% | -30-60% page weight |
| Add lazy loading | `loading="lazy"` on below-fold images | Faster initial load |
| Defer non-critical JS | Add `defer` or `async` attribute | Faster render |
| Enable browser caching | Set Cache-Control headers (max-age: 31536000 for static assets) | Faster repeat visits |
| Add font-display: swap | Prevents invisible text during font load | Faster perceived load |

### Strategic Fixes (P2)

| Fix | Implementation | Expected Impact |
|-----|---------------|-----------------|
| Implement CDN | Cloudflare, CloudFront, or Fastly | -20-40% TTFB globally |
| Code splitting | Load only critical JS for initial render | Faster FCP |
| Preload critical resources | `<link rel="preload">` for hero image, critical CSS | Faster LCP |
| Optimize server response | Upgrade hosting, add server-side caching | Faster TTFB |
| Remove unused CSS/JS | Audit and remove dead code | Reduced page weight |

### Technical Fixes (P3)

| Fix | Implementation | Expected Impact |
|-----|---------------|-----------------|
| Implement critical CSS | Inline above-fold CSS, defer the rest | Faster FCP |
| HTTP/2 or HTTP/3 | Server configuration | Better multiplexing |
| Service worker caching | Cache static assets for offline/fast reload | Near-instant repeat loads |
| Image CDN with transforms | Cloudinary, imgix for automatic format/size | Automated optimization |

## Benchmarks

| Metric | Good | Needs Work | Poor |
|--------|------|-----------|------|
| Performance Score (Mobile) | 90+ | 50-89 | < 50 |
| Performance Score (Desktop) | 90+ | 70-89 | < 70 |
| LCP | < 2.5s | 2.5-4.0s | > 4.0s |
| INP | < 200ms | 200-500ms | > 500ms |
| CLS | < 0.1 | 0.1-0.25 | > 0.25 |
| TTFB | < 200ms | 200-600ms | > 600ms |
| Page Weight | < 1MB | 1-3MB | > 3MB |

## Report Output Structure

```markdown
## Speed Analysis

### Current Performance
| Metric | Mobile | Desktop | Target | Status |
|--------|--------|---------|--------|--------|

### Bottleneck Breakdown
| # | Issue | Resource | Current | Target | Impact |
|---|-------|----------|---------|--------|--------|

### Fix Recommendations
{P1/P2/P3 fixes with specifics for each bottleneck found}

### Implementation Notes
- Developer tasks: {list}
- No-code fixes: {list, e.g., image compression, lazy loading plugins}
```
