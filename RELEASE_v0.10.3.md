# Hermes Agent v0.10.3 (v2026.4.23)

**Release Date:** April 23, 2026

> MoA observability and synthesis follow-up release. Adds full routed-turn forensics, deterministic attribution fallback, MiMo self-draft MoA v2, and a corrected Spar success contract in ACP logs.

---

## ✨ Highlights

- **MoA full forensics** — forced MoA turns now record `reference_outputs`, `reference_previews`, `failed_models`, `failed_model_errors`, `per_model_metrics`, `decision_trace`, and `aggregator_influence_log` in `~/.hermes/logs/route_forensics.jsonl`.

- **MiMo self-draft in MoA v2** — MoA now runs:
  1. `xiaomi/mimo-v2-pro (self-draft)`
  2. `minimax/MiniMax-M2.7-highspeed`
  3. `deepseek/deepseek-reasoner`
  4. `xiaomi/mimo-v2-pro` synthesis

- **Deterministic trace fallback** — when the auxiliary forensic-analysis subcall returns placeholder junk, Hermes now falls back to a deterministic trace built from the raw model outputs instead of logging unusable attribution.

- **Corrected Spar ACP contract** — completed `force-spar` routed turns now log `success: true` when the review executed, with `approved: true/false` preserved as the actual verdict.

---

## ⚠️ Upgrade Note

- Forced MoA forensic logs now include full raw reference outputs. Treat `route_forensics.jsonl` as sensitive operational data.
- Older routed turns are **not** backfilled. The expanded forensic schema only applies to turns executed after this release.
- ACP consumers should read `approved` for Spar verdicts and `success` for execution state.

---

## ✅ Validation

- `source venv/bin/activate && scripts/run_tests.sh tests/tools/test_mixture_of_agents_tool.py`
- `source venv/bin/activate && scripts/run_tests.sh tests/acp/test_server.py`
- live local and VPS routed-turn checks for:
  - `force-moa`
  - `force-spar`
