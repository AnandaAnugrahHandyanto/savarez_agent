# Execute — Diagnose Weak Offer Elements (E04)

Read when `/offer-maker diagnose` is invoked.

## Prerequisites

1. Check `context/analysis/offer-audit.md` exists
   - If missing: "No audit results found. Run `/offer-auditor` first to identify weak elements."
   - If exists: proceed
2. Read `context/business.md` for current offer state

---

## Flow

### Step 1: Extract Failures from Audit

Read `context/analysis/offer-audit.md`. Extract all FAIL and WARN items:

```
Issues found in last audit:

CRITICAL (FAIL):
- D01: Value proposition clarity — {detail}
- D09: Risk removal presence — {detail}

HIGH PRIORITY (WARN):
- D02: Dream outcome specificity — {detail}
- D04: Uniqueness/comparison resistance — {detail}
```

### Step 2: Map to Fix Actions

For each FAIL/WARN item, use the gap identification tables to map to specific fixes:

| Diagnostic | Issue | Fix Action | Difficulty | Impact |
|-----------|-------|------------|------------|--------|
| D01 FAIL | No clear value prop | Rewrite VP with customer outcome focus | Medium | Critical |
| D03 FAIL | Price > perceived value | Stack value or reframe pricing | Hard | Critical |
| D05 WARN | No unique mechanism | Name your process/method | Easy | High |
| D09 FAIL | No guarantee | Add money-back or trial | Easy | Critical |
| D11 WARN | Limited social proof | Start collecting reviews | Medium | High |

**Difficulty ratings:**
- **Easy:** Can be done in this session (naming a method, adding a guarantee statement)
- **Medium:** Requires some work (rewriting VP, collecting reviews, building bundles)
- **Hard:** Requires business-level changes (pricing structure, product features, partnerships)

**Impact ratings:**
- **Critical:** Blocking profitable advertising
- **High:** Significantly limits effectiveness
- **Medium:** Improvement opportunity

### Step 3: Prioritize Fixes

Sort by: Critical FAILs first, then by easiest-to-fix (quick wins), then by impact.

Present to user:
```
Prioritized Fix List:

1. [QUICK WIN] D09 — Add risk removal (Easy, Critical impact)
   Current: No guarantee found
   Fix: Add a money-back guarantee, free trial, or "no obligation" promise
   Question: What guarantee can you offer?

2. [QUICK WIN] D05 — Name your unique mechanism (Easy, High impact)
   Current: Process exists but unnamed
   Fix: Give your method a name (e.g., "The [Your] Method")
   Question: What would you call your approach?

3. [REQUIRES WORK] D01 — Rewrite value proposition (Medium, Critical impact)
   Current: "We provide marketing services" (generic)
   Fix: Reframe around customer outcome with specifics
   Question: In one sentence, what specific outcome does your customer achieve?
```

### Step 4: Interactive Fix Mode

Ask user: "Want to work through these fixes now, or just see the list?"

**If interactive:**
For each fix (in priority order):
1. Show current state
2. Explain the issue and why it matters
3. Ask the specific question
4. Help formulate the improved version
5. Ask: "Want me to update business.md with this?"

**If just the list:**
Present the full prioritized list and suggest: "Run `/offer-maker create` to work through a full offer redesign, or come back to `/offer-maker diagnose` when you're ready to fix specific items."

### Step 5: Update & Verify

After fixes are applied:
1. Update business.md with new offer elements (ask permission)
2. Suggest: "Run `/offer-auditor` again to verify your fixes improved the score"
3. Log to memory

---

## Fix Reference Tables

### Value Pillar Fixes

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| Generic value prop | Afraid to be specific | Narrow ICP; speak to their exact problem |
| No measurable outcome | Feature-focused thinking | Ask: "What changes for the customer in 30/60/90 days?" |
| Low perceived value | Price seems high | Stack value (add bonuses, bundles, extras) or anchor against alternatives |

### Uniqueness Pillar Fixes

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| Easily compared | Commoditized offer | Add unique mechanism, specialize, or bundle differently |
| Nothing unique to claim | No differentiation | Find or create proprietary element (name your process) |
| Thin value stack | Just selling the core product | Add 3+ extras: guides, templates, support, warranty extensions |

### Urgency Pillar Fixes

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| No urgency | Nothing driving action | Add authentic constraint: capacity limits, seasonal deadline, price increase |
| Fake urgency | Manufactured scarcity | Replace with real constraint or remove entirely |

### Trust Pillar Fixes

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| No guarantee | Fear of abuse | Strong guarantees increase conversions more than abuse costs |
| Vague guarantee | Unclear terms | Add specific terms: duration, process, conditions |
| No social proof | Haven't collected it | Start immediately: request reviews, publish case studies |
| No credibility | Haven't built authority | Pursue certifications, awards, partnerships |
