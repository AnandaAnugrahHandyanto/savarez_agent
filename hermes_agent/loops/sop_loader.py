"""Load the canonical UCPM SOP and per-company context for the loop.

The SOP lives in `paperclip-UCPM/companies/ucpm-default/SOP.md`. Per-property
companies under `paperclip-UCPM/companies/<slug>/` may add an
`SOP.overrides.yml` and a `state.yml`. This loader keeps the access pattern
explicit and read-only — the loop never mutates company-dir contents.

The loaded SOP text is used as a prompt-cache breakpoint when calling
Anthropic, so loading once per loop invocation is the right granularity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml


@dataclass(frozen=True)
class SopBundle:
    """Everything the agent reads from disk before processing messages."""

    sop_text: str
    company_slug: str
    company_state: dict[str, Any] = field(default_factory=dict)
    overrides: dict[str, Any] = field(default_factory=dict)
    extra_context: dict[str, Any] = field(default_factory=dict)


def _read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _read_yaml(p: Path) -> dict[str, Any]:
    raw = p.read_text(encoding="utf-8")
    data = yaml.safe_load(raw) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping at top of {p}, got {type(data).__name__}")
    return data


def find_default_sop(company_dir: Path) -> Path:
    """Resolve the canonical SOP.md from a company-dir.

    Resolution order:
      1) `<company_dir>/SOP.md` if present
      2) `<company_dir>/../ucpm-default/SOP.md`
      3) `<company_dir>/../../companies/ucpm-default/SOP.md`

    Raises FileNotFoundError if none exist.
    """
    direct = company_dir / "SOP.md"
    if direct.is_file():
        return direct

    sibling = company_dir.parent / "ucpm-default" / "SOP.md"
    if sibling.is_file():
        return sibling

    upward = company_dir.parent.parent / "companies" / "ucpm-default" / "SOP.md"
    if upward.is_file():
        return upward

    raise FileNotFoundError(
        f"Could not locate canonical SOP.md from company-dir={company_dir}. "
        "Looked at: ./SOP.md, ../ucpm-default/SOP.md, "
        "../../companies/ucpm-default/SOP.md."
    )


def load_sop_bundle(company_dir: Path) -> SopBundle:
    """Load SOP + per-company state for a property.

    The loop tolerates a stub property folder (empty / scripts/ tenants/ only).
    Anything missing is treated as "use ucpm-default".
    """
    company_dir = company_dir.resolve()
    sop_path = find_default_sop(company_dir)
    sop_text = _read_text(sop_path)

    state: dict[str, Any] = {}
    state_path = company_dir / "state.yml"
    if state_path.is_file():
        state = _read_yaml(state_path)

    overrides: dict[str, Any] = {}
    overrides_path = company_dir / "SOP.overrides.yml"
    if overrides_path.is_file():
        overrides = _read_yaml(overrides_path)

    # Per-property tenants: any *.yml directly under tenants/ is a candidate
    # tenant record. We don't parse fields here — the LLM gets the raw
    # YAML as context. Empty dirs return an empty list.
    tenants: list[dict[str, Any]] = []
    tenants_dir = company_dir / "tenants"
    if tenants_dir.is_dir():
        for tenant_file in sorted(tenants_dir.glob("*.yml")):
            try:
                tenants.append(_read_yaml(tenant_file))
            except Exception:  # noqa: BLE001 — best-effort, never fail the loop
                continue

    extra_context = {
        "company_dir": str(company_dir),
        "sop_path": str(sop_path),
        "tenants": tenants,
    }

    return SopBundle(
        sop_text=sop_text,
        company_slug=company_dir.name,
        company_state=state,
        overrides=overrides,
        extra_context=extra_context,
    )


def render_company_context_block(bundle: SopBundle) -> str:
    """Stable string form of company-context for prompt caching.

    Order matters for cache stability — keep keys sorted and serialization
    deterministic so the same bundle produces byte-identical output across
    runs.
    """
    payload = {
        "company_slug": bundle.company_slug,
        "company_state": bundle.company_state,
        "overrides": bundle.overrides,
        "tenants": bundle.extra_context.get("tenants", []),
    }
    return yaml.safe_dump(payload, sort_keys=True, default_flow_style=False)


def load_message(path: Path) -> dict[str, Any]:
    """Load and minimally validate an `inbox/<id>.json` file."""
    import json

    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected JSON object, got {type(data).__name__}")
    for required in ("id", "from", "body"):
        if required not in data:
            raise ValueError(f"{path}: missing required field '{required}'")
    return data


def discover_inbox_messages(inbox_dir: Path) -> list[Path]:
    """Return JSON files in inbox/, sorted by name (stable ordering)."""
    if not inbox_dir.is_dir():
        return []
    return sorted(p for p in inbox_dir.glob("*.json") if p.is_file())
