# Acta mobile module nav parity

## Objective
Give every secondary Acta Situation Room surface the same compact mobile bottom navigation affordance as Today, without changing data/auth/signed-link architecture.

## Visual contract
- Dark navy/black Imperatr operator shell.
- Compact dense UI, violet/blue Acta accents.
- Mobile-first route parity for Today, Jobs, Archive, Outputs, and signed/detail pages.
- No fake dashboards, charts, KPIs, or invented source data.

## Scope
1. Add a shared CSP-safe mobile bottom nav helper for secondary Acta pages.
2. Render it on Jobs, Archive index, Outputs, and detail drill-ins with the active module highlighted where applicable.
3. Keep signed row overlays, read-state script, Telegram ASK/FOLLOW-UP links, archive/jobs/output navigation, and existing CSP behavior intact.
4. Add regression tests that all secondary surfaces include compact mobile nav and stale palette/copy markers stay absent.

## Out of scope
- Production deploy changes.
- Auth/session changes.
- Data model changes.
- New Acta modules or fake metrics.

## Verification gates
- Targeted pytest for `tests/cron/test_acta_dashboard.py`.
- Generate local Acta dashboard artifacts without publishing.
- Scan generated/source artifacts for stale amber/generic-dashboard markers.
- Browser QA local generated pages at narrow/mobile viewport where possible; production visual QA may be auth-gated.
- Git diff/status inspection before commit.
