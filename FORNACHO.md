# FORNACHO — Hermes Agent

## Architecture

Hermes is a chat agent with several “surfaces” that all route into the same core runtime:

- **CLI** (`cli.py`) handles terminal slash commands like `/goal` and `/supergoal`.
- **Gateway** (`gateway/run.py`) handles Telegram/Discord/etc. slash commands.
- **Command registry** (`hermes_cli/commands.py`) is the shared source of truth for command names, aliases, help text, and platform menus.
- **Kanban DB** (`hermes_cli/kanban_db.py`) is the durable task board where multi-agent work can survive across sessions.

The important idea: chat commands should be thin surfaces. Durable behavior belongs in small reusable modules, so CLI and Telegram don’t drift.

## `/goal` vs `/supergoal`

`/goal` is the “Ralph loop”: Hermes keeps the current session working toward one standing objective. After each turn, a judge decides whether the goal is complete. If not, Hermes queues a continuation.

`/supergoal` is different. It creates a Kanban-backed control-plane task and queues Hermes to act as an orchestrator. Think of it as creating a mission folder, then asking Hermes to break the mission into smaller cards, assign/spawn builders, and verify proof before declaring victory.

Analogy:

- `/goal` = “keep thinking/working on this until done.”
- `/supergoal` = “start a tiny project studio around this objective.”

## Structure added for `/supergoal`

- `hermes_cli/supergoal.py`
  - Shared implementation.
  - Creates the Kanban parent/control-plane task.
  - Subscribes the originating gateway chat/thread to task notifications when possible.
  - Builds the kickoff prompt that tells Hermes to decompose, assign/spawn builders, review, and require proof.

- `cli.py`
  - Adds `_handle_supergoal_command()`.
  - Prints status or creates a supergoal.
  - Queues the kickoff prompt into the current CLI session.

- `gateway/run.py`
  - Adds `_handle_supergoal_command()`.
  - Handles Telegram/messaging `/supergoal`.
  - Queues a synthetic message event with the kickoff prompt.
  - Allows `/supergoal status` mid-run, but rejects creating a new supergoal while the agent is already running to avoid queue races.

- `hermes_cli/commands.py`
  - Registers `/supergoal` with alias `/sg`.

- `tests/test_supergoal.py`
  - Verifies the shared helper creates a Kanban task and notification subscription.
  - Verifies the command is registered.

## Tech choices

The first implementation is intentionally a **thin wrapper** rather than a full autonomous manager:

1. Create durable Kanban state.
2. Queue Hermes as the orchestrator in the current session.
3. Let Hermes use existing Kanban/delegation/Codex tools to do the next steps.

This avoids prematurely inventing a second workflow engine. The board is the durable memory; Hermes is the orchestrator; Codex/builders can be added behind the task decomposition step.

## Decisions

- Kept `/goal` unchanged to preserve its simple mental model.
- Added `/supergoal` instead of overloading `/goal` because project-scale orchestration has different expectations and side effects.
- Used `hermes_cli/supergoal.py` as a shared helper so CLI and gateway behavior stays aligned.
- Made proof requirements explicit in the Kanban task body and kickoff prompt.
- Did not auto-assign the parent task to a worker. The current Hermes session receives the kickoff prompt and becomes the orchestrator; it can then decide what child tasks/workers are needed.

## Bugs & fixes

- Initial test assumed Kanban task IDs started with uppercase `T`; the actual Hermes Kanban IDs are lowercase like `t_abc123`. The test was corrected to reflect real behavior.
- The Control Center API task creation worked, but PATCHing the task status via `/api/tasks/TASK-080` returned the app’s 404 HTML. That endpoint shape differs from the POST endpoint; not relevant to Hermes code, but worth remembering for Control Center automation.

## Pitfalls

- Kanban `task_links` are dependency links, not necessarily “epic/child” hierarchy. Don’t blindly link a supergoal parent to child work if that would block the child tasks until the parent is done.
- Creating a new `/supergoal` while an agent is already running would queue a kickoff turn and race the current session. Gateway handling allows status mid-run but rejects new supergoals until idle or `/stop`.
- If future versions spawn Codex directly, keep Hermes as the lifecycle owner: Codex should build, not decide whether the whole mission is done.

## Lessons

Good agent orchestration is mostly about **state and proof**, not model cleverness.

The durable loop should be:

1. Put the mission on a board.
2. Decompose into tasks with acceptance criteria.
3. Spawn focused workers.
4. Require verifiable proof.
5. Review before completion.
6. Keep the human updated only at useful boundaries.

That is what `/supergoal` is designed to grow into.
