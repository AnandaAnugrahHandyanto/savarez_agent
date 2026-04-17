"""Injection signature database.

Each pattern has a stable `id` so downstream consumers can allowlist/
denylist specific rules without relying on regex contents. Severities
are conservative: "high" is reserved for signatures that almost never
appear in legitimate tool output.

Adding a new pattern:
  1. Write the regex. Anchor it loosely — attackers pad with whitespace.
  2. Pick severity based on false-positive cost, not attack impact.
  3. Add a regression test in tests/agent/test_immune_system.py.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Pattern:
    id: str
    regex: re.Pattern
    severity: str  # "low" | "medium" | "high"
    description: str


# Order does not matter — the scanner runs every pattern. Keep high-severity
# signatures specific enough that legitimate content rarely matches.
PATTERNS: tuple[Pattern, ...] = (
    Pattern(
        id="override-prior-instructions",
        regex=re.compile(
            r"ignore\s+(all\s+)?(previous|prior|above|earlier|the)\s+"
            r"(instructions|prompts|rules|context|directives|commands)",
            re.IGNORECASE,
        ),
        severity="high",
        description="Attempt to override prior instructions",
    ),
    Pattern(
        id="forget-previous",
        regex=re.compile(
            r"(forget|disregard)\s+(everything|all|your\s+(previous|prior))",
            re.IGNORECASE,
        ),
        severity="high",
        description="Request to forget prior context",
    ),
    Pattern(
        id="exfil-system-prompt",
        regex=re.compile(
            r"(print|reveal|show|output|repeat|echo)\s+(your\s+)?"
            r"(system\s+|initial\s+|original\s+)(prompt|instructions|message)",
            re.IGNORECASE,
        ),
        severity="high",
        description="Attempt to exfiltrate the system prompt",
    ),
    Pattern(
        id="fake-system-tag",
        regex=re.compile(
            r"</?\s*(system|admin|developer|sudo|root|assistant)\s*>",
            re.IGNORECASE,
        ),
        severity="high",
        description="Fake privileged role tag embedded in data",
    ),
    Pattern(
        id="chatml-injection",
        regex=re.compile(
            r"<\|\s*im_(start|end)\s*\|>\s*(system|developer|user|assistant)?",
            re.IGNORECASE,
        ),
        severity="high",
        description="ChatML role-boundary injection",
    ),
    Pattern(
        id="role-override",
        regex=re.compile(
            r"you\s+are\s+(now\s+)?(a|an|the)\s+\w+",
            re.IGNORECASE,
        ),
        severity="medium",
        description="Attempt to redefine the agent's role",
    ),
    Pattern(
        id="llama-inst-tag",
        regex=re.compile(r"\[\s*/?\s*INST\s*\]"),
        severity="medium",
        description="Llama-family [INST] tag embedded in data",
    ),
    Pattern(
        id="new-instructions",
        regex=re.compile(
            r"new\s+(instructions|directives|orders|rules)\s*[:;]",
            re.IGNORECASE,
        ),
        severity="medium",
        description="'New instructions:' preamble",
    ),
    Pattern(
        id="shell-execution-request",
        regex=re.compile(
            r"(execute|run|eval|exfiltrate|send)\s+"
            r"(the\s+)?(following\s+)?"
            r"(curl|wget|cat|ls|sudo|rm|powershell|bash|sh|python)\s",
            re.IGNORECASE,
        ),
        severity="high",
        description="Request to execute shell commands from data",
    ),
    Pattern(
        id="tool-call-fake",
        regex=re.compile(
            r"(call|invoke|use)\s+the\s+\w+\s+tool\s+(with|to|and)\s+",
            re.IGNORECASE,
        ),
        severity="medium",
        description="Embedded instructions to call tools",
    ),
    Pattern(
        id="zero-width-chars",
        regex=re.compile(r"[\u200B-\u200D\u2060\uFEFF]"),
        severity="low",
        description="Zero-width unicode (possible steganography)",
    ),
    Pattern(
        id="rlhf-jailbreak",
        regex=re.compile(
            r"(DAN|do\s+anything\s+now|jailbreak|developer\s+mode\s+enabled)",
            re.IGNORECASE,
        ),
        severity="medium",
        description="Known jailbreak persona markers",
    ),
)
