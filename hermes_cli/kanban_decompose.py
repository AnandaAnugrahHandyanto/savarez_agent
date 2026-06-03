"""Kanban decomposer — fan a triage task out into a graph of child tasks.

Invoked by ``hermes kanban decompose [task_id | --all]`` and the
auto-decompose path in the gateway dispatcher loop. Reads the user's
profile roster (with descriptions) and asks the auxiliary LLM to
return a task graph in JSON. Then atomically creates the children,
links them under the root, and flips the root ``triage -> todo``.

The root task stays alive and becomes the parent of every leaf child,
so when the whole graph completes the root wakes back up — its
assignee (the orchestrator profile) gets a chance to judge completion
and add more tasks if the work isn't done yet.

Design notes
------------

* Mirrors the shape of ``hermes_cli/kanban_specify.py``: lazy aux
  client import inside the function, lenient response parse, never
  raises on expected failure modes.

* The system prompt sees the *configured* profile roster — names plus
  descriptions plus the default fallback. Profiles without a
  description are still listed (with a note) so the orchestrator can
  match on name as a fallback, but the user has an obvious incentive
  to describe them.

* ``fanout=false`` collapses to the same effect as ``kanban specify``:
  we tighten the body and flip ``triage -> todo`` as a single task,
  no children created. This makes ``decompose`` a strict superset of
  ``specify`` from the user's perspective.

* If the LLM picks an assignee that doesn't exist as a profile, we
  rewrite it to the configured ``default_assignee`` (or the default
  profile if unset). A child task NEVER ends up with ``assignee=None``.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from hermes_cli import kanban_db as kb
from hermes_cli import profile_contract as contract_mod
from hermes_cli import profiles as profiles_mod

logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = """You are the Kanban decomposer for the Hermes Agent board.

A user dropped a rough idea into the Triage column. Your job is to break it
into a small graph of concrete child tasks and route each one to the best-
matching profile from the available roster.

You will be given:
  - The original task title and body
  - The list of available profiles (each with name + description)
  - The fallback "default_assignee" used when no profile fits

Output a single JSON object with this exact shape:

  {
    "fanout": true,
    "rationale": "<one sentence on why this decomposition>",
    "tasks": [
      {
        "title": "<concrete task title, imperative voice, <= 80 chars>",
        "body":  "<detailed spec for the worker on this child task>",
        "assignee": "<profile name from the roster, or null for default>",
        "parents": [<int>, ...]
      },
      ...
    ]
  }

Rules:
  - "parents" is a list of INDICES (0-based) into this same "tasks" list,
    expressing actual data dependencies. Tasks with no parents run in
    PARALLEL. Tasks with parents wait until every parent completes.
  - Prefer parallelism. If two tasks can be done independently, give
    them no parents so the dispatcher fans them out at once.
  - Use 2-6 tasks for normal work. Don't create 20 tiny tasks. Don't
    cram everything into 1 task.
  - Pick assignees from the roster by matching the task to the profile's
    DESCRIPTION (not just the name). When nothing matches well, use null
    and the system will route to the default_assignee.
  - Each child task body is what a fresh worker will read with no other
    context — be specific about goal, approach, and acceptance criteria.

When the task is genuinely a single unit of work (no useful decomposition),
return:

  {
    "fanout": false,
    "rationale": "<one sentence>",
    "title": "<tightened title>",
    "body":  "<concrete spec for a single worker>",
    "assignee": "<profile name from the roster, or null for default>"
  }

In that case the task stays as one work item, just with a tightened spec and
a concrete assignee. If no profile fits, use null and the system will route to
the default_assignee.

No preamble, no closing remarks, no code fences. Output only the JSON object.
"""


_USER_TEMPLATE = """Task id: {task_id}
Title: {title}
Body:
{body}

Available profiles (assignees you may pick from):
{roster}

