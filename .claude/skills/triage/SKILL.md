<!--
Written fresh: v0.3.1 cleanup pass (closes dry-run trace #5 from docs/build-notes/adversarial-cleanup-2026-04-22.md)
Original purpose: Structured option-comparison framework for when user presents 2+ choices and asks for help picking.
Created: 2026-04-22
Operator: Porter Tanner
-->

---
name: triage
description: Use PROACTIVELY when user says "help me decide between", "which should I pick", "A or B", "what's better", or presents 2+ explicit options for comparison. Runs structured comparison framework — success criteria, tradeoffs on each option across the same dimensions, second-order effects, recommendation with confidence level. DO NOT USE for surfacing pending project decisions that need attention — that is the `decide` skill.
argument-hint: "[options to compare, or paste the choice context]"
allowed-tools: Read Grep Glob
---

# Triage — Structured Option Comparison

Help the user decide between 2+ explicit options.

**Options / context**: $ARGUMENTS

> **If the user has not named the options clearly**, ask: "What are the options I'm comparing? Please list each one explicitly so I can triage them against the same dimensions."

---

## The Problem This Solves

"Which should I pick, A or B?" is a decision-triage problem, not a decision-discovery problem. The `decide` skill is for surfacing project decisions the operator hasn't explicitly raised yet (pending work, stale branches, unresolved TODOs). `triage` is for when the options are already named and the operator wants help weighing them.

Unstructured "I recommend A because it seems better" wastes the operator's time. Structured triage applies the same dimensions to each option, surfaces second-order effects, and states a recommendation with an explicit confidence level — so the operator can either accept the call or push back on a specific dimension they weight differently.

---

## Protocol

### Step 1: Define success criteria (before comparing)

Before evaluating any option, state what a good answer looks like. Examples:
- "The right choice minimizes time-to-ship for this sprint."
- "The right choice preserves optionality for the architecture rewrite in Q3."
- "The right choice is the one we can reverse cheaply if we're wrong."

If success criteria are not stated, the comparison becomes a vibes contest. **Name them explicitly before comparing.**

If the operator has not given enough context to state success criteria, halt and ask:
> "Before I triage, what are you optimizing for? Speed, reversibility, long-term maintenance, something else?"

### Step 2: List tradeoffs per option across the same dimensions

Pick 3–6 dimensions that matter for this decision (drawn from the success criteria). Evaluate each option against every dimension. Keep the dimensions the same across options — no cherry-picking.

Typical dimensions:
- **Implementation effort** — time / complexity
- **Reversibility** — can we undo this cheaply?
- **Blast radius** — what else does this change touch?
- **Long-term maintenance** — who owns this in 6 months?
- **Dependencies** — what does this block or require?
- **Known unknowns** — what can't we predict?

### Step 3: Surface second-order effects

For each option, ask: "If we pick this, what else becomes true in 3–6 months that isn't obvious today?" Examples:
- Locks us into a vendor / library / pattern
- Forces a migration later
- Creates a dependency on a team / person
- Makes a future refactor easier or harder

Second-order effects often flip the first-order answer. Surface them explicitly.

### Step 4: Recommend with confidence level

State the recommendation plainly:
> "Recommend **Option A**. Confidence: **High / Medium / Low**."

- **High** = dimensions stack cleanly for one side; second-order effects confirm; reversible if wrong.
- **Medium** = dimensions mostly stack but one favors the other; second-order unclear.
- **Low** = tradeoffs are genuinely balanced; depends on factors not given; worth more thought.

### Step 5: Flag the escape hatches

State explicitly if any of these apply:
- **Neither option is correct** — the real answer is a third path or a scope change
- **More info needed** — one specific question would flip the recommendation
- **Time-sensitive** — the recommendation changes based on when the decision is made
- **Reversibility asymmetric** — one option is much easier to undo than the other; lean that way if confidence is Low

---

## Output Format

```
╔══════════════════════════════════════════════════╗
  TRIAGE
╚══════════════════════════════════════════════════╝

OPTIONS
  A: <short label>
  B: <short label>
  (C: <if more>)

SUCCESS CRITERIA
  <1–3 sentences>

COMPARISON
| Dimension      | Option A          | Option B          |
|----------------|-------------------|-------------------|
| <dim 1>        | <assessment>      | <assessment>      |
| <dim 2>        | <assessment>      | <assessment>      |
| ...            | ...               | ...               |

SECOND-ORDER EFFECTS
  A: <what becomes true if we pick A>
  B: <what becomes true if we pick B>

RECOMMENDATION
  <Option X>
  Confidence: <High | Medium | Low>
  Reasoning: <one paragraph>

ESCAPE HATCHES (if applicable)
  - <Neither option / more info needed / reversibility note>
```

---

## Rules

1. **Success criteria first, comparison second.** Do not compare options before naming what a good answer looks like.
2. **Same dimensions for every option.** No cherry-picked strengths. Evaluate A and B on the same axes.
3. **Always state confidence.** High / Medium / Low. No confident-looking recommendations without the confidence label.
4. **Flag "neither" when it's the answer.** If neither option is correct, say so — do not pick the least-bad option to look decisive.
5. **Do not surface pending project decisions** — the `decide` skill does that. Triage is only for options the user has explicitly put on the table.
