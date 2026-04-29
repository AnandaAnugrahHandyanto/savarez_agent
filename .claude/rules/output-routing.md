# Rule: output-routing - where every output goes

## Output destination table

| Output type | Lands at | Read by |
|---|---|---|
| Code edits | repo proper, branch `claude/<topic>-<date>` or `codex/<topic>-<date>` | reviewers, CI, operator merge |
| Chen audit findings | `audits/chen/<YYYY-MM-DD-HHMM>-<topic>.md` | next session, Chen on follow-up |
| /escalate artifacts | `audits/escalations/<timestamp>/` | operator on morning approval |
| Code-reviewer findings | `audits/code-review/<YYYY-MM-DD-HHMM>-<pr-number>.md` | PR author |
| Adversarial-review | `audits/adversarial/<timestamp>/` | architect synthesis |
| Out-of-scope items mid-session | append to `BACKLOG.md` | operator on planning |
| Hard lessons learned | append to `LEARNINGS.md` | every future session via session-start |
| Items operator MUST act on | `OPERATOR-INBOX/<YYYY-MM-DD>-<topic>.md` | Porter |
| Items Clay MUST rule on | `OPERATOR-INBOX/clay/<YYYY-MM-DD>-<topic>.md` | Clay |
| Session-end handoff | `audits/handoffs/<timestamp>.md` | next session, not operator |

## Forbidden output patterns

- Root-level files matching `SESSION-*`, `*-SUMMARY.md`, `WHAT-I-DID-*`, `STATUS-*`, `DRIFT-*`, `OPERATOR-QUEUE.md`, `CLAY-QUEUE.md`, `findings-summary.md`, `audits-summary.md`
- Writes to `LEARNINGS.md` that are not append-only
- Deletions in `BACKLOG.md` that are not operator-approved closeouts

## OPERATOR-INBOX admission criteria

Only three cases qualify:
1. Blocking decision - ambiguity only operator can resolve
2. Ratification request - agent did something needing operator sign-off
3. External-blocker surfacing - Clay ruling, provider outage, upstream Hermes regression

MUST NOT be status reports, session logs, or summaries.
