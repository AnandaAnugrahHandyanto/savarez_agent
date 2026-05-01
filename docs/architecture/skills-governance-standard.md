# Skills Governance Standard

## Scope
This document defines the minimum quality, taxonomy, validation, and promotion rules for skills that live in the Hermes repository.

It applies to:
- `skills/` (built-in)
- `optional-skills/` (official optional)
- skills that are being absorbed from external indexes before they become first-class Hermes assets

## Goals
1. Make skill quality measurable instead of subjective.
2. Reduce drift between docs, scripts, tests, and generated catalogs.
3. Keep routing quality high through stable taxonomy.
4. Make optional→built-in promotion explicit.
5. Prevent low-value skill sprawl.

---

## 1. Minimum Metadata Contract
Every `SKILL.md` must include frontmatter with at least:

```yaml
name: unique-skill-name
description: One-sentence operator-focused description
version: 1.0.0
author: Hermes Agent
```

Recommended additions:
- `license`
- `metadata.hermes.tags`
- `metadata.hermes.related_skills`
- `metadata.hermes.category` when directory category is not the right routing category
- `prerequisites.commands` for required CLIs

### Rules
- `name` must be unique across built-in + optional local skills.
- `description` must describe operator use, not marketing fluff.
- If a skill depends on specific CLIs, APIs, or env vars, say so explicitly.

---

## 2. Quality Tiers
Every local skill should be classifiable into one of these tiers.

### D0 — Document Exists
- `SKILL.md` exists
- frontmatter parses
- catalog indexing works

### D1 — Executable Guidance
Everything in D0, plus at least one of:
- concrete commands
- scripts in `scripts/`
- templates or references that support execution

### D2 — Operationally Safe
Everything in D1, plus:
- `Verification` section
- `Pitfalls` section
- explicit setup/prerequisite boundary
- clear route/decision rule when adjacent skills exist

### D3 — Regression Protected
Everything in D2, plus:
- pytest coverage or a deterministic smoke test
- CI or local automated validation path

### D4 — Runtime Validated
Everything in D3, plus:
- real runtime/live acceptance evidence
- validated against actual external service / artifact reopen / end-to-end outcome

### Repository Targets
- All built-in skills: **minimum D2**
- Core built-in skills: **target D3+**
- Promotion candidates from optional: **minimum D3**
- External absorption candidates: **minimum D2** before cataloging as first-class Hermes-native skills

---

## 3. Taxonomy Rules
Stable taxonomy matters for routing, discoverability, and governance.

### Approved categories
- `apple`
- `autonomous-ai-agents`
- `blockchain`
- `communication`
- `creative`
- `data-science`
- `devops`
- `dogfood`
- `domain`
- `email`
- `gaming`
- `github`
- `health`
- `inference-sh`
- `leisure`
- `mcp`
- `media`
- `migration`
- `mlops`
- `note-taking`
- `productivity`
- `red-teaming`
- `research`
- `security`
- `smart-home`
- `social-media`
- `software-development`

### Rules
- Do not use `other` unless no approved category fits.
- `other` is a temporary quarantine bucket, not a destination category.
- If a skill is routed primarily by workflow, prefer the workflow category over implementation detail.
- If the directory category and routing category differ, use `metadata.hermes.category` explicitly.

### Governance target
- `other` should remain below **5%** of local skills.

---

## 4. Documentation Standard
Every mature skill should answer these questions quickly:
- When should I use this skill?
- When should I NOT use this skill?
- What prerequisites must be checked first?
- What exact commands or scripts should I run?
- How do I verify the result independently?
- What common failure modes/pitfalls matter?

### Required sections for D2+
- `When to Use` or equivalent routing section
- `Prerequisites`
- `Verification`
- `Pitfalls`

### Recommended sections
- `Decision rule`
- `Workflow`
- `Common Patterns`
- `Included Files`
- `Live acceptance ladder`

---

## 5. Testing Standard
### Required for D3+
A skill should have at least one of:
- a dedicated `tests/skills/test_<skill>.py`
- deterministic script smoke coverage inside a broader test file

### Test expectations
Tests should prefer:
- parsing and metadata checks
- script behavior checks
- deterministic output shape
- artifact reopen validation for file-producing workflows
- controlled monkeypatching for network/process boundaries

Tests should avoid:
- brittle dependence on third-party uptime unless explicitly marked as live acceptance
- unbounded waits
- opaque snapshot assertions with no behavioral meaning

### First-wave priority skills for tests
- `docx`
- `xlsx`
- `ocr-and-documents`
- `dogfood`
- `fastmcp`
- `domain-intel`
- `duckduckgo-search`
- `powerpoint`
- `mcporter`
- `native-mcp`

---

## 6. Promotion: Optional → Built-in
Optional skills should be considered for promotion when all are true:
1. High routing value to Hermes core workflows.
2. Quality tier **D3 or above**.
3. Clear prerequisites and safe setup boundary.
4. Repeated real use or repeated audit recommendation.
5. Not overly niche to a single external provider without broad workflow value.

### Current likely promotion candidates
- `fastmcp`
- `honcho`
- `duckduckgo-search`
- `domain-intel`
- `docker-management`

Promotion is not automatic; it requires:
- taxonomy confirmation
- catalog confirmation
- regression coverage
- docs alignment

---

## 7. External Skill Absorption Rule
Do not absorb an external skill just because it exists in Anthropic/LobeHub/OpenAI indexes.

Absorption should happen only if at least one is true:
- it fills a workflow gap Hermes does not cover
- it materially improves an existing Hermes-native workflow
- it can be translated into Hermes-native operational guidance rather than just copied

When absorbing:
1. Audit source skill critically.
2. Strip stale or foreign assumptions.
3. Rebuild as Hermes-native workflow/docs/scripts/tests.
4. Add verification and pitfalls.
5. Prefer composition with existing skills over thin wrappers.

---

## 8. Generated Inventory Contract
The inventory generator should emit, at minimum, per skill:
- source
- category
- path
- tags
- author/version
- `has_scripts`
- `has_references`
- `has_tests`
- `has_verification_section`
- `has_pitfalls_section`
- `quality_tier`
- `runtime_validated`
- `promotion_candidate`

This inventory becomes the operating basis for:
- audit work
- promotion review
- taxonomy cleanup
- prioritizing test additions

---

## 9. Change Management Rule
Any time a skill is edited materially:
1. Re-check the current file before editing.
2. Re-run the relevant test or smoke path.
3. Update the inventory if quality signals changed.
4. If the skill was used and found wrong/outdated, patch it immediately.

The standard is not "file updated".
The standard is "skill still executable and still trustworthy".
