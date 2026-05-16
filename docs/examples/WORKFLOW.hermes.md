---
polling:
  interval_ms: 30000
agent:
  runner: hermes
  max_concurrent_agents: 1
  max_turns: 20
hermes:
  mode: subprocess
  command: hermes
tracker:
  api_key: $LINEAR_API_KEY
workspace:
  root: ./.symphony/workspaces
---
# Hermes Symphony Workflow

You are working on Linear issue `{{ issue.identifier }}`: {{ issue.title }}.

Issue URL: {{ issue.url }}
Current state: {{ issue.state }}
Attempt: {{ attempt }}

## Goals

1. Inspect the issue and the repository in the current workspace.
2. Make the smallest safe change that satisfies the issue.
3. Run targeted tests or checks that are appropriate for the change.
4. If the change affects UI behavior, capture before/after evidence and save it under the evidence directory shown in the Symphony Runtime Context.
5. Produce a concise handoff with:
   - what changed;
   - tests/checks run;
   - evidence file paths, if any;
   - remaining risks or follow-up.

## Evidence workflow

Use the `SYMPHONY_EVIDENCE_DIR` environment variable or the evidence path from the runtime context. Suggested filenames:

- `before.png`
- `after.png`
- `test-output.txt`

Do not include secrets in screenshots, logs, commits, or handoff comments. Do not upload evidence to third-party image hosts unless this repository's workflow explicitly asks for it.

## Safety rules

- Stay inside the assigned workspace.
- Do not commit or push unless the issue workflow explicitly asks for it.
- Do not modify unrelated files.
- Prefer reversible, minimal changes.
- If blocked by missing credentials, rate limits, or ambiguous requirements, stop and report the blocker clearly.
