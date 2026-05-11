"""Layer 1: Heuristic fast classifier. <5ms, no API calls.

High-precision regex rules ordered by specificity.  Simple/coding responses
with confidence ≥ threshold skip Layer 2 entirely.  Complex routing always
escalates to Layer 2 — L1 cannot assess reasoning depth.
"""

import re
from typing import List, Dict, Any, Optional

from agent.brain.types import RouteDecision


# ═══════════════════════════════════════════════════════════════════════
# Detectors
# ═══════════════════════════════════════════════════════════════════════

_GREETING_RE = re.compile(
    r'^(你好|您好|hi|hey|hello|哈喽|嗨|good\s*(morning|afternoon|evening)|'
    r'早上好|晚上好|下午好)[\s!！。.]*$',
    re.IGNORECASE,
)

_CHITCHAT_RE = re.compile(
    r'^(好的|ok|知道了|thanks|谢谢|thank you|got it|明白了|收到|嗯嗯|哦哦|好嘞|'
    r'没问题|行|可以|好|okay|好吧|了解了)[\s!！。.]*$',
    re.IGNORECASE,
)

_TRANSLATION_RE = re.compile(
    r'(翻译|translate|翻成|译成|用.*说|转成.*文)',
    re.IGNORECASE,
)

# Strong code signals — each worth 2 points
_CODE_STRONG_RE = re.compile(
    r'(```|`[^`]+`|'
    r'\.(py|js|ts|rs|go|java|rb|sh|cpp|h)\b|'
    r'\bimport\s+\w+\b|'
    r'\bfrom\s+\w+\s+import\b|'
    r'\bdef\s+\w+\s*\(|'
    r'\bclass\s+\w+[:\(]|'
    r'\bfunc\s+\w+\s*\(|'
    r'\basync\s+def\b|'
    r'\bawait\s+\w+|'
    r'\bSELECT\s+.*\bFROM\b|'
    r'\bgit\s+(commit|push|pull|clone|rebase|branch|merge)\b|'
    r'\bdocker\s+(run|build|compose|ps|exec)\b|'
    r'\bpip\s+install\b|'
    r'\bnpm\s+(install|run)\b|'
    r'\bcargo\s+(build|run)\b)',
)

# Code signal keywords — worth 1 point each
_CODE_WEAK_KEYWORDS = [
    "debug", "报错", "bug", "实现", "写个脚本", "修复",
    "重构", "refactor",
]

# Code block/context keywords — worth 1 point each
_CODE_BLOCK_KEYWORDS = [
    "代码", "code", "函数", "function", "算法", "algorithm",
    "部署", "deploy", "发布", "release",
]

# Negative context: stop words that indicate code keywords
# appear in a non-coding context (e.g. "帮我查一下 import 怎么用")
_CODE_NEGATIVE_CONTEXT = [
    "帮我查", "怎么用", "是什么意思", "介绍一下", "解释一下",
    "是什么", "查一下",
]

# Persona trigger keywords — Tier 2 intimacy mode activation.
# ONLY "Audra" triggers Tier 2. "未央" is a nickname/address, not a trigger.
# Route to simple (fast, cheap) — conversational intimacy, not complex reasoning.
_PERSONA_TRIGGER_RE = re.compile(
    r'\bAudra\b',
    re.IGNORECASE,
)

# Simple-intent keywords — low-complexity, low-token tasks
_SIMPLE_INTENT_KEYWORDS = [
    "翻译", "总结一下", "是什么", "怎么读", "几个字", "帮我查",
    "解释", "定义", "意思", "含义", "有什么区别",
    "告诉我", "列举", "列出",
]


def is_greeting(text: str) -> bool:
    """Check if text is a pure greeting (short, no code/technical content)."""
    return bool(_GREETING_RE.match(text.strip()))


def is_chitchat(text: str) -> bool:
    """Check if text is pure chitchat/acknowledgment."""
    return bool(_CHITCHAT_RE.match(text.strip()))


def is_translation_request(text: str) -> bool:
    """Check if text is an explicit translation request."""
    return bool(_TRANSLATION_RE.search(text))


