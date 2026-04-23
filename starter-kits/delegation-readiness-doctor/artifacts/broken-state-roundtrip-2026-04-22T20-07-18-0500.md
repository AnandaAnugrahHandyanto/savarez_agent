# Delegation Readiness Doctor — Broken-State Roundtrip

Generated: 2026-04-22 20:07 CDT

## Result
BROKEN_STATE_ROUNDTRIP_PROVED

## Broken state induced
- Temporary isolated `HERMES_HOME` was created under `mktemp`.
- `config.yaml` inside that isolated home was set to:
  - `delegation.provider: minimax`
  - `delegation.model: MiniMax-M2.7`
- `MINIMAX_API_KEY` and `MINIMAX_CN_API_KEY` were explicitly removed from the doctor subprocess environment so the readiness path had to fail on missing credentials instead of inheriting the real machine state.

## Before repair — doctor output
```text
◆ Delegation Readiness
  ⚠ Delegation blocked (Delegation provider 'minimax' resolved but has no API key. Set the appropriate environment variable or run 'hermes auth'.)
    → Set a working delegation.provider or delegation.base_url/api_key, or clear the override to inherit the parent runtime.
```

## Canonical repair path
1. Clear the delegation override so subagents inherit the parent runtime.
2. Re-run `python -m hermes_cli.main doctor`.
3. Confirm `◆ Delegation Readiness` flips from blocked to ready before trusting delegated work.

## After repair — doctor output
```text
◆ Delegation Readiness
  ✓ Delegation ready (no delegation override configured; subagents inherit the parent runtime when invoked from an active Hermes session)
```

## Proof notes
- The broken state was isolated to a temporary `HERMES_HOME`; the real `~/.hermes/config.yaml` was not modified.
- The ready state after repair was proved by replacing the isolated config with an empty config (`{}`), which removes the delegation override entirely.
- Script used: `starter-kits/delegation-readiness-doctor/scripts/prove-broken-state-roundtrip.sh`

## Honest next move
Run one real delegated task from the live ready environment and append that proof to the canonical packet.
