# kanban-final-closeout-gate

`kanban-final-closeout-gate` is a read-only helper for final closeout checks in GitHub-backed Kanban workflows.
It is a gate, not a second audit pass: it consumes existing evidence manifests and guard receipts, then reports pass/fail, gaps, evidence URLs, and the recommended next owner/action.

## Entry points

Installed console script:

```bash
kanban-final-closeout-gate check \
  --issue 157 \
  --pr 99999 \
  --task-id t_48bed874 \
  --repo GTZhou/TianGongKaiWu \
  --board tiangongkaiwu \
  --manifest executor-review-closeout.yaml \
  --guard-receipt duplicate-child-guard.json \
  --receipt-file closeout-gate-receipt.json \
  --markdown-report-file closeout-gate-report.md \
  --actor-profile jiangzuodajiang \
  --json
```

Source-tree smoke without installation:

```bash
python3 -m hermes_cli.kanban_final_closeout_gate doctor --actor-profile jiangzuodajiang --json
python3 -m hermes_cli.kanban_final_closeout_gate check --manifest manifests.yaml --guard-receipt guard.json --json
```

## Inputs consumed

The helper consumes the existing public contract objects only:

- `tiangongkaiwu.executor_handoff.v1`
- `tiangongkaiwu.review_decision.v1`
- optional `tiangongkaiwu.final_closeout_gate.v1`
- `kanban-duplicate-child-guard:receipt:v1`

It does not introduce a parallel metadata structure. The emitted receipt is derived evidence for the gate run.

## Gate checks

The JSON receipt includes these `gate_checks`:

- `artifact_matches_approval`
- `review_decision_approved`
- `required_tests_or_checks`
- `lifecycle_labels_readable`
- `trace_receipts_complete`
- `kanban_task_graph_terminal`
- `public_text_sanitation`
- `identity_block_verified`
- `duplicate_child_guard_receipt`

A failing gate includes `gaps[]` entries with `code`, `message`, `evidence`, `next_owner`, and `next_action`.

## Safety boundary

The helper is read-only. It does not merge PRs, close issues, change labels, send traces, mutate Kanban tasks, restart services, or touch credentials.

The receipt includes `public_safety.no_mutations_performed=true` and explicit false values for merge/close/label/trace side effects.

Public-text sanitation checks detect common credential/token patterns and raw platform locators such as raw Telegram/Discord/Slack target IDs. Public evidence should use aliases like `telegram:中书门下`, not raw platform locators.
