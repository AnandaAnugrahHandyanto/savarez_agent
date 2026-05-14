# LP Optimizer -- Full Optimization Methodology (LP-E04)

Used by: `/lp-optimizer audit`

This reference guides the full optimization guidance action. It reads the complete audit report and produces a prioritized fix-it plan.

## Approach

1. Read the full `context/analysis/lp-audit.md` report
2. Extract all FAIL and WARN diagnostics
3. Prioritize by: severity (Critical > High > Medium > Low), then by module weight
4. For each issue, deep-dive using Chrome DevTools to understand root cause
5. Produce specific, implementable fix recommendations

## Priority Framework

| Priority | Criteria | Timeline |
|----------|----------|----------|
| P1: Quick wins | High impact + low effort (copy changes, CTA tweaks, removing elements) | This week |
| P2: Strategic fixes | High impact + moderate effort (new sections, form redesign, page restructure) | Next 2 weeks |
| P3: Technical fixes | Medium impact + developer effort (speed, mobile, forms backend) | Sprint backlog |
| P4: Strategic improvements | Lower impact or high effort (A/B tests, full redesign, new page variants) | Quarterly plan |

## Impact Ranking by Diagnostic Area

These areas typically deliver the highest ROI when fixed, in order:

1. **Hero / headline clarity** (D02) -- 80% of visitors decide here
2. **Message match** (D13-D14) -- misaligned ads = wasted spend
3. **CTA presence and quality** (D03, D04, D10) -- no clear CTA = no conversion
4. **Page speed** (D17-D18) -- slow pages lose visitors before content loads
5. **Mobile experience** (D19-D20) -- 50%+ of traffic is mobile
6. **Trust and social proof** (D06, D07) -- visitors need reasons to believe
7. **Objection handling** (D08, D09) -- unaddressed doubts kill conversions
8. **Form friction** (D21-D22) -- every unnecessary field costs conversions
9. **Section hierarchy** (D12) -- wrong section order confuses the persuasion flow
10. **URL health** (D32-D37) -- broken URLs = zero conversions for that traffic

## Investigation Process

For each FAIL/WARN diagnostic:

1. **Navigate** to the affected URL via Chrome DevTools
2. **Screenshot** the specific page area with the issue
3. **Analyze** what's wrong and why (root cause, not just symptom)
4. **Cross-reference** ad data: compare `ads.csv` headlines to page content
5. **Write fix recommendation** with:
   - What to change (specific element)
   - How to change it (copy/design/code suggestion)
   - Who does it (developer, marketer, designer)
   - Expected impact (estimated CVR lift based on severity)

## Vertical-Specific Considerations

### Lead Gen
- Hero must include service + location + CTA
- Form fields are the primary conversion point -- optimize ruthlessly
- Trust signals: licenses, certifications, local references
- Guarantee near form is critical

### SaaS
- Hero must communicate the outcome, not the feature
- Social proof: user count, client logos, G2/Capterra ratings
- Free trial / demo CTA must be frictionless
- Feature sections should focus on benefits, not specs

### Ecommerce
- Product imagery is the hero -- large, multiple angles, zoomable
- Price must be visible above fold
- Trust: reviews, secure checkout, shipping/returns info
- Cross-reference with ecommerce diagnostics (D38-D40)

## Output Structure

The guidance report should follow this structure:

```markdown
# Landing Page Optimization Guidance

## Audit Summary
- Score: {x}% ({grade})
- Critical issues: {n}
- Total FAIL/WARN: {n}

## Priority Fix List

### P1: Quick Wins (do this week)
{For each P1 fix: issue, screenshot, root cause, specific fix, who does it}

### P2: Strategic Fixes (next 2 weeks)
{Same format}

### P3: Technical Fixes (sprint backlog)
{Same format}

### P4: Strategic Improvements (quarterly)
{Same format}

## Before/After Recommendations
{For key fixes: current state screenshot + recommended change description}

## Implementation Checklist
- [ ] Fix 1: {description} -- Owner: {role}
- [ ] Fix 2: {description} -- Owner: {role}

## Expected Impact
{Estimated overall CVR improvement if P1+P2 fixes are implemented}
```
