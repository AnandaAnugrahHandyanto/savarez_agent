"""Scanner: run the pattern DB over a tool output and aggregate matches."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .patterns import PATTERNS

SEVERITY_RANK = {"none": 0, "low": 1, "medium": 2, "high": 3}
DEFAULT_MAX_SCAN_LENGTH = 500_000  # cap CPU on multi-MB results


@dataclass
class Match:
    pattern_id: str
    severity: str
    description: str
    snippet: str


@dataclass
class ScanResult:
    matches: List[Match] = field(default_factory=list)
    max_severity: str = "none"
    truncated: bool = False

    @property
    def is_clean(self) -> bool:
        return not self.matches

    def at_least(self, min_severity: str) -> bool:
        """True when `max_severity` meets or exceeds `min_severity`."""
        return SEVERITY_RANK[self.max_severity] >= SEVERITY_RANK[min_severity]


def scan(content: str, max_length: int = DEFAULT_MAX_SCAN_LENGTH) -> ScanResult:
    """Scan `content` for prompt-injection signatures.

    Bounded by `max_length` so a 10MB file dump doesn't blow up scanning
    cost. If content exceeds the limit, the scan runs over the prefix and
    `truncated=True` is reported on the result.
    """
    result = ScanResult()
    if not content:
        return result

    if len(content) > max_length:
        text = content[:max_length]
        result.truncated = True
    else:
        text = content

    for pattern in PATTERNS:
        for m in pattern.regex.finditer(text):
            start = max(0, m.start() - 20)
            end = min(len(text), m.end() + 20)
            snippet = text[start:end].replace("\n", " ").replace("\r", " ")
            result.matches.append(
                Match(
                    pattern_id=pattern.id,
                    severity=pattern.severity,
                    description=pattern.description,
                    snippet=snippet[:120],
                )
            )
            if SEVERITY_RANK[pattern.severity] > SEVERITY_RANK[result.max_severity]:
                result.max_severity = pattern.severity

    return result
