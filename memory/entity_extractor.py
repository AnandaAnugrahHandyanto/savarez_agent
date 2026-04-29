"""
Entity extractor — pulls structured entities and relations from raw text.

Uses simple pattern-based extraction (NER-light) to avoid heavy dependencies.
In production, replace with an LLM-based extractor or spacy/huggingface NER.

Output format:
  entities = [{"name": "...", "entity_type": "...", "properties": {...}}]
  relations = [{"from_name": "...", "to_name": "...", "relation_type": "...", ...}]
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Entity types and their typical patterns
# -----------------------------------------------------------------------------

ENTITY_PATTERNS: List[Tuple[str, re.Pattern]] = [
    # Person names: "John", "Dr. Smith", "Elena"
    (
        "person",
        re.compile(
            r"\b((?:(?:Dr|Mr|Mrs|Ms|Prof|Prof\.)\s+)?"
            r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b",
            re.UNICODE,
        ),
    ),
    # Organization / company: "OpenAI", "the EPA"
    (
        "organization",
        re.compile(
            r"\b(?:the\s+)?"
            r"(?:[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,3}\s+)?"
            r"(?:Inc|LLC|Corp|Ltd|Co\.?|GmbH|PLC|Company|Institute|University|"
            r"Foundation|Association|Agency|Team|Group|Hospital|School)\b",
            re.UNICODE,
        ),
    ),
    # Software / project: "React", "Docker", "Kubernetes"
    (
        "software",
        re.compile(
            r"\b([A-Z][a-zA-Z0-9]{2,}(?:\s*[A-Z][a-zA-Z0-9]+)*)\b",
            re.UNICODE,
        ),
    ),
    # File / path: "/home/user/file.py"
    (
        "file",
        re.compile(r"(?:/[\w\-.~]+)+|[\w\-.~]+\.(?:py|js|ts|md|yaml|json|txt|cfg|ini|env)(?:\.\w+)?"),
    ),
    # URL: "https://..."
    (
        "url",
        re.compile(r"https?://[^\s<>\[\]\"']+"),
    ),
    # Email: "user@example.com"
    (
        "email",
        re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    ),
    # Date / time: "March 2024", "2024-01-15", "3 hours ago"
    (
        "datetime",
        re.compile(
            r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}|"
            r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}|"
            r"\d+\s+(?:seconds?|minutes?|hours?|days?|weeks?|months?|years?)\s+ago)\b",
            re.IGNORECASE,
        ),
    ),
    # Number + unit: "50 MB", "2 hours"
    (
        "quantity",
        re.compile(r"\b\d+(?:\.\d+)?\s*(?:MB|GB|TB|KB|ms|s|min|hours?|days?|weeks?|months?|years?|cm|m|kg|lb|px|em|%\b)"),
    ),
]

# Common stopwords that are too generic to be useful entity names
_STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "up", "about", "into", "through", "during",
    "before", "after", "above", "below", "between", "under", "again",
    "further", "then", "once", "here", "there", "when", "where", "why",
    "how", "all", "each", "few", "more", "most", "other", "some", "such",
    "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very",
    "just", "can", "will", "just", "now", "I", "you", "he", "she", "it",
    "we", "they", "what", "which", "who", "this", "that", "these", "those",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "having", "do", "does", "did", "doing", "would", "should", "could",
    "must", "might", "must", "going", "want", "need", "like", "know",
    "think", "see", "make", "get", "use", "also", "as", "if", "or", "when",
    "new", "first", "last", "long", "great", "little", "own", "old",
    "right", "big", "high", "different", "small", "large", "next", "early",
    "public", "bad", "same", "able", "right", "yes", "no", "maybe",
})

# Relation extraction patterns
RELATION_PATTERNS: List[Tuple[str, re.Pattern]] = [
    # X is Y's friend/partner/colleague
    (
        "knows",
        re.compile(
            r"(?P<from>[\w\s]{1,50})\s+(?:is|'s)\s+(?:friends?|partners?|colleagues?|married to|married with|"
            r"in a relationship with)\s+(?P<to>[\w\s]{1,50})",
            re.IGNORECASE,
        ),
    ),
    # X works at Y
    (
        "works_at",
        re.compile(
            r"(?P<from>[\w\s]{1,50})\s+works?\s+(?:at|for)\s+(?P<to>[\w\s]{1,50})",
            re.IGNORECASE,
        ),
    ),
    # X is the author/creator of Y
    (
        "authored",
        re.compile(
            r"(?P<from>[\w\s]{1,50})\s+is\s+(?:the\s+)?(?:author|creator|maker|creator|"
            r"founder|originator|developer)\s+(?:of|for)\s+(?P<to>[\w\s]{1,50})",
            re.IGNORECASE,
        ),
    ),
    # X uses Y (technology)
    (
        "uses",
        re.compile(
            r"(?P<from>[\w\s]{1,50})\s+(?:uses?|using|built with|powered by|"
            r"based on)\s+(?P<to>[\w\s]{1,50})",
            re.IGNORECASE,
        ),
    ),
    # X is a type/kind of Y
    (
        "is_a",
        re.compile(
            r"(?P<from>[\w\s]{1,50})\s+is\s+(?:a|an|the)?\s*(?:\w+\s+)?"
            r"(?:type|kind|version|part|instance)\s+(?:of|in)\s+(?P<to>[\w\s]{1,50})",
            re.IGNORECASE,
        ),
    ),
    # X is part of Y
    (
        "part_of",
        re.compile(
            r"(?P<from>[\w\s]{1,50})\s+is\s+(?:a|an|the)?\s*(?:part|component)\s+"
            r"of\s+(?P<to>[\w\s]{1,50})",
            re.IGNORECASE,
        ),
    ),
    # X depends on Y
    (
        "depends_on",
        re.compile(
            r"(?P<from>[\w\s]{1,50})\s+(?:depends? on|requires?|needs?)\s+(?P<to>[\w\s]{1,50})",
            re.IGNORECASE,
        ),
    ),
    # X created Y
    (
        "created",
        re.compile(
            r"(?P<from>[\w\s]{1,50})\s+(?:created|made|built|developed|wrote)\s+(?P<to>[\w\s]{1,50})",
            re.IGNORECASE,
        ),
    ),
]


@dataclass
class ExtractionResult:
    entities: List[Dict[str, Any]] = field(default_factory=list)
    relations: List[Dict[str, Any]] = field(default_factory=list)
    facts: List[str] = field(default_factory=list)  # free-text facts


class EntityExtractor:
    """Extracts entities and relations from raw text."""

    def __init__(self, min_confidence: float = 0.5):
        self.min_confidence = min_confidence

    def extract(self, text: str) -> ExtractionResult:
        """Main entry point — extract all entities and relations from text."""
        if not text or not text.strip():
            return ExtractionResult()

        text = text.strip()
        entities = self._extract_entities(text)
        relations = self._extract_relations(text)
        facts = self._extract_facts(text)

        return ExtractionResult(
            entities=entities,
            relations=relations,
            facts=facts,
        )

    def _extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """Find all matching entities by type-specific regex patterns."""
        seen: Dict[str, Tuple[str, str]] = {}  # key → (name, type)
        results: List[Dict[str, Any]] = []

        for entity_type, pattern in ENTITY_PATTERNS:
            for match in pattern.finditer(text):
                name = match.group(0).strip()
                key = f"{entity_type}:{name.lower()}"

                if len(name) < 2:
                    continue
                if name.lower() in _STOPWORDS:
                    continue
                if name.lower().startswith(("the ", "a ", "an ")):
                    # Strip leading article
                    stripped = name.lower().replace("the ", "", 1).replace("a ", "", 1).replace("an ", "", 1).strip()
                    if stripped and stripped not in _STOPWORDS:
                        name = stripped
                        key = f"{entity_type}:{name.lower()}"

                if key not in seen:
                    seen[key] = (name, entity_type)

        for _, (name, entity_type) in seen.items():
            results.append({
                "name": name,
                "entity_type": entity_type,
                "alias": "",
                "properties": {},
                "confidence": 0.7,
            })

        return results

    def _extract_relations(self, text: str) -> List[Dict[str, Any]]:
        """Extract typed relations between entities."""
        results: List[Dict[str, Any]] = []

        for rel_type, pattern in RELATION_PATTERNS:
            for match in pattern.finditer(text):
                from_name = match.group("from").strip()
                to_name = match.group("to").strip()

                # Skip very short or stopword-only names
                if len(from_name) < 2 or from_name.lower() in _STOPWORDS:
                    continue
                if len(to_name) < 2 or to_name.lower() in _STOPWORDS:
                    continue

                results.append({
                    "from_name": from_name,
                    "to_name": to_name,
                    "from_type": "concept",
                    "to_type": "concept",
                    "relation_type": rel_type,
                    "properties": {},
                    "confidence": 0.6,
                })

        return results

    def _extract_facts(self, text: str) -> List[str]:
        """Extract free-text fact sentences as string facts for storage."""
        # Split into sentences (roughly)
        sentences = re.split(r"[.!\n]+", text)
        facts = []
        for sent in sentences:
            sent = sent.strip()
            if len(sent) > 20 and len(sent) < 500:
                # Filter out questions
                if sent.endswith("?") or sent.startswith(("who", "what", "where", "when", "why", "how")):
                    continue
                facts.append(sent)
        return facts


# -----------------------------------------------------------------------------
# LLM-based extractor (optional, used when LLM is available)
# -----------------------------------------------------------------------------

EXTRACT_PROMPT = """You are an entity and relation extraction system. Given the following text, extract:

