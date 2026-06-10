"""Provider connectivity diagnostics for ``hermes provider diagnose <name>``.

Performs non-destructive read-only checks against a provider's configuration
and endpoint to surface common setup issues in one shot.
"""

from __future__ import annotations

import os
import sys
import time
from typing import Any, Dict, List, Optional


def _check_env_var(env_var: str) -> tuple[bool, str]:
    """Return (ok, description) for an env var check."""
    value = os.environ.get(env_var, "").strip()
    if value:
        masked = value[:4] + "..." + value[-4:] if len(value) > 12 else "..."
        return True, f"{env_var} is set (len: {len(value)} chars)"
    return False, f"{env_var} is not set"


def _check_url_reachable(url: str, timeout: float = 8.0) -> tuple[bool, str, float]:
    """Return (ok, description, latency_ms) for a HEAD request."""
    try:
        import urllib.request

        req = urllib.request.Request(url, method="HEAD")
        req.add_header("User-Agent", "hermes-cli/diagnose")
        start = time.time()
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            latency = (time.time() - start) * 1000
            return True, f"reachable ({resp.status})", latency
    except Exception as exc:
        return False, f"unreachable — {type(exc).__name__}: {exc}", 0.0


def _try_list_models_openai(base_url: str, api_key: str, timeout: float = 15.0) -> tuple[bool, str, int]:
    """Try OpenAI-compatible /v1/models. Return (ok, description, count)."""
    try:
        import urllib.request
        import json

        url = base_url.rstrip("/") + "/v1/models"
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {api_key}")
        req.add_header("User-Agent", "hermes-cli/diagnose")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = data.get("data", [])
            count = len(models)
            if count:
                return True, f"{count} models available", count
            return False, "empty model list", 0
    except Exception as exc:
        return False, f"API error — {type(exc).__name__}: {exc}", 0


def _try_anthropic_models(api_key: str, timeout: float = 15.0) -> tuple[bool, str, int]:
    """Try Anthropic /v1/models. Return (ok, description, count)."""
    try:
        import urllib.request
        import json

        req = urllib.request.Request("https://api.anthropic.com/v1/models")
        req.add_header("x-api-key", api_key)
        req.add_header("anthropic-version", "2023-06-01")
        req.add_header("User-Agent", "hermes-cli/diagnose")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = data.get("data", [])
            count = len(models)
            if count:
                return True, f"{count} models available", count
            return False, "empty model list", 0
    except Exception as exc:
        return False, f"API error — {type(exc).__name__}: {exc}", 0


def _try_bedrock_list_models(region: str, profile: str = "", timeout: float = 15.0) -> tuple[bool, str, int]:
    """Try Bedrock ListFoundationModels. Return (ok, description, count)."""
    try:
        import boto3

        session_kwargs: Dict[str, Any] = {"region_name": region}
        if profile:
            session_kwargs["profile_name"] = profile
        session = boto3.Session(**session_kwargs)
        client = session.client("bedrock")
        resp = client.list_foundation_models()
        count = len(resp.get("modelSummaries", []))
        return True, f"{count} models available", count
    except Exception as exc:
        return False, f"AWS error — {type(exc).__name__}: {exc}", 0


def _try_ollama_models(base_url: str, timeout: float = 8.0) -> tuple[bool, str, int]:
    """Try Ollama /api/tags. Return (ok, description, count)."""
    try:
        import urllib.request
        import json

        url = base_url.rstrip("/") + "/api/tags"
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "hermes-cli/diagnose")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = data.get("models", [])
            count = len(models)
            if count:
                return True, f"{count} models available", count
            return False, "no models loaded", 0
    except Exception as exc:
        return False, f"API error — {type(exc).__name__}: {exc}", 0


