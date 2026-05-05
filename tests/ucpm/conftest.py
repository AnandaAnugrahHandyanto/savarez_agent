"""Test fixtures for the UCPM file-based property loop.

Provides:
  - `fake_llm`         — drop-in `LlmClient` replacement that returns
                         pre-recorded JSON responses keyed by call type.
  - `tiny_sop_text`    — a minimal SOP excerpt sufficient for tests.
  - `company_dir`      — a tmp company directory with the tiny SOP at
                         `companies/ucpm-default/SOP.md`.
  - `example_message_paths` — pre-built inbox containing the three
                         example messages from `examples/test-emails/`.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Optional

import pytest

from hermes_agent.loops.llm_client import LlmClient


REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_DIR = REPO_ROOT / "hermes_agent" / "loops" / "sample_emails"


# ---------------------------------------------------------------------------
# Fake LLM
# ---------------------------------------------------------------------------


class _FakeMessages:
    def __init__(self, scripted: dict[str, list[dict[str, Any]]]):
        self._scripted = scripted
        self._cursor = {k: 0 for k in scripted}
        self.calls: list[dict[str, Any]] = []

    def create(self, *, model, max_tokens, system, messages):  # noqa: D401, ANN001
        instruction = ""
        for block in system:
            if not block.get("cache_control"):
                instruction = block["text"]
                break
        kind = _classify_call(instruction)
        responses = self._scripted.get(kind) or self._scripted.get("default") or []
        if not responses:
            raise AssertionError(
                f"FakeAnthropic has no scripted response for kind={kind!r}; "
                f"add one in the test."
            )
        idx = min(self._cursor[kind], len(responses) - 1)
        self._cursor[kind] += 1
        scripted = responses[idx]
        self.calls.append(
            {
                "kind": kind,
                "model": model,
                "max_tokens": max_tokens,
                "user_payload": messages[0]["content"] if messages else "",
            }
        )
        return _FakeResponse(text=json.dumps(scripted))


class _FakeAnthropic:
    def __init__(self, scripted: dict[str, list[dict[str, Any]]]):
        self.messages = _FakeMessages(scripted)


class _FakeResponse:
    def __init__(self, text: str):
        self.content = [_FakeBlock(text)]
        self.usage = {"input_tokens": 10, "output_tokens": 5}


class _FakeBlock:
    def __init__(self, text: str):
        self.text = text


def _classify_call(instruction: str) -> str:
    """Disambiguate call sites by signature phrases in their instruction text.

    Order matters — the drafter instruction also mentions P-01/P-02 (because
    it consumes their output), so we match on the most specific signature
    first. Whitespace is collapsed before matching so multi-line prompt
    headings (`Draft an outbound email\\nreply`) still hit.
    """
    flat = " ".join(instruction.split())
    if "Draft an outbound email reply" in flat:
        return "draft"
    if "Inbound tenant comm intake" in flat:
        return "classify"
    if "Maintenance request triage" in flat:
        return "triage"
    return "default"


def make_fake_llm(scripted: dict[str, list[dict[str, Any]]]) -> LlmClient:
    """Build an `LlmClient` whose underlying SDK is a deterministic fake."""
    fake = _FakeAnthropic(scripted)
    return LlmClient(client=fake, model="claude-sonnet-4-6-fake")


# ---------------------------------------------------------------------------
# Default scripted responses keyed to the three example messages.
# ---------------------------------------------------------------------------


def default_scripts_for_examples() -> dict[str, list[dict[str, Any]]]:
    """Match the three fixture emails by order of inbox traversal.

    Inbox is sorted by filename:
        emergency-water.json  (msg-003)
        maintenance-hvac.json (msg-001)
        rent-question.json    (msg-002)

    Each call list maps 1:1 to that order. The drafter is invoked once per
    message regardless of intent.
    """
    return {
        "classify": [
            # emergency-water.json -> maintenance
            {
                "intent": "maintenance",
                "tenant_slug": "beautiful-minds-a-101",
                "confidence": 0.99,
                "rationale": "Active flood / water leak — clear maintenance keyword set.",
            },
            # maintenance-hvac.json -> maintenance
            {
                "intent": "maintenance",
                "tenant_slug": "beautiful-minds-a-101",
                "confidence": 0.95,
                "rationale": "AC not cooling — mentions broken/won't cool.",
            },
            # rent-question.json -> payment
            {
                "intent": "payment",
                "tenant_slug": "beautiful-minds-a-101",
                "confidence": 0.92,
                "rationale": "Asks for current statement and balance due.",
            },
        ],
        "triage": [
            # emergency-water.json
            {
                "urgency": "emergency",
                "category": "plumbing",
                "rationale": "Active water flow / flood — emergency tier per SOP.",
                "payer_default": "landlord",
                "estimated_cost_band": "501-2000",
            },
            # maintenance-hvac.json
            {
                "urgency": "high",
                "category": "hvac",
                "rationale": "AC down during business hours — habitability impact.",
                "payer_default": "landlord",
                "estimated_cost_band": "<=500",
            },
            # rent-question.json — never reaches triage (intent=payment),
            # but include a stub in case ordering shifts during refactors.
            {
                "urgency": "normal",
                "category": "other",
                "rationale": "n/a — should not be invoked for payment intent.",
                "payer_default": "ambiguous",
                "estimated_cost_band": "unknown",
            },
        ],
        "draft": [
            # emergency-water.json
            {
                "subject": "Re: URGENT - water flooding from ceiling in suite A-101",
                "body": "We've received your report and are dispatching an emergency plumber now. WO-XXXX. Expect contact within the hour.",
                "template_id": "ack_maintenance",
                "queued_for_approval": False,
                "vendor_summary": "EMERGENCY plumbing — active flood through ceiling, A-101 lobby. Mitigate first.",
            },
            # maintenance-hvac.json
            {
                "subject": "Re: AC not cooling in suite A-101",
                "body": "Thanks for letting us know. We've opened WO-YYYY and will dispatch an HVAC tech today; expect a scheduling note within 4 hours.",
                "template_id": "ack_maintenance",
                "queued_for_approval": False,
                "vendor_summary": "HIGH hvac — AC blowing warm air, suite A-101 medical office, business hours.",
            },
            # rent-question.json
            {
                "subject": "Re: Question about May rent balance",
                "body": "Thanks — I'll pull a current statement and send it over shortly. Queued for our property accountant.",
                "template_id": "ack_payment_question",
                "queued_for_approval": True,
                "vendor_summary": "",
            },
        ],
    }


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_llm() -> LlmClient:
    return make_fake_llm(default_scripts_for_examples())


@pytest.fixture
def tiny_sop_text() -> str:
    return (
        "# UCPM SOP (test fixture)\n"
        "## P-01 — classify intent into one of: maintenance, payment, ...\n"
        "## P-02 — triage maintenance urgency: emergency, high, normal, scheduled.\n"
    )


@pytest.fixture
def company_dir(tmp_path: Path, tiny_sop_text: str) -> Path:
    # Mimic the canonical layout: <root>/companies/ucpm-default/SOP.md and a
    # per-property dir at <root>/companies/<slug>/.
    companies = tmp_path / "companies"
    default = companies / "ucpm-default"
    default.mkdir(parents=True)
    (default / "SOP.md").write_text(tiny_sop_text, encoding="utf-8")

    prop = companies / "1011-verrado-office"
    prop.mkdir()
    (prop / "state.yml").write_text("property_id: 1011-verrado\n", encoding="utf-8")
    return prop


@pytest.fixture
def inbox_dir(tmp_path: Path) -> Path:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    for src in EXAMPLES_DIR.glob("*.json"):
        shutil.copy(src, inbox / src.name)
    return inbox


@pytest.fixture
def outbox_dir(tmp_path: Path) -> Path:
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    return outbox


@pytest.fixture
def audit_dir(tmp_path: Path) -> Path:
    audit = tmp_path / "audit-log"
    audit.mkdir()
    return audit


@pytest.fixture
def example_message_paths() -> dict[str, Path]:
    return {p.stem: p for p in EXAMPLES_DIR.glob("*.json")}
