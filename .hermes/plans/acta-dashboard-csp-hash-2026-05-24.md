# Acta dashboard CSP hash hardening

## Objective
Remove the broad `script-src 'unsafe-inline'` CSP allowance from the main Acta Situation Room dashboard while preserving the existing inline read-state, row-open, pull-to-refresh, and mobile bottom-nav behavior.

## Scope
- `cron/acta_dashboard.py`: generate the main dashboard inline script as a deterministic string and use `_inline_script_csp(script)` for the page CSP, matching the `/outputs` page pattern.
- `tests/cron/test_acta_dashboard.py`: add/adjust regression coverage proving the main dashboard CSP uses a `sha256-...` source and does not include `unsafe-inline`, while preserving existing JS markers such as `location.reload()`, `IntersectionObserver`, and row overlay hooks.

## Out of scope
- No visual redesign beyond security hardening.
- No cron/job scheduling changes.
- No production deploy changes unless tests and local artifacts pass.

## Verification gates
- Targeted pytest for `tests/cron/test_acta_dashboard.py`.
- Static scan for `unsafe-inline` in Acta dashboard generated HTML and source tests.
- Generate local Acta dashboard artifacts and open `/`, `/jobs`, `/archive`, `/outputs`, plus a signed/detail target where available.
- Inspect git diff/status for unrelated files or secrets.
