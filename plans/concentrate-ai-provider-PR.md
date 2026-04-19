# Concentrate AI Provider — PR Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Add Concentrate AI as a first-class provider to hermes-agent and submit a PR to NousResearch/hermes-agent.

**Architecture:** Concentrate AI is a Path A (OpenAI-compatible) aggregator provider with 115+ models, auto-routing, and pay-per-use pricing. It follows the same pattern as the Arcee AI provider PR #9276 but with aggregator semantics (like OpenRouter/Nous).

**Tech Stack:** Python, pytest, git, gh CLI

**Repo:** ~/projects/oss_contributions/hermes-agent (fork: gama-oni/hermes-agent, upstream: NousResearch/hermes-agent)

**Key API Details:**
- Base URL: `https://api.concentrate.ai/v1`
- Auth: Bearer token via `Authorization: Bearer <CONCENTRATE_API_KEY>`
- Env vars: `CONCENTRATE_API_KEY` (primary), `CONCENTRATE_BASE_URL` (override)
- Protocol: Standard OpenAI Chat Completions
- Live model list: `GET /v1/models` (returns list of model objects with slug, aliases, etc.)
- `is_aggregator=True` (like OpenRouter)

---

## Phase 1: Branch Setup

### Task 1: Create feature branch from latest upstream/main

```bash
cd ~/projects/oss_contributions/hermes-agent
git fetch upstream
git checkout -b feat/concentrate-ai-provider upstream/main
```

**Verify:** `git branch --show-current` outputs `feat/concentrate-ai-provider`

---

## Phase 2: Core Provider Registration (8 files)

### Task 2: Add ProviderConfig to hermes_cli/auth.py

**Files:**
- Modify: `hermes_cli/auth.py`

**Step 1:** Find the `xiaomi` ProviderConfig entry in `PROVIDER_REGISTRY` (after `xiaomi`).

**Step 2:** Add after it:

```python
    "concentrate": ProviderConfig(
        id="concentrate",
        name="Concentrate AI",
        auth_type="api_key",
        inference_base_url="https://api.concentrate.ai/v1",
        api_key_env_vars=("CONCENTRATE_API_KEY",),
        base_url_env_var="CONCENTRATE_BASE_URL",
    ),
```

**Step 3:** Find the `_PROVIDER_ALIASES` dict inside `resolve_provider()`. Add after `xiaomi`-related aliases:

```python
    "concentrate-ai": "concentrate",
```

Note: There are TWO alias dicts in auth.py — one in `resolve_provider()` and one later in the file near `_PROVIDER_ALIASES`. Check both and add to whichever pattern exists.

**Verify:** `source venv/bin/activate && python -c "from hermes_cli.auth import PROVIDER_REGISTRY; print('concentrate' in PROVIDER_REGISTRY)"` → True

### Task 3: Add HermesOverlay to hermes_cli/providers.py

**Files:**
- Modify: `hermes_cli/providers.py`

**Step 1:** Find `HERMES_OVERLAYS` dict. Add after the `arcee` entry:

```python
    "concentrate": HermesOverlay(
        transport="openai_chat",
        is_aggregator=True,
        base_url_env_var="CONCENTRATE_BASE_URL",
    ),
```

**Step 2:** Find the `ALIASES` dict (or `PROVIDER_ALIASES`). Add:

```python
    "concentrate-ai": "concentrate",
```

Note: providers.py may have TWO alias locations (like auth.py). Check both.

**Verify:** `source venv/bin/activate && python -c "from hermes_cli.providers import HERMES_OVERLAYS; print('concentrate' in HERMES_OVERLAYS)"` → True

### Task 4: Add model catalog to hermes_cli/models.py

**Files:**
- Modify: `hermes_cli/models.py`

**Step 1:** Find `_PROVIDER_MODELS` dict. Add a `"concentrate"` key with model list:

```python
    "concentrate": [
        # OpenAI
        "gpt-5.4", "gpt-5.4-mini", "gpt-5.4-nano", "gpt-5.4-pro",
        "gpt-5.3-codex", "gpt-5.2", "gpt-5.1", "gpt-5.1-codex-max", "gpt-5.1-codex-mini",
        "gpt-5", "gpt-5-mini", "gpt-5-nano",
        "o1", "o3", "o4-mini",
        "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano", "gpt-4o", "gpt-4o-mini",
        # Google
        "gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-flash",
        # Anthropic
        "claude-opus-4-6", "claude-sonnet-4", "claude-haiku-3.5",
        # Meta
        "llama-4-maverick", "llama-4-scout",
        # DeepSeek
        "deepseek-r1", "deepseek-v3-0324",
        # xAI
        "grok-3", "grok-3-mini",
    ],
```