Default assignee (used when no profile fits a task): {default_assignee}
"""


_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


@dataclass
class DecomposeOutcome:
    """Result of decomposing a single triage task."""

    task_id: str
    ok: bool
    reason: str = ""
    fanout: bool = False
    child_ids: list[str] | None = None
    new_title: Optional[str] = None


@dataclass
class ProfileRoutePolicy:
    """Roster entry plus contract-derived execution/safety policy."""

    name: str
    description: str
    has_description: bool
    contract: dict | None = None
    contract_ready: bool = False
    executable: bool = True
    non_executable_reason: str = ""


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _extract_json_blob(raw: str) -> Optional[dict]:
    if not raw:
        return None
    stripped = _FENCE_RE.sub("", raw.strip())
    first = stripped.find("{")
    last = stripped.rfind("}")
    if first == -1 or last == -1 or last <= first:
        return None
    candidate = stripped[first : last + 1]
    try:
        val = json.loads(candidate)
    except (ValueError, json.JSONDecodeError):
        return None
    if not isinstance(val, dict):
        return None
    return val


def _profile_author() -> str:
    """Mirror of ``hermes_cli.kanban._profile_author``."""
    return (
        os.environ.get("HERMES_PROFILE")
        or os.environ.get("USER")
        or "decomposer"
    )


def _load_config() -> dict:
    try:
        from hermes_cli.config import load_config
        return load_config() or {}
    except Exception:
        return {}


def _resolve_orchestrator_profile(cfg: dict) -> str:
    """Resolve which profile owns decomposition.

    Falls back to the active default profile when ``kanban.orchestrator_profile``
    is unset, so a task is never stranded for lack of an orchestrator.
    """
    kanban_cfg = cfg.get("kanban", {}) if isinstance(cfg, dict) else {}
    explicit = (kanban_cfg.get("orchestrator_profile") or "").strip()
    if explicit:
        try:
            if profiles_mod.profile_exists(explicit):
                return explicit
        except Exception:
            pass
    # Fall back to the active default profile.
    try:
        return profiles_mod.get_active_profile_name() or "default"
    except Exception:
        return "default"


def _resolve_default_assignee(cfg: dict) -> str:
    """Resolve which profile catches child tasks the orchestrator can't route."""
    kanban_cfg = cfg.get("kanban", {}) if isinstance(cfg, dict) else {}
    explicit = (kanban_cfg.get("default_assignee") or "").strip()
    if explicit:
        try:
            if profiles_mod.profile_exists(explicit):
                return explicit
        except Exception:
            pass
    try:
        return profiles_mod.get_active_profile_name() or "default"
    except Exception:
        return "default"


def _profile_contract_dir(name: str) -> Path:
    return contract_mod.profile_dir_for(name)


def _load_profile_policy(name: str, description: str, has_description: bool) -> ProfileRoutePolicy:
    profile_dir = _profile_contract_dir(name)
    contract_path = profile_dir / contract_mod.CONTRACT_FILENAME
    contract = contract_mod.read_contract(profile_dir)
    if contract is None:
        if contract_path.exists():
            return ProfileRoutePolicy(
                name,
                description,
                has_description,
                contract=None,
                contract_ready=False,
                executable=False,
                non_executable_reason=f"contract.yaml present but unreadable at {contract_path}",
            )
        # Legacy/non-specialist profiles remain executable if the profile exists.
        return ProfileRoutePolicy(name, description, has_description)

    errors = contract_mod.validate_contract(contract, name)
    if errors:
        return ProfileRoutePolicy(
            name,
            description,
            has_description,
            contract=contract,
            contract_ready=False,
            executable=False,
            non_executable_reason="invalid contract.yaml: " + "; ".join(errors),
        )

    dims = contract_mod.assess_autonomy_dimensions(profile_dir)
    child_supervision = (dims.get("child_supervision_ready") or {}).get("status")
    if child_supervision != contract_mod.DIM_YES:
        reasons = (dims.get("child_supervision_ready") or {}).get("reasons") or []
        return ProfileRoutePolicy(
            name,
            description,
            has_description,
            contract=contract,
            contract_ready=True,
            executable=False,
            non_executable_reason=(
                "contract present but child supervision lane is not executable"
                + (": " + "; ".join(reasons) if reasons else "")
            ),
        )

    return ProfileRoutePolicy(
        name,
        description,
        has_description,
        contract=contract,
        contract_ready=True,
        executable=True,
    )


