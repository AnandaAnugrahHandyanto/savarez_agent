---
sidebar_position: 5
title: "Route Contracts"
description: "Content-safe runtime route proofs for provider/model/auth/cost invariants"
---

# Route Contracts

Hermes route contracts answer a concrete operator question: **what route am I on, and is it allowed before work starts?**

The contract layer does not choose providers. Runtime resolution still lives in `hermes_cli/runtime_provider.py`. Route contracts take the resolved provider/model/auth/runtime shape and produce a small, content-safe proof object that can be surfaced in health, trace, dashboard, and TUI surfaces without leaking credentials.

## Covered surfaces

Tier 2 treats these as separate routes, even when they share implementation plumbing:

| Surface | Source | Why it is separate |
|---|---|---|
| `primary` / `cli` | foreground chat agent | Baseline model/provider/runtime proof |
| `delegation` | `tools/delegate_tool.py` child agents | Children can override provider/model/toolsets and must not silently inherit the wrong API mode |
| `cron` | `cron/scheduler.py` autonomous jobs | Fresh sessions can run unattended, so forbidden fallback must fail before work starts |
| `tui` | `tui_gateway/server.py` | The Ink/Dashboard chat session has its own startup resolver and session info event |
| `gateway` | `gateway/run.py` platform sessions | Messaging platforms can apply per-session `/model`, reasoning, service-tier, and fallback settings |
| `dashboard` | `hermes_cli/web_server.py` `/api/status` | The operator status panel needs route evidence without exposing secrets |

## Proof shape

`hermes_cli.route_contracts.build_agent_route_proof(...)` returns a redacted dictionary with fields including:

- `surface`
- `provider`
- `model`
- `api_mode`
- `runtime`
- `base_url_host`
- `base_url_path_hint` (only known-safe API route segments such as `/backend-api/codex` or `/api/v1`; arbitrary proxy paths become `/<redacted-path>`)
- `credential_present`
- `credential_kind`
- `auth_surface`
- `cost_surface`
- `reasoning_effort`
- `service_tier`
- `fallback_chain_count`
- `contract.status`
- `contract.violations[]`

It intentionally does **not** include:

- raw API keys
- OAuth bearer tokens
- query parameters
- connection strings
- raw prompt/user content

## Hard contract: Codex app-server auth

`api_mode = codex_app_server` is the Codex subprocess/runtime route. It must not be backed by an OpenAI Platform API key.

Blocked example:

```text
provider=openai-codex
api_mode=codex_app_server
auth_surface=platform_api_key
```

Allowed shape:

```text
provider=openai-codex
api_mode=codex_app_server
auth_surface=oauth
cost_surface=subscription
```

This catches the failure mode where Hermes silently falls back from the intended ChatGPT/OAuth subscription route to per-token OpenAI API billing.

## Cost-surface policy

The proof classifies cost as one of:

- `subscription`
- `local`
- `per_token_api`
- `cloud_metered`
- `none`

By default, Hermes records the cost surface without forbidding API-backed routes globally, because many users intentionally configure paid APIs. Callers that need a stricter environment can pass a policy such as:

```python
verify_agent_route_contract(
    ...,
    policy={"allowed_cost_surfaces": ["subscription", "local"]},
)
```

That blocks `per_token_api` before a model turn starts.

## Runtime integration points

- `AIAgent.__init__` builds `agent._route_proof` after credentials/fallback are resolved and before the first model turn.
- Delegated child agents pass `route_surface="delegation"`.
- Cron agents pass `route_surface="cron"`.
- TUI session info includes `route_proof`.
- Dashboard `/api/status` includes a dashboard route proof.
- Harness turn traces include `route_proof` in `turn.start` and normalized turn result records.

## Testing

Focused route-contract tests live in:

- `tests/hermes_cli/test_route_contracts.py`
- `tests/hermes_cli/test_web_server.py::TestWebServerEndpoints::test_get_status`

Run them through the hermetic wrapper:

```bash
scripts/run_tests.sh tests/hermes_cli/test_route_contracts.py tests/hermes_cli/test_web_server.py::TestWebServerEndpoints::test_get_status -q
```