1. ENTITIES: Key concepts, people, organizations, software, files, locations mentioned.
   - For each entity provide: name, type (person/organization/concept/software/file/location/event)
   - Types must be one of: person, organization, concept, software, file, location, event, project, policy

2. RELATIONS: Relationships between entities.
   - For each relation: from_entity, to_entity, relation_type (e.g. works_at, created_by, uses, depends_on, part_of, knows, authored)
   - from_entity and to_entity should use entity names

3. FACTS: Important facts stated in the text (max 5, skip generic ones).

Return JSON:
{
  "entities": [{"name": "...", "entity_type": "...", "properties": {...}}],
  "relations": [{"from_name": "...", "to_name": "...", "from_type": "...", "to_type": "...", "relation_type": "..."}],
  "facts": ["fact 1", "fact 2"]
}

Text:
{text}

JSON:
"""


def extract_with_llm(text: str, llm_client: Any) -> ExtractionResult:
    """Use an LLM to extract entities/relations (requires an LLM client)."""
    try:
        response = llm_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You extract structured entities and relations from text."},
                {"role": "user", "content": EXTRACT_PROMPT.format(text=text)},
            ],
            temperature=0.0,
            max_tokens=2000,
        )
        content = response.choices[0].message.content
        # Try to parse JSON
        import json as _json
        # Strip markdown code fences
        content = content.strip()
        if content.startswith("```"):
            content = _json.loads(content.split("```")[1].strip("json\n"))  # type: ignore
        data = _json.loads(content)
        return ExtractionResult(
            entities=data.get("entities", []),
            relations=data.get("relations", []),
            facts=data.get("facts", []),
        )
    except Exception as exc:
        logger.warning("LLM extraction failed: %s", exc)
        return ExtractionResult()
