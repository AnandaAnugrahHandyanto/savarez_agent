<!--
Extracted from: (synthesized scaffold from Motion-Granted-Production SKILL.md conventions)
Original purpose: Structural template for authoring new skills in tanner-stack.
Genericized: 2026-04-21
Operator: Porter Tanner
-->

---
name: <lowercase-name>
description: >
  One-paragraph description of what this skill does, when to use it, and what it
  produces. Keep it specific enough that the model can decide relevance without reading
  the body. Prefer active voice and imperative verbs.
disable-model-invocation: true
context: fork
argument-hint: "[expected argument description, or remove if none]"
effort: low | medium | high | max
allowed-tools: Bash(grep *) Bash(rg *) Read Grep Glob
---

# <SKILL NAME> — <One-Line Headline>

<One paragraph orienting the reader to what this skill is for. Who should invoke it, on what target, and what kind of output to expect.>

## When to Invoke

- "<Example trigger phrase 1>"
- "<Example trigger phrase 2>"
- "<Third scenario that makes this the right tool>"

## Protocol

### Step 1: <Action verb>
<What the skill does first. Concrete commands where applicable.>

```bash
<example command>
```

### Step 2: <Action verb>
<Next step.>

### Step 3: <Action verb>
<Next step.>

## Output Format

```
╔══════════════════════════════════════════════════╗
  <REPORT TITLE>
╚══════════════════════════════════════════════════╝

<slot>: <value>
<slot>: <value>

VERDICT: <enum of possible outcomes>
```

## Rules

1. <Rule 1 — what this skill refuses to do or what it insists on.>
2. <Rule 2 — evidence standard, if applicable.>
3. <Rule 3 — when to hand off to another skill or persona.>

## Notes

- <Edge case 1>
- <Edge case 2>
- <Integration with other skills, if relevant>

---

## How to use this template

1. Copy this directory: `cp -r skills/_template skills/<your-skill-name>`
2. Replace all `<placeholder>` text.
3. Fill in the frontmatter fields; delete any that don't apply (e.g., `argument-hint` for arg-less skills).
4. Test the skill with a realistic scenario before committing.
5. Add a row to `docs/extending.md` under "Skills registry."
6. Keep the provenance header — update `Extracted from:`, `Original purpose:`, `Genericized:`, and `Operator:`.