def compute_code_score(text: str) -> int:
    """Weighted code signal scoring.

    Strong signals (code blocks, extensions, language keywords): 2 points each.
    Weak signals (context keywords): 1 point each.
    """
    score = 0

    # Strong signals — check individually for more granularity
    if bool(re.search(r'```', text)):
        score += 2
    if bool(re.search(r'`[^`]+`', text)):
        score += 1
    if bool(re.search(r'\.(py|js|ts|rs|go|java|rb|sh|cpp|h)\b', text)):
        score += 2
    if bool(_CODE_STRONG_RE.search(text)):
        score += 2

    # Weak signals
    text_lower = text.lower()
    if any(kw in text_lower for kw in _CODE_WEAK_KEYWORDS):
        score += 1
    if any(kw in text_lower for kw in _CODE_BLOCK_KEYWORDS):
        score += 1

    return score


def _has_negative_context(text: str) -> bool:
    """Check if code keywords appear in a non-coding context."""
    return any(kw in text for kw in _CODE_NEGATIVE_CONTEXT)


def has_simple_intent(text: str) -> bool:
    """Check for simple-intent keywords."""
    return any(kw in text for kw in _SIMPLE_INTENT_KEYWORDS)


def is_persona_trigger(text: str) -> bool:
    """Check if text contains the Tier 2 trigger word (Audra only).

    "Audra" (case-insensitive) signals the user is entering Tier 2 intimacy
    mode — a conversational interaction that should route to simple (fast/cheap),
    never complex.
    """
    return bool(_PERSONA_TRIGGER_RE.search(text))


# ═══════════════════════════════════════════════════════════════════════
# Main classifier
# ═══════════════════════════════════════════════════════════════════════

def layer1_heuristic(
    user_input: str,
    history: List[Dict[str, Any]],
    turns: int = 0,
    est_tokens: int = 0,
) -> Optional[RouteDecision]:
    """
    Layer 1: Heuristic classifier. Ordered by precision (highest first).

    Args:
        user_input: The user's message.
        history: Conversation history (unused by rules, passed for future use).
        turns: Number of user turns in this session.
        est_tokens: Estimated token count from Layer 0.

    Returns:
        RouteDecision for high-confidence matches, or None to escalate to Layer 2.
    """

    # ── HIGH-PRECISION RULES (confidence ≥ 0.95) ──

    # Rule 1: Greeting — only on turn 0 or 1
    if is_greeting(user_input) and turns <= 1:
        return RouteDecision("simple", confidence=1.0, source="l1_greeting")

    # Rule 2: Chitchat / acknowledgment
    if is_chitchat(user_input):
        return RouteDecision("simple", confidence=0.98, source="l1_chitchat")

    # Rule 2b (REMOVED v4.1): Persona trigger "Audra" → simple.
    # ModeDetector (agent/mode_detection.py) now handles this pre-L1:
    #   "Audra" → LIFE mode switch → message content routed normally.
    #   Pure "Audra" (no task) → ModeDetector intercepts, L1 never reached.
    #   "Audra 帮我查..." → ModeDetector switches to LIFE, L1 routes task content.

    # Rule 3: Explicit translation request
    if is_translation_request(user_input):
        return RouteDecision("simple", confidence=0.95, source="l1_translation")

    # ── MEDIUM-PRECISION RULES (confidence 0.85–0.90) ──

    # Rule 4: Very short, early turn, non-technical
    if est_tokens < 60 and turns <= 2 and not compute_code_score(user_input):
        return RouteDecision("simple", confidence=0.95, source="l1_short")

    # Rule 5: Code detection (weighted scoring)
    # Only apply if no negative context — prevents "帮我查一下 import" from
    # being misrouted to coding.
    if not _has_negative_context(user_input):
        code_score = compute_code_score(user_input)
        if code_score >= 2:
            return RouteDecision("coding", confidence=0.90, source="l1_code")

    # Rule 6: Simple-intent keywords (after code exclusion)
    if has_simple_intent(user_input) and est_tokens < 100:
        return RouteDecision("simple", confidence=0.85, source="l1_simple_intent")

    # No match — escalate to Layer 2
    return None
