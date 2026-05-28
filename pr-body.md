## feat: add modelark-coding-plan provider

### What This PR Does

Adds first-class support for **BytePlus/VolcEngine ModelArk Coding Plan** as a built-in model provider, following the [Adding Providers](https://hermes-agent.nousresearch.com/docs/developer-guide/contributing#adding-providers) contribution path.

### Provider Details

- **Name**: `modelark-coding-plan`
- **Display Name**: BytePlus/VolcEngine ModelArk Coding Plan
- **Aliases**: `modelark`, `byteplus-coding`, `byteplus_coding`, `volcengine-coding`, `bytedance`, `bytepluses`, `bytedance-coding`, `bytedance_coding`
- **Env Var**: `BYTEPLUS_API_KEY`
- **Base URL**: `https://ark.ap-southeast.bytepluses.com/api/coding/v3`
- **Auth**: API key

### Models (13 curated)

`ark-code-latest`, `dola-seed-2.0-pro`, `dola-seed-2.0-lite`, `dola-seed-2.0-code`, `bytedance-seed-code`, `kimi-k2.5`, `glm-5.1`, `glm-4.7`, `deepseek-v3.2`, `deepseek-v4-flash`, `deepseek-v4-pro`, `kimi-k2-thinking`, `gpt-oss-120b`

### Files Changed

| File | Change |
|------|--------|
| `plugins/model-providers/modelark-coding-plan/plugin.yaml` | New — provider manifest |
| `plugins/model-providers/modelark-coding-plan/__init__.py` | New — `ProviderProfile` with aliases |
| `hermes_cli/auth.py` | Add `ProviderConfig` |
| `hermes_cli/providers.py` | Add `HermesOverlay` + aliases |
| `hermes_cli/models.py` | Add `_PROVIDER_MODELS` static list + validation skip + `provider_model_ids()` early return |
| `hermes_cli/config.py` | Add `BYTEPLUS_API_KEY` / `BYTEPLUS_BASE_URL` metadata |
| `hermes_cli/main.py` | Add to explicit provider set |
| `hermes_cli/doctor.py` | Add to `_PROVIDER_ENV_HINTS` |
| `agent/model_metadata.py` | Add prefixes, aliases, context windows |
| `agent/auxiliary_client.py` | Add default aux model fallback |
| `tests/providers/test_plugin_discovery.py` | Add to expected providers |
| `website/docs/integrations/providers.md` | Add provider table + examples |
| `website/docs/reference/cli-commands.md` | Add to `--provider` list |
| `website/docs/user-guide/features/fallback-providers.md` | Add to fallback table |

### Design

- Follows `alibaba-coding-plan` pattern — lean, no models.dev entry, pure static curation
- No `fallback_models` in plugin — single source of truth in `_PROVIDER_MODELS`
- Static validation skips live `/models` probe (like `minimax`, `openai-codex`)
- `supports_health_check` defaults to `True` (matches `alibaba-coding-plan`)
- Model IDs are lowercase per BytePlus docs

### Testing

- **Windows PowerShell** — primary dev environment
- **`hermes model` CLI** — verified provider appears, 13 models listed, model switch works
- **TUI `/model` command** — verified picker shows 13 models, selection succeeds, session switches correctly
- No existing code modified — pure addition, zero regression risk

### Checklist

- [x] Follows existing provider patterns (`alibaba-coding-plan`)
- [x] Model IDs match official docs
- [x] Static curation overrides live discovery
- [x] Documentation updated
- [x] Tests updated
- [x] No existing code modified
- [x] Physically tested on Windows via CLI and TUI