Adjust model list to match what the Concentrate API actually returns (we confirmed 115 models via curl).

**Step 2:** Find `CANONICAL_PROVIDERS` (or `ProviderEntry` list). Add:

```python
    ProviderEntry("concentrate", "Concentrate AI", "Concentrate AI (115+ models, auto-routing, pay-per-use)"),
```

**Step 3:** Find the `_PROVIDER_ALIASES` dict in models.py. Add:

```python
    "concentrate-ai": "concentrate",
```

**Step 4 (Optional):** Add `fetch_concentrate_models()` function following the `fetch_openrouter_models()` pattern, for live model catalog fetching from `GET /v1/models`.

**Verify:** `source venv/bin/activate && python -c "from hermes_cli.models import _PROVIDER_MODELS, CANONICAL_PROVIDERS; print('concentrate' in _PROVIDER_MODELS, any('concentrate' in str(p) for p in CANONICAL_PROVIDERS))"` → True True

### Task 5: Add env vars to hermes_cli/config.py

**Files:**
- Modify: `hermes_cli/config.py`

**Step 1:** Find `OPTIONAL_ENV_VARS` dict. Add after the `XIAOMI_BASE_URL` entry:

```python
    "CONCENTRATE_API_KEY": {
        "description": "Concentrate AI API key (115+ models, auto-routing)",
        "prompt": "Concentrate AI API key",
        "url": "https://app.concentrate.ai",
        "password": True,
        "category": "provider",
        "advanced": False,
    },
    "CONCENTRATE_BASE_URL": {
        "description": "Concentrate AI base URL override (default: https://api.concentrate.ai/v1)",
        "prompt": "Concentrate base URL (leave empty for default)",
        "url": None,
        "password": False,
        "category": "provider",
        "advanced": True,
    },
```

**Verify:** `source venv/bin/activate && python -c "from hermes_cli.config import OPTIONAL_ENV_VARS; print('CONCENTRATE_API_KEY' in OPTIONAL_ENV_VARS, 'CONCENTRATE_BASE_URL' in OPTIONAL_ENV_VARS)"` → True True

### Task 6: Add provider to hermes_cli/main.py

**Files:**
- Modify: `hermes_cli/main.py`

**Step 1:** Find the `_model_flow_api_key_provider` dispatch tuple. Add `"concentrate"` to it.

**Step 2:** Find the `--provider` argument choices list. Add `"concentrate"` to it.

**Verify:** Search for `"concentrate"` in main.py — should appear in both locations.

### Task 7: Add provider to hermes_cli/runtime_provider.py

**Files:**
- Modify: `hermes_cli/runtime_provider.py`

**Step 1:** Find the provider dispatch logic. Add `elif provider == "concentrate":` with `api_mode = "chat_completions"`.

**Verify:** `source venv/bin/activate && python -c "from hermes_cli.runtime_provider import resolve_runtime_provider; print('ok')"`

### Task 8: Add auxiliary model mapping to agent/auxiliary_client.py

**Files:**
- Modify: `agent/auxiliary_client.py`

**Step 1:** Find `_API_KEY_PROVIDER_AUX_MODELS` dict. Add:

```python
    "concentrate": "gemini-3-flash-preview",
```

**Verify:** `source venv/bin/activate && python -c "from agent.auxiliary_client import _API_KEY_PROVIDER_AUX_MODELS; print('concentrate' in _API_KEY_PROVIDER_AUX_MODELS)"` → True

### Task 9: Add context lengths to agent/model_metadata.py

**Files:**
- Modify: `agent/model_metadata.py`

**Step 1:** Find `_PROVIDER_PREFIXES` frozenset. Add `"concentrate"`.

**Step 2:** Find the provider alias section near `_PROVIDER_PREFIXES`. Add `"concentrate-ai"`.

**Step 3:** Find `_URL_TO_PROVIDER` dict. Add:

```python
    "api.concentrate.ai": "concentrate",
```

**Step 4:** Find `DEFAULT_CONTEXT_LENGTHS` dict. Add context lengths for concentrate-specific model slugs that aren't already covered by prefix matching. Key models:

