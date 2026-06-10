from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Callable

from .config import MonicaConfig


SYSTEM_PROMPT = """You are Monica, an agentic mobile frontend bug triage agent.
Classify only the tagged Slack request and its thread context.
Return strict JSON with keys: is_mobile_bug, wants_linear, wants_fix,
confidence, summary, observed_behavior, expected_behavior, reproduction_steps,
platforms, device_context, build_context, missing_questions, reason.
Do not require command syntax. Infer intent from natural language.
When uncertain, ask for clarification instead of taking action."""


@dataclass(frozen=True)
class IntentResult:
    is_mobile_bug: bool
    wants_linear: bool
    wants_fix: bool
    confidence: float
    summary: str
    observed_behavior: str = ""
    expected_behavior: str = ""
    reproduction_steps: tuple[str, ...] = ()
    platforms: tuple[str, ...] = ()
    device_context: str = ""
    build_context: str = ""
    missing_questions: tuple[str, ...] = ()
    reason: str = ""

    @property
    def needs_clarification(self) -> bool:
        return bool(self.missing_questions) or self.confidence < 0.5

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["missing_questions"] = list(self.missing_questions)
        data["reproduction_steps"] = list(self.reproduction_steps)
        data["platforms"] = list(self.platforms)
        data["needs_clarification"] = self.needs_clarification
        return data


AgentFactory = Callable[[], Any]


class IntentClassifier:
    def __init__(
        self,
        *,
        config: MonicaConfig | None = None,
        agent_factory: AgentFactory | None = None,
    ) -> None:
        self.config = config or MonicaConfig()
        self.agent_factory = agent_factory or self._default_agent

    def classify(self, *, request_text: str, thread_text: str) -> IntentResult:
        prompt = "\n".join(
            [
                "Tagged request:",
                request_text.strip() or "(empty)",
                "",
                "Slack thread:",
                thread_text.strip() or "(empty)",
            ]
        )
        try:
            agent = self.agent_factory()
            result = agent.run_conversation(user_message=prompt, system_message=SYSTEM_PROMPT)
            content = str((result or {}).get("final_response") or "")
            parsed = json.loads(_extract_json(content))
            return _result_from_mapping(parsed)
        except Exception:
            return _fallback_intent(request_text=request_text, thread_text=thread_text)

    def _default_agent(self) -> Any:
        from run_agent import AIAgent

        return AIAgent(
            max_iterations=max(1, min(self.config.loop.max_iterations, 4)),
            quiet_mode=True,
            platform="monica",
            skip_memory=True,
        )


def _extract_json(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        return stripped[start : end + 1]
    raise ValueError("no JSON object found in classifier response")


def _result_from_mapping(data: dict[str, Any]) -> IntentResult:
    return IntentResult(
        is_mobile_bug=_coerce_bool(data.get("is_mobile_bug")),
        wants_linear=_coerce_bool(data.get("wants_linear"), default=True),
        wants_fix=_coerce_bool(data.get("wants_fix")),
        confidence=_clamp_float(data.get("confidence"), 0.0, 1.0),
        summary=str(data.get("summary") or "").strip()[:180],
        observed_behavior=str(data.get("observed_behavior") or "").strip()[:1000],
        expected_behavior=str(data.get("expected_behavior") or "").strip()[:1000],
        reproduction_steps=_as_string_tuple(data.get("reproduction_steps"), limit=12),
        platforms=_as_string_tuple(data.get("platforms"), limit=8),
        device_context=str(data.get("device_context") or "").strip()[:500],
        build_context=str(data.get("build_context") or "").strip()[:500],
        missing_questions=_as_string_tuple(data.get("missing_questions"), limit=8),
        reason=str(data.get("reason") or "").strip()[:1000],
    )


def _fallback_intent(*, request_text: str, thread_text: str) -> IntentResult:
    text = "\n".join([request_text, thread_text]).lower()
    bug_words = ("bug", "crash", "broken", "issue", "error", "regression", "not working", "fails")
    fix_words = ("fix", "patch", "pr", "clean it up", "clean up", "ship", "resolve")
    ticket_words = ("linear", "ticket", "file", "triage")
    platforms = _fallback_platforms(text)
    is_bug = any(word in text for word in bug_words)
    is_mobile = _has_explicit_mobile_context(text)
    wants_fix = any(word in text for word in fix_words)
    asked_ticket = any(word in text for word in ticket_words)
    is_mobile_bug = is_bug and is_mobile
    question_only = _is_actionless_question(request_text.lower())
    wants_linear = asked_ticket or (is_mobile_bug and not question_only)
    summary = _first_line(request_text or thread_text)
    questions: tuple[str, ...] = ()
    confidence = 0.78 if is_mobile_bug else 0.25
    if not is_mobile_bug:
        questions = ("What mobile app bug or platform should I file or investigate?",)
    return IntentResult(
        is_mobile_bug=is_mobile_bug,
        wants_linear=wants_linear,
        wants_fix=wants_fix,
        confidence=confidence,
        summary=summary,
        observed_behavior=summary if is_mobile_bug else "",
        platforms=platforms,
        missing_questions=questions,
        reason="Fallback keyword triage used because model classification was unavailable.",
    )


def _has_explicit_mobile_context(text: str) -> bool:
    if _has_negated_mobile_context(text):
        return False
    if _fallback_platforms(text):
        return True
    return (
        "mobile app" in text
        or "native app" in text
        or "app store" in text
        or "play store" in text
    )


def _has_negated_mobile_context(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:not|isn'?t|is not|not the|not a)\s+(?:mobile|mobile app|native|native app)\b",
            text,
        )
    )


def _is_actionless_question(text: str) -> bool:
    return bool(
        re.search(
            r"\b("
            r"any thoughts"
            r"|what do you think"
            r"|wdyt"
            r"|thoughts\?"
            r"|is this"
            r"|could this be"
            r"|does this look like"
            r")\b",
            text,
        )
    )


def _as_string_tuple(value: Any, *, limit: int) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, (list, tuple, set)):
        values = list(value)
    else:
        return ()
    clean: list[str] = []
    for item in values:
        text = str(item).strip()
        if text:
            clean.append(text[:500])
        if len(clean) >= limit:
            break
    return tuple(clean)


def _fallback_platforms(text: str) -> tuple[str, ...]:
    platforms: list[str] = []
    if "android" in text:
        platforms.append("Android")
    if "ios" in text or "iphone" in text or "ipad" in text:
        platforms.append("iOS")
    if "react native" in text or "\nrn" in text or " rn " in text:
        platforms.append("React Native")
    return tuple(platforms)


def _contains_term(text: str, term: str) -> bool:
    return bool(re.search(rf"\b{re.escape(term)}\b", text))


def _clamp_float(value: Any, lower: float, upper: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = lower
    return max(lower, min(upper, parsed))


def _coerce_bool(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "y", "1", "on"}:
            return True
        if normalized in {"false", "no", "n", "0", "off", ""}:
            return False
    return default


def _first_line(text: str) -> str:
    for line in text.splitlines():
        clean = re.sub(r"\s+", " ", line).strip()
        if clean:
            return clean[:180]
    return "Tagged mobile bug report"
