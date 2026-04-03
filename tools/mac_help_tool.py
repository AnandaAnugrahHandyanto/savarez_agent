#!/usr/bin/env python3
"""macOS Help Tool — Answer 'how do I...' questions using a local feature knowledge base."""

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml


# --- Knowledge Base ---

_STOP_WORDS = {
    "how", "do", "i", "can", "to", "the", "a", "an", "is", "it",
    "my", "on", "in", "of", "for", "with", "this", "that", "what",
    "where", "when", "why", "me", "make", "want", "need", "get",
    "set", "up", "use", "using", "does", "way", "there",
}


def _tokenize(text: str, remove_stopwords: bool = True) -> List[str]:
    """Tokenize text: lowercase, remove non-alphanumeric, optional stop word removal."""
    cleaned = re.sub(r"[^a-z0-9 ]", " ", text.lower())
    tokens = [t for t in cleaned.split() if len(t) > 1]
    if remove_stopwords:
        tokens = [t for t in tokens if t not in _STOP_WORDS]
    return tokens


def _dice_score(a: List[str], b: List[str]) -> float:
    """Dice coefficient between two token lists."""
    set_a = set(a)
    set_b = set(b)
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    if intersection == 0:
        return 0.0
    return (2.0 * intersection) / (len(set_a) + len(set_b))


class FeatureDatabase:
    """Loads and queries macOS feature YAML files."""

    def __init__(self, kb_path: str = "~/.hermes/macos-kb"):
        self.features: Dict[str, Dict[str, Any]] = {}
        self.categories: Dict[str, List[str]] = {}
        expanded = os.path.expanduser(kb_path)
        if os.path.isdir(expanded):
            self._load(expanded)

    def _load(self, directory: str):
        for f in sorted(Path(directory).glob("*.yaml")):
            try:
                data = yaml.safe_load(f.read_text())
                for feat in data.get("features", []):
                    fid = feat.get("id")
                    if fid:
                        self.features[fid] = feat
                        cat = feat.get("category", "uncategorized")
                        self.categories.setdefault(cat, []).append(fid)
            except Exception:
                pass

    def find(self, feature_id: str) -> Optional[Dict[str, Any]]:
        return self.features.get(feature_id)

    def by_category(self, category: str) -> List[Dict[str, Any]]:
        ids = self.categories.get(category, [])
        return [self.features[fid] for fid in ids if fid in self.features]

    def all_categories(self) -> List[str]:
        return sorted(self.categories.keys())


class IntentMatcher:
    """Fuzzy-matches natural language queries to macOS features."""

    def __init__(self, db: FeatureDatabase):
        self.db = db

    def match(self, query: str, limit: int = 3) -> List[Tuple[Dict[str, Any], float, str]]:
        """Returns list of (feature, score, reason) tuples."""
        query_tokens = _tokenize(query)
        query_lower = query.lower()
        if not query_tokens:
            return []

        scored = []
        for feat in self.db.features.values():
            score, reason = self._score(feat, query_tokens, query_lower)
            if score > 0.1:
                scored.append((feat, score, reason))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]

    def _score(self, feat: Dict, query_tokens: List[str], query_lower: str) -> Tuple[float, str]:
        best_score = 0.0
        best_reason = ""

        # Name match
        name_score = _dice_score(query_tokens, _tokenize(feat.get("name", "")))
        if name_score > best_score:
            best_score = name_score
            best_reason = f"Matched name: '{feat['name']}'"

        # Alias match
        for alias in feat.get("aliases", []):
            alias_lower = alias.lower()
            if len(alias_lower) >= 4 and (query_lower in alias_lower or alias_lower in query_lower):
                if 0.95 > best_score:
                    best_score = 0.95
                    best_reason = f"Matched alias: '{alias}'"
            alias_score = _dice_score(query_tokens, _tokenize(alias))
            if alias_score > best_score:
                best_score = alias_score
                best_reason = f"Matched alias: '{alias}'"

        # User intent match (boosted)
        for intent in feat.get("user_intents", []):
            intent_lower = intent.lower()
            if len(intent_lower) >= 4 and (query_lower in intent_lower or intent_lower in query_lower):
                if 0.9 > best_score:
                    best_score = 0.9
                    best_reason = f"Matched intent: '{intent}'"
            raw_tokens = _tokenize(intent, remove_stopwords=False)
            query_raw = _tokenize(query_lower, remove_stopwords=False)
            intent_score = _dice_score(query_raw, raw_tokens) * 1.15
            if intent_score > best_score:
                best_score = min(intent_score, 1.0)
                best_reason = f"Matched intent: '{intent}'"

        # Tag bonus
        tag_tokens = {t.lower() for t in feat.get("tags", [])}
        overlap = set(query_tokens) & tag_tokens
        if overlap:
            best_score = min(best_score + len(overlap) * 0.08, 1.0)
            if not best_reason:
                best_reason = f"Matched tags: {', '.join(sorted(overlap))}"

        return best_score, best_reason


# --- Singleton instances ---
_db: Optional[FeatureDatabase] = None
_matcher: Optional[IntentMatcher] = None


def _get_db() -> FeatureDatabase:
    global _db
    if _db is None:
        _db = FeatureDatabase()
    return _db


def _get_matcher() -> IntentMatcher:
    global _matcher
    if _matcher is None:
        _matcher = IntentMatcher(_get_db())
    return _matcher


# --- Formatting ---

