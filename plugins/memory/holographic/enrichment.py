"""Lightweight enrichment helpers for the holographic memory provider.

The goal is not perfect NLP. We want deterministic, local, testable signal
extraction that improves retrieval quality without introducing hard runtime
dependencies or network calls.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Iterable


_RE_CAPITALIZED_MULTI = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b")
_RE_DOUBLE_QUOTE = re.compile(r'"([^"]+)"')
_RE_SINGLE_QUOTE = re.compile(r"'([^']+)'")
_RE_AKA = re.compile(
    r"(\w+(?:\s+\w+)*)\s+(?:aka|also known as)\s+(\w+(?:\s+\w+)*)",
    re.IGNORECASE,
)
_RE_MENTION = re.compile(r"@([A-Za-z0-9_][A-Za-z0-9_.-]{1,31})")
_RE_HASHTAG = re.compile(r"#([A-Za-z0-9_-]{2,32})")
_RE_ISO_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_RE_SLASH_DATE = re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b")
_RE_MONTH_DATE = re.compile(
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec|"
    r"January|February|March|April|June|July|August|September|October|November|December)"
    r"\s+\d{1,2}(?:,\s*\d{4})?\b",
    re.IGNORECASE,
)
_RE_TIME = re.compile(r"\b\d{1,2}(?::\d{2})?\s?(?:am|pm)\b", re.IGNORECASE)
_RE_24H_TIME = re.compile(r"\b(?:[01]?\d|2[0-3]):[0-5]\d\b")
_RE_LOCATION = re.compile(
    r"\b(?:in|at|from|near|around|to)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,2})\b"
)
_RE_PROJECT = re.compile(
    r"\b(?:project|repo|repository|service|app|application|workspace|module|plugin|pipeline|job|bot|agent)\s+"
    r"([A-Za-z0-9._/-]+(?:\s+[A-Za-z0-9._/-]+){0,2})",
    re.IGNORECASE,
)
_RE_PREFIX_PROJECT = re.compile(
    r"\b([A-Za-z0-9._/-]+(?:\s+[A-Za-z0-9._/-]+){0,2})\s+"
    r"(?:project|repo|repository|service|app|application|workspace|module|plugin|pipeline|job|bot|agent)\b",
    re.IGNORECASE,
)
_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{1,}")

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "being", "but", "by",
    "can", "could", "did", "do", "does", "for", "from", "had", "has", "have",
    "he", "her", "hers", "him", "his", "i", "if", "in", "into", "is", "it",
    "its", "me", "my", "of", "on", "or", "our", "ours", "she", "should", "so",
    "that", "the", "their", "them", "they", "this", "to", "up", "use", "using",
    "was", "we", "were", "what", "when", "where", "which", "who", "why", "with",
    "you", "your", "yours",
}

_PROJECT_HINTS = {
    "project", "repo", "repository", "service", "app", "application",
    "workspace", "module", "plugin", "pipeline", "job", "bot", "agent",
}
_PROJECT_LEADING_ARTICLES = {"a", "an", "the"}
_PROJECT_REJECT_HEADS = {"needs", "uses", "requires", "with", "for", "to"}
_CANONICAL_SEPARATORS = re.compile(r"[_./:-]+")
_CANONICAL_STRIP = re.compile(r"[^a-z0-9\s]")

_INTENT_PATTERNS = [
    ("preference", re.compile(r"\b(?:i prefer|i like|i love|my preferred|my favorite)\b", re.IGNORECASE)),
    ("decision", re.compile(r"\b(?:we decided|we chose|decision:|decided to|agreed to)\b", re.IGNORECASE)),
    ("goal", re.compile(r"\b(?:i want|i need|goal:|trying to|plan to)\b", re.IGNORECASE)),
    ("task", re.compile(r"\b(?:todo|task|follow up|next step|remember to)\b", re.IGNORECASE)),
    ("issue", re.compile(r"\b(?:bug|broken|error|incident|failure|regression)\b", re.IGNORECASE)),
    ("event", re.compile(r"\b(?:met|meeting|call with|appointment|trip|travel)\b", re.IGNORECASE)),
]

_HIGH_SALIENCE_TERMS = {
    "always", "never", "must", "important", "critical", "urgent", "blocker",
    "production", "incident", "regression", "decision",
}


def _ordered_unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        cleaned = value.strip()
        key = cleaned.lower()
        if cleaned and key not in seen:
            seen.add(key)
            output.append(cleaned)
    return output


def _normalize_topic_token(token: str) -> str:
    cleaned = token.strip(".,;:!?\"'()[]{}")
    cleaned = cleaned.lstrip("#@").lower()
    return cleaned


def canonicalize_key(value: str, *, drop_project_hints: bool = False) -> str:
    cleaned = (value or "").strip().lower()
    if not cleaned:
        return ""

    cleaned = cleaned.lstrip("#@")
    cleaned = _CANONICAL_SEPARATORS.sub(" ", cleaned)
    cleaned = _CANONICAL_STRIP.sub(" ", cleaned)
    tokens = [token for token in cleaned.split() if token]
    if drop_project_hints:
        tokens = [token for token in tokens if token not in _PROJECT_HINTS]
    if not tokens:
        return ""
    return " ".join(tokens)


def _clean_project_candidate(value: str) -> str:
    cleaned = (value or "").strip(" \t\r\n,.;:!?\"'()[]{}")
    if not cleaned:
        return ""

    tokens = cleaned.split()
    while tokens and tokens[0].lower() in _PROJECT_LEADING_ARTICLES:
        tokens.pop(0)
    if not tokens or tokens[0].lower() in _PROJECT_REJECT_HEADS:
        return ""
    return " ".join(tokens)


def _extract_topic_tokens(text: str, tags: str = "", limit: int = 12) -> list[str]:
    candidates = []
    for source in (text, tags):
        for raw in _TOKEN_RE.findall(source or ""):
            token = _normalize_topic_token(raw)
            if len(token) < 3 or token in _STOPWORDS or token.isdigit():
                continue
            candidates.append(token)
    return _ordered_unique(candidates)[:limit]


@dataclass
class EnrichedFact:
    entities: list[str]
    people: list[str]
    projects: list[str]
    topics: list[str]
    entity_keys: list[str]
    person_keys: list[str]
    project_keys: list[str]
    topic_keys: list[str]
    cluster_keys: list[str]
    dates: list[str]
    times: list[str]
    locations: list[str]
    intent_type: str
    source_channel: str
    salience_score: float
    source_confidence: float
    keywords: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def build_cluster_keys(
    entities: Iterable[str],
    people: Iterable[str],
    projects: Iterable[str],
    topics: Iterable[str],
) -> tuple[list[str], list[str], list[str], list[str], list[str]]:
    entity_keys = _ordered_unique(canonicalize_key(entity) for entity in entities)
    person_keys = _ordered_unique(canonicalize_key(person) for person in people)
    project_keys = _ordered_unique(
        canonicalize_key(project, drop_project_hints=True) for project in projects
    )
    topic_keys = _ordered_unique(canonicalize_key(topic) for topic in topics)
    cluster_keys = _ordered_unique(
        [f"entity:{value}" for value in entity_keys]
        + [f"person:{value}" for value in person_keys]
        + [f"project:{value}" for value in project_keys]
        + [f"topic:{value}" for value in topic_keys]
    )
    return entity_keys, person_keys, project_keys, topic_keys, cluster_keys


def extract_entities(text: str, tags: str = "") -> list[str]:
    candidates: list[str] = []
    for match in _RE_CAPITALIZED_MULTI.finditer(text):
        candidates.append(match.group(1))
    for match in _RE_DOUBLE_QUOTE.finditer(text):
        candidates.append(match.group(1))
    for match in _RE_SINGLE_QUOTE.finditer(text):
        candidates.append(match.group(1))
    for match in _RE_AKA.finditer(text):
        candidates.extend([match.group(1), match.group(2)])
    for match in _RE_MENTION.finditer(text):
        candidates.append(match.group(1))
    for match in _RE_HASHTAG.finditer(text):
        candidates.append(match.group(1))
    for tag in (tags or "").split(","):
        tag = tag.strip()
        if tag:
            candidates.append(tag)
    return _ordered_unique(candidates)


def extract_people(entities: Iterable[str]) -> list[str]:
    people = []
    for entity in entities:
        if " " in entity and entity[:1].isupper():
            people.append(entity)
        elif entity.startswith("@"):
            people.append(entity.lstrip("@"))
    return _ordered_unique(people)


def extract_projects(text: str, entities: Iterable[str], tags: str = "") -> list[str]:
    projects: list[str] = []
    for match in _RE_PROJECT.finditer(text):
        cleaned = _clean_project_candidate(match.group(1))
        if cleaned:
            projects.append(cleaned)
    for match in _RE_PREFIX_PROJECT.finditer(text):
        cleaned = _clean_project_candidate(match.group(1))
        if cleaned:
            projects.append(cleaned)

    topic_tokens = set(_extract_topic_tokens(text, tags))
    for entity in entities:
        lowered = entity.lower()
        if any(hint in lowered for hint in _PROJECT_HINTS):
            projects.append(entity)
            continue
        if lowered in topic_tokens and any(marker in lowered for marker in ("hermes", "neo", "repo", "service", "bot")):
            projects.append(entity)

    for tag in (tags or "").split(","):
        cleaned = tag.strip()
        if cleaned.lower().startswith("project:"):
            project_value = _clean_project_candidate(cleaned.split(":", 1)[1].strip())
            if project_value:
                projects.append(project_value)

    return _ordered_unique(projects)


def extract_dates(text: str) -> list[str]:
    matches: list[str] = []
    for pattern in (_RE_ISO_DATE, _RE_SLASH_DATE, _RE_MONTH_DATE):
        matches.extend(match.group(0) for match in pattern.finditer(text))
    return _ordered_unique(matches)


def extract_times(text: str) -> list[str]:
    matches: list[str] = []
    for pattern in (_RE_TIME, _RE_24H_TIME):
        matches.extend(match.group(0) for match in pattern.finditer(text))
    return _ordered_unique(matches)


def extract_locations(text: str) -> list[str]:
    return _ordered_unique(match.group(1) for match in _RE_LOCATION.finditer(text))


def infer_intent_type(text: str, category: str = "general") -> str:
    lowered = (category or "").lower()
    if lowered == "user_pref":
        return "preference"
    if lowered == "project":
        return "decision"
    for label, pattern in _INTENT_PATTERNS:
        if pattern.search(text or ""):
            return label
    return "general"


def estimate_salience(
    text: str,
    *,
    category: str = "general",
    tags: str = "",
    intent_type: str = "general",
    override: float | None = None,
) -> float:
    if override is not None:
        return max(0.0, min(1.0, float(override)))

    score = 0.45
    lowered = (text or "").lower()
    if category in {"user_pref", "project"}:
        score += 0.08
    if intent_type in {"decision", "goal", "issue", "task"}:
        score += 0.12
    if any(term in lowered for term in _HIGH_SALIENCE_TERMS):
        score += 0.1
    if len(text or "") > 160:
        score += 0.05
    if tags:
        score += 0.03
    return max(0.15, min(1.0, score))


def estimate_source_confidence(
    source_channel: str,
    *,
    intent_type: str = "general",
    override: float | None = None,
) -> float:
    if override is not None:
        return max(0.0, min(1.0, float(override)))

    source = (source_channel or "").lower()
    if source.startswith("builtin:user"):
        base = 0.9
    elif source.startswith("tool:") or source.startswith("explicit:"):
        base = 0.88
    elif source.startswith("builtin:memory"):
        base = 0.82
    elif source.startswith("session_auto_extract"):
        base = 0.62
    elif source.startswith("telegram") or source.startswith("discord") or source.startswith("slack"):
        base = 0.76
    elif source:
        base = 0.72
    else:
        base = 0.68

    if intent_type in {"decision", "preference"}:
        base += 0.04

    return max(0.1, min(1.0, base))


def enrich_fact(
    text: str,
    *,
    category: str = "general",
    tags: str = "",
    source_channel: str = "",
    intent_type: str | None = None,
    salience_score: float | None = None,
    source_confidence: float | None = None,
) -> EnrichedFact:
    entities = extract_entities(text, tags=tags)
    people = extract_people(entities)
    projects = extract_projects(text, entities, tags=tags)
    topics = _extract_topic_tokens(text, tags=tags)
    entity_keys, person_keys, project_keys, topic_keys, cluster_keys = build_cluster_keys(
        entities,
        people,
        projects,
        topics,
    )
    dates = extract_dates(text)
    times = extract_times(text)
    locations = extract_locations(text)
    inferred_intent = intent_type or infer_intent_type(text, category=category)
    effective_source = source_channel or "unknown"

    return EnrichedFact(
        entities=entities,
        people=people,
        projects=projects,
        topics=topics,
        entity_keys=entity_keys,
        person_keys=person_keys,
        project_keys=project_keys,
        topic_keys=topic_keys,
        cluster_keys=cluster_keys,
        dates=dates,
        times=times,
        locations=locations,
        intent_type=inferred_intent,
        source_channel=effective_source,
        salience_score=estimate_salience(
            text,
            category=category,
            tags=tags,
            intent_type=inferred_intent,
            override=salience_score,
        ),
        source_confidence=estimate_source_confidence(
            effective_source,
            intent_type=inferred_intent,
            override=source_confidence,
        ),
        keywords=topics[:8],
    )
