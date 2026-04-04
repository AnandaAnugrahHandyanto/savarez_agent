"""Guardrails Framework — composable input/output validation pipeline.

Consolidates duplicated threat patterns from memory_tool, knowledge_tool,
context_graph_tool, and cronjob_tools into a single source of truth.
Adds PII detection and a pluggable guardrail pipeline.

Inspired by agno's Guardrail ABC with PII/injection/moderation implementations.

Usage:
    from agent.guardrails import scan_content, GuardrailPipeline, InjectionGuardrail, PIIGuardrail

    # Simple scan (backward-compatible replacement for _scan_memory_content etc.)
    error = scan_content("some user input")
    if error:
        reject(error)

    # Pipeline for agent-level pre/post processing
    pipeline = GuardrailPipeline([InjectionGuardrail(), PIIGuardrail()])
    result = pipeline.check_input("user message")
    if not result.passed:
        handle_block(result.reason)
"""

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)


# ============================================================================
# Shared threat patterns (single source of truth)
# ============================================================================

THREAT_PATTERNS = [
    # Prompt injection
    (r'ignore\s+(?:\w+\s+)*(previous|all|above|prior)\s+(?:\w+\s+)*instructions', "prompt_injection"),
    (r'you\s+are\s+now\s+', "role_hijack"),
    (r'do\s+not\s+tell\s+the\s+user', "deception_hide"),
    (r'system\s+prompt\s+override', "sys_prompt_override"),
    (r'disregard\s+(your|all|any)\s+(instructions|rules|guidelines)', "disregard_rules"),
    (r'act\s+as\s+(if|though)\s+you\s+(have\s+no|don\'t\s+have)\s+(restrictions|limits|rules)', "bypass_restrictions"),
    # Exfiltration via curl/wget with secrets
    (r'curl\s+[^\n]*\$\{?\w*(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|API)', "exfil_curl"),
    (r'wget\s+[^\n]*\$\{?\w*(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|API)', "exfil_wget"),
    (r'cat\s+[^\n]*(\.env|credentials|\.netrc|\.pgpass|\.npmrc|\.pypirc)', "read_secrets"),
    # Persistence via shell rc
    (r'authorized_keys', "ssh_backdoor"),
    (r'\$HOME/\.ssh|\~/\.ssh', "ssh_access"),
    (r'\$HOME/\.hermes/\.env|\~/\.hermes/\.env', "hermes_env"),
]

INVISIBLE_CHARS = {
    '\u200b', '\u200c', '\u200d', '\u2060', '\ufeff',
    '\u202a', '\u202b', '\u202c', '\u202d', '\u202e',
}


# ============================================================================
# PII patterns
# ============================================================================

