# Control-Plane Artifact Path Verification

Use this during unattended crypto_bot PM/control-plane runs when preflight/self-check/readiness tools write timestamped evidence artifacts.

## Durable lesson

Do not infer the final artifact path from the wall-clock command start time or from a nearby timestamp. Some tools write evidence after internal sub-runs, so the created file may be a few seconds later than the timestamp shown in surrounding terminal output.

## Pattern

1. Run the control-plane/self-check/readiness command normally.
2. Before writing a Kanban/Gitea/PM evidence comment that cites a timestamped artifact, verify the exact file exists.
3. Prefer discovering the newest matching file under the expected evidence directory after the command completes, then cite that path.
4. If a status comment already cited the wrong timestamped path, add a minimal correction comment immediately rather than editing history or leaving ambiguous evidence.

## Applies to

- `/Users/preston/.local/state/hermes-operator/control-plane-self-checks/*-crypto-bot-control-plane-self-check.json`
- completion-gate JSON paths
- PR evidence packets
- Codex sidecar audit prompt/result files

## Reporting shape

Include the verified artifact path and the boolean gate result together, e.g.:

`self-check PASS /Users/preston/.local/state/hermes-operator/control-plane-self-checks/YYYYMMDDTHHMMSSZ-crypto-bot-control-plane-self-check.json; readiness PASS ready_for_next_task=true`
