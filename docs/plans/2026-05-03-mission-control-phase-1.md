# Hermes Mission Control Phase 1 Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Build the first read-only Hermes Mission Control dashboard that combines chat-adjacent operational awareness with projects, agents, usage/cost, cron, sessions, and skills.

**Architecture:** Extend the existing local Hermes Web Dashboard instead of introducing a separate app. Add one protected REST endpoint that aggregates existing Hermes state, then add a React page and sidebar tab that renders the command-center view. Phase 1 is read-only and local-first.

**Tech Stack:** FastAPI backend in `hermes_cli/web_server.py`; React/Vite TypeScript frontend in `web/src`; existing Hermes session DB, cron job store, skill finder, project index at `~/.hermes/projects/`.

---

## Task 1: Backend overview endpoint

**Objective:** Add `/api/mission-control/overview` that returns read-only command-center data.

**Files:**
- Modify: `hermes_cli/web_server.py`
- Test: `tests/hermes_cli/test_mission_control_dashboard.py`

**Steps:**
1. Add project inventory helpers that read `get_hermes_home() / "projects" / "inventory.json"` and group projects by bucket.
2. Add lightweight process scanner for Hermes/OpenClaw/Codex/Claude/OpenCode processes using `ps`.
3. Add usage summary helper using the existing `sessions` table columns.
4. Add active sessions, cron, and skills summaries using existing code paths.
5. Expose `GET /api/mission-control/overview` with no side effects.
6. Add tests for project grouping and process parsing.

## Task 2: Frontend API types

**Objective:** Add typed API client support for the new overview endpoint.

**Files:**
- Modify: `web/src/lib/api.ts`

**Steps:**
1. Add `getMissionControlOverview()` API method.
2. Add TypeScript interfaces for projects, agents, usage, cron, skills, sessions, and overview response.

## Task 3: Mission Control page

**Objective:** Add a read-only dashboard page that renders the overview data.

**Files:**
- Create: `web/src/pages/MissionControlPage.tsx`

**Steps:**
1. Fetch overview on mount and refresh button.
2. Show summary cards: cost, tokens, active agents, current/planning/future projects.
3. Render project buckets.
4. Render active agents/processes and active sessions.
5. Render cron jobs, skills summary, and recent sessions.
6. Keep all controls read-only except navigation links to existing tabs.

## Task 4: Navigation integration

**Objective:** Make Mission Control the dashboard home.

**Files:**
- Modify: `web/src/App.tsx`

**Steps:**
1. Import `MissionControlPage`.
2. Route `/mission-control` to the page.
3. Add sidebar nav item before Sessions.
4. Redirect `/` to `/mission-control`.

## Task 5: Verification

**Objective:** Confirm backend tests and frontend build/type checks pass.

**Commands:**
- `python -m pytest tests/hermes_cli/test_mission_control_dashboard.py -q`
- `npm --prefix web run build`

**Acceptance Criteria:**
- `/api/mission-control/overview` returns JSON without mutating Hermes state.
- Dashboard has Mission Control tab and home redirect.
- Page shows token/cost, projects by bucket, active processes/agents, cron, sessions, and skills.
- Phase 1 does not create/start/kill agents or mutate projects.