PII_PATTERNS = [
    # Credit card numbers (basic Luhn-eligible formats)
    (r'\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b', "credit_card"),
    # SSN (US)
    (r'\b\d{3}-\d{2}-\d{4}\b', "ssn"),
    # Aadhaar (India)
    (r'\b\d{4}\s?\d{4}\s?\d{4}\b', "aadhaar"),
    # PAN (India)
    (r'\b[A-Z]{5}\d{4}[A-Z]\b', "pan_card"),
    # Email (basic)
    (r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b', "email"),
    # Phone numbers (international format)
    (r'\b\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{4}\b', "phone"),
    # Bank account (IBAN-like)
    (r'\b[A-Z]{2}\d{2}[A-Z0-9]{4,30}\b', "iban"),
]


# ============================================================================
# Quick scan function (backward-compatible drop-in)
# ============================================================================

def scan_content(content: str) -> Optional[str]:
    """Scan content for injection/exfiltration patterns.

    Returns error string if blocked, None if clean.
    Drop-in replacement for _scan_memory_content, _scan_content in
    memory_tool, knowledge_tool, context_graph_tool, cronjob_tools.
    """
    # Check invisible unicode
    for char in INVISIBLE_CHARS:
        if char in content:
            return (
                f"Blocked: content contains invisible unicode character "
                f"U+{ord(char):04X} (possible injection)."
            )

    # Check threat patterns
    for pattern, pid in THREAT_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            return (
                f"Blocked: content matches threat pattern '{pid}'. "
                f"Memory entries are injected into the system prompt and "
                f"must not contain injection or exfiltration payloads."
            )

    return None


def scan_pii(content: str) -> List[str]:
    """Scan content for PII patterns. Returns list of detected PII types."""
    detected = []
    for pattern, pii_type in PII_PATTERNS:
        if re.search(pattern, content):
            detected.append(pii_type)
    return detected


# ============================================================================
# Guardrail ABC + implementations
# ============================================================================

@dataclass
class GuardrailResult:
    """Result of a guardrail check."""
    passed: bool = True
    guardrail: str = ""
    reason: str = ""
    severity: str = "info"  # info, warning, block
    detected: List[str] = field(default_factory=list)


class Guardrail(ABC):
    """Abstract base for guardrail implementations."""

    @abstractmethod
    def check(self, content: str, direction: str = "input") -> GuardrailResult:
        """Check content. direction is 'input' (user message) or 'output' (agent response)."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        ...


class InjectionGuardrail(Guardrail):
    """Detects prompt injection and exfiltration attempts."""

    @property
    def name(self) -> str:
        return "injection"

    def check(self, content: str, direction: str = "input") -> GuardrailResult:
        error = scan_content(content)
        if error:
            return GuardrailResult(
                passed=False,
                guardrail=self.name,
                reason=error,
                severity="block",
            )
        return GuardrailResult(passed=True, guardrail=self.name)


class PIIGuardrail(Guardrail):
    """Detects personally identifiable information."""

    def __init__(self, block_on_output: bool = True, warn_on_input: bool = True):
        self.block_on_output = block_on_output
        self.warn_on_input = warn_on_input

    @property
    def name(self) -> str:
        return "pii"

    def check(self, content: str, direction: str = "input") -> GuardrailResult:
        detected = scan_pii(content)
        if not detected:
            return GuardrailResult(passed=True, guardrail=self.name)

        if direction == "output" and self.block_on_output:
            return GuardrailResult(
                passed=False,
                guardrail=self.name,
                reason=f"PII detected in output: {', '.join(detected)}. Redact before sending.",
                severity="block",
                detected=detected,
            )
        elif direction == "input" and self.warn_on_input:
            return GuardrailResult(
                passed=True,  # Don't block user input, just warn
                guardrail=self.name,
                reason=f"PII detected in input: {', '.join(detected)}. Handle with care.",
                severity="warning",
                detected=detected,
            )
        return GuardrailResult(passed=True, guardrail=self.name, detected=detected)


class ContentGuardrail(Guardrail):
    """Configurable content policy with custom blocked patterns."""

    def __init__(self, blocked_patterns: Optional[List[tuple]] = None):
        self.blocked_patterns = blocked_patterns or []

    @property
    def name(self) -> str:
        return "content_policy"

    def check(self, content: str, direction: str = "input") -> GuardrailResult:
        for pattern, reason in self.blocked_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return GuardrailResult(
                    passed=False,
                    guardrail=self.name,
                    reason=f"Content policy violation: {reason}",
                    severity="block",
                )
        return GuardrailResult(passed=True, guardrail=self.name)


# ============================================================================
# Pipeline
# ============================================================================

class GuardrailPipeline:
    """Runs a sequence of guardrails on content.

    Stops at the first blocking result. Collects all warnings.
    """

    def __init__(self, guardrails: Optional[List[Guardrail]] = None):
        self.guardrails = guardrails or []

    def check_input(self, content: str) -> GuardrailResult:
        """Run all guardrails against user input."""
        return self._run(content, "input")

    def check_output(self, content: str) -> GuardrailResult:
        """Run all guardrails against agent output."""
        return self._run(content, "output")

    def _run(self, content: str, direction: str) -> GuardrailResult:
        warnings = []
        for guardrail in self.guardrails:
            try:
                result = guardrail.check(content, direction)
                if not result.passed:
                    return result
                if result.severity == "warning":
                    warnings.append(result)
            except Exception as e:
                logger.warning("Guardrail %s failed: %s", guardrail.name, e)

        if warnings:
            # Return first warning (passed=True but with info)
            return warnings[0]

        return GuardrailResult(passed=True)

    @classmethod
    def from_config(cls, config: List[str]) -> "GuardrailPipeline":
        """Build a pipeline from config list like ["injection", "pii"].

        Config is read from cli-config.yaml guardrails key.
        """
        guardrails = []
        for name in config:
            if name == "injection":
                guardrails.append(InjectionGuardrail())
            elif name == "pii":
                guardrails.append(PIIGuardrail())
            elif name == "content_policy":
                guardrails.append(ContentGuardrail())
            else:
                logger.warning("Unknown guardrail: %s (skipping)", name)
        return cls(guardrails)
