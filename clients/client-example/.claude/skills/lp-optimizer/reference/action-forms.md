# LP Optimizer -- Form Friction Reduction (LP-E10)

Used by: `/lp-optimizer forms`

## Investigation Steps

### 1. Extract Form Structure

Use Chrome DevTools to find all `<form>` elements:

For each form:
- Count total fields
- Count required fields
- List each field: name, type, label, required status, placeholder
- Check for multi-step/progressive disclosure
- Check form action/submission method
- Screenshot the form in context

### 2. Evaluate Field Necessity

For each field, assess necessity:

| Field Category | Typically Required | Can Remove/Defer |
|---------------|-------------------|-----------------|
| Email | Yes -- primary identifier | Never remove |
| Full name | Yes -- contact | Consider "First name" only |
| Company name | Depends on B2B | Move to optional or post-conversion |
| Phone number | Depends on vertical | Move to optional or post-conversion |
| Address fields | Only for delivery/local | Move to post-conversion |
| Job title | Lead qualification | Move to optional or post-conversion |
| Message/comments | Low value for initial conversion | Move to optional or remove |
| "How did you hear about us?" | Analytics only | Remove (use UTM tracking instead) |

**Benchmarks:**
- Lead gen: PASS <= 5 required fields, WARN 6-8, FAIL > 8
- SaaS trial: PASS <= 3 required fields (email, name, password)
- Ecommerce: Checkout PASS <= 6 required fields (shipping info)
- Contact form: PASS <= 3 required fields (name, email, message)

### 3. Check Form UX

| Check | How to evaluate | Best practice |
|-------|----------------|--------------|
| Labels visible | Check if labels are persistent (not placeholder-only) | Labels above fields, always visible |
| Placeholder text | Check if placeholders provide useful hints | Examples, not label repeats |
| Error handling | Trigger validation errors | Inline, specific, near the field |
| Autofill support | Check `autocomplete` attributes | Proper autocomplete values set |
| Mobile keyboard | Check `inputmode` attributes | Numeric for phone/zip, email for email |
| Tab order | Check logical tab progression | Fields tab in visual order |
| Submit button | Check CTA text | Benefit-driven, not "Submit" |
| Privacy text | Check near submit button | Short privacy reassurance present |
| Progress indicator | Check for multi-step forms | Step count visible if multi-step |

### 4. Check Form Placement

- Is the form visible above the fold? (lead gen critical)
- If below fold, is there a CTA above fold that scrolls to it?
- Is the form placed after a trust section?
- Does the form have a clear heading explaining what happens next?

## Fix Patterns

### Quick Wins (P1)

| Issue | Fix | Expected Impact |
|-------|-----|-----------------|
| Too many required fields | Remove non-essential fields | +5-15% form completion |
| Generic "Submit" button | Change to benefit-driven CTA: "Get My Free Quote" | +5-10% form completion |
| No privacy text | Add "We'll never share your email. Unsubscribe anytime." | +3-5% form completion |
| Placeholder-only labels | Add persistent labels above fields | Reduced errors, better UX |
| No autofill | Add `autocomplete` attributes | Faster form completion |

### Strategic Fixes (P2)

| Issue | Fix | Expected Impact |
|-------|-----|-----------------|
| Long single-step form | Convert to multi-step with progress bar | +10-20% form completion |
| No inline validation | Add real-time field validation | Reduced form errors |
| Form below fold | Add above-fold micro-form or CTA that scrolls to form | +10-15% engagement |
| No social proof near form | Add testimonial or trust badge next to form | +5-10% form completion |
| Missing "what happens next" | Add text: "We'll call you within 2 hours" | Sets expectations, reduces anxiety |

### Multi-Step Form Pattern

When field count > 5, recommend progressive disclosure:

```
Step 1 (above fold): Email only -- lowest friction entry
Step 2: Name + key qualifier (e.g., company size, budget range)
Step 3: Details (phone, address, message)

Benefits:
- 60-80% complete step 1 (email captured for nurture)
- 40-60% complete all steps (vs 20-30% for single long form)
- Abandoned emails can be recovered via email automation
```

## Report Output Structure

```markdown
## Form Friction Analysis

### Form Inventory
| Form # | Location | Fields (required/total) | CTA Text | Placement |
|--------|----------|------------------------|----------|-----------|

### Field-by-Field Assessment
| # | Field | Required? | Necessary? | Recommendation |
|---|-------|-----------|-----------|---------------|

### UX Issues
| # | Issue | Severity | Current State | Recommendation |
|---|-------|----------|--------------|---------------|

### Fix Recommendations
{P1/P2 fixes with specific implementation details}

### Recommended Form Layout
{If restructure needed: new field order and multi-step design}
```
