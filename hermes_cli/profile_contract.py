"""Specialist-orchestrator contract — machine-checkable autonomy policy.

Each Spearhead specialist (Gond, Helm, Waukeen, Mystra, Tymora, …) is
declared a "standalone orchestrator" via a small YAML file at
``<profile_dir>/contract.yaml``. This file hardcodes the autonomy
shape: division/domain, source-of-truth intake, child-lane policy,
escalation/approval categories, evidence requirements, and forbidden
autonomy scopes.

This module is the single source of truth for that schema. SOUL.md
prompts can document the policy, but acceptance is deterministic.

Two distinct readiness questions are answered here:

* ``CONTRACT_READY``  — does this profile have a valid ``contract.yaml``
  declaring the autonomy policy? This is the wrapper/audit layer:
  schema present, baseline rules populated. Implemented by
  ``contract_ready(profile_dir)``.

* ``FULL_AUTONOMY_READY`` — can this profile actually run autonomously,
  end-to-end: Notion intake → kanban decomposition → child supervision
  → implementation loop → escalation? Implemented by
  ``full_autonomy_readiness(profile_dir)``. A specialist with a valid
  contract can still fail this because the surrounding machinery (cron,
  decomposer hook, knowledge corpus, supervision tick) is not wired up.

Filip correction 2026-05-29: prior reports labelled the contract check
``STANDALONE_READY`` and let it imply full autonomy. That is misleading
— contract validity is necessary but not sufficient. The two functions
above keep the layers explicit so downstream reports cannot conflate
them. ``standalone_ready_*`` aliases remain for backward compatibility
and mean exactly contract readiness, nothing more.

API:

  - ``read_contract(profile_dir)``   — load contract.yaml (or None)
  - ``validate_contract(contract, name)`` — list of error strings
  - ``contract_ready(profile_dir)``       — {ok, missing, contract_path}
  - ``contract_ready_matrix(names)``      — bulk dict for reporting
  - ``assess_autonomy_dimensions(profile_dir)`` — per-dimension probe
  - ``full_autonomy_readiness(profile_dir)``    — aggregated verdict
  - ``full_autonomy_matrix(names)``       — bulk full-autonomy matrix
  - ``default_specialist_contract(...)``  — factory template

CLI:

  python -m hermes_cli.profile_contract validate [<name>...]
  python -m hermes_cli.profile_contract matrix
  python -m hermes_cli.profile_contract autonomy [<name>...]
  python -m hermes_cli.profile_contract init <name> --division X

Exit code is non-zero whenever any specified profile fails validation
(``validate``) or full autonomy (``autonomy --strict``), which makes
the validators usable as a CI gate or a kanban dry-run hook.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Iterable, Optional


# Canonical contract filename inside a profile directory.
CONTRACT_FILENAME = "contract.yaml"


# Top-level required keys with required Python type. ``standalone_orchestrator``
# is checked separately (must be exactly True, not just truthy).
_REQUIRED_TOP_KEYS: dict[str, type] = {
    "name": str,
    "division": str,
    "domain": list,
    "reports_to": str,
    "standalone_orchestrator": bool,
    "sot_intake": dict,
    "child_lane_policy": dict,
    "escalation_categories": list,
    "approval_gate_categories": list,
    "evidence_requirements": list,
    "forbidden_autonomy": list,
}

# Required keys inside sot_intake. Each list may be empty only when the
# specialist genuinely has no SoT in that channel — keep both present so
# the absence is explicit, not accidental.
_REQUIRED_SOT_KEYS: dict[str, type] = {
    "sources": list,
    "commands": list,
    "paths": list,
}

# Required keys inside child_lane_policy.
_REQUIRED_LANE_KEYS: dict[str, type] = {
    "default_lane": str,
    "heavy_lane": str,
    "max_parallel": int,
    "delegate_task_scope": str,
}

# Specialist profile names that MUST carry a contract. Keep small and
# explicit — adding a name here is the gating decision. Other profiles
# may still ship a contract, but absence is not a failure for them.
KNOWN_SPECIALISTS: tuple[str, ...] = (
    "gond",
    "helm",
    "waukeen",
    "mystra",
    "tymora",
)


def _profiles_root() -> Path:
    """Return the shared ``~/.hermes/profiles`` directory.

    When a worker runs inside a named Hermes profile, ``$HOME`` may be a
    profile-scoped sandbox such as ``~/.hermes/profiles/gond/home`` and
    ``$HERMES_HOME`` points at ``~/.hermes/profiles/gond``. In that mode,
    deriving from ``Path.home()`` would incorrectly look for nested profiles
    under ``.../gond/home/.hermes/profiles``. Prefer ``HERMES_HOME`` when set:
    a profile home resolves to its parent ``profiles`` directory; the default
    Hermes home resolves to ``<HERMES_HOME>/profiles``.
    """
    hermes_home = os.environ.get("HERMES_HOME")
    if hermes_home:
        hhome = Path(hermes_home).expanduser()
        if hhome.parent.name == "profiles":
            return hhome.parent
        return hhome / "profiles"
    return Path.home() / ".hermes" / "profiles"


def profile_dir_for(name: str) -> Path:
    return _profiles_root() / name


def _load_yaml(path: Path) -> Optional[dict]:
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("PyYAML is required to read contract.yaml") from exc
    if not path.is_file():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    return data


def read_contract(profile_dir: Path) -> Optional[dict]:
    """Return parsed contract dict, or ``None`` when missing/corrupt."""
    return _load_yaml(profile_dir / CONTRACT_FILENAME)


def _check_required_keys(
    data: dict,
    spec: dict[str, type],
    *,
    path_prefix: str,
) -> list[str]:
    errors: list[str] = []
    for key, expected_type in spec.items():
        if key not in data:
            errors.append(f"{path_prefix}{key}: missing")
            continue
        value = data[key]
        if expected_type is bool and not isinstance(value, bool):
            errors.append(f"{path_prefix}{key}: must be bool, got {type(value).__name__}")
        elif expected_type is int and (isinstance(value, bool) or not isinstance(value, int)):
            # bool is a subclass of int — exclude it explicitly
            errors.append(f"{path_prefix}{key}: must be int, got {type(value).__name__}")
        elif not isinstance(value, expected_type):
            errors.append(
                f"{path_prefix}{key}: must be {expected_type.__name__}, got {type(value).__name__}"
            )
    return errors


def validate_contract(contract: Optional[dict], profile_name: str) -> list[str]:
    """Return a list of human-readable error strings. Empty means valid."""
    if contract is None:
        return [f"{profile_name}: contract.yaml missing or unreadable"]

    errors: list[str] = _check_required_keys(contract, _REQUIRED_TOP_KEYS, path_prefix="")

    # standalone_orchestrator must be exactly True. A field present but
    # False would silently disable autonomy — fail loudly.
    sao = contract.get("standalone_orchestrator")
    if isinstance(sao, bool) and sao is not True:
        errors.append("standalone_orchestrator: must be true")

    # name must match the profile directory name (no rename drift).
    declared_name = contract.get("name")
    if isinstance(declared_name, str) and declared_name.strip() != profile_name:
        errors.append(
            f"name: declared {declared_name!r} does not match profile dir {profile_name!r}"
        )

    # Non-empty domain / escalation / evidence / forbidden — empty lists
    # would let a contract claim full autonomy with zero guardrails.
    for k in (
        "domain",
        "escalation_categories",
        "approval_gate_categories",
        "evidence_requirements",
        "forbidden_autonomy",
    ):
        v = contract.get(k)
        if isinstance(v, list) and len(v) == 0:
            errors.append(f"{k}: must not be empty")

    sot = contract.get("sot_intake")
    if isinstance(sot, dict):
        errors.extend(_check_required_keys(sot, _REQUIRED_SOT_KEYS, path_prefix="sot_intake."))
        # At least one SoT channel must be populated. A specialist with
        # zero sources/commands/paths cannot answer "where do I pull
        # work from?" deterministically.
        if all(isinstance(sot.get(k), list) and len(sot[k]) == 0 for k in _REQUIRED_SOT_KEYS):
            errors.append("sot_intake: at least one of sources/commands/paths must be non-empty")

    lane = contract.get("child_lane_policy")
    if isinstance(lane, dict):
        errors.extend(
            _check_required_keys(lane, _REQUIRED_LANE_KEYS, path_prefix="child_lane_policy.")
        )
        mp = lane.get("max_parallel")
        if isinstance(mp, int) and not isinstance(mp, bool) and mp < 1:
            errors.append("child_lane_policy.max_parallel: must be >= 1")

    return errors


def contract_ready(profile_dir: Path) -> dict:
    """Return {ok, missing, contract_path, has_file} for one profile.

    This measures *contract readiness only* — i.e. ``contract.yaml`` is
    present and validates against the schema. It is NOT a claim of full
    autonomy; see ``full_autonomy_readiness`` for that.
    """
    name = profile_dir.name
    contract = read_contract(profile_dir)
    errors = validate_contract(contract, name)
    return {
        "name": name,
        "ok": len(errors) == 0,
        "missing": errors,
        "contract_path": str(profile_dir / CONTRACT_FILENAME),
        "has_file": (profile_dir / CONTRACT_FILENAME).is_file(),
    }


def contract_ready_matrix(
    names: Optional[Iterable[str]] = None,
    *,
    profiles_root: Optional[Path] = None,
) -> dict:
    """Bulk contract-readiness matrix. Default set is KNOWN_SPECIALISTS.

    ``profiles_root`` overrides the default ``~/.hermes/profiles`` —
    used by tests with ``tmp_path``.
    """
    root = profiles_root if profiles_root is not None else _profiles_root()
    targets = list(names) if names is not None else list(KNOWN_SPECIALISTS)
    rows = [contract_ready(root / name) for name in targets]
    return {
        "profiles_root": str(root),
        "generated_for": targets,
        "rows": rows,
        "all_ok": all(r["ok"] for r in rows) if rows else True,
    }


# Backwards-compatible aliases. Existing callers and tests use the
# ``standalone_ready`` name; we keep the names but the semantics are
# now explicit: this is contract readiness only.
standalone_ready = contract_ready
standalone_ready_matrix = contract_ready_matrix


# ---------------------------------------------------------------------------
# Full-autonomy readiness — multi-dimensional probe.
# ---------------------------------------------------------------------------

# Per-dimension status vocabulary. ``yes`` is the only value that counts
# towards FULL_AUTONOMY_READY; ``partial`` / ``no`` / ``unknown`` all
# block the aggregate.
DIM_YES = "yes"
DIM_NO = "no"
DIM_PARTIAL = "partial"
DIM_UNKNOWN = "unknown"

# Required dimensions for FULL_AUTONOMY_READY. Order is preserved in
# reports so reviewers see the same column order every time.
AUTONOMY_DIMENSIONS: tuple[str, ...] = (
    "contract_ready",
    "scheduler_ready",
    "notion_intake_ready",
    "decomposition_ready",
    "child_supervision_ready",
    "knowledge_corpus_ready",
    "implementation_loop_ready",
    "escalation_ready",
)


def _dim(status: str, *reasons: str) -> dict:
    return {"status": status, "reasons": list(reasons)}


def _probe_contract(profile_dir: Path) -> dict:
    row = contract_ready(profile_dir)
    if row["ok"]:
        return _dim(DIM_YES)
    return _dim(DIM_NO, *row["missing"])


def _probe_scheduler(profile_dir: Path) -> dict:
    """Profile must have at least one active registered scheduler job that
    invokes its standalone orchestrator.

    Spearhead can wire those jobs in either of two supported places:
    profile-local ``<profile>/cron/jobs.json`` or the default scheduler's
    shared ``<hermes-home>/cron/jobs.json`` using a no-agent wrapper script
    such as ``gond_standalone_orchestrator_default_wrapper.sh``. The latter
    is the live deployment shape for the specialist factory, so absence of a
    profile-local jobs file is not by itself a scheduler failure.
    """
    name = profile_dir.name.lower()
    expected_script_fragments = (
        f"{name}_standalone_orchestrator.py",
        f"{name}_standalone_orchestrator_default_wrapper.sh",
    )
    scheduler_paths = [profile_dir / "cron" / "jobs.json"]
    shared_jobs_path = profile_dir.parent.parent / "cron" / "jobs.json"
    if shared_jobs_path not in scheduler_paths:
        scheduler_paths.append(shared_jobs_path)

    seen_jobs = False
    relevant: list[tuple[Path, dict]] = []
    unreadable: list[str] = []
    existing_paths: list[Path] = []

    for jobs_path in scheduler_paths:
        if not jobs_path.is_file():
            continue
        existing_paths.append(jobs_path)
        try:
            with open(jobs_path, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
        except Exception as exc:
            unreadable.append(f"{jobs_path}: {exc}")
            continue
        jobs = data.get("jobs") if isinstance(data, dict) else None
        if not isinstance(jobs, list) or not jobs:
            continue
        seen_jobs = True
        for job in jobs:
            if not isinstance(job, dict):
                continue
            script = str(job.get("script") or "").lower()
            job_name = str(job.get("name") or "").lower()
            job_profile = str(job.get("profile") or "").lower()
            name_or_script = f"{job_name} {script}"
            if (
                any(fragment in script for fragment in expected_script_fragments)
                or (name in job_name and "standalone" in job_name)
                or (job_profile == name and "standalone" in name_or_script)
            ):
                relevant.append((jobs_path, job))

    if not existing_paths:
        checked = ", ".join(str(p) for p in scheduler_paths)
        return _dim(DIM_NO, f"cron/jobs.json missing at checked scheduler paths: {checked}")
    if unreadable and not seen_jobs:
        return _dim(DIM_NO, *[f"cron/jobs.json unreadable: {r}" for r in unreadable])
    if not seen_jobs:
        return _dim(DIM_NO, "cron/jobs.json has no registered jobs")
    if not relevant:
        return _dim(
            DIM_PARTIAL,
            "cron jobs registered but none reference standalone orchestrator",
        )

    inactive_reasons: list[str] = []
    for jobs_path, job in relevant:
        enabled = job.get("enabled", True)
        state = str(job.get("state") or "").lower()
        if enabled is False:
            inactive_reasons.append(f"{jobs_path}: standalone scheduler job disabled")
            continue
        if state in {"paused", "disabled"}:
            inactive_reasons.append(f"{jobs_path}: standalone scheduler job {state}")
            continue
        return _dim(DIM_YES)

    return _dim(DIM_NO, *inactive_reasons)


def _probe_notion_intake(profile_dir: Path, contract: Optional[dict]) -> dict:
    """Contract must list a notion source AND a snapshot path that
    actually exists. Without a fresh snapshot the orchestrator has no
    way to discover Notion-side work.
    """
    if not contract:
        return _dim(DIM_NO, "contract missing — cannot verify notion intake")
    sot = contract.get("sot_intake") or {}
    sources = sot.get("sources") or []
    has_notion = any("notion" in str(s).lower() for s in sources)
    if not has_notion:
        return _dim(DIM_NO, "sot_intake.sources does not mention notion")
    paths = sot.get("paths") or []
    existing = [p for p in paths if isinstance(p, str) and Path(p).exists()]
    if not existing:
        return _dim(
            DIM_PARTIAL,
            "sot_intake.paths declared but no path resolvable on disk",
        )
    return _dim(DIM_YES)


def _probe_decomposition(profile_dir: Path) -> dict:
    """The kanban decomposer must read the specialist's contract — else
    the orchestrator depends on prompt-only roster guidance. We probe
    by source-grep on ``kanban_decompose.py``. Parent handoff t_8c39511c
    explicitly listed this as an unresolved gap, so this probe is
    expected to return ``no`` until that follow-up lands.
    """
    here = Path(__file__).resolve().parent
    decompose = here / "kanban_decompose.py"
    if not decompose.is_file():
        return _dim(DIM_UNKNOWN, f"{decompose} not found")
    try:
        text = decompose.read_text(encoding="utf-8")
    except Exception as exc:
        return _dim(DIM_UNKNOWN, f"unreadable: {exc}")
    if "contract.yaml" in text or "profile_contract" in text:
        return _dim(DIM_YES)
    return _dim(
        DIM_NO,
        "kanban_decompose.py does not yet load contract.yaml (follow-up t_8c39511c)",
    )


def _probe_child_supervision(profile_dir: Path, contract: Optional[dict]) -> dict:
    """child_lane_policy must be present in the contract and the profile
    must ship a standalone orchestrator script (the loop runner)."""
    if not contract:
        return _dim(DIM_NO, "contract missing")
    policy = contract.get("child_lane_policy") or {}
    if not policy:
        return _dim(DIM_NO, "child_lane_policy missing")
    heavy = policy.get("heavy_lane")
    if not heavy:
        return _dim(DIM_NO, "child_lane_policy.heavy_lane missing")
    script = profile_dir / "scripts" / f"{profile_dir.name}_standalone_orchestrator.py"
    if not script.is_file():
        return _dim(
            DIM_PARTIAL,
            f"standalone orchestrator script missing at {script}",
        )
    return _dim(DIM_YES)


def _probe_knowledge_corpus(profile_dir: Path) -> dict:
    """Per-specialist evidence corpus check.

    Authoritative source: :mod:`hermes_cli.profile_knowledge` —
    ``knowledge_corpus_ready`` means ``corpus.jsonl`` exists AND
    contains at least one entry with ``confidence: verified`` and no
    invalid entries. Gated/unread URLs in ``gates.jsonl`` are
    informational only; they do not count as verified evidence.

    Falls back to the legacy "any non-empty knowledge bucket" heuristic
    only when the new corpus module cannot be imported, so a host
    without the upgraded module still grades sensibly.
    """
    try:
        from hermes_cli import profile_knowledge as pk
    except Exception:
        pk = None  # type: ignore[assignment]
    if pk is not None:
        row = pk.corpus_ready(profile_dir)
        if row["ok"]:
            return _dim(DIM_YES)
        if row["invalid_entries"]:
            return _dim(DIM_NO, *[f"invalid: {e}" for e in row["invalid_entries"]])
        if row["has_corpus_dir"] and row["entries"] == 0 and row["gates"] > 0:
            return _dim(
                DIM_PARTIAL,
                f"only {row['gates']} gated metadata entries; no verified evidence yet",
            )
        if row["has_corpus_dir"] and row["entries"] > 0 and row["verified_entries"] == 0:
            return _dim(DIM_PARTIAL, "corpus has entries but none are verified")
        if row["has_corpus_dir"]:
            return _dim(DIM_PARTIAL, "knowledge/corpus.jsonl present but empty")
    for sub in ("references", "knowledge", "corpus"):
        d = profile_dir / sub
        if d.is_dir():
            try:
                entries = [p for p in d.iterdir() if not p.name.startswith(".")]
            except Exception:
                entries = []
            if entries:
                return _dim(
                    DIM_PARTIAL,
                    f"{sub}/ has files but no profile_knowledge corpus.jsonl",
                )
            return _dim(DIM_PARTIAL, f"{sub}/ exists but is empty")
    return _dim(
        DIM_NO,
        "no references/, knowledge/, or corpus/ directory present",
    )


def _probe_implementation_loop(profile_dir: Path, contract: Optional[dict]) -> dict:
    """The orchestrator must (a) declare evidence requirements and
    (b) have at least one recent run artifact under ``logs/`` or
    ``sessions/`` proving the loop has actually fired. Without artifacts
    we cannot claim the implementation loop is closed.
    """
    if not contract:
        return _dim(DIM_NO, "contract missing")
    if not (contract.get("evidence_requirements") or []):
        return _dim(DIM_NO, "evidence_requirements missing/empty")
    any_artifact = False
    for sub in ("logs", "sessions"):
        d = profile_dir / sub
        if d.is_dir():
            try:
                if any(d.iterdir()):
                    any_artifact = True
                    break
            except Exception:
                continue
    if not any_artifact:
        return _dim(
            DIM_PARTIAL,
            "evidence_requirements declared but no logs/ or sessions/ artifacts yet",
        )
    return _dim(DIM_YES)


def _probe_escalation(contract: Optional[dict]) -> dict:
    if not contract:
        return _dim(DIM_NO, "contract missing")
    cats = contract.get("escalation_categories") or []
    gates = contract.get("approval_gate_categories") or []
    if not cats:
        return _dim(DIM_NO, "escalation_categories missing/empty")
    if not gates:
        return _dim(DIM_NO, "approval_gate_categories missing/empty")
    return _dim(DIM_YES)


def assess_autonomy_dimensions(profile_dir: Path) -> dict:
    """Return ``{dimension_name: {status, reasons}}`` for every probe.

    Deterministic, on-disk only. No network calls. Used both directly
    and by ``full_autonomy_readiness``.
    """
    contract = read_contract(profile_dir)
    return {
        "contract_ready": _probe_contract(profile_dir),
        "scheduler_ready": _probe_scheduler(profile_dir),
        "notion_intake_ready": _probe_notion_intake(profile_dir, contract),
        "decomposition_ready": _probe_decomposition(profile_dir),
        "child_supervision_ready": _probe_child_supervision(profile_dir, contract),
        "knowledge_corpus_ready": _probe_knowledge_corpus(profile_dir),
        "implementation_loop_ready": _probe_implementation_loop(profile_dir, contract),
        "escalation_ready": _probe_escalation(contract),
    }


def full_autonomy_readiness(profile_dir: Path) -> dict:
    """Return a single row of full-autonomy readiness for one profile.

    Shape::

        {
            "name": "gond",
            "full_autonomy_ready": False,
            "dimensions": {
                "contract_ready": {"status": "yes", "reasons": []},
                "scheduler_ready": {"status": "no", "reasons": [...]},
                ...
            },
            "blocking_dimensions": ["scheduler_ready", ...],
        }

    ``full_autonomy_ready`` is True iff every dimension status is
    ``yes``. A wrapper-only specialist (contract valid, surrounding
    machinery missing) will land here with multiple blocking dimensions
    — exactly the misleading-yes case the t_0990d9a3 card is fixing.
    """
    name = profile_dir.name
    dims = assess_autonomy_dimensions(profile_dir)
    blocking = [
        d for d, r in dims.items()
        if r.get("status") != DIM_YES
    ]
    return {
        "name": name,
        "full_autonomy_ready": len(blocking) == 0,
        "dimensions": dims,
        "blocking_dimensions": blocking,
    }


def full_autonomy_matrix(
    names: Optional[Iterable[str]] = None,
    *,
    profiles_root: Optional[Path] = None,
) -> dict:
    """Bulk full-autonomy matrix across the known specialists."""
    root = profiles_root if profiles_root is not None else _profiles_root()
    targets = list(names) if names is not None else list(KNOWN_SPECIALISTS)
    rows = [full_autonomy_readiness(root / name) for name in targets]
    return {
        "profiles_root": str(root),
        "generated_for": targets,
        "dimensions": list(AUTONOMY_DIMENSIONS),
        "rows": rows,
        "all_full_autonomy_ready": all(r["full_autonomy_ready"] for r in rows) if rows else True,
        "all_contract_ready": all(
            r["dimensions"]["contract_ready"]["status"] == DIM_YES for r in rows
        ) if rows else True,
    }


def default_specialist_contract(
    name: str,
    *,
    division: str,
    domain: list[str],
    reports_to: str = "ema",
) -> dict:
    """Return a baseline contract dict for a new specialist profile.

    The factory baseline encodes Filip's standing autonomy policy:
    Claude Code CLI as the heavy child lane, EMA as the escalation
    target, NEEDS FILIP APPROVAL gates for destructive/public/cost
    actions. Callers tune ``domain`` and supply specialist-specific
    intake/escalation lists after writing the template.
    """
    return {
        "name": name,
        "division": division,
        "domain": list(domain),
        "reports_to": reports_to,
        "standalone_orchestrator": True,
        "sot_intake": {
            "sources": ["kanban: assignee=" + name],
            "commands": ["hermes kanban list --assignee " + name],
            "paths": [],
        },
        "child_lane_policy": {
            "default_lane": "delegate_task",
            "heavy_lane": "gond-cc",
            "max_parallel": 3,
            "delegate_task_scope": "small bounded subtask, no repo mutation, single short pass",
        },
        "escalation_categories": [
            "credentials_missing",
            "scope_outside_division",
            "repeated_failure_after_3_attempts",
            "evidence_conflict",
        ],
        "approval_gate_categories": [
            "destructive_or_irreversible",
            "public_or_client_facing_send",
            "cost_incurring_or_paid_api",
            "credential_rotation",
            "production_or_deploy",
        ],
        "evidence_requirements": [
            "exact_files_changed_list",
            "test_or_check_command_output",
            "source_citations_for_claims",
        ],
        "forbidden_autonomy": [
            "push_or_merge_without_approval",
            "send_public_or_client_messages",
            "install_or_provision_services",
            "rotate_credentials_or_secrets",
            "spend_money_or_enable_paid_apis",
            "destructive_data_or_repo_actions",
        ],
    }


def write_contract(profile_dir: Path, contract: dict) -> Path:
    """Persist ``contract`` as YAML at ``<profile_dir>/contract.yaml``.

    Refuses to overwrite an existing file — the factory path is for
    initial creation, not reset. Caller can delete first if a fresh
    rewrite is intended.
    """
    import yaml

    if not profile_dir.is_dir():
        raise FileNotFoundError(f"profile directory does not exist: {profile_dir}")
    path = profile_dir / CONTRACT_FILENAME
    if path.exists():
        raise FileExistsError(f"contract already exists: {path}")
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(contract, f, sort_keys=False, default_flow_style=False)
    return path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _format_matrix_text(matrix: dict) -> str:
    lines = [
        "CONTRACT_READY matrix  (NOTE: contract/wrapper layer only — not FULL_AUTONOMY_READY)",
        f"profiles_root: {matrix['profiles_root']}",
        "",
    ]
    width = max((len(r["name"]) for r in matrix["rows"]), default=4)
    for r in matrix["rows"]:
        mark = "OK  " if r["ok"] else "FAIL"
        lines.append(f"  {mark}  {r['name']:<{width}}  ({r['contract_path']})")
        for m in r["missing"]:
            lines.append(f"          - {m}")
    lines.append("")
    lines.append("all_contract_ready: " + ("yes" if matrix["all_ok"] else "no"))
    lines.append(
        "for full autonomy verification, run: "
        "python -m hermes_cli.profile_contract autonomy"
    )
    return "\n".join(lines)


def _format_autonomy_text(matrix: dict) -> str:
    lines = [
        "FULL_AUTONOMY_READY matrix",
        f"profiles_root: {matrix['profiles_root']}",
        "",
        "Dimensions: " + ", ".join(matrix["dimensions"]),
        "",
    ]
    width = max((len(r["name"]) for r in matrix["rows"]), default=4)
    for r in matrix["rows"]:
        mark = "OK  " if r["full_autonomy_ready"] else "FAIL"
        lines.append(f"  {mark}  {r['name']:<{width}}  full_autonomy_ready={r['full_autonomy_ready']}")
        for dim_name in matrix["dimensions"]:
            d = r["dimensions"].get(dim_name) or {}
            status = d.get("status", "unknown")
            reasons = d.get("reasons") or []
            lines.append(f"          [{status:<7}] {dim_name}")
            for reason in reasons:
                lines.append(f"                     - {reason}")
    lines.append("")
    lines.append("all_contract_ready:       " + ("yes" if matrix["all_contract_ready"] else "no"))
    lines.append("all_full_autonomy_ready:  " + ("yes" if matrix["all_full_autonomy_ready"] else "no"))
    return "\n".join(lines)


def _cmd_validate(args: argparse.Namespace) -> int:
    names = args.profiles or list(KNOWN_SPECIALISTS)
    matrix = contract_ready_matrix(names)
    if args.json:
        print(json.dumps(matrix, indent=2, sort_keys=False))
    else:
        print(_format_matrix_text(matrix))
    return 0 if matrix["all_ok"] else 1


def _cmd_matrix(args: argparse.Namespace) -> int:
    matrix = contract_ready_matrix()
    if args.json:
        print(json.dumps(matrix, indent=2, sort_keys=False))
    else:
        print(_format_matrix_text(matrix))
    # matrix is informational — always exit 0 unless --strict
    if args.strict and not matrix["all_ok"]:
        return 1
    return 0


def _cmd_autonomy(args: argparse.Namespace) -> int:
    names = args.profiles or list(KNOWN_SPECIALISTS)
    matrix = full_autonomy_matrix(names)
    if args.json:
        print(json.dumps(matrix, indent=2, sort_keys=False))
    else:
        print(_format_autonomy_text(matrix))
    if args.strict and not matrix["all_full_autonomy_ready"]:
        return 1
    return 0


def _cmd_init(args: argparse.Namespace) -> int:
    profile_dir = profile_dir_for(args.name)
    if not profile_dir.is_dir():
        print(f"profile directory does not exist: {profile_dir}", file=sys.stderr)
        return 2
    contract = default_specialist_contract(
        args.name,
        division=args.division,
        domain=args.domain or [args.division],
    )
    try:
        path = write_contract(profile_dir, contract)
    except FileExistsError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    print(f"wrote {path}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m hermes_cli.profile_contract",
        description="Validate specialist-orchestrator contracts (autonomy policy).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_val = sub.add_parser("validate", help="validate contracts (non-zero exit on failure)")
    p_val.add_argument("profiles", nargs="*", help="profile names; default: known specialists")
    p_val.add_argument("--json", action="store_true", help="emit JSON instead of text")
    p_val.set_defaults(func=_cmd_validate)

    p_mat = sub.add_parser(
        "matrix",
        help="emit CONTRACT_READY matrix (contract/wrapper layer only)",
    )
    p_mat.add_argument("--json", action="store_true", help="emit JSON instead of text")
    p_mat.add_argument(
        "--strict",
        action="store_true",
        help="exit non-zero if any specialist fails (default: always 0)",
    )
    p_mat.set_defaults(func=_cmd_matrix)

    p_aut = sub.add_parser(
        "autonomy",
        help="emit FULL_AUTONOMY_READY matrix across all autonomy dimensions",
    )
    p_aut.add_argument("profiles", nargs="*", help="profile names; default: known specialists")
    p_aut.add_argument("--json", action="store_true", help="emit JSON instead of text")
    p_aut.add_argument(
        "--strict",
        action="store_true",
        help="exit non-zero if any specialist is not full-autonomy-ready",
    )
    p_aut.set_defaults(func=_cmd_autonomy)

    p_init = sub.add_parser("init", help="write a baseline contract.yaml into an existing profile")
    p_init.add_argument("name", help="profile name (must already exist on disk)")
    p_init.add_argument("--division", required=True, help="division id, e.g. engineering")
    p_init.add_argument(
        "--domain",
        action="append",
        help="repeatable; one domain bullet per flag",
    )
    p_init.set_defaults(func=_cmd_init)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
