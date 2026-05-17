"""
Heuristic Tool-Name Normalizer

When an LLM hallucinates a tool name that doesn't exist in the available tools,
try to map the hallucinated name to the closest available tool by substring
matching. Useful for Gemma 4 and similar models trained on different tool
naming conventions (e.g. Google-AI tool namespace).

Examples:
    google:tool:shell:index:0  -> terminal  (matches "shell" hint)
    tool:execute_terminal      -> terminal  (matches "terminal" substring)
    google/search              -> web_search  (matches "search" substring)
"""
from typing import Optional, Iterable
import logging
import re

_LOG = logging.getLogger(__name__)

# Tool-name aliases. Maps tokens that appear in hallucinated names to
# canonical Hermes tool-name patterns. Specific before generic.
_ALIAS_TOKENS = {
    "shell": ["terminal", "bash", "execute_command"],
    "bash": ["terminal"],
    "exec": ["terminal", "code_execution"],
    "terminal": ["terminal"],
    "process": ["process"],
    "search": ["web_search", "web", "search"],
    "browser": ["browser_navigate", "browser"],
    "read": ["read_file", "file_read"],
    "write": ["write_file", "file_write"],
    "edit": ["edit_file", "file_edit"],
    "memory": ["memory_search", "memory"],
}


def _tokenize(name: str) -> list[str]:
    """Split hallucinated name into lowercase tokens by non-alphanum boundaries."""
    return [t for t in re.split(r"[^a-zA-Z0-9]+", name.lower()) if t]


def normalize_tool_name(
    hallucinated: str,
    available: Iterable[str],
) -> Optional[str]:
    """
    Try to map a hallucinated tool name to an available one.

    Returns the matched available tool name, or None if no plausible match.
    Strategy (in order):
        1. Exact match (case-insensitive)
        2. Available name is substring of hallucinated (e.g. "terminal" in "tool:execute_terminal")
        3. Hallucinated name is substring of available (rare)
        4. Token-based alias mapping via _ALIAS_TOKENS
    """
    if not hallucinated or not available:
        return None
    available_list = list(available)
    avail_lower = {a.lower(): a for a in available_list}
    h_lower = hallucinated.lower()

    # 1. Exact match (already case-fixed)
    if h_lower in avail_lower:
        return avail_lower[h_lower]

    # 2. Available name is substring of hallucinated
    # Sort longest-first so "execute_terminal" matches "terminal" not "exec"
    for avail in sorted(available_list, key=len, reverse=True):
        if avail.lower() in h_lower:
            return avail

    # 3. Hallucinated name is substring of available (rare, weak signal)
    if len(h_lower) >= 4:
        for avail in available_list:
            if h_lower in avail.lower():
                return avail

    # 4. Token-based alias mapping
    tokens = _tokenize(hallucinated)
    for token in tokens:
        if token in _ALIAS_TOKENS:
            for candidate in _ALIAS_TOKENS[token]:
                if candidate in avail_lower:
                    return avail_lower[candidate]

    return None