def _build_roster() -> tuple[list[dict], set[str], dict[str, ProfileRoutePolicy]]:
    """Return (roster_for_prompt, executable_assignee_names, policies_by_name).

    Contract-backed specialists are listed with their machine-readable
    domain/lane/safety policy, but only profiles with an executable child lane
    are allowed as assignees. This prevents a wrapper-only/profile-contract-only
    directory from becoming a live dispatch lane.
    """
    roster: list[dict] = []
    valid: set[str] = set()
    policies: dict[str, ProfileRoutePolicy] = {}
    try:
        all_profiles = profiles_mod.list_profiles()
    except Exception as exc:
        logger.warning("decompose: failed to list profiles: %s", exc)
        return roster, valid, policies
    for p in all_profiles:
        desc = (p.description or "").strip()
        policy = _load_profile_policy(
            p.name,
            desc or f"(no description; profile named {p.name!r})",
            bool(desc),
        )
        policies[p.name] = policy
        entry = {
            "name": policy.name,
            "description": policy.description,
            "has_description": policy.has_description,
            "executable": policy.executable,
        }
        if policy.contract:
            entry.update({
                "contract_ready": policy.contract_ready,
                "division": policy.contract.get("division"),
                "reports_to": policy.contract.get("reports_to"),
                "domain": policy.contract.get("domain") or [],
                "child_lane_policy": policy.contract.get("child_lane_policy") or {},
                "approval_gate_categories": policy.contract.get("approval_gate_categories") or [],
                "forbidden_autonomy": policy.contract.get("forbidden_autonomy") or [],
                "evidence_requirements": policy.contract.get("evidence_requirements") or [],
            })
        if not policy.executable:
            entry["non_executable_reason"] = policy.non_executable_reason
        roster.append(entry)
        if policy.executable:
            valid.add(p.name)
    return roster, valid, policies


def _format_roster(roster: list[dict]) -> str:
    if not roster:
        return "  (no profiles installed — decomposer cannot route work)"
    lines = []
    for entry in roster:
        tag_bits = []
        if not entry["has_description"]:
            tag_bits.append("undescribed")
        if not entry.get("executable", True):
            tag_bits.append("not-executable")
        tag = "" if not tag_bits else " ⚠ " + ", ".join(tag_bits)
        lines.append(f"  - {entry['name']}{tag}: {entry['description']}")
        if entry.get("contract_ready"):
            lines.append(f"      contract.yaml domain: {entry.get('domain')}")
            lines.append(f"      reports_to: {entry.get('reports_to')}  division: {entry.get('division')}")
            lines.append(f"      child_lane_policy: {entry.get('child_lane_policy')}")
            lines.append(f"      approval_gate_categories: {entry.get('approval_gate_categories')}")
            lines.append(f"      forbidden_autonomy: {entry.get('forbidden_autonomy')}")
            lines.append(f"      evidence_requirements: {entry.get('evidence_requirements')}")
        if entry.get("non_executable_reason"):
            lines.append(f"      DO NOT ASSIGN: {entry['non_executable_reason']}")
    return "\n".join(lines)


def _normalize_assignee_choice(
    assignee: object,
    *,
    default_assignee: str,
    valid_names: set[str],
) -> str:
    """Return a valid executable assignee, falling back to ``default_assignee``.

    Fan-out children and the single-task fallback should share the same
    routing guarantee: promoted work must not be left unassigned or routed to a
    profile whose contract exists but whose execution lane is not wired.
    """
    if not isinstance(assignee, str) or not assignee.strip():
        return default_assignee
    chosen = assignee.strip()
    if chosen not in valid_names:
        return default_assignee
    return chosen


def _sanitize_default_assignee(
    default_assignee: str,
    *,
    orchestrator: str,
    valid_names: set[str],
) -> str:
    """Ensure fallback routing never points at a non-executable profile.

    ``_resolve_default_assignee`` can only check whether a profile exists. The
    contract-aware roster later decides whether that profile is safe to execute.
    If the configured fallback is wrapper-only/non-executable, use the
    orchestrator when executable, otherwise any executable profile, and finally
    keep the original value only as a last resort for legacy empty rosters.
    """
    if default_assignee in valid_names:
        return default_assignee
    if orchestrator in valid_names:
        return orchestrator
    if valid_names:
        return sorted(valid_names)[0]
    return default_assignee


_APPROVAL_GATE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("credentials", r"\b(credential|credentials|secret|token|api[-_ ]?key|password|login)\b"),
    ("public_send", r"\b(public|client[- ]?facing|external|official)\b.*\b(send|message|email|publish|post|disclos)"),
    ("paid_api", r"\b(paid|cost|billable|subscription|purchase|real money|spend)\b|\bpaid[-_ ]?api\b"),
    ("finance_trading", r"\b(payment|pay|trade|trading|portfolio|investment|invoice|bank|tax|finance)\b"),
    ("live_deploy", r"\b(live|production|prod|deploy|merge|push)\b"),
    ("notion_write", r"\bnotion\b.*\b(write|update|close|closure|mark done|edit)\b|\b(write|update|close|closure)\b.*\bnotion\b"),
    ("destructive", r"\b(delete|destroy|drop|wipe|purge|irreversible|rotate|revoke|disable)\b"),
)


