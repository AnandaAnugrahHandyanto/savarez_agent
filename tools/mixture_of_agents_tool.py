#!/usr/bin/env python3
"""
Mixture-of-Agents Tool Module

Config-driven MoA runner for Hermes.  Unlike the old OpenRouter-only version,
this implementation routes through Hermes' auxiliary provider layer so it can
use Joe's subscription/OAuth providers (Codex, Claude Code OAuth, Nous, etc.)
without requiring direct API keys.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
from typing import Any, Dict, Iterable, List, Optional

from agent.auxiliary_client import async_call_llm, resolve_provider_client
from agent.auxiliary_client import extract_content_or_reasoning
from tools.debug_helpers import DebugSession

try:  # Imported lazily in tests / stripped-down environments.
    from hermes_cli.config import load_config
except Exception:  # pragma: no cover - defensive fallback for standalone import
    load_config = lambda: {}  # type: ignore

logger = logging.getLogger(__name__)

# Config defaults match Joe/Migi's subscription-first route.  Direct API-key
# providers (OpenRouter / direct Anthropic) are intentionally not required.
DEFAULT_REFERENCE_MODELS = [
    {
        "provider": "openai-codex",
        "model": "gpt-5.5",
        "label": "codex-subscription:gpt-5.5",
    },
]
DEFAULT_AGGREGATOR_MODEL = {
    "provider": "openai-codex",
    "model": "gpt-5.5",
    "label": "codex-subscription:gpt-5.5",
}
DEFAULT_REFERENCE_TEMPERATURE = 0.6
DEFAULT_AGGREGATOR_TEMPERATURE = 0.4
DEFAULT_MIN_SUCCESSFUL_REFERENCES = 1
DEFAULT_MAX_RETRIES = 2
DEFAULT_REFERENCE_MAX_TOKENS = 8192
DEFAULT_AGGREGATOR_MAX_TOKENS = 8192
DEFAULT_TIMEOUT_SECONDS = 600
DEFAULT_REASONING_EFFORT = "xhigh"

# System prompt for the aggregator model (adapted from the MoA paper).
AGGREGATOR_SYSTEM_PROMPT = """You have been provided with a set of responses from various models to the latest user query. Your task is to synthesize these responses into a single, high-quality response. It is crucial to critically evaluate the information provided in these responses, recognizing that some of it may be biased or incorrect. Your response should not simply replicate the given answers but should offer a refined, accurate, and comprehensive reply to the instruction. Ensure your response is well-structured, coherent, and adheres to the highest standards of accuracy and reliability.

