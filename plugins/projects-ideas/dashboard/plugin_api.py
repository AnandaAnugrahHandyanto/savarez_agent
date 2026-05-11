"""Projects + Ideas dashboard plugin backend.

Mounted at /api/plugins/projects-ideas/ by the Hermes dashboard.
Builds a private, local-only portfolio snapshot from curated defaults, local
Hermes memory artifacts, and (when LINEAR_API_KEY is present) archived/canceled
Linear work. The response intentionally contains titles, statuses, next actions,
and links only; it never returns raw note bodies or secrets.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

try:
    from fastapi import APIRouter
except Exception:  # pragma: no cover - lets import smoke tests run w/o fastapi
    APIRouter = None  # type: ignore

try:
    from hermes_constants import get_hermes_home
except Exception:  # pragma: no cover
    def get_hermes_home() -> Path:  # type: ignore
        return Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes")

router = APIRouter() if APIRouter else None

LINEAR_URL = "https://linear.app/ryans-ai-hub/issue"
SNAPSHOT_VERSION = "0.1.0"


@dataclass
class Link:
    label: str
    url: str


@dataclass
class Card:
    id: str
    name: str
    kind: str
    status: str
    priority: str
    owner: str
    last_activity: str
    next_action: str
    summary: str
    links: List[Link] = field(default_factory=list)
    signals: List[str] = field(default_factory=list)
    lane: Optional[str] = None
    stage: Optional[str] = None
    evidence: Optional[str] = None
    potential_value: Optional[str] = None
    source: str = "curated"


CURATED_PROJECTS: List[Card] = [
    Card(
        id="life-church-hub", name="Life Church Hub", kind="project", status="active", priority="high",
        owner="Hermes + Ryan", last_activity="current priority", lane="Active",
        summary="Primary app workstream; Pulse parity and ChurchPulse data shape remain the main focus.",
        next_action="Keep active implementation work in Linear; use this card for cross-project scan and links.",
        links=[Link("Linear Development", "https://linear.app/ryans-ai-hub/team/RAN/all"), Link("Hub repo", "file://~/Desktop/Projects/life-church-hub")],
        signals=["top priority", "Pulse module parity", "private repo"],
    ),
    Card(
        id="churchpulse-cp2", name="ChurchPulse / CP2", kind="project", status="active", priority="high",
        owner="Hermes", last_activity="ongoing", lane="Active",
        summary="Ship and validate ChurchPulse before broader productization.",
        next_action="Track concrete build/validation tasks in Linear; keep market/ops notes as dashboard links rather than perpetual issues.",
        links=[Link("ChurchPulse context", "file://~/Desktop/Projects/churchpulse")],
        signals=["Phase 1", "shipping over tinkering"],
    ),
    Card(
        id="ai-revenue-lab", name="AI Revenue Lab / Aligned Insights", kind="project", status="active", priority="high",
        owner="Ryan + Hermes", last_activity="strategic direction", lane="Active",
        summary="Business-development lane for consulting-first revenue and validated offers.",
        next_action="Promote only validated implementation moves into Linear; keep scans and experiments here as lanes/cards.",
        links=[Link("Strategic direction", "file://~/.hermes/memory/strategic-direction-2026-04-07.md")],
        signals=["$10k–$12.5k/mo target", "consulting-first"],
    ),
    Card(
        id="mission-control", name="Mission Control / personal ops", kind="project", status="active", priority="medium",
        owner="Hermes", last_activity="local dashboard", lane="Active",
        summary="Ryan's personal ops dashboard and command-center experiments.",
        next_action="Use this Projects + Ideas tab as the portfolio layer; reserve Mission Control tasks for concrete app changes.",
        links=[Link("Mission Control", "file://~/Desktop/Projects/mission-control")],
        signals=["port 4200/4201", "personal ops"],
    ),
    Card(
        id="revenue-streams", name="Revenue streams / opportunity scans", kind="standing_lane", status="active", priority="high",
        owner="Scout + Hermes", last_activity="recurring scans", lane="Standing Lanes",
        summary="Recurring discovery and packaging of possible revenue opportunities.",
        next_action="Summarize outputs here and graduate only Ryan-approved opportunities into implementation issues.",
        links=[Link("Opportunity scans", "file://~/.hermes/memory/opportunity-scans")],
        signals=["cadence lane", "not fake In Progress"],
    ),
    Card(
        id="linear-agent-ops", name="Linear cleanup / agent ops", kind="standing_lane", status="active", priority="medium",
        owner="Hercules + Hermes", last_activity="every few hours", lane="Standing Lanes",
        summary="Operational hygiene for Linear, kanban dispatch, stale PRs, and agent work queues.",
        next_action="Keep as a health lane; create Linear issues only for concrete fixes or Ryan decisions.",
        links=[Link("Kanban dashboard", "/kanban"), Link("Linear", "https://linear.app/ryans-ai-hub/team/RAN/all")],
        signals=["standing workflow", "source of truth reconciliation"],
    ),
]

CURATED_IDEAS: List[Card] = [
    Card(
        id="father-son-welding", name="Father/son summer business", kind="idea", status="idea", priority="medium",
        owner="Ryan", last_activity="memory", lane="Ideas", stage="concept",
        summary="Explore an AI-assisted summer business with Ryan's 16-year-old son and his welding skills.",
        next_action="Capture 3 low-risk offer tests before creating any implementation issues.",
        evidence="Existing skill/assets: welding capability + Ryan's interest.", potential_value="Family project + potential side revenue.",
        signals=["needs validation", "do not over-task in Linear"],
    ),
]

STATUS_TO_SECTION = {
    "active": "Active",
    "waiting": "Waiting/Blocked",
    "blocked": "Waiting/Blocked",
    "paused": "Paused",
    "idea": "Ideas",
    "archived": "Archived / Parking Lot",
    "parking": "Archived / Parking Lot",
}


def _safe_read(path: Path, limit: int = 120_000) -> str:
    try:
        if not path.exists() or not path.is_file():
            return ""
        data = path.read_text(encoding="utf-8", errors="ignore")
        return data[:limit]
    except Exception:
        return ""


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:64] or "item"


def _first_sentence(text: str, max_len: int = 180) -> str:
    compact = re.sub(r"\s+", " ", text).strip(" -*#\t")
    if not compact:
        return ""
    sentence = re.split(r"(?<=[.!?])\s+", compact)[0]
    return sentence[:max_len].rstrip() + ("…" if len(sentence) > max_len else "")


def _extract_markdown_items(path: Path, *, kind: str, default_status: str, limit: int = 12, include_lists: bool = True) -> List[Card]:
    """Extract headings/list items without exposing raw note bodies."""
    text = _safe_read(path)
    if not text:
        return []
    cards: List[Card] = []
    seen: set[str] = set()
    lines = text.splitlines()
    for idx, raw in enumerate(lines):
        line = raw.strip()
        title = ""
        if line.startswith("##"):
            title = line.lstrip("#").strip()
        elif include_lists and re.match(r"^[-*]\s+\S", line):
            title = re.sub(r"^[-*]\s+", "", line).strip()
        elif include_lists and re.match(r"^\d+[.)]\s+\S", line):
            title = re.sub(r"^\d+[.)]\s+", "", line).strip()
        title = re.sub(r"\[[ xX]\]\s*", "", title).strip()
        title = re.sub(r"^\*\*(.*?)\*\*.*$", r"\1", title).strip()
        title = re.split(r"\s+[—-]\s+", title, maxsplit=1)[0].strip()
        title = re.sub(r"\*\*", "", title).strip()
        title = re.sub(r"\s+#\w+.*$", "", title).strip()
        if not title or len(title) < 4 or title.lower() in {"active right now", "ideas", "ideas backlog", "ideas (unresearched)", "ideas (research started)", "graduated to task queue", "backlog", "notes", "todo"}:
            continue
        key = _slug(title)
        if key in seen:
            continue
        seen.add(key)
        context = " ".join(lines[idx + 1: idx + 4])
        summary = _first_sentence(context) or "Curated from local Hermes notes; open source note for details."
        status = default_status
        lowered = (title + " " + context).lower()
        if any(w in lowered for w in ["park", "archive", "cancel"]):
            status = "parking"
        elif any(w in lowered for w in ["blocked", "waiting", "needs ryan"]):
            status = "waiting"
        elif any(w in lowered for w in ["paused", "someday"]):
            status = "paused"
        cards.append(Card(
            id=f"{kind}-{key}", name=title[:96], kind=kind, status=status,
            priority="medium" if kind == "idea" else "low", owner="Ryan + Hermes",
            last_activity="local notes", lane=STATUS_TO_SECTION.get(status, "Ideas"),
            summary=summary, next_action="Review and either keep parked, promote to an active card, or create one concrete Linear follow-up.",
            links=[Link(path.name, f"file://{path}")], source=str(path), stage="noted" if kind == "idea" else None,
            evidence="Mentioned in local Hermes memory artifacts." if kind == "idea" else None,
            potential_value="Unknown until Ryan validates." if kind == "idea" else None,
        ))
        if len(cards) >= limit:
            break
    return cards


def _local_note_cards() -> List[Card]:
    home = Path(get_hermes_home())
    profile_home = Path.home()
    user_name = os.environ.get("SUDO_USER") or os.environ.get("USER")
    user_home = Path("/Users") / user_name if user_name and Path("/Users", user_name).exists() else profile_home
    candidates = [
        (home / "memory" / "ideas-backlog.md", "idea", "idea", 14, True),
        (home / "memory" / "task-queue.md", "standing_lane", "active", 8, True),
        (home / "vault" / "working-context.md", "project", "active", 8, False),
        # Ryan's OpenClaw vault is the durable cross-agent note store for
        # business/projects/ideas context. Read titles and tiny summaries only;
        # do not leak raw note bodies into the dashboard API.
        (user_home / "Documents" / "OpenClaw-Vault" / "Agent-Shared" / "ideas-backlog.md", "idea", "idea", 14, True),
        (user_home / "Documents" / "OpenClaw-Vault" / "Agent-Shared" / "task-queue.md", "standing_lane", "active", 8, True),
        (user_home / "Documents" / "OpenClaw-Vault" / "Agent-Charles" / "working-context.md", "project", "active", 8, False),
    ]
    cards: List[Card] = []
    for path, kind, status, limit, include_lists in candidates:
        cards.extend(_extract_markdown_items(path, kind=kind, default_status=status, limit=limit, include_lists=include_lists))
    return cards


def _linear_archived_cards(limit: int = 12) -> List[Card]:
    """Fetch parked/canceled/archived Linear issues with tiny, title-only cards."""
    if not os.environ.get("LINEAR_API_KEY"):
        return []
    script = Path(__file__).resolve().parents[3] / "skills" / "productivity" / "linear" / "scripts" / "linear_api.py"
    if not script.exists():
        # Plugin lives under repo/plugins; skill lives outside repo in profiles on Ryan's machine.
        script = Path.home() / ".hermes" / "profiles" / "hermes-coder" / "skills" / "productivity" / "linear" / "scripts" / "linear_api.py"
    if not script.exists():
        return []
    query = """
