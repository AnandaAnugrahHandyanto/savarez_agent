# Acta Dashboard Digest/Trace Sprint — 2026-05-25

## Objective
Make the Acta Situation Room home feed feel like an operator daily brief instead of a cron résumé: default to a compact Digest view, preserve full provenance/confidence in an explicit Trace mode, and keep development sprint noise tucked behind a background lane.

## CEO feature bets
1. Obvious but necessary — keep feed lane separation and mobile density intact after recent Acta feed changes.
2. High-leverage personal workflow — add a digest/trace split so P sees what to read/action first, while deeper provenance remains one tap away.
3. Weird/ambitious but potentially magical — start turning Acta into an attention router that labels items as Read now / Later / Needs decision / Background.

## MVP slice for this run
- Add/validate Digest vs Trace mode on the dashboard.
- Add Today’s Brief with compact counts and top item names/action state.
- Keep dev sprint lane collapsed as background by default.
- Preserve signed row overlays, read toggles, ASK/thread links, confidence, freshness, provenance, and mobile lane separation.

## Out of scope
- No new fake data, model scoring, charts, or generic dashboard widgets.
- No cron scheduling/delivery changes.
- No SSO weakening or production credential use.

## Verification gates
- `pytest tests/cron/test_acta_dashboard.py -q`
- `pytest tests/cron/test_acta_browser_uat.py -q`
- Direct browser UAT harness against a generated local dashboard fixture, viewport 390x844, console clean, no horizontal overflow.
- Stale marker scan for old amber/generic dashboard markers in touched/generated Acta output.
