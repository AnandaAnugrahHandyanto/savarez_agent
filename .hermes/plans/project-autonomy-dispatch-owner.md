# Project Autonomy Dispatch-Owner Implementation Plan

> For Hermes: route implementation through Hermes Maintenance Kanban tasks. Coordinator owns planning/decomposition; developer/researcher profiles own implementation and reviewable changes.

Goal: implement the system-wide project-autonomy model: one project, one coordinator, one project board, one Matrix Space/room, one project dispatch loop, and one project watchdog.

Architecture: add deterministic board ownership metadata, make gateway dispatchers select only boards they own, and extend project bootstrap/watchdog policy so every project has coordinator-owned runtime dispatch plus PA audit-only oversight. This is not migration-only; hermes-migration-system is the motivating example and must remain separately owned until its milestone review.

Tech Stack: Hermes Agent Python codebase, `hermes_cli/kanban_db.py`, `gateway/run.py`, `hermes_cli/kanban.py`, config defaults in `hermes_cli/config.py`, existing project watchdog policy/docs under the Hermes Maintenance repository, pytest.

---

## Requirements from Task 2

Target model:

```text
one project
one coordinator
one project board
one project Matrix room/Space
one project dispatch loop
one project watchdog
```

Deterministic ownership metadata per board should include at minimum:

```yaml
board: <project-slug>
coordinator_profile: coordinator_<project>
dispatch_owner: coordinator_<project>
watchdog_owner: coordinator_<project>
matrix_space: <project Matrix Space>
matrix_room: <project coordinator/project room>
pa_audit_owner: pa_yunuen or pa-global-audit-only
```

Operational rule: a gateway may dispatch only boards whose `dispatch_owner` equals that gateway's active profile, plus any explicitly allowed admin/default board if configured. PA/default gateways must not dispatch project boards.

Watchdog split:
- Project watchdog: coordinator-owned runtime check for progress, dispatcher health, stale tasks, missing heartbeats, Matrix/Kanban/GitHub drift, and coordinator gateway dispatch health.
- PA audit watchdog: PA-owned audit-only check that every project has a watchdog, every watchdog is alive, and every board has exactly one dispatch owner.

## Discovery notes

Existing code shape in the Hermes Agent repo:
- Board metadata already lives in `<root>/kanban/boards/<slug>/board.json` and is read/written by `hermes_cli/kanban_db.py` via `read_board_metadata()` / `write_board_metadata()`.
- Current board metadata fields are presentation/config fields only: `slug`, `name`, `description`, `icon`, `color`, `default_workdir`, `created_at`, `archived`, and computed `db_path`.
- `gateway/run.py::_kanban_dispatcher_watcher()` currently enumerates all non-archived boards and calls `dispatch_once()` on each board when `kanban.dispatch_in_gateway` is true.
- `gateway/run.py::_kanban_notifier_watcher()` also enumerates all boards, but notifier ownership is already scoped by subscription `notifier_profile`; notifier changes are not part of this dispatch-owner fix except for audit/proof.
- `hermes_cli/config.py` defaults `kanban.dispatch_in_gateway` to true, so today any running gateway with the flag enabled can attempt all boards it can see.
- Available project profiles discovered on this host: `coordinator_hermes_maintenance`, `developer_hermes_maintenance`, `researcher_hermes_maintenance`, plus project-specific migration/qwen coordinator/developer/researcher profiles.
- Prior Hermes Maintenance watchdog chain exists from task `t_59b3d78d`; Task 2 must coordinate with, not conflate with, that chain.

## Open design decisions for research before coding

1. Metadata compatibility: whether to extend `board.json` directly or add a nested `ownership` object while preserving existing presentation metadata.
2. Bootstrap CLI shape: whether ownership should be part of `hermes kanban boards create/edit` first, then higher-level project bootstrap consumes it, or whether a dedicated project bootstrap command owns both.
3. Default/admin semantics: exact safe default for `default` board and PA profile. Recommended default: default board can be dispatched by the active default profile only; project boards require explicit dispatch_owner.
4. Migration/backfill: how to detect existing project boards lacking metadata and place them into audit/report-only state until assigned an owner.

## Task graph

Independent research/planning lane first, then implementation tasks with dependencies:

1. Researcher: design deterministic board ownership contract and migration/backfill rules.
2. Developer: add board ownership metadata primitives and tests.
3. Developer: restrict gateway dispatcher by ownership and add multi-profile tests.
4. Developer: update project bootstrap/backfill docs/scripts to assign coordinator dispatch/watchdog ownership and PA audit registration.
5. Developer: update project watchdog policy/templates so watchdog_owner and dispatch_owner are first-class, separate from PA audit-only checks.
6. Developer: prove runtime on Hermes Maintenance and produce a rollout/backfill report for existing boards/projects.

