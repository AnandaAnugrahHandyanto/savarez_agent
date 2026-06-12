"""Safe local workpack helpers for broad /goal planning.

The helper creates only the standard skeleton under ``$HERMES_HOME/workpacks``
and is idempotent: existing ROADMAP/STATE files are preserved.
"""

from __future__ import annotations

import re
from pathlib import Path

from hermes_constants import get_hermes_home

_MAX_SLUG_LEN = 64


def safe_slug(text: str, *, max_len: int = _MAX_SLUG_LEN) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    if not cleaned:
        return "goal"
    return cleaned[:max_len].strip("-") or "goal"


def _default_roadmap(goal: str) -> str:
    return f"""# {goal}

## Goal
{goal}

## Non-goals / safety gates
- No secrets, credentials, destructive actions, live trading/order/payment/public-posting, or profile-crossing writes unless explicitly approved.

## Phases
1. Intake/scope
2. Implementation/research slice
3. Verification
4. Final audit / handoff

## Acceptance criteria
- [ ] Direct evidence/readback exists.
- [ ] Adjacent/global visible-state trust sweep is clean or classified.
- [ ] Durable knowledge decision is recorded when relevant.
"""


def _default_state(goal: str) -> str:
    return f"""# State

Status: planned

## Current phase
Intake/scope

## Goal
{goal}

## Decisions needed from user
- none

## Evidence
- pending

## Next action
Define first implementation slice and verification gate.
"""


def create_or_update_workpack(
    slug: str,
    goal: str,
    *,
    hermes_home: str | Path | None = None,
) -> Path:
    """Create a workpack skeleton under ``hermes_home/workpacks`` safely."""

    home = Path(hermes_home) if hermes_home is not None else get_hermes_home()
    root = (home / "workpacks").resolve()
    workpack = (root / safe_slug(slug)).resolve()
    try:
        workpack.relative_to(root)
    except ValueError as exc:
        raise ValueError("workpack path escaped Hermes workpacks root") from exc

    workpack.mkdir(parents=True, exist_ok=True)
    for dirname in ("phases", "evidence", "handoff"):
        (workpack / dirname).mkdir(exist_ok=True)

    roadmap = workpack / "ROADMAP.md"
    if not roadmap.exists():
        roadmap.write_text(_default_roadmap(goal), encoding="utf-8")

    state = workpack / "STATE.md"
    if not state.exists():
        state.write_text(_default_state(goal), encoding="utf-8")

    return workpack