```python
    "gpt-5.4": 1050000,
    "gpt-5.4-pro": 1050000,
    "gpt-5.4-mini": 128000,
    "gpt-5.4-nano": 128000,
```

Note: Many models like `gpt-5.1`, `gemini-2.5-flash`, `claude-opus-4-6` are already covered by existing prefix entries. Only add entries for models that would NOT be matched.

**Verify:** `source venv/bin/activate && python -c "from agent.model_metadata import _PROVIDER_PREFIXES, _URL_TO_PROVIDER; print('concentrate' in _PROVIDER_PREFIXES, 'api.concentrate.ai' in _URL_TO_PROVIDER)"` → True True

---

## Phase 3: Supporting Files (6 files)

### Task 10: Add .env.example entry

**Files:**
- Modify: `.env.example`

**Step 1:** Find the Arcee AI section. Add after it:

```
# =============================================================================
# LLM PROVIDER (Concentrate AI)
# =============================================================================
# Concentrate AI provides access to 115+ models with auto-routing
# Get a Concentrate key at: https://app.concentrate.ai
# CONCENTRATE_API_KEY=***
# CONCENTRATE_BASE_URL=                                 # Override default base URL
```

### Task 11: Add cli-config.yaml.example entry

**Files:**
- Modify: `cli-config.yaml.example`

**Step 1:** Find the provider comment section. Add after the Arcee line:

```yaml
  #   "concentrate"  - Concentrate AI 115+ models, auto-routing (requires: CONCENTRATE_API_KEY)
```

### Task 12: Add doctor.py health check

**Files:**
- Modify: `hermes_cli/doctor.py`

**Step 1:** Find the `_apikey_providers` list. Add after the Arcee entry:

```python
        ("Concentrate AI",   ("CONCENTRATE_API_KEY",),                       "https://api.concentrate.ai/v1/models", "CONCENTRATE_BASE_URL", True),
```

**Verify:** `source venv/bin/activate && python -c "from hermes_cli.doctor import _apikey_providers; print(any('CONCENTRATE_API_KEY' in p for p in _apikey_providers))"` → True

### Task 13: Add model_normalize.py entries

**Files:**
- Modify: `hermes_cli/model_normalize.py`

**Step 1:** Find `_MATCHING_PREFIX_STRIP_PROVIDERS`. Add `"concentrate"`.

**Step 2:** Check if there's a `_VENDOR_MAP`. If so, add appropriate entries for Concentrate model vendors.

**Step 3:** Check for `_AGGREGATOR_PROVIDERS`. Since Concentrate is an aggregator (like OpenRouter), add `"concentrate"` if this set exists.

**Verify:** `source venv/bin/activate && python -c "from hermes_cli.model_normalize import _MATCHING_PREFIX_STRIP_PROVIDERS; print('concentrate' in _MATCHING_PREFIX_STRIP_PROVIDERS)"` → True

### Task 14: Add setup.py entry

**Files:**
- Modify: `hermes_cli/setup.py`

**Step 1:** Find `_supports_same_provider_pool_setup` dict. Add:

```python
    "concentrate": ["gpt-5.4", "gemini-2.5-flash", "claude-sonnet-4", "deepseek-v3-0324"],
```

Pick 3-4 representative models across different vendors to show diversity.

**Verify:** `source venv/bin/activate && python -c "from hermes_cli.setup import _supports_same_provider_pool_setup; print('concentrate' in _supports_same_provider_pool_setup)"` → True

### Task 15: Add trajectory_compressor.py entry

**Files:**
- Modify: `trajectory_compressor.py`

**Step 1:** Find the `_detect_provider()` function. Add after the Arcee check:

```python
        if "concentrate.ai" in url:
            return "concentrate"
```

**Verify:** `source venv/bin/activate && python -c "from trajectory_compressor import _detect_provider; print(_detect_provider('https://api.concentrate.ai/v1/chat/completions'))"` → "concentrate"

---

## Phase 4: Tests

### Task 16: Create test file tests/hermes_cli/test_concentrate_provider.py

**Files:**
- Create: `tests/hermes_cli/test_concentrate_provider.py`

Follow the Arcee test pattern (tests/hermes_cli/test_arcee_provider.py). Key test classes:

```python
"""Tests for the Concentrate AI provider integration."""

import os
import pytest
from unittest.mock import patch


class TestConcentrateProviderRegistry:
    """Verify ProviderConfig registration."""

    def test_in_registry(self):
        from hermes_cli.auth import PROVIDER_REGISTRY
        assert "concentrate" in PROVIDER_REGISTRY

    def test_config_fields(self):
        from hermes_cli.auth import PROVIDER_REGISTRY
        cfg = PROVIDER_REGISTRY["concentrate"]
        assert cfg.id == "concentrate"
        assert cfg.name == "Concentrate AI"
        assert cfg.auth_type == "api_key"
        assert cfg.inference_base_url == "https://api.concentrate.ai/v1"
        assert "CONCENTRATE_API_KEY" in cfg.api_key_env_vars
        assert cfg.base_url_env_var == "CONCENTRATE_BASE_URL"


class TestConcentrateAliases:
    """Verify alias resolution."""

    def test_resolve_concentrate(self):
        from hermes_cli.auth import resolve_provider
        assert resolve_provider("concentrate") == "concentrate"

    def test_resolve_concentrate_ai(self):
        from hermes_cli.auth import resolve_provider
        assert resolve_provider("concentrate-ai") == "concentrate"

    def test_providers_alias(self):
        from hermes_cli.providers import ALIASES
        assert ALIASES.get("concentrate-ai") == "concentrate"

    def test_models_alias(self):
        from hermes_cli.models import _PROVIDER_ALIASES
        assert _PROVIDER_ALIASES.get("concentrate-ai") == "concentrate"


class TestConcentrateCredentials:
    """Verify credential resolution."""

    def test_configured_when_key_set(self):
        from hermes_cli.auth import get_api_key_provider_status
        with patch.dict(os.environ, {"CONCENTRATE_API_KEY": "test-key"}):
            status = get_api_key_provider_status("concentrate")
            assert status == "configured"

    def test_not_configured_without_key(self):
        from hermes_cli.auth import get_api_key_provider_status
        env = os.environ.copy()
        env.pop("CONCENTRATE_API_KEY", None)
        with patch.dict(os.environ, env, clear=True):
            status = get_api_key_provider_status("concentrate")
            assert status != "configured"

    def test_credentials_with_key(self):
        from hermes_cli.auth import resolve_api_key_provider_credentials
        with patch.dict(os.environ, {"CONCENTRATE_API_KEY": "sk-test-123"}):
            creds = resolve_api_key_provider_credentials("concentrate")
            assert creds["api_key"] == "sk-test-123"
            assert "concentrate.ai" in creds.get("base_url", "")

    def test_custom_base_url(self):
        from hermes_cli.auth import resolve_api_key_provider_credentials
        with patch.dict(os.environ, {
            "CONCENTRATE_API_KEY": "sk-test",
            "CONCENTRATE_BASE_URL": "https://custom.example.com/v1",
        }):
            creds = resolve_api_key_provider_credentials("concentrate")
            assert creds["base_url"] == "https://custom.example.com/v1"


class TestConcentrateModelCatalog:
    """Verify model catalog."""

    def test_in_provider_models(self):
        from hermes_cli.models import _PROVIDER_MODELS
        assert "concentrate" in _PROVIDER_MODELS

    def test_has_openai_models(self):
        from hermes_cli.models import _PROVIDER_MODELS
        models = _PROVIDER_MODELS["concentrate"]
        assert any("gpt-5" in m for m in models)

    def test_has_google_models(self):
        from hermes_cli.models import _PROVIDER_MODELS
        models = _PROVIDER_MODELS["concentrate"]
        assert any("gemini" in m for m in models)

    def test_in_canonical_providers(self):
        from hermes_cli.models import CANONICAL_PROVIDERS
        assert any(p.slug == "concentrate" for p in CANONICAL_PROVIDERS)


class TestConcentrateNormalization:
    """Verify model name normalization."""

    def test_in_prefix_strip_providers(self):
        from hermes_cli.model_normalize import _MATCHING_PREFIX_STRIP_PROVIDERS
        assert "concentrate" in _MATCHING_PREFIX_STRIP_PROVIDERS


class TestConcentrateURLMapping:
    """Verify URL-to-provider detection."""

    def test_url_to_provider(self):
        from agent.model_metadata import _URL_TO_PROVIDER
        assert _URL_TO_PROVIDER.get("api.concentrate.ai") == "concentrate"

    def test_in_provider_prefixes(self):
        from agent.model_metadata import _PROVIDER_PREFIXES
        assert "concentrate" in _PROVIDER_PREFIXES

    def test_trajectory_detection(self):
        from trajectory_compressor import _detect_provider
        assert _detect_provider("https://api.concentrate.ai/v1/chat/completions") == "concentrate"


class TestConcentrateProvidersModule:
    """Verify providers.py registration."""

    def test_in_overlays(self):
        from hermes_cli.providers import HERMES_OVERLAYS
        assert "concentrate" in HERMES_OVERLAYS

    def test_overlay_is_aggregator(self):
        from hermes_cli.providers import HERMES_OVERLAYS
        overlay = HERMES_OVERLAYS["concentrate"]
        assert overlay.is_aggregator is True

    def test_overlay_transport(self):
        from hermes_cli.providers import HERMES_OVERLAYS
        overlay = HERMES_OVERLAYS["concentrate"]
        assert overlay.transport == "openai_chat"


class TestConcentrateAuxiliary:
    """Verify auxiliary client integration."""

    def test_in_aux_models(self):
        from agent.auxiliary_client import _API_KEY_PROVIDER_AUX_MODELS
        assert "concentrate" in _API_KEY_PROVIDER_AUX_MODELS


class TestConcentrateEnvVars:
    """Verify env var registration."""

    def test_api_key_in_optional_env_vars(self):
        from hermes_cli.config import OPTIONAL_ENV_VARS
        assert "CONCENTRATE_API_KEY" in OPTIONAL_ENV_VARS

    def test_base_url_in_optional_env_vars(self):
        from hermes_cli.config import OPTIONAL_ENV_VARS
        assert "CONCENTRATE_BASE_URL" in OPTIONAL_ENV_VARS


class TestConcentrateDoctor:
    """Verify doctor health check registration."""

    def test_in_apikey_providers(self):
        from hermes_cli.doctor import _apikey_providers
        keys = [p[1] for p in _apikey_providers]
        assert ("CONCENTRATE_API_KEY",) in keys
```

