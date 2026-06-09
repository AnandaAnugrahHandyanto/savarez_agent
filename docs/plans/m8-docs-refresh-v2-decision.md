# M8 — Exhaustive docs refresh v2 (decision)

**Decision (2026-06-09):** **Deferred** — not started in this roadmap phase.

## Rationale

- M6 watcher + M7 wiki/receipt index satisfies “current docs discoverable” without a 344-page semantic swarm.
- M8 trigger (roadmap): operator must explicitly request full reconciliation.
- Cost/risk: bounded worker timeouts, large corpus; no automatic skill rewrites.

## If triggered later

1. Run `hermes_docs_watcher.py`; on hash change, open DWF under `/tmp/hermes-workflows/docs-refresh-v2/<run-id>/`.
2. Deterministic URL map from sitemap (344 URLs) — section partitions.
3. Cap workers (≤3 sources each); parent-verify skill edits.
4. No config/profile/gateway/cron mutation.

## Acceptance when run

- Per-section receipts; failed lanes listed.
- Every skill change cites official URL handle.