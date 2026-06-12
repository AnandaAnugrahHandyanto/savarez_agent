# Codex Dispatch Template

You are executing a delegated Hermes task. Follow this contract exactly.

## Report Path Contract

- Write the final report to `<ABS_REPORT_PATH>`.
- `<ABS_REPORT_PATH>` must be an absolute path inside the target repository.
- If no explicit report path is provided, use `<repo>/.hermes-artifacts/reviews/<JOB_ID>.md`.
- Create the parent directory first: `mkdir -p "$(dirname "$ABS_REPORT_PATH")"`.
- Never use `~` in report paths.

## Turn Budget Baseline

| Task class | Range | Default |
|---|---:|---:|
| `review` | 30-120 | 60 |
| `implementation` | 20-80 | 40 |
| `extract` | 1-10 | 5 |

- Use `<TASK_CLASS>` to choose the correct baseline.
- Respect `<TURN_BUDGET>` when it is explicitly provided.

## End-State Contract

Use exactly one final status:

- `completed` — the task is fully finished and the report is complete.
- `over_budget` — the turn budget was exhausted before the task finished.
- `interrupted` — execution was stopped by an external interruption.
- `partial_output` — there is usable output, but the task is incomplete.

Do not label partial work as `completed`.

## Final Report Template

```md
Status: completed | over_budget | interrupted | partial_output
Job-ID: <JOB_ID>
Task-Class: <TASK_CLASS>
Turn-Budget: <TURN_BUDGET>
Report-Path: <ABS_REPORT_PATH>

Summary:
- ...

Work Completed:
- ...

Remaining Work / Next Step:
- ...
```
