# Hermes Frontend Engineering Doctrine - 2026-05-17

Status: canonical proposal for `frontend-eng` and frontend-heavy coding work.

Purpose: define how Hermes frontend agents should build polished, useful, verified user interfaces.

## Scope

Use this doctrine for:

- product UI and information architecture;
- web app screens, dashboards, forms, and operator tools;
- frontend state, data loading, interaction flows, and error states;
- visual QA, responsive behavior, accessibility, and browser verification;
- frontend portions of full-stack work.

## Frontend Priorities

1. Understand the user workflow before designing the surface.
2. Fit the existing product and design system.
3. Make the first screen useful, not decorative.
4. Include real states: loading, empty, error, disabled, success, and long-content cases.
5. Verify in a browser when the user-facing surface matters.
6. Avoid generic or average UI when product quality is the point.
7. Use Penpot, reference screenshots, or a written visual brief before high-quality design-to-code work.
8. Treat animation as functional feedback or orientation, not decoration.

## Discovery Before Editing

Before editing, identify:

- app framework and routing;
- existing component library or design tokens;
- current page structure and data flow;
- target user and workflow;
- responsive breakpoints;
- accessibility expectations;
- visual assets and asset ownership;
- Penpot/reference screenshot/design brief availability;
- component library, token, and design-system constraints;
- browser/dev-server command;
- test and screenshot workflow.

If product intent is unclear, ask or create a short assumption note before building.

## Product And Visual Standards

Frontend work should be:

- domain-appropriate;
- scannable and efficient for operational tools;
- visually calm but not bland;
- responsive without text overlap;
- accessible by keyboard and screen reader basics;
- stable under loading, error, empty, and long-content states;
- verified with screenshots or browser inspection for meaningful UI changes.
- aligned with Penpot/reference intent when a design source exists.

Avoid:

- marketing-style hero pages for operational apps;
- nested cards and unnecessary decoration;
- one-note palettes;
- viewport-scaled fonts;
- hidden functionality with no visible affordance;
- fake data that looks like production truth unless clearly fixture/demo data.

## Browser Verification

Use browser or Playwright verification when:

- layout changes;
- forms or interactions change;
- responsive behavior matters;
- screenshots are needed for handoff;
- the change could create overlap, broken spacing, or unreadable states.

Minimum browser evidence for meaningful UI work:

- desktop viewport check;
- narrow/mobile viewport check;
- interaction or state check for the changed workflow;
- console error check when practical.

If browser verification cannot run, state why and provide the strongest alternative evidence.

## Penpot And Design-To-Code

Use `docs/runbooks/penpot-design-to-code.md` when Penpot is part of the work.
The first MCP operation must be read-only. Write actions require an intended
change summary, and MCP keys or URLs containing `userToken` must not be
committed. A meaningful design-to-code handoff includes the design reference,
token/component assumptions, implementation notes, and browser screenshots.

## Data And Backend Boundaries

- Do not invent backend contracts silently.
- If API shape is unclear, inspect backend code or split a backend card.
- Handle missing, partial, delayed, duplicate, and error data.
- Keep local mock/demo data clearly separate from live/customer truth.
- Do not change live GHL/customer-facing behavior unless routed through Blue/GHL doctrine.

## Handoff Checklist

Frontend handoff must include:

- files changed;
- user-facing behavior changed;
- screenshots or browser QA evidence when applicable;
- Penpot/reference screenshot or design brief used when applicable;
- visual critique notes for premium UI work;
- viewports checked;
- interactions/states checked;
- tests/checks run and result;
- known limitations;
- follow-up work or needed approvals.

## Frontend Kanban Done Definition

A frontend card is done when:

- the workflow works for the target user;
- visual hierarchy and spacing are intentional;
- loading/empty/error/long-content states are covered or explicitly out of scope;
- responsive behavior has been checked;
- relevant browser/test checks were run;
- no public/account/customer-facing action was taken without approval;
- handoff evidence is concise and inspectable.
