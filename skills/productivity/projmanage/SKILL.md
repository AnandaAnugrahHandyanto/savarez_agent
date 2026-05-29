---
name: projmanage
description: "Use when managing local projects, tasks, or milestones via the projmanage CLI. Covers project/task/milestone CRUD, board view, stats, and automatic status transitions."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
prerequisites:
  commands: [python3]
metadata:
  hermes:
    tags: [projmanage, project-management, task-manager, CLI, milestone, local-db]
---

# projmanage — Local Project & Task CLI

## Overview

`projmanage` is a local-first project/task/milestone management CLI backed by SQLite. The data lives at `~/.projmanage/projmanage.db`. The command entry point is `python /root/.projmanage/__init__.py` (aliased as `projmanage` in PATH).

**Hierarchy:** `Project → Milestone → Task` (milestone is NOT optional for tasks)

**Automatic milestone status rule:**
- No tasks → `planning`
- Has incomplete tasks → `in_progress`
- All tasks done → `completed`

Manual `--status` on milestones is rejected by the CLI and overwritten by the DB layer.

---

## When to Use

- User asks to create/view/update/delete a project, task, or milestone
- User asks to see a board view or project stats
- User asks about task progress, milestone completion, or project statistics
- User asks to assign tasks, link dependencies, or add comments
- **Don't use** for cloud/team features (Linear, GitHub Issues, etc.) — use the appropriate skill instead

---

## Project Commands

### Create project
```bash
projmanage proj new "<title>" [--desc "description"]
```

### List all projects
```bash
projmanage proj list
```

### View project
```bash
projmanage proj view <project_id>
```

### Update project
```bash
projmanage proj update <project_id> [--name "新名称"] [--desc "新描述"]
```

### Delete project
```bash
projmanage proj delete <project_id> [--force]
```
> `-` cascades and deletes all milestones, tasks, and attachment files in that project

---

## Attachment Commands

### Add attachment (copy file to project folder, record in task)
```bash
projmanage task add-attachment <task_id> <local_file_path>
```
> The file is copied (not referenced) to `~/.projmanage/projects/{project_id}/attachments/{timestamp}_{filename}`. The path stored in the task is the absolute path to the stored copy.

### Remove attachment (deletes file + DB record)
```bash
projmanage task remove-attachment <attachment_id> [--force]
```
> `task view` shows `[attachment_id]` next to each file — use that ID.

### Attachment display
`task view <task_id>` automatically shows all attachments inline (filename + path + size).

### Cascade behavior
- Deleting a task → attachment files + DB records auto-deleted
- Deleting a project → entire attachments folder deleted

---

## Milestone Commands

### Create milestone
```bash
projmanage milestone new <project_id> "<title>" \
  [--desc "description"] \
  [--due YYYY-MM-DD]
```
> New milestones are always `planning`. Status auto-updates as tasks are added/completed.

### List milestones for a project
```bash
projmanage milestone list <project_id>
```
Output columns: ID / status / progress bar / title / due date

### View milestone detail
```bash
projmanage milestone view <milestone_id>
```

### Update milestone (title/desc/due only — NOT status)
```bash
projmanage milestone update <milestone_id> \
  [--title "新标题"] \
  [--desc "新描述"] \
  [--due YYYY-MM-DD]
```
> `--status` is intentionally absent. Status is auto-managed.

### Delete milestone
```bash
projmanage milestone delete <milestone_id> [--force]
```
> RESTRICT: refuses if any tasks belong to this milestone. Delete tasks first.

---

## Task Commands

### Create task (milestone REQUIRED)
```bash
projmanage task new <project_id> "<title>" \
  --milestone <milestone_id> \
  [--desc "description"] \
  [--priority 1|2|3] \
  [--assignee <member_id>] \
  [--due YYYY-MM-DD]
```

### List tasks
```bash
projmanage task list <project_id> [--milestone <milestone_id>]
```

### View task
```bash
projmanage task view <task_id>
```

### Update task
```bash
projmanage task update <task_id> \
  [--title "新标题"] \
  [--desc "追加的描述内容"] \
  [--status todo|doing|done|blocked] \
  [--priority 1|2|3] \
  [--assignee <member_id>] \
  [--due YYYY-MM-DD] \
  [--milestone <new_milestone_id>]
```
> **描述追加规则：** `--desc` 会追加到原描述末尾（用换行分隔），不是替换。

### Delete task
```bash
projmanage task delete <task_id> [--force]
```

### Task lifecycle shortcuts
```bash
projmanage task start <task_id>    # → status: doing
projmanage task done <task_id>     # → status: done; may auto-complete milestone
projmanage task block <task_id>    # → status: blocked
projmanage task unblock <task_id>  # → status: todo
```

### Assign task
```bash
projmanage task assign <task_id> [--assignee <member_id>]
```

---

## Board & Stats

### Board view (grouped by milestone)
```bash
projmanage board view <project_id>
```
Shows per-milestone progress bars, task IDs grouped by status, overdue tasks, unassigned tasks.

### Stats panel
```bash
projmanage board stats <project_id>
```
Shows overall progress bar, task counts by status, per-milestone progress bars, member stats.

### Shortcut
```bash
projmanage stats <project_id>   # same as board stats
```

---

## Member Commands

```bash
projmanage member new "<name>" [--role "role"] [--email "email@example.com"]
projmanage member list
projmanage member view <member_id>
projmanage member update <member_id> [--name "新名称"] [--role "新角色"] [--email "新邮箱"]
projmanage member delete <member_id>
```

---

## Task Dependency Commands