**Verify:** `cd ~/projects/oss_contributions/hermes-agent && source venv/bin/activate && python -m pytest tests/hermes_cli/test_concentrate_provider.py -v`

### Task 17: Run full test suite

```bash
cd ~/projects/oss_contributions/hermes-agent
source venv/bin/activate
pytest tests/ -v --tb=short 2>&1 | tail -30
```

Fix any failures. Expected: All concentrate tests pass, no regressions.

---

## Phase 5: Website Docs (5 files)

### Task 18: Add Concentrate to website docs

**Files:**
- Modify: `website/docs/getting-started/quickstart.md` — Add Concentrate AI row to provider table
- Modify: `website/docs/integrations/providers.md` — Add Concentrate AI row, example command, config, supported list
- Modify: `website/docs/reference/cli-commands.md` — Add `concentrate` to `--provider` choices
- Modify: `website/docs/reference/environment-variables.md` — Add `CONCENTRATE_API_KEY`, `CONCENTRATE_BASE_URL` entries, add `concentrate` to `HERMES_INFERENCE_PROVIDER` list
- Modify: `website/docs/user-guide/configuration.md` — Add `concentrate` to auxiliary providers list

Follow the Arcee AI pattern in each file. Search for `arcee` in each doc to find the exact location.

---

## Phase 6: Commit and PR

### Task 19: Commit all changes

```bash
cd ~/projects/oss_contributions/hermes-agent
git add -A
git commit -m "feat(providers): add Concentrate AI provider

Adds Concentrate AI as a first-class aggregator provider with 115+
models, auto-routing, and pay-per-use pricing.

Base URL: https://api.concentrate.ai/v1
Auth: CONCENTRATE_API_KEY env var
Protocol: Standard OpenAI Chat Completions

Provider registration: auth.py, providers.py, config.py
Model catalog: models.py with 30 curated models
Supporting: doctor.py, model_normalize.py, setup.py,
            trajectory_compressor.py, .env.example,
            cli-config.yaml.example
Tests: test_concentrate_provider.py (20+ tests)
Docs: 5 website doc pages updated"
```

### Task 20: Push to fork and create PR

