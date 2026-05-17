# Review handoff state machine + observability events

Use this when creating Oracle Lab / AgentFlow / Kanban graphs that route implementation through `ccsupervisor` and review through `ccreviewer`.

## State-machine invariant

For implementation cards with a linked/pre-created review child:

```text
implementation_running -> done_GO_for_review      # expected
implementation_running -> blocked_review_required # anomaly unless no review child exists
review_todo_stalled_due_parent_blocked            # anomaly caused by blocked parent
final_ack_missing                                  # anomaly after terminal verdict without origin ACK
```

Why: Kanban dependency promotion treats `done` parents as satisfied. A parent blocked with `review-required` strands the review child in `todo`, so the graph looks idle even though implementation is ready for review.

## Prompt-template rule for ccsupervisor / ccreviewer

Embed this in implementation/review task bodies and profile overlays:

```text
If code/tests pass and a review child already exists, close the implementation parent as done / GO-for-review with changed files, tests, risks, and diff/worktree refs. Do not block as review-required. Use blocked only for real blockers: failed tests, unsafe scope, credentials, destructive approval, or missing user decision. Reviewer owns final GO/BLOCK/NEED_MORE. Operator/fan-in owns origin ACK.
```

## Eval/trace event contract

Minimum event payloads:

```yaml
task_status_transition:
  task_id: t_impl
  transition: implementation_running→done_GO_for_review | implementation_running→blocked_review_required
  expected_transition: implementation_running→done_GO_for_review
  child_review_task_id: t_review
  anomaly: true|false

review_todo_stalled_due_parent_blocked:
  review_task_id: t_review
  parent_task_id: t_impl
  reason: parent_blocked_review_required
  anomaly: true

final_ack_missing:
  task_id: t_final_or_impl
  task_verdict: GO|BLOCK|NEED_MORE|GO-for-review-not-promoted
  ack_status: MISSING|PENDING|FAILED
  return_to: <origin channel/thread/ref>
  anomaly: true
```

Keep task verdict and ACK status separate. `GO` work with a missing ACK is not a code failure; it is an ACK-edge/control-plane failure.

## Operator resolver

1. Inspect parent + child (`hermes kanban show ... --json`) and confirm the block reason is a review handoff, not a real blocker.
2. If a valid review child exists, complete the parent with `GO-for-review` summary and dispatch.
3. If no review child exists, create/assign a review card immediately.
4. Watch final fan-in/ACK. If the verdict is delivered passively but the origin agent did not wake, relay it yourself and record a durable comment.
