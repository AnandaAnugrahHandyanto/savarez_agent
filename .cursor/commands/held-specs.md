---
description: Check active held-spec constraints before governed edits
arguments:
  - name: spec_id
    description: Optional spec identifier to narrow the check
    required: false
---

# Held Specs Check: {{spec_id}}

## Step 1: Fetch governed state

1. `knowledge_read(artifact="held_spec_ledger")`
2. `knowledge_read(artifact="contradiction_ledger")`
3. If a spec ID is supplied: `town_handoff_bundle(spec_id="{{spec_id}}")`

## Step 2: Determine edit posture

- If the spec appears in held-spec matches: design-only or operator-approved work.
- If the spec appears in contradiction matches: resolve or escalate before editing.
- If no match appears: absence in local artifacts is not proof of approval.

## Step 3: Report

Summarize:
- Spec: `{{spec_id}}`
- Held matches: `[list or none]`
- Contradiction matches: `[list or none]`
- Latest-state matches: `[list or none]`
- Next allowed action: `[specific action]`

Do not bypass held specifications, regardless of change size.
