"""Product-boundary guard for the standalone ContextOps/ESE core.

The ``contextops_ese`` core is harness-agnostic middleware: harnesses adapt to
it, never the reverse. Its package source must not carry product-specific
schema assumptions or product/harness names. This test scans the core package
``.py`` source text and fails closed if a forbidden boundary string appears.
"""

from __future__ import annotations

from pathlib import Path

_CORE_SRC = Path(__file__).resolve().parents[1] / "src" / "contextops_ese"

# Case-insensitive substrings that must never appear in core package source.
# ``hermes_dogfood`` is listed explicitly so a regression is reported with the
# precise schema/source label rather than only the generic ``hermes`` hit.
_FORBIDDEN_BOUNDARY_STRINGS = (
    "hermes_dogfood",
    "hermes",
    "gateway",
    "prompt_builder",
)


def _core_py_files() -> list[Path]:
    return sorted(_CORE_SRC.rglob("*.py"))


def test_core_package_has_python_source() -> None:
    """Sanity check: the scan below has something to scan."""

    assert _core_py_files(), f"no .py source found under {_CORE_SRC}"


def test_core_package_source_has_no_product_boundary_strings() -> None:
    """No Hermes/gateway product-boundary strings in core package source."""

    violations: list[str] = []
    for path in _core_py_files():
        text = path.read_text(encoding="utf-8")
        lowered = text.lower()
        for needle in _FORBIDDEN_BOUNDARY_STRINGS:
            if needle in lowered:
                rel = path.relative_to(_CORE_SRC.parents[1])
                violations.append(f"{rel}: forbidden boundary string {needle!r}")

    assert not violations, "core package leaks product-boundary strings:\n" + "\n".join(
        sorted(set(violations))
    )


def test_core_schema_version_is_neutral() -> None:
    """The core schema label must not encode a product/harness name."""

    from contextops_ese import SCHEMA_VERSION

    assert SCHEMA_VERSION == "contextops.contract.v0"
    lowered = SCHEMA_VERSION.lower()
    for needle in _FORBIDDEN_BOUNDARY_STRINGS:
        assert needle not in lowered, f"SCHEMA_VERSION leaks {needle!r}"


def test_runtime_event_source_default_is_neutral() -> None:
    """RuntimeEvent.source must not default to a product/harness label."""

    from contextops_ese import RuntimeEvent

    event = RuntimeEvent(event_ref="ref:abc", event_type="runtime_event")
    lowered = event.source.lower()
    for needle in _FORBIDDEN_BOUNDARY_STRINGS:
        assert needle not in lowered, f"RuntimeEvent.source leaks {needle!r}"


def test_exported_contract_defaults_have_no_harness_assumptions() -> None:
    """No exported core DTO default value may carry a harness/product name.

    This serializes every core contract DTO built with default-only field
    values and fails closed if a forbidden boundary string appears anywhere in
    the resulting payload (keys or values), or in ``SCHEMA_VERSION`` itself.
    """

    import json

    from contextops_ese import (
        SCHEMA_VERSION,
        ContextPack,
        EvidenceBundle,
        Finding,
        MessageSummary,
        Observation,
        PreviewConfig,
        Recommendation,
        RuntimeEvent,
        SafetyDecision,
        TaskHandoffAckObservation,
    )

    ref = "ref:abc"
    defaults = [
        Observation(raw_id="raw-1", signal="safe signal").to_dict(),
        ContextPack(id="pack", restore=(), avoid=(), refs=()).to_dict(),
        PreviewConfig().to_dict(),
        RuntimeEvent(event_ref=ref, event_type="runtime_event").to_dict(),
        MessageSummary(message_ref=ref, session_ref=ref).to_dict(),
        TaskHandoffAckObservation(task_ref=ref).to_dict(),
        SafetyDecision().to_dict(),
        EvidenceBundle(evidence_refs=(ref,), summary="safe summary").to_dict(),
        Recommendation(
            routing_category="contextops_backlog",
            suggested_operator_action="operator owns any action",
        ).to_dict(),
        Finding(
            finding_ref=ref,
            kind="missing_origin_ack",
            title="safe title",
            confidence=0.5,
            evidence=EvidenceBundle(evidence_refs=(ref,), summary="safe summary"),
            recommendation=Recommendation(
                routing_category="contextops_backlog",
                suggested_operator_action="operator owns any action",
            ),
        ).to_dict(),
    ]

    haystack = (json.dumps(defaults) + " " + SCHEMA_VERSION).lower()
    for needle in _FORBIDDEN_BOUNDARY_STRINGS:
        assert needle not in haystack, f"exported core contract default leaks {needle!r}"
