# audits/

Append-only working-artifact storage for audit/review/escalate outputs. Five subfolders:

- `chen/` - Chen sub-agent findings
- `escalations/` - /escalate runs
- `code-review/` - code-reviewer findings
- `adversarial/` - adversarial-review outputs
- `handoffs/` - session-end handoff context

Individual reports are gitignored as working artifacts. Folder structure is committed via .gitkeep. Operator manually commits high-signal audits.