def _detect_approval_gate(title: str, body: str, policy: ProfileRoutePolicy | None) -> list[str]:
    """Return obvious approval-gate labels detected from child text.

    This is deliberately conservative and deterministic. It does not replace
    specialist judgment; it parks children that clearly cross standing Filip/
    EMA gates before they become executable dispatcher work.
    """
    text = f"{title}\n{body}".casefold()
    hits: list[str] = []
    for label, pattern in _APPROVAL_GATE_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            hits.append(label)

    if policy and policy.contract:
        for category in policy.contract.get("approval_gate_categories") or []:
            words = [w for w in re.split(r"[^a-z0-9]+", str(category).casefold()) if len(w) >= 4]
            if words and any(w in text for w in words):
                hits.append(f"contract:{category}")
        for forbidden in policy.contract.get("forbidden_autonomy") or []:
            words = [w for w in re.split(r"[^a-z0-9]+", str(forbidden).casefold()) if len(w) >= 4]
            if words and any(w in text for w in words):
                hits.append(f"forbidden:{forbidden}")

    # Preserve order while deduping.
    deduped: list[str] = []
    seen: set[str] = set()
    for hit in hits:
        if hit not in seen:
            seen.add(hit)
            deduped.append(hit)
    return deduped


def decompose_task(
    task_id: str,
    *,
    author: Optional[str] = None,
    timeout: Optional[int] = None,
) -> DecomposeOutcome:
    """Decompose a triage task into a graph of child tasks.

    Returns an outcome describing what happened. Never raises for
    expected failure modes (task not in triage, no aux client
    configured, API error, malformed response, decomposer returned
    fanout=true with empty task list) — those surface via ``ok=False``.
    """
    with kb.connect_closing() as conn:
        task = kb.get_task(conn, task_id)
    if task is None:
        return DecomposeOutcome(task_id, False, "unknown task id")
    if task.status != "triage":
        return DecomposeOutcome(
            task_id, False, f"task is not in triage (status={task.status!r})"
        )

    cfg = _load_config()
    orchestrator = _resolve_orchestrator_profile(cfg)
    default_assignee = _resolve_default_assignee(cfg)
    kanban_cfg = cfg.get("kanban", {}) if isinstance(cfg, dict) else {}
    auto_promote = bool(kanban_cfg.get("auto_promote_children", True))
    roster, valid_names, policies = _build_roster()
    default_assignee = _sanitize_default_assignee(
        default_assignee,
        orchestrator=orchestrator,
        valid_names=valid_names,
    )

    try:
        from agent.auxiliary_client import (  # type: ignore
            get_auxiliary_extra_body,
            get_text_auxiliary_client,
        )
    except Exception as exc:
        logger.debug("decompose: auxiliary client import failed: %s", exc)
        return DecomposeOutcome(task_id, False, "auxiliary client unavailable")

    try:
        client, model = get_text_auxiliary_client("kanban_decomposer")
    except Exception as exc:
        logger.debug("decompose: get_text_auxiliary_client failed: %s", exc)
        return DecomposeOutcome(task_id, False, "auxiliary client unavailable")

    if client is None or not model:
        return DecomposeOutcome(task_id, False, "no auxiliary client configured")

    user_msg = _USER_TEMPLATE.format(
        task_id=task.id,
        title=_truncate(task.title or "", 400),
        body=_truncate(task.body or "(no body)", 4000),
        roster=_format_roster(roster),
        default_assignee=default_assignee,
    )

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.3,
            max_tokens=4000,
            timeout=timeout or 180,
            extra_body=get_auxiliary_extra_body() or None,
        )
    except Exception as exc:
        logger.info(
            "decompose: API call failed for %s (%s)", task_id, exc,
        )
        return DecomposeOutcome(task_id, False, f"LLM error: {type(exc).__name__}")

    try:
        raw = resp.choices[0].message.content or ""
    except Exception:
        raw = ""

    parsed = _extract_json_blob(raw)
    if parsed is None:
        return DecomposeOutcome(task_id, False, "LLM returned malformed JSON")

    fanout = bool(parsed.get("fanout"))
    audit_author = author or _profile_author()

    if not fanout:
        # Fall back to single-task spec promotion (same effect as specify).
        new_title = parsed.get("title")
        new_body = parsed.get("body")
        title_val = new_title.strip() if isinstance(new_title, str) and new_title.strip() else None
        body_val = new_body if isinstance(new_body, str) and new_body.strip() else None
        assignee_val = None
        if not task.assignee:
            assignee_val = _normalize_assignee_choice(
                parsed.get("assignee"),
                default_assignee=default_assignee,
                valid_names=valid_names,
            )
        if title_val is None and body_val is None:
            return DecomposeOutcome(
                task_id, False, "decomposer returned fanout=false with no title/body",
            )
        with kb.connect_closing() as conn:
            ok = kb.specify_triage_task(
                conn,
                task_id,
                title=title_val,
                body=body_val,
                assignee=assignee_val,
                author=audit_author,
            )
        if not ok:
            return DecomposeOutcome(
                task_id, False, "task moved out of triage before promotion",
            )
        return DecomposeOutcome(
            task_id, True, "single task (no fanout)",
            fanout=False, new_title=title_val,
        )

    raw_tasks = parsed.get("tasks") or []
    if not isinstance(raw_tasks, list) or not raw_tasks:
        return DecomposeOutcome(
            task_id, False, "decomposer returned fanout=true with empty tasks list",
        )

    # Rewrite invalid assignees to the default fallback. Never leave a
    # task with assignee=None — the user explicitly does not want that.
    children: list[dict] = []
    for idx, entry in enumerate(raw_tasks):
        if not isinstance(entry, dict):
            return DecomposeOutcome(
                task_id, False, f"tasks[{idx}] is not an object",
            )
        title = entry.get("title")
        if not isinstance(title, str) or not title.strip():
            return DecomposeOutcome(
                task_id, False, f"tasks[{idx}].title is missing or empty",
            )
        body = entry.get("body")
        if not isinstance(body, str):
            body = ""
        assignee = entry.get("assignee")
        requested = assignee.strip() if isinstance(assignee, str) else ""
        chosen = _normalize_assignee_choice(
            assignee,
            default_assignee=default_assignee,
            valid_names=valid_names,
        )
        if requested and requested not in valid_names:
            policy = policies.get(requested)
            if policy and not policy.executable:
                logger.info(
                    "decompose: task %s child %d picked non-executable assignee %r (%s) — "
                    "routing to default_assignee %r",
                    task_id, idx, assignee, policy.non_executable_reason, default_assignee,
                )
            else:
                logger.info(
                    "decompose: task %s child %d picked unknown assignee %r — "
                    "routing to default_assignee %r",
                    task_id, idx, assignee, default_assignee,
                )
        parents = entry.get("parents") or []
        if not isinstance(parents, list):
            parents = []
        # Clean parent indices: drop non-int and out-of-range.
        clean_parents = [p for p in parents if isinstance(p, int) and 0 <= p < len(raw_tasks) and p != idx]
        body_clean = body.strip()
        gate_hits = _detect_approval_gate(title.strip(), body_clean, policies.get(chosen))
        child: dict = {
            "title": title.strip()[:200],
            "body": body_clean,
            "assignee": chosen,
            "parents": clean_parents,
        }
        if gate_hits:
            approval_text = (
                "NEEDS FILIP APPROVAL: approve this child task crossing "
                f"approval gates {', '.join(gate_hits)} before any worker executes it."
            )
            child["body"] = approval_text + "\n\n" + body_clean
            child["initial_status"] = "blocked"
            child["block_reason"] = approval_text
        children.append(child)

    try:
        with kb.connect_closing() as conn:
            child_ids = kb.decompose_triage_task(
                conn,
                task_id,
                root_assignee=orchestrator,
                children=children,
                author=audit_author,
                auto_promote=auto_promote,
            )
    except ValueError as exc:
        return DecomposeOutcome(task_id, False, f"DB rejected graph: {exc}")
    except Exception as exc:
        logger.exception("decompose: DB error on task %s", task_id)
        return DecomposeOutcome(task_id, False, f"DB error: {type(exc).__name__}")

    if child_ids is None:
        return DecomposeOutcome(
            task_id, False, "task moved out of triage before decomposition",
        )

    return DecomposeOutcome(
        task_id, True, f"decomposed into {len(child_ids)} children",
        fanout=True, child_ids=child_ids,
    )


def list_triage_ids(*, tenant: Optional[str] = None) -> list[str]:
    """Return task ids currently in the triage column."""
    with kb.connect_closing() as conn:
        rows = kb.list_tasks(
            conn,
            status="triage",
            tenant=tenant,
            limit=1000,
        )
    return [row.id for row in rows]
