"""Layer 2: Lightweight Planner — cheap LLM classifier.

Uses a flash-level model (deepseek-v4-flash by default) to classify
messages when Layer 1 cannot determine the route with high confidence.
~500ms target, 5s timeout, 1 retry on parse failure.  Never raises.

Temperature 0.0 for deterministic classification.  Fails safe: any error
returns RouteDecision("complex", low_confidence, "l2_error").
"""

import json
import logging
import re
import time
from typing import List, Dict, Any, Optional

from agent.brain.types import RouteDecision
from agent.brain.config import BrainConfig

logger = logging.getLogger(__name__)

PLANNER_SYSTEM_PROMPT = """你是一个路由分析器。分析用户输入，输出合法 JSON。
只输出 JSON 对象，第一个字符必须是 {，最后一个字符必须是 }。

{
  "task_type": "simple|complex",
  "confidence": 0.0-1.0,
  "reason": "一句话理由"
}

分类标准：
- simple: 翻译、查资料、简单解释、闲聊、确认、打招呼、亲密互动（含"Audra"/"未央"等称呼触发）
- complex: 写代码、调试、技术实现、长上下文、多步推理、深度分析、多工具链
"""


def _extract_json(raw: str) -> Optional[dict]:
    """Robust JSON extraction from LLM output.

    Handles: markdown code fences, trailing commas, unquoted values,
    truncated output.  Returns None only if completely unparseable.
    """
    if not raw or not raw.strip():
        return None

    # Try direct parse first (best case)
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        pass

    # Strip markdown code fences
    cleaned = raw.strip()
    for prefix in ("```json", "```"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3].strip()

    # Try after fence stripping
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Extract first { ... } block from any position
    match = re.search(r'\{[^{}]*\}', cleaned)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Repair common issues
    repaired = re.sub(r',\s*}', '}', cleaned)   # trailing comma before }
    repaired = re.sub(r',\s*]', ']', repaired)  # trailing comma before ]
    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        pass

    return None


