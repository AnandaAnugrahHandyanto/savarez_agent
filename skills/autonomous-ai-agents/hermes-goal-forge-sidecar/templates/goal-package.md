# Hermes Goal Package Template

Copy this into `GOAL.md` and fill only what matters for the task.

```xml
<goal>
[Specific deliverable. Avoid vague "improve" unless paired with measurable behavior.]
</goal>

<context>
[Repo path, files to read first, systems to inspect, and discovery commands.]
</context>

<constraints>
[Architecture rules, non-goals, protected files, safety boundaries, and anti-patterns.]
</constraints>

<scorecard>
Primary metric/checklist: [metric or rubric]
Passing threshold: [number/checklist threshold]
Regression checks: [commands or inspection paths]
Scoring command/path: [exact command or file]
Stop condition: [when the main runner may stop]
</scorecard>

<done_when>
- [Concrete user-visible behavior, command, artifact, or file state.]
- [Each item must be verifiable.]
</done_when>

<feedback_loop>
Fast check: [quick representative command/check]
Expected runtime: [duration]
Cadence: [after each attempt / before phase changes / etc.]
Why representative: [why this catches likely regressions]
Final check: [slower complete verification]
</feedback_loop>

<workflow>
1. Inspect relevant files and existing tests.
2. Update PLAN.md with current phase and next action.
3. Write or update tests first when changing behavior.
4. Implement the smallest safe change.
5. Run the fast feedback loop.
6. Update ATTEMPTS.md with evidence and result.
7. Reread CONTROL.md before phase changes, strategic pivots, expensive steps, or sidecar ingestion.
8. Run final verification before completion.
</workflow>

<working_memory>
Maintain:
- PLAN.md for current strategy, phases, blockers, and next action.
- ATTEMPTS.md for each meaningful attempt, evidence, result, and next adjustment.
- NOTES.md for durable discoveries that should survive context compaction.
</working_memory>

<human_control_surface>
Create and maintain CONTROL.md as the compact operator panel.
Include:
- status_file, attempt_log, durable_notes
- check_control_before
- human priorities
- scope/resource knobs
- approval gates
- sidecar_apply_cadence
- Latest Human Nudge
CONTROL.md may narrow, pause, or require approval, but must not silently weaken done_when or scorecard thresholds.
</human_control_surface>

<verification_loop>
[Targeted test command]
[Broader regression command]
[Manual artifact inspection if needed]
</verification_loop>

<execution_rules>
Preserve unrelated user changes. Inspect before editing. Prefer focused patches. Do not expose secrets.
If using a sidecar, sidecar findings are advice, not success evidence; verify through commands/artifacts.
</execution_rules>

<output_contract>
Final response must include result, tests_run, artifacts, accepted_commits or rejected_reason, sidecar verdict summary, and remaining risks.
</output_contract>
```

## CONTROL.md starter

```md
# CONTROL

## Status Contract
status_file: PLAN.md
attempt_log: ATTEMPTS.md
durable_notes: NOTES.md
check_control_before: phase_change, strategic_pivot, expensive_step, sidecar_ingestion

## Human Priorities
primary_priority: quality
secondary_priority: speed

## Scope Knobs
allowed_files:
- [path/glob]
protected_files:
- [path/glob]
max_blast_radius: [module/package/app]

## Resource Knobs
max_runtime_per_step: [duration]
max_parallel_jobs: [number]
network_allowed: [true | false | approval_required]
external_api_allowed: [true | false | approval_required]

## Decision Gates
require_approval_for:
- strategic_pivot
- destructive_change
- dependency_change
- schema_or_migration_change
- public_api_change
- scope_expansion

## Sidecar Inputs
sidecar_apply_cadence: before_phase_change
nudge_file: none
human_overlay_file: none
review_queue_file: none

## Latest Human Nudge
[Short directive or none.]
```