Responses from models:"""

_debug = DebugSession("moa_tools", env_var="MOA_TOOLS_DEBUG")


def _main_provider_from_config(config: Dict[str, Any]) -> str:
    model_cfg = config.get("model") if isinstance(config, dict) else None
    if isinstance(model_cfg, dict):
        provider = str(model_cfg.get("provider") or "").strip()
        if provider:
            return provider
    return "auto"


def _label_for(provider: str, model: str, label: str = "") -> str:
    return label or f"{provider}:{model}"


def _looks_like_provider_model(value: str) -> bool:
    """Return True for legacy OpenRouter-style slugs like provider/model."""
    return "/" in value and not value.startswith("/")


def _normalize_model_spec(entry: Any, *, config: Dict[str, Any]) -> Dict[str, str]:
    """Normalize config entries into {provider, model, label} specs.

    Supported shapes:
      - {provider: openai-codex, model: gpt-5.5, label: ...}
      - "anthropic/claude-opus-4.6" (legacy OpenRouter slug)
      - "gpt-5.5" (bare model routed through the configured main provider)
    """
    main_provider = _main_provider_from_config(config)

    if isinstance(entry, dict):
        model = str(entry.get("model") or entry.get("name") or "").strip()
        provider = str(entry.get("provider") or "").strip()
        label = str(entry.get("label") or "").strip()
        if not provider:
            provider = "openrouter" if _looks_like_provider_model(model) else main_provider
        if not model:
            raise ValueError(f"MoA model entry is missing model/name: {entry!r}")
        return {"provider": provider, "model": model, "label": _label_for(provider, model, label)}

    model = str(entry or "").strip()
    if not model:
        raise ValueError("MoA model entry is empty")
    provider = "openrouter" if _looks_like_provider_model(model) else main_provider
    return {"provider": provider, "model": model, "label": _label_for(provider, model)}


def _as_model_specs(entries: Iterable[Any], *, config: Dict[str, Any]) -> List[Dict[str, str]]:
    specs = [_normalize_model_spec(entry, config=config) for entry in entries]
    if not specs:
        raise ValueError("MoA reference_models cannot be empty")
    return specs


def _load_moa_runtime_config(
    reference_models: Optional[List[Any]] = None,
    aggregator_model: Optional[Any] = None,
) -> Dict[str, Any]:
    config = load_config() or {}
    moa = config.get("moa") if isinstance(config, dict) else None
    moa = moa if isinstance(moa, dict) else {}

    raw_refs = reference_models if reference_models is not None else moa.get("reference_models", DEFAULT_REFERENCE_MODELS)
    raw_agg = aggregator_model if aggregator_model is not None else moa.get("aggregator_model", DEFAULT_AGGREGATOR_MODEL)

    # Legacy configs sometimes store a single string by mistake; accept it.
    if isinstance(raw_refs, (str, dict)):
        raw_refs = [raw_refs]

    refs = _as_model_specs(raw_refs, config=config)
    agg = _normalize_model_spec(raw_agg, config=config)

    min_success = int(moa.get("min_successful_references", DEFAULT_MIN_SUCCESSFUL_REFERENCES))
    min_success = max(1, min(min_success, len(refs)))

    return {
        "reference_models": refs,
        "aggregator_model": agg,
        "reference_temperature": float(moa.get("reference_temperature", DEFAULT_REFERENCE_TEMPERATURE)),
        "aggregator_temperature": float(moa.get("aggregator_temperature", DEFAULT_AGGREGATOR_TEMPERATURE)),
        "min_successful_references": min_success,
        "max_retries": max(1, int(moa.get("max_retries", DEFAULT_MAX_RETRIES))),
        "reference_max_tokens": int(moa.get("reference_max_tokens", DEFAULT_REFERENCE_MAX_TOKENS)),
        "aggregator_max_tokens": int(moa.get("aggregator_max_tokens", DEFAULT_AGGREGATOR_MAX_TOKENS)),
        "timeout": float(moa.get("timeout", DEFAULT_TIMEOUT_SECONDS)),
        "reasoning_effort": str(moa.get("reasoning_effort", DEFAULT_REASONING_EFFORT) or "").strip(),
    }


def _construct_aggregator_prompt(system_prompt: str, responses: List[str]) -> str:
    response_text = "\n".join([f"{i + 1}. {response}" for i, response in enumerate(responses)])
    return f"{system_prompt}\n\n{response_text}"


def _reasoning_extra_body(reasoning_effort: str) -> Dict[str, Any]:
    if not reasoning_effort:
        return {}
    return {"reasoning": {"enabled": True, "effort": reasoning_effort}}


async def _run_model_safe(
    spec: Dict[str, str],
    messages: List[Dict[str, str]],
    *,
    temperature: float,
    max_tokens: int,
    timeout: float,
    max_retries: int,
    reasoning_effort: str,
) -> tuple[str, str, bool]:
    """Run one MoA leg with retry and provider-agnostic Hermes routing."""
    label = spec["label"]
    for attempt in range(max_retries):
        try:
            logger.info("MoA querying %s (attempt %s/%s)", label, attempt + 1, max_retries)
            response = await async_call_llm(
                task="moa",
                provider=spec["provider"],
                model=spec["model"],
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                extra_body=_reasoning_extra_body(reasoning_effort),
            )
            content = extract_content_or_reasoning(response)
            if not content:
                raise RuntimeError("model returned empty content")
            logger.info("MoA %s responded (%s chars)", label, len(content))
            return label, content, True
        except Exception as exc:
            logger.warning("MoA %s failed attempt %s/%s: %s", label, attempt + 1, max_retries, exc)
            if attempt < max_retries - 1:
                await asyncio.sleep(min(2 ** (attempt + 1), 30))
            else:
                return label, f"{label} failed after {max_retries} attempts: {exc}", False


async def mixture_of_agents_tool(
    user_prompt: str,
    reference_models: Optional[List[Any]] = None,
    aggregator_model: Optional[Any] = None,
) -> str:
    """Process a complex query with a config-driven Mixture-of-Agents pass."""
    start_time = datetime.datetime.now()
    runtime = _load_moa_runtime_config(reference_models, aggregator_model)

    debug_call_data = {
        "parameters": {
            "user_prompt": user_prompt[:200] + "..." if len(user_prompt) > 200 else user_prompt,
            "reference_models": runtime["reference_models"],
            "aggregator_model": runtime["aggregator_model"],
            "reference_temperature": runtime["reference_temperature"],
            "aggregator_temperature": runtime["aggregator_temperature"],
            "min_successful_references": runtime["min_successful_references"],
        },
        "error": None,
        "success": False,
        "reference_responses_count": 0,
        "failed_models_count": 0,
        "failed_models": [],
        "final_response_length": 0,
        "processing_time_seconds": 0,
        "models_used": {},
    }

    try:
        logger.info("Starting Mixture-of-Agents processing with %s reference model(s)", len(runtime["reference_models"]))

        reference_messages = [{"role": "user", "content": user_prompt}]
        model_results = await asyncio.gather(*[
            _run_model_safe(
                spec,
                reference_messages,
                temperature=runtime["reference_temperature"],
                max_tokens=runtime["reference_max_tokens"],
                timeout=runtime["timeout"],
                max_retries=runtime["max_retries"],
                reasoning_effort=runtime["reasoning_effort"],
            )
            for spec in runtime["reference_models"]
        ])

        successful_responses: List[str] = []
        failed_models: List[str] = []
        for model_name, content, success in model_results:
            if success:
                successful_responses.append(content)
            else:
                failed_models.append(model_name)

        if len(successful_responses) < runtime["min_successful_references"]:
            raise ValueError(
                f"Insufficient successful reference models ({len(successful_responses)}/{len(runtime['reference_models'])}). "
                f"Need at least {runtime['min_successful_references']} successful response(s)."
            )

        aggregator_system_prompt = _construct_aggregator_prompt(
            AGGREGATOR_SYSTEM_PROMPT,
            successful_responses,
        )
        agg_label, final_response, agg_success = await _run_model_safe(
            runtime["aggregator_model"],
            [
                {"role": "system", "content": aggregator_system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=runtime["aggregator_temperature"],
            max_tokens=runtime["aggregator_max_tokens"],
            timeout=runtime["timeout"],
            max_retries=runtime["max_retries"],
            reasoning_effort=runtime["reasoning_effort"],
        )
        if not agg_success:
            raise RuntimeError(final_response or f"Aggregator {agg_label} failed")

        processing_time = (datetime.datetime.now() - start_time).total_seconds()
        result = {
            "success": True,
            "response": final_response,
            "models_used": {
                "reference_models": [spec["label"] for spec in runtime["reference_models"]],
                "aggregator_model": runtime["aggregator_model"]["label"],
            },
        }

        debug_call_data.update({
            "success": True,
            "reference_responses_count": len(successful_responses),
            "failed_models_count": len(failed_models),
            "failed_models": failed_models,
            "final_response_length": len(final_response),
            "processing_time_seconds": processing_time,
            "models_used": result["models_used"],
        })
        _debug.log_call("mixture_of_agents_tool", debug_call_data)
        _debug.save()
        return json.dumps(result, indent=2, ensure_ascii=False)

    except Exception as exc:
        error_msg = f"Error in MoA processing: {exc}"
        logger.error("%s", error_msg, exc_info=True)
        processing_time = (datetime.datetime.now() - start_time).total_seconds()
        result = {
            "success": False,
            "response": "MoA processing failed. Please try again or use a single model for this query.",
            "models_used": {
                "reference_models": [spec["label"] for spec in runtime["reference_models"]],
                "aggregator_model": runtime["aggregator_model"]["label"],
            },
            "error": error_msg,
        }
        debug_call_data["error"] = error_msg
        debug_call_data["processing_time_seconds"] = processing_time
        _debug.log_call("mixture_of_agents_tool", debug_call_data)
        _debug.save()
        return json.dumps(result, indent=2, ensure_ascii=False)


def _provider_available(spec: Dict[str, str]) -> bool:
    try:
        client, resolved_model = resolve_provider_client(spec["provider"], model=spec["model"])
        return client is not None and bool(resolved_model or spec["model"])
    except Exception as exc:
        logger.debug("MoA provider availability check failed for %s: %s", spec.get("label"), exc)
        return False


def check_moa_requirements() -> bool:
    """Return True when the configured MoA providers can be resolved.

    This intentionally does not require OPENROUTER_API_KEY.  It asks Hermes'
    provider router whether the configured subscription/OAuth providers are
    available, which is the same path the actual MoA calls use.
    """
    try:
        runtime = _load_moa_runtime_config()
        available_refs = sum(1 for spec in runtime["reference_models"] if _provider_available(spec))
        aggregator_ok = _provider_available(runtime["aggregator_model"])
        return aggregator_ok and available_refs >= runtime["min_successful_references"]
    except Exception as exc:
        logger.debug("MoA requirement check failed: %s", exc)
        return False


def get_moa_configuration() -> Dict[str, Any]:
    runtime = _load_moa_runtime_config()
    refs = runtime["reference_models"]
    return {
        "reference_models": refs,
        "aggregator_model": runtime["aggregator_model"],
        "reference_temperature": runtime["reference_temperature"],
        "aggregator_temperature": runtime["aggregator_temperature"],
        "min_successful_references": runtime["min_successful_references"],
        "max_retries": runtime["max_retries"],
        "reference_max_tokens": runtime["reference_max_tokens"],
        "aggregator_max_tokens": runtime["aggregator_max_tokens"],
        "reasoning_effort": runtime["reasoning_effort"],
        "total_reference_models": len(refs),
        "failure_tolerance": f"{len(refs) - runtime['min_successful_references']}/{len(refs)} models can fail",
    }


if __name__ == "__main__":
    print("🤖 Mixture-of-Agents Tool Module")
    print("=" * 50)
    ready = check_moa_requirements()
    print("✅ MoA providers ready" if ready else "❌ MoA providers unavailable; run `hermes auth status` / `hermes model`")
    print("\n⚙️  Current Configuration:")
    print(json.dumps(get_moa_configuration(), indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
from tools.registry import registry

MOA_SCHEMA = {
    "name": "mixture_of_agents",
    "description": "Route a hard problem through multiple configured Hermes providers collaboratively. Uses subscription/OAuth providers from config.yaml (for example Codex and Claude Code OAuth) and does not require OpenRouter unless you configure OpenRouter models. Use sparingly for genuinely difficult analysis.",
    "parameters": {
        "type": "object",
        "properties": {
            "user_prompt": {
                "type": "string",
                "description": "The complex query or problem to solve using multiple configured AI models."
            }
        },
        "required": ["user_prompt"]
    }
}

registry.register(
    name="mixture_of_agents",
    toolset="moa",
    schema=MOA_SCHEMA,
    handler=lambda args, **kw: mixture_of_agents_tool(user_prompt=args.get("user_prompt", "")),
    check_fn=check_moa_requirements,
    requires_env=[],
    is_async=True,
    emoji="🧠",
)
