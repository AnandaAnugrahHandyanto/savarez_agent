"""Layer 0: Preprocessing — multimodal detection, token estimation. <2ms, no API."""

import re
from typing import List, Dict, Any, Optional

from agent.brain.types import RouteDecision
from agent.brain.config import BrainConfig

# Image indicator patterns
IMAGE_PATTERNS = [
    r'!\[.*?\]\(.*?\.(png|jpg|jpeg|gif|webp|bmp)(\?.*)?\)',
    r'https?://[^\s]+\.(png|jpg|jpeg|gif|webp)(\?[^\s]*)?',
    r'data:image/',
]

# Document indicator patterns
DOCUMENT_PATTERNS = [
    r'!\[.*?\]\(.*?\.(pdf|docx?|pptx?|xlsx?|txt|csv)(\?.*)?\)',
    r'\[.*?\]\(.*?\.(pdf|docx?|pptx?|xlsx?|txt|csv)(\?.*)?\)',
    r'https?://[^\s]+\.(pdf|docx?|pptx?)(\?[^\s]*)?',
]


def token_estimate(text: str) -> int:
    """Fast token estimation using character ratios. <0.1ms.

    English: ~4 chars/token, CJK: ~1.5 chars/token.
    """
    if not text:
        return 0
    cjk = sum(
        1 for c in text
        if '\u4e00' <= c <= '\u9fff' or '\u3040' <= c <= '\u30ff'
    )
    other = len(text) - cjk
    return max(1, int(cjk / 1.5 + other / 4))


def _has_image(text: str) -> bool:
    return any(re.search(p, text) for p in IMAGE_PATTERNS)


def _has_document(text: str) -> bool:
    return any(re.search(p, text) for p in DOCUMENT_PATTERNS)


def layer0_preprocess(
    user_input: str,
    history: List[Dict[str, Any]],
    config: BrainConfig,
) -> Optional[RouteDecision]:
    """
    Layer 0: Preprocessing. Must complete in <2ms. No API calls.

    Returns RouteDecision for early-exit signals (image, document, long-context),
    or None to pass through to Layer 0.5.

    Early-exit routes (vision, doc_extract) are terminal — no further
    classification needed.  Long-context gate returns a 'complex' decision
    that is NOT terminal (downstream layers may refine it).
    """

    # 1. Multimodal detection — strong signal, exit early
    if _has_image(user_input):
        return RouteDecision(
            route="vision",
            confidence=0.95,
            source="l0_image",
            metadata={
                "check_code_context": True,
                "reroute_after_extract": True,
            },
        )

    if _has_document(user_input):
        return RouteDecision(
            route="doc_extract",
            confidence=0.95,
            source="l0_document",
            metadata={"reroute_after_extract": True},
        )

    # 2. Lightweight token estimation
    #    Runs once here and re-used by downstream layers via metadata,
    #    avoiding redundant per-layer counting.
    input_tokens = token_estimate(user_input)
    history_text = " ".join(
        m.get("content", "")
        for m in history
        if isinstance(m.get("content"), str)
    )
    history_tokens = token_estimate(history_text)
    total_estimated = input_tokens + history_tokens

    # 3. Long-context gate
    #    Threshold is configurable — different models have different windows.
    if total_estimated > config.layer0.max_context_threshold:
        return RouteDecision(
            route="complex",
            confidence=0.85,
            source="l0_long_context",
            metadata={
                "estimated_tokens": total_estimated,
                "input_tokens": input_tokens,
                "history_tokens": history_tokens,
            },
        )

    # 4. Pass through with metadata for downstream layers
    return None
