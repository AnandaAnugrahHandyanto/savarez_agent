# Hermes AI Office — Agent Observability Pattern Survey

Last updated: 2026-05-08 11:32 KST
Status: Stage 1 research artifact. Documentation-only.

## Sources and patterns considered

Search results and product knowledge reviewed for:

- LangSmith / LangGraph observability
- OpenTelemetry AI-agent observability conventions
- GitHub Actions / CI pipeline dashboards
- Linear/Jira-style issue boards
- Cron/automation health dashboards
- Pixel Agents / Smallville game-like visualization

Representative source URLs from web search:

- https://www.langchain.com/langsmith/observability
- https://www.langchain.com/articles/agent-observability
- https://opentelemetry.io/blog/2025/ai-agent-observability/
- https://blog.langchain.com/end-to-end-opentelemetry-langsmith/

## Pattern 1 — Trace tree / execution graph

Used by LangSmith-like products.

Strengths:

- Excellent for debugging exact model/tool/retrieval steps.
- Shows latency, cost, errors, and nested calls.
- Useful when a single task fails or quality degrades.

Weaknesses for Hermes AI Office MVP:

- Too detailed for at-a-glance operations.
- May expose prompts, tool arguments, files, or private content.
- Requires instrumentation discipline and redaction.

Hermes use:

- Later task inspector detail panel.
- Not the main office overview.

## Pattern 2 — Kanban/issue board

Used by Linear/Jira/GitHub Projects-like tools.

Strengths:

- Natural fit for Hermes Kanban.
- Easy to group by status, assignee, project, blocked/done.
- User already cares about project handoffs.

Weaknesses:

- Less visually delightful than pixel office.
- Does not show automation health unless integrated.

Hermes use:

- Primary data model for read-only MVP.
- Pixel rooms should be a visual projection of board/task state.

## Pattern 3 — CI/pipeline dashboard

Used by GitHub Actions, Buildkite, CircleCI.

Strengths:

- Good for automation status, failed jobs, retry history, last/next run.
- Highlights broken recurring jobs.

Weaknesses:

- Does not represent user-requested work well.

Hermes use:

- Automation room / cron panel.
- Daily health digest job failures should be visible.

## Pattern 4 — Event stream / activity feed

Used by operations dashboards and incident tools.

Strengths:

- Provides chronological ground truth.
- Good handoff material.
- Can drive speech bubbles later.

Weaknesses:

- Can become noisy.
- Needs redaction and summarization.

Hermes use:

- Task inspector and “recent office activity” panel.
- Store/display event type and safe summary, not raw transcripts in MVP.

## Pattern 5 — Spatial/pixel office

Used by Pixel Agents and game-like dashboards.

Strengths:

- Fast emotional recognition of “what is busy/blocked/idle.”
- Good for multi-agent mental model.
- User specifically requested this style.

Weaknesses:

- Harder to make accurate than tables/cards.
- Can become novelty over utility.
- Renderer/assets/dependency concerns.

Hermes use:

- Stage 8 after data layer is reliable.
- Keep inspector/table fallback for exact state.

## Recommended UX composition

MVP should combine patterns:

1. Top summary strip: running / blocked / ready / done / failed automation counts.
2. Board rooms: Kanban boards grouped by status.
3. Automation panel: cron jobs with last/next/error/delivery target.
4. Topic map: known Telegram topics and their routed boards/jobs.
5. Task inspector: safe metadata, dependencies, events, session links.
6. Later pixel layer: visual projection of the same normalized `OfficeState`.

## Critical design rule

The office view must be an observability surface over real Hermes state, not a second source of truth.

If a pixel character says “blocked,” that status must come from Kanban/session/gateway/cron state. If the UI cannot prove the state, it should show “unknown” rather than invent behavior.