def _run_openai_test_completion(
    base_url: str, api_key: str, model: str, timeout: float = 15.0
) -> tuple[bool, str, float]:
    """Send a minimal chat completion. Return (ok, description, latency_ms)."""
    try:
        import urllib.request
        import json

        url = base_url.rstrip("/") + "/v1/chat/completions"
        body = json.dumps(
            {
                "model": model,
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 5,
            }
        ).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Authorization", f"Bearer {api_key}")
        req.add_header("Content-Type", "application/json")
        req.add_header("User-Agent", "hermes-cli/diagnose")
        start = time.time()
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            latency = (time.time() - start) * 1000
            data = json.loads(resp.read().decode("utf-8"))
            content = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
            return True, f'"{content[:20]}..." ({latency:.0f}ms)', latency
    except Exception as exc:
        return False, f"completion failed — {type(exc).__name__}: {exc}", 0.0


def _run_anthropic_test_completion(
    api_key: str, model: str, timeout: float = 15.0
) -> tuple[bool, str, float]:
    """Send a minimal Anthropic message. Return (ok, description, latency_ms)."""
    try:
        import urllib.request
        import json

        url = "https://api.anthropic.com/v1/messages"
        body = json.dumps(
            {
                "model": model,
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 5,
            }
        ).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("x-api-key", api_key)
        req.add_header("anthropic-version", "2023-06-01")
        req.add_header("Content-Type", "application/json")
        req.add_header("User-Agent", "hermes-cli/diagnose")
        start = time.time()
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            latency = (time.time() - start) * 1000
            data = json.loads(resp.read().decode("utf-8"))
            content = (
                data.get("content", [{}])[0]
                .get("text", "")
                .strip()
            )
            return True, f'"{content[:20]}..." ({latency:.0f}ms)', latency
    except Exception as exc:
        return False, f"completion failed — {type(exc).__name__}: {exc}", 0.0


