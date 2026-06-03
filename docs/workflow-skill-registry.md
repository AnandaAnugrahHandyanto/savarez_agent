# Workflow Skill Registry

## Status

This is a docs-only design for the approved Skill registry and Skill candidate lifecycle.
It does not install, publish, or mutate any runtime Skill library.

## Purpose

The Skill Registry stores reusable business procedures, checklists, review rubrics, and work templates. It improves repeatability by making the expected workflow explicit and approved.

A Skill is not just a prompt. It is a structured procedure that can be read by humans and AI-assisted tools.

## Approved Skill fields

An approved Skill should include:

- `name`: stable identifier such as `review-readonly`.
- `version`: semantic or organization-approved version.
- `status`: `approved`, `deprecated`, `archived`, or `superseded`.
- `purpose`: what the Skill is for.
- `applies_to`: task types and contexts where it applies.
- `inputs`: required and optional inputs.
- `procedure`: ordered steps.
- `constraints`: actions the operator must not take.
- `output_contract`: required output shape.
- `checklist`: verification items.
- `failure_handling`: what to do when the workflow cannot complete.
- `related_knowledge_tags`: tags used to retrieve supporting Knowledge.
- `owner`: accountable maintainer.
- `approved_by`: human reviewer.
- `approved_at`: approval timestamp.

## Example Skill

```json
{
  "name": "review-readonly",
  "version": "1.0.0",
  "status": "approved",
  "purpose": "Review code diffs or plans without mutating files or external state.",
  "applies_to": ["code_review", "pr_review", "diff_review"],
  "inputs": {
    "required": ["diff_or_plan", "task_scope"],
    "optional": ["test_results", "known_constraints"]
  },
  "procedure": [
    "Confirm the review scope.",
    "Inspect only the supplied diff, plan, and referenced files needed for verification.",
    "Identify blockers, high-risk findings, medium-risk findings, and test gaps.",
    "Do not modify files or create external side effects."
  ],
  "constraints": [
    "Do not edit files.",
    "Do not commit.",
    "Do not push.",
    "Do not create a PR.",
    "Do not change config, auth, identity, or credentials."
  ],
  "output_contract": [
    "summary",
    "blockers",
    "high_risk_findings",
    "medium_risk_findings",
    "test_gaps",
    "recommended_next_action"
  ],
  "checklist": [
    "Scope was respected.",
    "No mutation was performed.",
    "Findings cite concrete evidence.",
    "Unverified concerns are labeled as such."
  ],
  "failure_handling": {
    "insufficient_context": "Return a blocked verdict and list the missing evidence.",
    "potential_sensitive_data": "Stop and request redaction review."
  },
  "related_knowledge_tags": ["review", "safety", "read-only"]
}
```

## Skill candidate lifecycle

Skill candidates are stored separately from approved Skills.

Lifecycle states:

- `pending`: proposed and awaiting review.
- `needs_redaction`: may contain sensitive material.
- `needs_more_evidence`: needs examples or proof of repeated usefulness.
- `approved`: promoted to `workflow_skills`.
- `rejected`: rejected with reason.
- `superseded`: replaced by a newer candidate or existing Skill.

## Candidate sources

A Skill candidate may come from:

- repeated review feedback,
- repeated operational mistakes,
- meeting retrospectives,
- incident analysis,
- handoff failures,
- process gaps discovered during work,
- human-authored procedure proposals.

## Promotion criteria

A candidate should become an approved Skill only when:

- it is reusable beyond one incident,
- the scope is clear,
- required inputs are explicit,
- procedure steps are actionable,
- constraints prevent unsafe overreach,
- output contract is testable,
- failure handling is defined,
- redaction is complete,
- the owner and approver are recorded.

## Rejection reasons

Common rejection reasons:

- one-off and not reusable,
- too vague to execute,
- too broad for one Skill,
- duplicates an existing Skill,
- contains sensitive material,
- lacks evidence,
- too heavy for the value it provides,
- belongs in Knowledge rather than Skill.

## Versioning

Use versioning to preserve reviewability:

- Minor changes can update checklist items or wording.
- Major behavior changes should create a new version.
- Deprecated Skills should remain readable for audit and migration.
- Superseded Skills should point to the replacement.

## Resolver integration

Resolver rules should reference Skills by stable name and optionally version constraints. Resolver output should separate:

- required Skills,
- optional Skills,
- output contract,
- approval requirements.

The Resolver must not mutate Skills. It only recommends what to read.

## Review checklist for Skill changes

Before approval, reviewers should check:

- Is this a Skill rather than a Knowledge note?
- Is the procedure reusable?
- Are inputs and outputs explicit?
- Are constraints strong enough?
- Does it avoid automatic production changes?
- Does it avoid storing credential material?
- Does it define failure handling?
- Does it reference relevant Knowledge tags?
- Is ownership clear?

## Non-goals for the first version

- No automatic Skill promotion.
- No runtime Skill installation.
- No automatic rewrite of assistant behavior.
- No direct config changes.
- No automatic execution based on Skill content.
- No bulk import of raw transcripts.