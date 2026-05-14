# LP Optimizer -- Mobile Experience Improvement (LP-E08)

Used by: `/lp-optimizer mobile`

## Investigation Steps

### 1. Emulate Mobile Viewports

Test on two standard viewports:

**iPhone (375px width):**
```
mcp__chrome-devtools__emulate with device: "iPhone 12"
```

**Android (360px width):**
```
mcp__chrome-devtools__resize_page with width: 360, height: 800
```

For each viewport:
1. Take full-page screenshot
2. Screenshot above-fold area specifically
3. Check each section for mobile issues

### 2. Check Mobile CVR Gap

Read `context/google-ads/data/device-performance.csv`:
- Compare mobile CVR to desktop CVR
- If mobile < 60% of desktop: significant mobile UX problem
- If mobile < 40% of desktop: critical mobile UX problem
- Calculate potential revenue from closing the gap

### 3. Mobile-Specific Checks

| Check | How to evaluate | FAIL criteria |
|-------|----------------|---------------|
| **Tap targets** | Evaluate button/link sizes in DOM | Any interactive element < 44x44px |
| **Text readability** | Check body font-size | Body text < 16px |
| **Horizontal scroll** | Check for elements wider than viewport | Any horizontal overflow detected |
| **CTA visibility** | Check if primary CTA is visible above fold on mobile | CTA not visible without scrolling |
| **Image scaling** | Check if images fit viewport without overflow | Images wider than viewport |
| **Form usability** | Check input field sizes and keyboard types | Input fields < 44px height, wrong keyboard types |
| **Navigation** | Check if mobile menu works, if present | Nav items too small or hamburger broken |
| **Content stacking** | Check if multi-column layouts stack properly | Overlapping content on mobile |

### 4. Mobile Form Analysis (if forms present)

- Are input fields full-width on mobile?
- Do number fields trigger numeric keyboard? (`inputmode="numeric"`)
- Does email field trigger email keyboard? (`inputmode="email"`)
- Is autofill enabled? (proper `autocomplete` attributes)
- Can the user see the CTA while filling the form?

### 5. Mobile Speed Check

Run Lighthouse in mobile emulation mode:
- Mobile-specific performance score
- Mobile-specific LCP (often much higher than desktop)
- Touch delay / INP on mobile

## Fix Patterns

### Quick Wins (P1)

| Issue | Fix | Implementation |
|-------|-----|---------------|
| Small tap targets | Increase to minimum 44x44px with 8px spacing | CSS: `min-height: 44px; min-width: 44px; padding: 12px` |
| Small text | Set minimum 16px body text | CSS: `body { font-size: 16px; }` |
| CTA not visible above fold | Move CTA higher or make it sticky | CSS: `position: sticky; bottom: 0;` for mobile |
| Wrong keyboard types | Add inputmode attributes | HTML: `inputmode="email"`, `inputmode="tel"`, `inputmode="numeric"` |
| Images overflow | Set max-width 100% | CSS: `img { max-width: 100%; height: auto; }` |

### Strategic Fixes (P2)

| Issue | Fix | Implementation |
|-------|-----|---------------|
| Poor content stacking | Redesign multi-column layouts for mobile-first | CSS Grid/Flexbox with mobile-first breakpoints |
| Form too long on mobile | Convert to multi-step form | Progressive disclosure: step 1 (email), step 2 (details) |
| Slow mobile load | Mobile-specific image sizes | `<picture>` element with mobile-optimized `srcset` |
| Desktop-only features | Remove or adapt hover interactions | Replace hover states with tap interactions |
| Fixed headers eating screen space | Auto-hide header on scroll down, show on scroll up | JavaScript scroll direction detection |

### Technical Fixes (P3)

| Issue | Fix | Implementation |
|-------|-----|---------------|
| Mobile-specific JS issues | Audit mobile-only JavaScript errors | Check console in mobile emulation mode |
| Touch event handling | Ensure no 300ms tap delay | CSS: `touch-action: manipulation;` |
| Viewport meta tag issues | Verify correct viewport configuration | `<meta name="viewport" content="width=device-width, initial-scale=1">` |

## Mobile Revenue Calculator

Use this to quantify the impact of the mobile CVR gap:

```
Desktop CVR: {x}%
Mobile CVR: {y}%
Mobile traffic (monthly clicks): {n}
Current mobile conversions: mobile_clicks * mobile_CVR

If mobile CVR improved to 70% of desktop:
  Target mobile CVR: desktop_CVR * 0.7
  Additional conversions: mobile_clicks * (target_CVR - current_CVR)
  Additional revenue: additional_conversions * avg_conversion_value

Present this as the ROI case for mobile optimization.
```

## Report Output Structure

```markdown
## Mobile Experience Analysis

### Mobile CVR Gap
| Device | Clicks | Conversions | CVR | CPA |
|--------|--------|-------------|-----|-----|
| Desktop | {n} | {n} | {x}% | ${x} |
| Mobile | {n} | {n} | {x}% | ${x} |

Gap: Mobile CVR is {x}% of desktop ({revenue opportunity})

### Mobile Issues Found
| # | Issue | Severity | Screenshot | Location |
|---|-------|----------|-----------|----------|

### Fix Recommendations
{P1/P2/P3 fixes with mobile-specific implementation details}

### Revenue Impact
{Mobile revenue calculator results}
```
