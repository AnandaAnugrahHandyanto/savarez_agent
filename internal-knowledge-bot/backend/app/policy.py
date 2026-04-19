import re
from dataclasses import dataclass
from typing import Any, Iterable


EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d\s\-]{7,}\d)(?!\w)")


DEFAULT_POLICY_PACKS: dict[str, dict[str, Any]] = {
    "safe": {
        "min_confidence": 0.45,
        "max_citations": 6,
        "daily_query_budget": 300,
        "daily_run_budget": 300,
        "daily_cost_budget_usd": 10.0,
        "max_top_k": 6,
        "max_question_chars": 2000,
        "force_handoff_keywords": ["legal", "breach", "incident", "complaint", "gdpr"],
    },
    "balanced": {
        "min_confidence": 0.25,
        "max_citations": 5,
        "daily_query_budget": 1000,
        "daily_run_budget": 1000,
        "daily_cost_budget_usd": 25.0,
        "max_top_k": 8,
        "max_question_chars": 4000,
        "force_handoff_keywords": ["legal", "complaint", "incident", "breach"],
    },
    "aggressive": {
        "min_confidence": 0.12,
        "max_citations": 4,
        "daily_query_budget": 4000,
        "daily_run_budget": 4000,
        "daily_cost_budget_usd": 100.0,
        "max_top_k": 12,
        "max_question_chars": 8000,
        "force_handoff_keywords": ["legal", "breach"],
    },
}


@dataclass
class PolicyRuleMatch:
    name: str
    action: str
    reason: str


@dataclass
class PolicyDecision:
    handoff_recommended: bool
    matched_keywords: list[str]
    matched_rules: list[str]
    final_action: str


def normalize_keywords(keywords: Iterable[str]) -> list[str]:
    seen = set()
    out = []
    for k in keywords:
        v = (k or "").strip().lower()
        if not v or v in seen:
            continue
        seen.add(v)
        out.append(v)
    return out


def matched_keywords(question: str, keywords: Iterable[str]) -> list[str]:
    q = (question or "").lower()
    return [k for k in normalize_keywords(keywords) if k in q]


def _match_rule(field_value: Any, op: str, expected: Any) -> bool:
    if op == "contains":
        return str(expected).lower() in str(field_value).lower()
    if op == "equals":
        return str(field_value).lower() == str(expected).lower()
    if op == "lt":
        return float(field_value) < float(expected)
    if op == "lte":
        return float(field_value) <= float(expected)
    if op == "gt":
        return float(field_value) > float(expected)
    if op == "gte":
        return float(field_value) >= float(expected)
    if op == "in":
        if isinstance(expected, list):
            return str(field_value).lower() in {str(v).lower() for v in expected}
        return str(field_value).lower() in {v.strip().lower() for v in str(expected).split(",") if v.strip()}
    if op == "regex":
        try:
            return bool(re.search(str(expected), str(field_value), flags=re.IGNORECASE))
        except re.error:
            return False
    return False


def evaluate_policy_rules(
    *,
    rules: Iterable[dict],
    question: str,
    answer: str,
    confidence: float,
    classification: str,
    role: str,
) -> list[PolicyRuleMatch]:
    context = {
        "question": question,
        "answer": answer,
        "confidence": confidence,
        "classification": classification,
        "role": role,
    }

    matches: list[PolicyRuleMatch] = []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        if not bool(rule.get("enabled", True)):
            continue

        name = str(rule.get("name") or "unnamed_rule")
        field = str(rule.get("field") or "").strip().lower()
        op = str(rule.get("op") or "").strip().lower()
        action = str(rule.get("action") or "allow").strip().lower()
        expected = rule.get("value")
        reason = str(rule.get("reason") or "")

        if field not in context:
            continue

        try:
            if _match_rule(context[field], op, expected):
                matches.append(PolicyRuleMatch(name=name, action=action, reason=reason))
        except Exception:
            continue

    return matches


def evaluate_handoff_decision(
    *,
    question: str,
    confidence: float,
    min_confidence: float,
    force_keywords: Iterable[str],
    rules: Iterable[dict] | None = None,
    answer: str = "",
    classification: str = "internal",
    role: str = "employee",
) -> PolicyDecision:
    hits = matched_keywords(question, force_keywords)
    rule_matches = evaluate_policy_rules(
        rules=rules or [],
        question=question,
        answer=answer,
        confidence=confidence,
        classification=classification,
        role=role,
    )

    actions = [m.action for m in rule_matches]
    if "deny" in actions:
        return PolicyDecision(
            handoff_recommended=True,
            matched_keywords=hits,
            matched_rules=[m.name for m in rule_matches],
            final_action="deny",
        )
    if "handoff" in actions:
        return PolicyDecision(
            handoff_recommended=True,
            matched_keywords=hits,
            matched_rules=[m.name for m in rule_matches],
            final_action="handoff",
        )

    handoff = confidence < min_confidence or len(hits) > 0
    return PolicyDecision(
        handoff_recommended=handoff,
        matched_keywords=hits,
        matched_rules=[m.name for m in rule_matches],
        final_action="redact" if "redact" in actions else "allow",
    )


def redact_pii(text: str) -> str:
    txt = EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    txt = PHONE_RE.sub("[REDACTED_PHONE]", txt)
    return txt


def get_policy_pack(pack_name: str | None) -> dict[str, Any]:
    key = (pack_name or "balanced").strip().lower()
    return DEFAULT_POLICY_PACKS.get(key, DEFAULT_POLICY_PACKS["balanced"])
