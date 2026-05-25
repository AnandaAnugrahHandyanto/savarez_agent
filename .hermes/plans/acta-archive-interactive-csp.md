# Acta archive-day interactive CSP slice

## Objective
Make published `/archive/YYYY-MM-DD` Acta day snapshots preserve the same read/unread hydration and mobile swipe/read affordances as Today, without making the archive index or signed detail reports script-enabled.

## Persona/scenario
Persona: mobile operator reviewing yesterday's Acta archive from Telegram.
Scenario: open `/archive`, tap a dated snapshot, inspect the highest-priority archived row, mark/open it, and verify confidence/freshness/provenance remain legible on a narrow viewport.

## Acceptance criteria
- Worker maps `/archive/YYYY-MM-DD` to `public/archive/YYYY-MM-DD.html` and serves the interactive dashboard CSP headers for that exact day-page pattern.
- `/archive` / `public/archive/index.html` remains scriptless/default headers.
- Signed detail reports remain scriptless/default headers.
- Existing signed row gating/read-state behavior remains unchanged in the renderer.
- Regression tests cover route/header parity.
- Fixture/browser QA demonstrates archive day page read-state script works and mobile layout has no horizontal overflow.

## Out of scope
- No cron job changes.
- No production deploy in this run unless all local gates pass and deployment is already configured.
- No redesign of detail report internals.
