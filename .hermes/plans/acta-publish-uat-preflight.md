# Acta publish UAT preflight slice

Objective: harden Acta publishing so the Situation Room does not upload a broken operator-facing dashboard without a real-browser mobile/feed-lane UAT pass.

## Feature bets

1. Obvious but necessary — publish-time browser UAT gate.
   - MVP: run existing Acta browser UAT harness before upload; fail closed; provide explicit emergency skip.
2. High-leverage personal workflow — verify P's mobile operator scenario before publishing.
   - MVP: assert daily/dev lanes, mobile viewport, console/page errors, and no horizontal overflow in the preflight report.
3. Weird/ambitious — Acta self-critiques and drafts follow-ups before P opens a brief.
   - MVP: not this run; too much agency risk without interaction design.

BUILD NOW: publish-time browser UAT gate.

## Scope

- Keep Acta data/auth/publishing architecture intact.
- Preserve signed artifact/detail publishing, read-state affordances, ASK/follow-up links, and archive/jobs/outputs routes.
- Add regression tests for preflight run, fail-closed abort, skip hatch, and diagnostics.

## Verification gates

- Targeted Acta dashboard and browser UAT tests pass.
- Real browser fixture UAT runs at 390x844 where tooling is available.
- Diff review confirms no secrets/unrelated files.