query($first: Int!) {
  issues(first: $first, filter: {
    team: { key: { eq: \"RAN\" } },
    state: { type: { in: [\"canceled\"] } }
  }, orderBy: updatedAt) {
    nodes { identifier title url updatedAt state { name type } labels { nodes { name } } }
  }
}
"""
    try:
        proc = subprocess.run(
            ["python3", str(script), "raw", query, "--vars", json.dumps({"first": limit})],
            text=True, capture_output=True, timeout=12, check=False,
        )
        if proc.returncode != 0:
            return []
        payload = json.loads(proc.stdout)
        root = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        nodes = (((root.get("issues") if isinstance(root, dict) else {}) or {}).get("nodes") or [])
    except Exception:
        return []
    cards: List[Card] = []
    for issue in nodes[:limit]:
        ident = issue.get("identifier") or "Linear"
        title = issue.get("title") or ident
        state = (issue.get("state") or {}).get("name") or "Canceled"
        labels = [n.get("name", "") for n in ((issue.get("labels") or {}).get("nodes") or [])]
        cards.append(Card(
            id=f"linear-{ident.lower()}", name=title, kind="idea", status="parking", priority="low",
            owner="Linear", last_activity=(issue.get("updatedAt") or "")[:10], lane="Archived / Parking Lot",
            summary=f"Surfaced from Linear {state}; kept out of active task flow until Ryan reactivates it.",
            next_action="Leave parked unless Ryan explicitly promotes it back into active planning.",
            links=[Link(ident, issue.get("url") or f"{LINEAR_URL}/{ident.lower()}")],
            signals=[state] + [l for l in labels if l], source="Linear archived/canceled",
            stage="parked", evidence="Archived/canceled Linear work.", potential_value="Revisit only if strategic fit improves.",
        ))
    return cards


def _dedupe(cards: Iterable[Card]) -> List[Card]:
    out: List[Card] = []
    seen: set[str] = set()
    for card in cards:
        key = card.id or _slug(card.name)
        if key in seen:
            continue
        seen.add(key)
        if not card.lane:
            card.lane = STATUS_TO_SECTION.get(card.status, "Ideas")
        out.append(card)
    return out


def _section_counts(cards: List[Card]) -> Dict[str, int]:
    counts = {section: 0 for section in ["Active", "Waiting/Blocked", "Paused", "Ideas", "Archived / Parking Lot", "Standing Lanes"]}
    for card in cards:
        lane = card.lane or STATUS_TO_SECTION.get(card.status, "Ideas")
        counts[lane] = counts.get(lane, 0) + 1
    return counts


def build_snapshot(*, include_linear: bool = True) -> Dict[str, Any]:
    cards = _dedupe([*CURATED_PROJECTS, *CURATED_IDEAS, *_local_note_cards(), *(_linear_archived_cards() if include_linear else [])])
    cards.sort(key=lambda c: (
        ["high", "medium", "low"].index(c.priority) if c.priority in {"high", "medium", "low"} else 3,
        c.kind != "project",
        c.name.lower(),
    ))
    return {
        "version": SNAPSHOT_VERSION,
        "generated_at": int(time.time()),
        "title": "Ryan Projects + Ideas",
        "subtitle": "Portfolio scan for active projects, standing lanes, ideas, and parking-lot work — Linear stays reserved for actionable tasks.",
        "privacy_note": "Served inside the authenticated/local Hermes dashboard. Cards expose curated summaries and links, not raw private note bodies or secrets.",
        "refresh_path": "Refresh calls this plugin API, which re-reads curated defaults, local Hermes memory artifacts, and archived/canceled Linear items when LINEAR_API_KEY is available.",
        "sections": ["Active", "Waiting/Blocked", "Paused", "Ideas", "Archived / Parking Lot", "Standing Lanes"],
        "counts": _section_counts(cards),
        "cards": [
            {**asdict(c), "links": [asdict(l) for l in c.links]}
            for c in cards
        ],
    }


if router:
    @router.get("/snapshot")
    async def snapshot() -> Dict[str, Any]:
        return build_snapshot(include_linear=True)

    @router.post("/refresh")
    async def refresh() -> Dict[str, Any]:
        return build_snapshot(include_linear=True)
