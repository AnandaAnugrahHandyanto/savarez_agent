---
name: fleet-market-data-staleness
description: Production runs aborting due to market_data.json staleness — recurs across multiple days when collect_market_data.py fails to run
metadata:
  type: project
---

market_data.json last successfully collected 2026-05-15. Gate threshold is 5d max staleness. As of 2026-05-21/22, it is 6–7d stale, causing EVERY production run invocation to abort before screen execution.

**Why:** cron_data_refresh.sh does NOT call collect_market_data.py — that must be run manually or via a separate mechanism. The auto-refresh inside run_daily_production.py only catches minor drift, not a >5d gap. build_historical_iv_features.py within data_refresh is being OOM-killed (Killed signal), which may be disrupting the broader refresh.

**How to apply:** When production snapshot is missing (no rankings.csv), check market_data.json modification date first. If >5d stale, manual `python collect_market_data.py --universe production_data/universe.json` is required before any production run can complete. This is a P0 blocker — all downstream agents that expect rankings.csv will fail or skip (data_auditor ERROR, fleet_steward WARN, qa STALE, ic_health_monitor STALE, etc.).
