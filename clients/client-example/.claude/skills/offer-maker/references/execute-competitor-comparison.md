# Execute — Competitor Offer Comparison (E03)

Read when `/offer-maker competitor` is invoked.

## Prerequisites

1. Check `context/competitor-ads/*.csv` exists
   - If missing: "No competitor ad data found. Run `/competitor-scraper [domain]` first to pull competitor ads."
   - If exists: proceed
2. Read `context/business.md` for our offer details
3. Read `context/brand.md` for our value prop, USPs, trust signals

---

## Flow

### Step 1: Extract Our Offer Elements

From business.md and brand.md, extract our offer across the 4 pillars:

| Pillar | What to extract |
|--------|----------------|
| Value | Value prop, dream outcome, perceived value |
| Uniqueness | USPs, unique mechanism, value stack |
| Urgency | Deadlines, scarcity, time constraints |
| Trust | Guarantee, social proof, credibility signals |

### Step 2: Extract Competitor Offers

Read each `context/competitor-ads/*.csv` file. For each competitor:

1. Extract ad headlines and descriptions
2. Identify offer elements: pricing, guarantees, free trials, discounts
3. Identify proof claims: customer counts, ratings, awards
4. Identify urgency elements: deadlines, limited offers
5. Identify differentiation claims: unique features, specializations

Group by competitor (use domain or brand name).

### Step 3: Build Comparison Matrix

Create a pillar-by-pillar comparison:

| Pillar | Our Offer | Competitor 1 | Competitor 2 | Competitor 3 | Assessment |
|--------|-----------|-------------|-------------|-------------|------------|
| **Value** | {our VP} | {their VP} | {their VP} | {their VP} | Win/Tie/Lose |
| **Uniqueness** | {our USP} | {their USP} | {their USP} | {their USP} | Win/Tie/Lose |
| **Urgency** | {our urgency} | {theirs} | {theirs} | {theirs} | Win/Tie/Lose |
| **Trust** | {our proof} | {their proof} | {their proof} | {their proof} | Win/Tie/Lose |

### Step 4: Identify Positioning

For each pillar:
- **Win:** We have a clear, defensible advantage
- **Tie:** Similar offering, no clear winner
- **Lose:** Competitor has stronger positioning

### Step 5: Generate Recommendations

Based on comparison:

| Scenario | Recommendation |
|----------|---------------|
| Win 3-4 pillars | "Strong competitive position. Emphasize your advantages in ad copy." |
| Win 2, Tie 2 | "Competitive but not dominant. Strengthen your tie areas." |
| Win 1 or fewer | "Weak positioning. Run `/offer-maker create` to redesign the offer." |

Specific recommendations per losing pillar:
- Lose on Value → Stack more value, reframe outcome
- Lose on Uniqueness → Find or create proprietary element
- Lose on Urgency → Add authentic scarcity
- Lose on Trust → Strengthen guarantee, collect more proof

---

## Output

Write to `context/analysis/competitor-offer-comparison.md`:

```markdown
# Competitor Offer Comparison

**Date:** {YYYY-MM-DD}
**Account:** {client name}
**Competitors analyzed:** {count}

---

## Summary

| Pillar | Us | {Comp 1} | {Comp 2} | {Comp 3} | Result |
|--------|-------|----------|----------|----------|--------|
| Value | {summary} | {summary} | {summary} | {summary} | {Win/Tie/Lose} |
| Uniqueness | {summary} | {summary} | {summary} | {summary} | {Win/Tie/Lose} |
| Urgency | {summary} | {summary} | {summary} | {summary} | {Win/Tie/Lose} |
| Trust | {summary} | {summary} | {summary} | {summary} | {Win/Tie/Lose} |

**Overall:** {X} wins, {X} ties, {X} losses

---

## Detailed Analysis

### {Competitor 1 Name}
**Source:** {csv filename}

**Their offer elements:**
- Value: {extracted}
- Uniqueness: {extracted}
- Urgency: {extracted}
- Trust: {extracted}

**Key ad copy themes:**
- {theme 1}
- {theme 2}

**Our advantage:** {what we do better}
**Their advantage:** {what they do better}

[Repeat for each competitor]

---

## Recommendations

1. {Priority 1: specific action}
2. {Priority 2: specific action}
3. {Priority 3: specific action}

---

## Messaging Implications

Based on competitive positioning, adjust angle emphasis:
- **Double down on:** {angles where we win}
- **Address head-on:** {angles where we're competitive but not dominant}
- **Avoid:** {claims competitors can counter}
```