```bash
# Set parent_id must-complete-before child_id can start
projmanage task link <parent_id> <child_id>

# Remove dependency
projmanage task unlink <parent_id> <child_id>

# View parent tasks (what blocks this)
projmanage task parents <task_id>

# View child tasks (what this blocks)
projmanage task children <task_id>
```

> When parent task is marked done, child task is auto-unblocked to `todo`. If parent is not done and child is not `blocked`, child is auto-set to `todo`.

---

## Task Comments & Events

```bash
# Add comment
projmanage task comment add <task_id> <author> "<body>"

# List comments
projmanage task comment list <task_id>

# Event log (status changes, assignments, blocks, etc.)
projmanage task log <task_id>
```

---

## Milestone Status — Auto Rule Details

| Condition | Status |
|---|---|
| milestone has 0 tasks | `planning` |
| milestone has tasks and some are not done | `in_progress` |
| all tasks in milestone are done | `completed` |

Trigger points (all in `db.py`):
- `task_create` → `_sync_milestone_status(milestone_id)`
- `task_delete` → `_sync_milestone_status(milestone_id)`
- `task_update` (milestone_id changed) → sync both old and new milestone
- `task_set_status` → `_sync_milestone_status` after status update

**If the user tries to manually set milestone status:** The CLI rejects `--status` on `milestone new/update`. Even if they somehow bypass the CLI, `_sync_milestone_status` will overwrite it on the next task operation.

---

## Common Patterns

### Full project bootstrap
```bash
projmanage proj new "新项目" --desc "描述"
# note the project_id from output
projmanage milestone new <project_id> "v1.0 MVP" --due 2026-06-01
projmanage task new <project_id> "任务1" --milestone <milestone_id> --priority 1
projmanage task new <project_id> "任务2" --milestone <milestone_id> --priority 2
projmanage board view <project_id>
```

### Complete a milestone (automatic)
```bash
projmanage task done <task_id>   # repeat until all done
# when last task is done:
# → milestone status auto becomes completed
# → output shows: "🎉 里程碑 [xxx] 已自动完成！"
```

### Append to task description
```bash
# Each --desc appends to the existing description (not replaces)
projmanage task update <task_id> --desc "第一阶段完成"
projmanage task update <task_id> --desc "补充：需要联调"
# Description now contains both lines
```

### Migrate task to different milestone
```bash
projmanage task update <task_id> --milestone <new_milestone_id>
# both old and new milestones recalculate their status
```

### Clean up before deleting milestone
```bash
# Must delete tasks first (RESTRICT enforced)
projmanage task list <project_id> --milestone <milestone_id>
# note task IDs
projmanage task delete <task_id_1> --force
projmanage task delete <task_id_2> --force
projmanage milestone delete <milestone_id> --force
```

---

## Important Constraints

1. **Task must belong to a milestone.** `milestone_id` is `NOT NULL` in the schema. `task new` requires `--milestone`.
2. **One task → one milestone.** No multi-milestone assignments.
3. **Milestone deletion is RESTRICTED.** If the milestone has any tasks, deletion is rejected. Delete all tasks first.
4. **Project deletion cascades.** Deleting a project deletes all its milestones and tasks automatically (FK CASCADE).
5. **Milestone status is auto-only.** There is no CLI flag to manually set it. Any attempt goes through `_sync_milestone_status` which overwrites based on task state.

---

## Database Location

```
~/.projmanage/projmanage.db
```

Schema files:
- `/root/.projmanage/schema.sql` — raw DDL
- `/root/.projmanage/schema.py` — SQLAlchemy models
- `/root/.projmanage/db.py` — all DB operations

Key tables: `projects`, `milestones`, `tasks`, `members`, `task_links`, `task_events`, `task_comments`, `attachments`

---

## Code Reference

**`_sync_milestone_status`** (`db.py`): The central function that computes and writes milestone status based on task state. Called by `task_create`, `task_delete`, `task_update`, `task_set_status`.

**`_check_milestone_completion`** (`db.py`): Legacy completion check. Still called after `task_set_status` for the "milestone auto-complete" echo message in the CLI. Do not remove.

**`fmt_milestone_status`** (`__init__.py`): Formats milestone status for terminal output with color. `planning`→yellow, `in_progress`→cyan, `completed`→green.

---

## Common Pitfalls

1. **Forgetting `--milestone` on `task new`.** It is required. Without it the DB raises a NOT NULL constraint error.

2. **Trying to manually set milestone status.** The `--status` flag doesn't exist on milestone commands. Tell the user status is automatic.

3. **Trying to delete a milestone with tasks.** Use `task delete <id> --force` for each task first, then delete the milestone.

4. **Assuming `task new` accepts `--status`.** It does not. Task status is set via `task start/done/block/unblock` after creation.

5. **Migrating a task to a milestone in a different project.** The FK constraint doesn't prevent cross-project assignment, but the business logic assumes milestones are per-project. Don't do this.

6. **Passing a non-existent file to `add-attachment`.** The file must exist locally. Click validates with `exists=True` in the argument definition.

7. **Forgetting the attachment ID on `remove-attachment`.** Run `task view <task_id>` first to see the `[attachment_id]` for each file.

---

## Verification Checklist

- [ ] `projmanage proj list` works
- [ ] `milestone new` creates milestone in `planning` state (0 tasks)
- [ ] `task new --milestone <id>` creates task and milestone becomes `in_progress`
- [ ] `task done` on last incomplete task → milestone becomes `completed`
- [ ] `milestone delete` with tasks → error "请先删除任务"
- [ ] `task update --milestone <new_id>` syncs both old and new milestone status
- [ ] `board view` shows per-milestone progress bars
- [ ] `board stats` shows milestone progress bars
