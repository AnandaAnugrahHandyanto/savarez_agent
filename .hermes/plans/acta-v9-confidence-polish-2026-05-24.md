# Acta v9 Confidence/Read-State Polish — 2026-05-24

## Visual contract
- Keep Acta on Imperatr Suite v9: near-black/navy base, violet/blue accents, glass panels, compact source-backed rows.
- Do not revive the archived amber terminal/Bloomberg/Palantir contract.
- Preserve signed links, read-state data keys, Telegram follow-up links, jobs/archive/outputs routes, and CSP constraints.

## Scope
1. Add a derived confidence label to Acta source objects so home/feed and Outputs preserve the explicit confidence signal requested by the active design contract.
2. Make the home row read-state/confidence metadata visually tighter and more v9-native without changing open/read behavior.
3. Add focused regression coverage for confidence labels and no old-design remnants.
4. Polish the mobile bottom navigation away from flat black terminal chrome while preserving the same Today/Jobs/Archive/Outputs links and delayed reveal behavior.
5. Harden `/outputs` as a source-object surface: direct row opens, safe signed/Telegram URL gating, CSP-hashed read-state persistence, and regression coverage for unsigned/unsafe rows.

## Out of scope
- No auth/session changes.
- No changes to upload/signing/token behavior.
- No fake dashboards, charts, or non-existent modules.

## Verification gates
- `python -m pytest tests/cron/test_acta_dashboard.py tests/cron/test_html_publish.py -q -o 'addopts='`
- Refresh/publish via `/Users/mozzie/.hermes/scripts/acta_situation_room_refresh.sh` after renderer changes.
- Authenticated QA via `/Users/mozzie/.hermes/scripts/acta_authenticated_qa.sh`.
- Click at least one feed/detail item with Playwright and capture mobile screenshots.
- Search generated artifacts/code for old amber/terminal/Bloomberg/generated-file remnants.
