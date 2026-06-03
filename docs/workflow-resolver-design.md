# Workflow Resolver Design

## Status

This is a docs-only Resolver design. It does not implement an API, connect to Supabase, or trigger any action.

## Purpose

The Resolver selects relevant approved Knowledge and Skills for a work request. It reduces the burden of manually finding the right context and helps maintain consistent workflows.

The first version is **recommendation-only**. It returns what to read and what output contract to follow. It does not execute tasks or change state.

## Resolver inputs

A Resolver request can include:

- `project`: project or domain, such as `gstack`.
- `task_type`: task category, such as `code_review`, `research_note`, `meeting_summary`, or `handoff`.
- `agent_type`: human, review assistant, research assistant, operations assistant, or improvement extraction tool.
- `risk_level`: low, medium, high.
- `requested_action`: review, summarize, implement, approve, reject, export, etc.
- `files_or_domains`: files, systems, teams, or domains involved.
- `active_tools`: tools available in the current workflow.
- `sensitivity`: public internal, internal, restricted, or confidential redacted.

## Resolver outputs

A Resolver response can include:

- `required_skills`: Skills that must be loaded or read.
- `optional_skills`: useful but not mandatory Skills.
- `required_knowledge`: approved Knowledge records or tags.
- `relevant_failure_lessons`: failure lessons to avoid repeating mistakes.
- `relevant_decisions`: prior decisions that constrain the task.
- `required_safety_rules`: safety or risk rules.
- `output_contract`: expected final output shape.
- `approval_requirements`: required human review or approval gates.

## Rule model

A rule contains:

- `rule_name`: stable identifier.
- `priority`: lower numbers win first.
- `match`: JSON object describing conditions.
- `return_config`: JSON object describing returned Skills, Knowledge tags, output contract, and approvals.
- `status`: approved, deprecated, archived, or superseded.
- approval metadata.

Example:

```json
{
  "rule_name": "gstack_code_review",
  "priority": 10,
  "match": {
    "project": "gstack",
    "task_type": "code_review"
  },
  "return_config": {
    "required_skills": [
      "review-readonly",
      "tool-budget-guard"
    ],
    "optional_skills": [
      "redteam-readonly",
      "closeout-pr-readiness"
    ],
    "required_knowledge_tags": [
      "gstack",
      "safety",
      "pr-review"
    ],
    "required_output_contract": "review_findings_v1",
    "approval_requirements": []
  }
}
```

## Resolution algorithm

Initial deterministic algorithm:

1. Validate request shape and organization context.
2. Fetch approved Resolver rules for the organization.
3. Match rules by project, task type, risk level, requested action, and sensitivity.
4. Sort matches by priority and specificity.
5. Merge required Skills, optional Skills, Knowledge tags, output contract, and approval requirements.
6. Fetch approved Knowledge by tags and full-text search.
7. Return a recommendation response.
8. Write an audit row for the resolution request.

The Resolver should not directly write approved records or execute tools.

## API proposal

### POST /workflow-resolve

Request:

```json
{
  "project": "gstack",
  "task_type": "code_review",
  "agent_type": "review",
  "risk_level": "medium"
}
```

Response:

```json
{
  "required_skills": [
    "review-readonly",
    "tool-budget-guard"
  ],
  "optional_skills": [
    "redteam-readonly",
    "closeout-pr-readiness"
  ],
  "knowledge": [
    {
      "type": "project_context",
      "title": "gstack current architecture"
    },
    {
      "type": "failure_lesson",
      "title": "Do targeted checks before broad checks"
    }
  ],
  "output_contract": "review_findings_v1",
  "approval_requirements": []
}
```

### GET /workflow-context

Returns approved Knowledge and Skill context by explicit ids or tags.

### GET /workflow-search

Searches approved Knowledge and Skills. Candidate tables are not broadly searchable by normal users unless policy allows it.

## Candidate-related APIs

Candidate APIs are separate from Resolver APIs:

- `POST /workflow-improvement-candidate`
- `POST /workflow-skill-candidate`
- `POST /workflow-approve-candidate`
- `POST /workflow-reject-candidate`
- `POST /workflow-approve-skill-candidate`
- `POST /workflow-reject-skill-candidate`

Approvals should require reviewer/admin role and audit logging.

## Safety behavior

Resolver output must preserve these boundaries:

- recommendation-only by default,
- no automatic execution,
- no automatic approved Knowledge updates,
- no automatic Skill updates,
- no automatic Resolver rule updates,
- high-risk tasks include explicit approval requirements,
- all resolution calls are auditable.

## Audit behavior

Each Resolver call should log:

- actor id,
- actor role,
- project,
- task type,
- matched rule ids,
- returned Skill names,
- returned Knowledge ids or tags,
- outcome,
- request id,
- timestamp.

Audit logs help detect Resolver rules that are unused, overbroad, or frequently overridden by humans.

## Quality controls

To reduce bad recommendations:

- keep initial rules narrow,
- prefer recommendation-only behavior,
- audit matched rules,
- review high-risk matches manually,
- record user feedback as candidates rather than automatic rule changes,
- periodically review unused Skills and overbroad rules.

## Non-goals for the first version

- No automatic task execution.
- No direct assistant configuration changes.
- No production data writes.
- No automatic approved state updates.
- No implicit approvals.
- No RAG requirement before the basic rule-based Resolver is working.

## Future extensions

After the basic workflow is stable:

- pgvector similarity search for Knowledge and Skills,
- GitHub export mirror of approved Resolver rules,
- UI for rule testing,
- Resolver result feedback loop,
- per-project rule ownership,
- Notion mirror for human browsing.