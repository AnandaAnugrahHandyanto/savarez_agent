<!--
Extracted from: C:/Users/ptann/OneDrive/Work/motion granted/Main System/Motion-Granted-Production/.claude/skills/lossy/SKILL.md
Original purpose: Hunts for design-level lossy transformations — silent data loss across pipeline boundaries.
Genericized: 2026-04-21
Operator: Porter Tanner
-->

---
name: lossy
description: Use PROACTIVELY when user says "data is mysteriously degraded", "values dropped between stages", "information lost", or is debugging silent data loss across pipeline boundaries. Hunts design-level lossy transformations — silent field drops, truncations, type narrowing, scale mismatches, JSON round-trips that lose keys, compat layers that discard fields. Not syntax bugs — structural loss that compiles and looks intentional.
disable-model-invocation: true
context: fork
argument-hint: "[pipeline area or file to investigate]"
effort: max
allowed-tools: Bash(grep *) Bash(rg *) Bash(cat *) Bash(head *) Bash(tail *) Bash(wc *) Bash(find *) Read Grep Glob
---

# Lossy Transformation Hunter

Find design-level lossy transformations in this pipeline.

**Target area**: $ARGUMENTS

You are looking for places where data is SILENTLY LOST as it crosses a boundary.
Not syntax errors. Not missing null checks. Structural data loss that compiles fine, passes type checks, and produces plausible-but-wrong results.

## What "Lossy" Means Here

A lossy transformation is when:
- A field with rich data is mapped to a field with less capacity (semantic flattening)
- An array is truncated without logging
- A JSON object is serialized and parsed back with lost keys
- A type assertion narrows away valid variants
- A string template drops structured data into a format that can't be parsed back
- A compat/translation layer silently discards fields
- An aggregation step combines values in a way that destroys the ability to trace back

## Common Lossy Patterns

These are the patterns that have actually burned teams:

1. **JSON repair truncation** — oversized JSON silently truncated by a repair library before the next stage reads it
2. **Field overwrite with wrong semantic** — a field that should hold ground-truth gets overwritten with an earlier-stage prediction
3. **Compat-layer scaling drift** — numeric scales (0.0–1.0 vs 0–100) not reconciled between producer and consumer
4. **ID namespace mismatch** — IDs reformatted across a boundary such that the downstream reader can't reverse-look-up the source

## Hunt Protocol

### 1. Map the Boundaries

For the target area, identify every data boundary:
- Function call interfaces (what goes in vs what comes out)
- DB reads and writes (what the code sends vs what the schema accepts)
- JSON serialization/deserialization points
- Compat/adapter layers
- Type assertions and casts

### 2. Check Each Boundary for Loss

At each boundary, ask:
- **Type narrowing**: Is the output type less expressive than the input type?
- **Field dropping**: Are any input fields absent from the output?
- **Truncation**: Is there a length limit, MAX, or slice that could cut data?
- **Default substitution**: Does a fallback value replace missing data without logging?
- **Serialization round-trip**: Does serialize → deserialize → use lose anything?
- **Aggregation collapse**: Does a reduce/merge destroy per-item identity?

### 3. Trace Actual Data Shapes

Don't just read types — grep for actual runtime data:
```bash
# Find where the data is constructed
grep -n "{field_name}" src/<producer_area>/ --include="*.ts"

# Find where the data is consumed
grep -n "{field_name}" src/<consumer_area>/ --include="*.ts"

# Compare: is the producer writing the same shape the consumer reads?
```

### 4. Check Compat / Adapter Layers

Compat layers are the most common source of silent loss. For any cross-version or cross-system adapter:
```bash
grep -n "=>" src/<adapter_file>.ts | head -30
```
Identify every field mapping. Check for:
- Fields present in input but absent in output
- Numeric scaling (0-1 vs 0-100)
- Enum/string narrowing

## Output Format

```
╔══════════════════════════════════════════════════╗
  LOSSY TRANSFORMATION REPORT
╚══════════════════════════════════════════════════╝

AREA: {target}

BOUNDARY 1: {source} → {destination}
  TYPE: {truncation / field drop / type narrowing / default substitution / ...}
  EVIDENCE: {file}:{line} — {what happens}
  IMPACT: {what data is lost and what downstream effect it has}
  SEVERITY: {SILENT (no log) / LOGGED (but continues) / GATED (blocks pipeline)}

BOUNDARY 2: ...

────────────────────────────────────────────────────
SUMMARY: {N} lossy boundaries found, {N} silent
HIGHEST RISK: {the one most likely to cause wrong results}
```

No soft conclusions. Show the exact transformation, the exact data loss, the exact impact. If you can't prove data is lost at a boundary, it's not a finding.