def _format_feature(feat: Dict, depth: str, confidence: float) -> str:
    """Format a feature for display."""
    lines = []
    conf_label = "high" if confidence > 0.8 else "good" if confidence > 0.5 else "partial"
    lines.append(f"# {feat['name']}")
    lines.append(f"Match confidence: {conf_label} ({confidence*100:.0f}%)")
    lines.append(feat.get("description", ""))

    pd = feat.get("progressive_depth", {})

    if depth == "quick":
        lines.append(f"\n**Quick answer:** {pd.get('quick', '')}")
    elif depth == "power":
        lines.append(f"\n**How to:** {pd.get('detailed', '')}")
        lines.append(f"\n**Advanced:** {pd.get('power', '')}")
        _append_methods(lines, feat.get("methods", []), include_scripts=True)
    else:
        lines.append(f"\n**How to:** {pd.get('detailed', '')}")
        _append_methods(lines, feat.get("methods", []), include_scripts=False)

    # Automation offer
    automatable = any(m.get("type") in ("applescript", "terminal", "defaults_write")
                      for m in feat.get("methods", []))
    if automatable:
        lines.append("\n*This can be automated. Ask me to do it for you if you'd like.*")

    # Metadata
    meta = [f"Difficulty: {feat.get('difficulty', 'beginner')}"]
    if feat.get("available_since"):
        meta.append(f"Available since: {feat['available_since']}")
    lines.append("\n" + " | ".join(meta))

    related = feat.get("related", [])
    if related:
        lines.append(f"Related: {', '.join(related)}")

    return "\n".join(lines)


def _append_methods(lines: List[str], methods: List[Dict], include_scripts: bool):
    for m in methods:
        mtype = m.get("type", "")
        if mtype == "system_settings" and m.get("path"):
            lines.append(f"\n**Via System Settings:** {m['path']}")
            for i, step in enumerate(m.get("steps", []), 1):
                lines.append(f"{i}. {step}")
        elif mtype == "keyboard_shortcut" and m.get("shortcut"):
            lines.append(f"\n**Keyboard shortcut:** {m['shortcut']}")
        elif mtype == "siri" and m.get("command"):
            lines.append(f'\n**Siri:** "{m["command"]}"')
        elif mtype == "terminal" and include_scripts and m.get("command"):
            lines.append(f"\n**Terminal:** `{m['command']}`")
        elif mtype == "defaults_write" and include_scripts and m.get("command"):
            lines.append(f"\n**defaults write:** `{m['command']}`")


# --- Tool handler ---

def mac_help_handler(
    query: str,
    depth: str = "detailed",
    action: str = "explain",
) -> str:
    """Handle mac_help tool calls."""
    db = _get_db()
    matcher = _get_matcher()

    if not db.features:
        return json.dumps({"error": "macOS knowledge base not found at ~/.hermes/macos-kb/"})

    if action == "list_category":
        cat = query.lower()
        features = db.by_category(cat)
        if not features:
            # Try fuzzy match
            for c in db.all_categories():
                if cat in c or c in cat:
                    features = db.by_category(c)
                    cat = c
                    break
        if features:
            lines = [f"# {cat.replace('-', ' ').title()}", f"{len(features)} features:\n"]
            for f in features:
                pd = f.get("progressive_depth", {})
                lines.append(f"- **{f['name']}**: {pd.get('quick', f.get('description', ''))}")
            return "\n".join(lines)
        else:
            available = "\n".join(f"- {c}" for c in db.all_categories()[:10])
            return f"Category '{query}' not found.\n\nAvailable categories:\n{available}"

    if action == "lookup":
        feat = db.find(query)
        if feat:
            return _format_feature(feat, depth, 1.0)
        # Fall through to explain

    # Explain (default)
    matches = matcher.match(query, limit=3)
    if not matches or matches[0][1] < 0.15:
        cats = "\n".join(f"- {c}" for c in db.all_categories()[:5])
        return (
            f'No matching macOS feature found for: "{query}"\n\n'
            f"This might not be in the knowledge base yet. "
            f"The agent can still try to answer from general knowledge.\n\n"
            f"Available categories:\n{cats}"
        )

    best_feat, best_score, best_reason = matches[0]
    result = _format_feature(best_feat, depth, best_score)

    # Runner-up alternatives
    alternatives = [(f, s, r) for f, s, r in matches[1:] if s > 0.3]
    if alternatives:
        alt_lines = [f"- {f['name']} ({r})" for f, s, r in alternatives]
        result += "\n\n## Also Relevant\n" + "\n".join(alt_lines)

    return result


def check_mac_help_requirements() -> bool:
    """Check if macOS KB directory exists."""
    return os.path.isdir(os.path.expanduser("~/.hermes/macos-kb"))


MAC_HELP_SCHEMA = {
    "name": "mac_help",
    "description": (
        "Answer how-to questions about macOS features, settings, keyboard shortcuts, "
        "and hidden capabilities. Returns explanations at the requested depth level."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "Natural language question about macOS, e.g. "
                    "'how do I sign a PDF' or 'keep my Mac from sleeping'"
                ),
            },
            "depth": {
                "type": "string",
                "enum": ["quick", "detailed", "power"],
                "description": (
                    "Response depth: quick (1-line answer), "
                    "detailed (steps + options), power (advanced/terminal). "
                    "Defaults to detailed."
                ),
            },
            "action": {
                "type": "string",
                "enum": ["explain", "lookup", "list_category"],
                "description": (
                    "explain = answer a how-to question, "
                    "lookup = find a specific feature by name, "
                    "list_category = list all features in a category. "
                    "Defaults to explain."
                ),
            },
        },
        "required": ["query"],
    },
}


# --- Registry ---
from tools.registry import registry

registry.register(
    name="mac_help",
    toolset="macos",
    schema=MAC_HELP_SCHEMA,
    handler=lambda args, **kw: mac_help_handler(
        query=args.get("query", ""),
        depth=args.get("depth", "detailed"),
        action=args.get("action", "explain"),
    ),
    check_fn=check_mac_help_requirements,
    emoji="🖥️",
)