def diagnose_provider(provider_id: str) -> int:
    """Run diagnostics for *provider_id* and print a structured report.

    Returns 0 when the provider looks healthy, 1 when a check failed.
    """
    from hermes_cli.auth import PROVIDER_REGISTRY
    from hermes_cli.config import load_config
    from hermes_cli.models import CANONICAL_PROVIDERS
    from hermes_cli.providers import normalize_provider

    normalized = normalize_provider(provider_id) or provider_id.lower()
    cfg = load_config()
    user_providers = cfg.get("providers") or {}
    custom_providers = cfg.get("custom_providers") or []

    # --- Resolve provider definition ---
    pconfig = PROVIDER_REGISTRY.get(normalized)
    user_cfg = user_providers.get(normalized) if isinstance(user_providers, dict) else {}
    if not isinstance(user_cfg, dict):
        user_cfg = {}

    # Find matching custom_providers entry (by model name or base_url)
    cp_entry = None
    for entry in custom_providers:
        if not isinstance(entry, dict):
            continue
        cp_name = (entry.get("name") or "").lower()
        cp_model = (entry.get("model") or "").lower()
        if normalized in cp_name or normalized in cp_model:
            cp_entry = entry
            break

    # Also check canonical providers list for built-in slugs
    from hermes_cli.models import CANONICAL_PROVIDERS

    canonical = next((c for c in CANONICAL_PROVIDERS if c.slug == normalized), None)

    # Determine effective base_url
    base_url = (
        user_cfg.get("base_url")
        or user_cfg.get("api")
        or user_cfg.get("url")
        or (cp_entry.get("base_url") if cp_entry else None)
        or (cp_entry.get("url") if cp_entry else None)
        or getattr(pconfig, "inference_base_url", "")
        or getattr(canonical, "inference_base_url", "")
        or ""
    )

    # Determine effective api_key / key_env
    key_env = getattr(pconfig, "api_key_env_var", "") if pconfig else ""
    if not key_env and canonical:
        key_env = getattr(canonical, "api_key_env_var", "")
    inline_key = (
        user_cfg.get("api_key")
        or (cp_entry.get("api_key") if cp_entry else None)
        or ""
    )
    api_key = inline_key or os.environ.get(key_env, "")

    # Determine model for test completion
    model = (
        user_cfg.get("model")
        or user_cfg.get("default_model")
        or (cp_entry.get("model") if cp_entry else None)
        or ""
    )

    print(f"═══ Provider: {provider_id} ═══")

    checks: List[tuple[str, bool, str]] = []
    any_failed = False

    # 1. Provider definition
    if pconfig or user_cfg or cp_entry:
        checks.append(("Provider definition", True, "found in config or registry"))
    else:
        checks.append(
            (
                "Provider definition",
                False,
                f"'{provider_id}' not found in built-in registry or config",
            )
        )
        any_failed = True

    # 2. API key / credential env var
    if key_env:
        ok, detail = _check_env_var(key_env)
        checks.append((f"API key env var ({key_env})", ok, detail))
        if not ok:
            any_failed = True
    elif normalized in {"ollama", "lmstudio"}:
        checks.append(("API key", True, "local provider — no key required"))
    elif normalized == "bedrock":
        bedrock_ok = bool(
            os.environ.get("AWS_BEARER_TOKEN_BEDROCK", "").strip()
            or (
                os.environ.get("AWS_ACCESS_KEY_ID", "").strip()
                and os.environ.get("AWS_SECRET_ACCESS_KEY", "").strip()
            )
            or os.environ.get("AWS_PROFILE", "").strip()
        )
        if bedrock_ok:
            checks.append(("AWS credentials", True, "detected"))
        else:
            checks.append(("AWS credentials", False, "no AWS credentials found"))
            any_failed = True
    else:
        checks.append(("API key", False, "no key env var known for this provider"))
        any_failed = True

    # 3. Base URL reachability
    if base_url:
        ok, detail, latency = _check_url_reachable(base_url)
        if ok:
            checks.append(("Base URL", True, f"{base_url} — {detail} ({latency:.0f}ms)"))
        else:
            checks.append(("Base URL", False, f"{base_url} — {detail}"))
            any_failed = True
    elif normalized == "bedrock":
        checks.append(("Base URL", True, "not applicable — uses AWS boto3"))
    else:
        checks.append(("Base URL", False, "no base_url configured"))
        any_failed = True

    # 4. API key validity (list models)
    model_count = 0
    if normalized == "bedrock":
        region = os.environ.get("AWS_REGION", "us-east-1")
        profile = cfg.get("bedrock", {}).get("profile", "") if isinstance(cfg.get("bedrock"), dict) else ""
        ok, detail, model_count = _try_bedrock_list_models(region, profile)
        checks.append(("Model list", ok, detail))
        if not ok:
            any_failed = True
    elif normalized == "ollama":
        ok, detail, model_count = _try_ollama_models(base_url or "http://localhost:11434")
        checks.append(("Model list", ok, detail))
        if not ok:
            any_failed = True
    elif normalized == "anthropic" and api_key:
        ok, detail, model_count = _try_anthropic_models(api_key)
        checks.append(("Model list", ok, detail))
        if not ok:
            any_failed = True
    elif api_key and base_url:
        ok, detail, model_count = _try_list_models_openai(base_url, api_key)
        checks.append(("Model list", ok, detail))
        if not ok:
            any_failed = True
    else:
        checks.append(("Model list", False, "skipped — missing api_key or base_url"))

    # 5. Test completion
    if model and api_key and base_url and normalized != "bedrock":
        if normalized == "anthropic":
            ok, detail, latency = _run_anthropic_test_completion(api_key, model)
        else:
            ok, detail, latency = _run_openai_test_completion(base_url, api_key, model)
        checks.append(("Test completion", ok, detail))
        if not ok:
            any_failed = True
    elif normalized == "bedrock":
        checks.append(("Test completion", True, "Bedrock diagnostic limited to model list"))
    else:
        checks.append(("Test completion", False, "skipped — missing model, api_key, or base_url"))

    # 6. Proxy
    proxy = os.environ.get("HTTP_PROXY", "") or os.environ.get("HTTPS_PROXY", "")
    if proxy:
        checks.append(("Proxy", True, f"{proxy}"))
    else:
        checks.append(("Proxy", True, "not configured (direct)"))

    # Print checks
    for label, ok, detail in checks:
        icon = "✓" if ok else "✗"
        print(f"{icon} {label}: {detail}")

    # Summary
    status = "READY" if not any_failed else "ISSUES FOUND"
    print(f"\n─── Summary ───")
    print(f"Status: {status}")
    if model_count:
        print(f"Models available: {model_count}")

    return 1 if any_failed else 0