## Acceptance criteria

- Board metadata can represent coordinator_profile, dispatch_owner, watchdog_owner, matrix_space, matrix_room, and pa_audit_owner without breaking existing boards.
- A gateway with profile `coordinator_<project>` dispatches only that project's owned board(s).
- PA/default gateways do not dispatch project boards unless explicitly marked as their non-project/default ownership domain.
- Project bootstrap creates or updates all seven layers: coordinator profile, board, Matrix Space, coordinator Matrix room, dispatch owner, watchdog owner, PA audit registration.
- Project watchdog and PA audit watchdog responsibilities remain separate in code/docs/tests.
- Existing boards without metadata are treated safely: report/audit/skip project dispatch rather than allowing every gateway to fight over them.
- Tests cover multi-board and multi-profile dispatch ownership, missing/legacy metadata, explicit default/admin ownership, and new bootstrap metadata.
- Runtime proof includes healthy silence, unhealthy alert, blocked dormancy, unblock reactivation, and dispatcher ownership enforcement.

## Suggested implementation details

### Phase 1: Ownership metadata primitives

Files likely to modify:
- `hermes_cli/kanban_db.py`
- `hermes_cli/kanban.py`
- `tests/hermes_cli/test_kanban_boards.py`

Implement:
- Extend `read_board_metadata()` defaults with nullable ownership fields or a nested `ownership` object.
- Extend `write_board_metadata()` and relevant CLI board commands to set ownership fields safely.
- Add validation: profile-like values are strings; live Matrix IDs may exist in concrete board metadata but reusable templates must not hard-code them.
- Preserve unknown fields for forward compatibility.

### Phase 2: Dispatcher ownership filter

Files likely to modify:
- `gateway/run.py`
- `tests/gateway/test_kanban_notifier.py` or new gateway dispatcher test file
- `tests/hermes_cli/test_kanban_boards.py`

Implement:
- Add helper, probably in `kanban_db.py`, e.g. `board_dispatch_owner(meta)` and `boards_dispatchable_by(profile)`.
- In `_kanban_dispatcher_watcher()`, compute active profile once with `_active_profile_name()` and enumerate only boards whose `dispatch_owner` equals that profile.
- Legacy board behavior should be safe: project-looking boards without dispatch_owner should not be dispatched by arbitrary gateways; default board can retain legacy dispatch only for profile `default` unless configured otherwise.
- Keep notifier watcher separate; do not accidentally suppress notifications for boards whose dispatcher lives elsewhere.

### Phase 3: Bootstrap/backfill

Files likely to modify:
- `hermes_cli/kanban.py` and/or new project bootstrap command/module
- project coordination docs under `/home/engs2272/.hermes/coordination/`
- Hermes Maintenance repo docs for project-owned watchdogs

Implement:
- Project bootstrap records dispatch_owner and watchdog_owner as coordinator profile.
- Bootstrap creates PA audit registration without making PA a runtime dispatch owner.
- Backfill command/report identifies boards missing exact ownership fields and emits concrete repair commands.

### Phase 4: Watchdog policy integration

Files likely to modify in Hermes Maintenance repo/worktree:
- watchdog/project_watchdog/policy.py
- watchdog/project-watchdog-policy.example.json
- docs/project-owned-watchdog-implementation-plan.md

Implement:
- Add dispatch_owner and watchdog_owner as required/validated fields if not already covered by coordinator/runtime_owner terms.
- Add PA audit checks: every project has a watchdog, watchdog alive, exactly one dispatch owner.
- Keep project watchdog checks coordinator-owned.

### Phase 5: Runtime proof and rollout

Prove:
- `coordinator_hermes_maintenance` dispatches `hermes-maintenance` board.
- `pa_yunuen` does not dispatch project boards.
- `default` does not dispatch project boards.
- `coordinator_hermes_migration_system` ownership is represented but not merged into Hermes Maintenance until migration milestone review.

Deliver:
- rollout/backfill report listing default, pa_yunuen, hermes-maintenance, hermes-migration-system, qwen-image-layered ownership state and required repairs.

## Coordinator note

Blocker status: NOT BLOCKED — Task 2 autonomy handoff received, Matrix contact completed, and implementation/research lanes are being queued through the Hermes Maintenance board.