```bash
cd ~/projects/oss_contributions/hermes-agent
git push -u origin feat/concentrate-ai-provider
gh pr create \
  --repo NousResearch/hermes-agent \
  --head gama-oni:feat/concentrate-ai-provider \
  --base main \
  --title "feat(providers): add Concentrate AI provider" \
  --body "## What does this PR do?

Adds Concentrate AI as a first-class aggregator provider (115+ models, auto-routing, pay-per-use).

Concentrate AI provides a unified OpenAI-compatible API that routes to multiple underlying providers (OpenAI, Google, Anthropic, Meta, DeepSeek, xAI, etc.) with automatic provider selection and failover.

## Type of Change

- [x] ✨ New feature (non-breaking change that adds functionality)

## Changes Made

**Core registration (8 files):**
- \`hermes_cli/auth.py\` — ProviderConfig + aliases
- \`hermes_cli/providers.py\` — HermesOverlay (aggregator) + aliases
- \`hermes_cli/models.py\` — Model catalog (30 models) + ProviderEntry + aliases
- \`hermes_cli/config.py\` — CONCENTRATE_API_KEY + CONCENTRATE_BASE_URL env vars
- \`hermes_cli/main.py\` — Model flow dispatch + --provider choices
- \`hermes_cli/runtime_provider.py\` — Provider resolution + api_mode
- \`agent/auxiliary_client.py\` — Default aux model mapping (gemini-3-flash-preview)
- \`agent/model_metadata.py\` — Provider prefixes + URL mapping + context lengths

**Supporting (6 files):**
- \`.env.example\` — API key + base URL entries
- \`cli-config.yaml.example\` — Provider comment
- \`hermes_cli/doctor.py\` — Health check entry
- \`hermes_cli/model_normalize.py\` — Prefix strip + aggregator flag
- \`hermes_cli/setup.py\` — Setup wizard model pool
- \`trajectory_compressor.py\` — URL-based provider detection

**Tests:**
- \`tests/hermes_cli/test_concentrate_provider.py\` — 20+ tests covering registry, aliases, credentials, model catalog, normalization, URL mapping, overlays, auxiliary, env vars, doctor

**Docs (5 files):**
- website/docs/getting-started/quickstart.md
- website/docs/integrations/providers.md
- website/docs/reference/cli-commands.md
- website/docs/reference/environment-variables.md
- website/docs/user-guide/configuration.md

## How to Test

1. Set \`CONCENTRATE_API_KEY\` env var
2. Run \`hermes doctor\` — should show Concentrate AI as configured
3. Run \`hermes --provider concentrate -q \"Hello\"\` — should route through Concentrate
4. Run \`/model\` in interactive mode — Concentrate AI should appear in provider list
5. Run \`pytest tests/hermes_cli/test_concentrate_provider.py -v\` — all tests pass

## Checklist

### Code
- [x] I've read the Contributing Guide
- [x] My commit messages follow Conventional Commits
- [x] I searched for existing PRs — no duplicate
- [x] My PR contains only changes related to this feature
- [x] I've run \`pytest tests/ -q\` and all tests pass
- [x] I've added tests for my changes (20+ tests)
- [x] I've tested on my platform: macOS 15

### Documentation & Housekeeping
- [x] I've updated relevant documentation (5 website pages)
- [x] I've updated \`cli-config.yaml.example\` for new config keys
- [x] N/A: No architecture/workflow changes to CONTRIBUTING.md or AGENTS.md
- [x] N/A: No cross-platform concerns (pure provider registration)
- [x] N/A: No tool behavior changes"
```

### Task 21: Monitor CI and address feedback

```bash
gh pr checks --repo NousResearch/hermes-agent
```

If CI fails, diagnose and push fixes. Engage with reviewer feedback.

---

## Summary of All Files (20 total)

| # | File | Phase | Action |
|---|------|-------|--------|
| 1 | hermes_cli/auth.py | 2 | Modify |
| 2 | hermes_cli/providers.py | 2 | Modify |
| 3 | hermes_cli/models.py | 2 | Modify |
| 4 | hermes_cli/config.py | 2 | Modify |
| 5 | hermes_cli/main.py | 2 | Modify |
| 6 | hermes_cli/runtime_provider.py | 2 | Modify |
| 7 | agent/auxiliary_client.py | 2 | Modify |
| 8 | agent/model_metadata.py | 2 | Modify |
| 9 | .env.example | 3 | Modify |
| 10 | cli-config.yaml.example | 3 | Modify |
| 11 | hermes_cli/doctor.py | 3 | Modify |
| 12 | hermes_cli/model_normalize.py | 3 | Modify |
| 13 | hermes_cli/setup.py | 3 | Modify |
| 14 | trajectory_compressor.py | 3 | Modify |
| 15 | tests/hermes_cli/test_concentrate_provider.py | 4 | Create |
| 16-20 | website/docs/* (5 files) | 5 | Modify |