def _trim_history(
    history: List[Dict[str, Any]],
    max_tokens: int = 14000,
) -> List[Dict[str, Any]]:
    """Trim history to fit planner's context window. Keep most recent."""
    if not history:
        return []
    result = []
    total = 0
    for msg in reversed(history):
        content = msg.get("content", "")
        if isinstance(content, str):
            est = max(1, len(content) // 4)
        elif isinstance(content, list):
            # Multimodal content — rough estimate
            est = sum(
                len(block.get("text", "")) // 4
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            )
        else:
            est = 50  # rough fallback
        if total + est > max_tokens:
            break
        result.insert(0, msg)
        total += est
    return result


def _ensure_reasoning_content(
    messages: List[Dict[str, Any]],
    cfg,
) -> List[Dict[str, Any]]:
    """Inject ``reasoning_content=""`` on assistant messages with tool_calls.

    DeepSeek V4 models in thinking mode (enabled by default on api.deepseek.com)
    require ``reasoning_content`` on every assistant message that carries
    ``tool_calls``.  Replaying cross-provider history without this field
    triggers HTTP 400.  The main agent loop handles this via
    ``_copy_reasoning_content_for_api()``, but the Layer 2 planner bypasses
    that path — so we patch it here.
    """
    # Only DeepSeek direct API needs this (Kimi/MiniMax/etc. don't).
    provider = getattr(cfg, "provider", "")
    model = getattr(cfg, "model", "")
    if ("deepseek" not in (provider or "").lower()
            and "deepseek" not in (model or "").lower()):
        base_url = getattr(cfg, "base_url", "")
        if "deepseek" not in (base_url or "").lower():
            from utils import base_url_host_matches
            if not base_url_host_matches(base_url, "api.deepseek.com"):
                return messages
    for msg in messages:
        if msg.get("role") != "assistant":
            continue
        # DeepSeek V4 thinking mode requires reasoning_content on ALL assistant
        # messages in history, not just those with tool_calls.
        if msg.get("reasoning_content") is None:
            msg["reasoning_content"] = ""
    return messages


def layer2_planner(
    user_input: str,
    history: List[Dict[str, Any]],
    config: BrainConfig,
    l1_hint: Optional[RouteDecision] = None,
) -> RouteDecision:
    """
    Layer 2: Lightweight planner using a cheap LLM for classification.

    Args:
        user_input: The user's message.
        history: Conversation history.
        config: Brain configuration (layer2 section used).
        l1_hint: Optional hint from Layer 1 for context enrichment.

    Returns:
        RouteDecision.  Never raises — always returns a conservative
        fallback (coding, low confidence) on any failure.
    """
    cfg = config.layer2
    trimmed_history = _trim_history(history, cfg.max_context - 2000)

    # Build context enrichment from Layer 1 hint
    context_parts = []
    if l1_hint:
        context_parts.append(
            f"Layer 1 hint: route={l1_hint.route}, confidence={l1_hint.confidence:.2f}"
        )
    context_str = "\n".join(context_parts) if context_parts else ""

    user_message = user_input
    if context_str:
        user_message = f"[Context: {context_str}]\n\nUser: {user_input}"

    messages = [{"role": "system", "content": PLANNER_SYSTEM_PROMPT}]
    if trimmed_history:
        messages.extend(trimmed_history)
    messages.append({"role": "user", "content": user_message})

    # DeepSeek V4 thinking mode requires reasoning_content on every assistant
    # message that carries tool_calls.  Without it, replaying cross-provider
    # history (e.g. Kimi → DeepSeek) causes HTTP 400.  Inject "" as a
    # compatibility fallback for messages that are missing the field.
    messages = _ensure_reasoning_content(messages, cfg)

    # ── Provider fallback chain: primary → fallback ──
    # Try primary provider first; if client creation fails or API is unreachable,
    # fall back to secondary provider (e.g. dashscope/qwen3.6-flash) to avoid
    # forcing ALL unclassified messages to complex(Pro) at ~12x cost.
    _provider_chain = [
        (cfg.provider, cfg.model),
    ]
    if cfg.fallback_model and cfg.fallback_provider:
        _provider_chain.append((cfg.fallback_provider, cfg.fallback_model))

    for _provider, _model in _provider_chain:
        for attempt in range(cfg.max_retries + 1):
            try:
                from agent.auxiliary_client import resolve_provider_client as _resolve

                client, resolved_model = _resolve(
                    provider=_provider,
                    model=_model,
                )

                if client is None:
                    logger.warning(
                        "L2 planner: no client for %s/%s, %s",
                        _provider, _model,
                        "trying fallback" if (_provider, _model) != _provider_chain[-1] else "giving up",
                    )
                    break  # break retry loop, try next provider in chain

                response = client.chat.completions.create(
                    model=resolved_model or _model,
                    messages=messages,
                    max_tokens=200,
                    temperature=cfg.temperature,
                    timeout=cfg.timeout,
                )

                raw = response.choices[0].message.content or ""
                scores = _extract_json(raw)

                if scores is None:
                    if attempt < cfg.max_retries:
                        messages.append({
                            "role": "user",
                            "content": "OUTPUT VALID JSON ONLY. No markdown, no prefix, just { ... }.",
                        })
                        continue
                    return RouteDecision(
                        "complex", 0.2, "l2_parse_failure",
                        metadata={"attempts": attempt + 1, "raw": raw[:200]},
                    )

                # Extract fields
                task_type = scores.get("task_type", "complex")
                if task_type not in ("simple", "complex"):
                    task_type = "complex"
                confidence = float(scores.get("confidence", 0.5))

                # Gate: low confidence → conservative
                if confidence < 0.60:
                    return RouteDecision(
                        "complex", confidence, "l2_low_confidence",
                        metadata={
                            "original_type": task_type,
                            "reason": scores.get("reason", ""),
                            "provider": _provider,
                        },
                    )

                return RouteDecision(
                    task_type, confidence, "l2_planner",
                    metadata={
                        "reason": scores.get("reason", ""),
                        "attempts": attempt + 1,
                        "provider": _provider,
                    },
                )

            except Exception as e:
                logger.warning(
                    "L2 planner %s/%s attempt %d failed: %s",
                    _provider, _model, attempt + 1, e,
                )
                if attempt < cfg.max_retries:
                    time.sleep(0.5)
                    continue
                break  # break retry loop, try next provider in chain

    # All providers exhausted — conservative fallback
    return RouteDecision("complex", 0.2, "l2_no_client",
        metadata={"reason": f"All providers exhausted: {_provider_chain}"})
