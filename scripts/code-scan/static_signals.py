"""Static Signals Schema and Helpers (Tier 1).

Minimal stdlib-only implementation per ua-tier1-001-static-signals-schema bead.

This module defines:
- make_signal_record / SignalRecord: canonical shape for a single heuristic marker.
- build_static_signals_artifact: produces the full document with forced
  claim_type="heuristic_signal" and semantic_status="not_validated".

Core boundary contract (verbatim):
Tier 1 static signals are heuristic content markers only.
They do not prove security, RLS correctness, auth correctness, runtime behavior,
deployment readiness, CI success, or policy semantics.

Every emitted Tier 1 claim MUST be labelled heuristic_signal and not_validated
unless it is an existing deterministic inventory fact from Tier 0.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
import re
from typing import Any, Dict, List, Optional

SCHEMA_VERSION = "1.0.0"
CLAIM_TYPE = "heuristic_signal"
SEMANTIC_STATUS = "not_validated"

DEFAULT_BOUNDARIES: List[str] = [
    "Tier 1 static signals are content markers only; they do not prove security, "
    "RLS correctness, auth correctness, runtime behavior, deployment readiness, "
    "CI success, or policy semantics."
]

SUPABASE_MIGRATION_SURFACE = "supabase_migration"
SUPABASE_EDGE_FUNCTION_SURFACE = "supabase_edge_function"
PACKAGE_CONFIG_SURFACE = "package_config"

PACKAGE_CONFIG_BOUNDARY = (
    "Tier 1 static signals are content markers only; package/config markers identify "
    "available or declared gates only and do not prove the gates were executed or passed. "
    "This does not prove security, RLS correctness, auth correctness, runtime behavior, "
    "deployment readiness, CI success, or policy semantics."
)

_SUPABASE_MIGRATION_PATH_RE = re.compile(
    r"(?:^|/)supabase/migrations/[^/]+\.sql\Z",
    re.IGNORECASE,
)

_SUPABASE_MIGRATION_MARKERS = (
    ("enable_rls", re.compile(r"\benable\s+row\s+level\s+security\b", re.IGNORECASE)),
    ("create_policy", re.compile(r"\bcreate\s+policy\b", re.IGNORECASE)),
    ("drop_policy", re.compile(r"\bdrop\s+policy\b", re.IGNORECASE)),
    ("using_clause", re.compile(r"\busing\s*\(", re.IGNORECASE)),
    ("with_check_clause", re.compile(r"\bwith\s+check\s*\(", re.IGNORECASE)),
    ("auth_uid", re.compile(r"\bauth\s*\.\s*uid\s*\(", re.IGNORECASE)),
    ("auth_role", re.compile(r"\bauth\s*\.\s*role\s*\(", re.IGNORECASE)),
    ("anon_role", re.compile(r"(?<![\w])anon(?![\w])", re.IGNORECASE)),
    ("authenticated_role", re.compile(r"(?<![\w])authenticated(?![\w])", re.IGNORECASE)),
    (
        "permissive_true",
        re.compile(r"\b(?:using|with\s+check)\s*\(\s*true\s*\)", re.IGNORECASE),
    ),
    ("security_definer", re.compile(r"\bsecurity\s+definer\b", re.IGNORECASE)),
    ("service_role", re.compile(r"(?<![\w])service_role(?![\w])", re.IGNORECASE)),
    ("grant_statement", re.compile(r"^\s*grant\b", re.IGNORECASE)),
    ("revoke_statement", re.compile(r"^\s*revoke\b", re.IGNORECASE)),
    (
        "create_function",
        re.compile(r"\bcreate\s+(?:or\s+replace\s+)?function\b", re.IGNORECASE),
    ),
)

_SUPABASE_EDGE_FUNCTION_PATH_RE = re.compile(
    r"^supabase/functions/[^/]+/index\.(?:ts|js)\Z",
    re.IGNORECASE,
)

_SUPABASE_EDGE_FUNCTION_MARKERS = (
    (
        "authorization_header",
        re.compile(r"headers\s*\.\s*get\s*\(\s*['\"][Aa]uthorization['\"]|['\"]Authorization['\"]"),
    ),
    ("bearer_token", re.compile(r"(?<![\w])bearer(?![\w])", re.IGNORECASE)),
    ("jwt", re.compile(r"(?<![\w])jwt(?![\w])", re.IGNORECASE)),
    ("get_user", re.compile(r"\bgetUser\s*\(", re.IGNORECASE)),
    ("service_role_env", re.compile(r"service[_-]?role", re.IGNORECASE)),
    ("deno_env", re.compile(r"\bDeno\s*\.\s*env\s*\.\s*get\s*\(", re.IGNORECASE)),
    ("cors_header", re.compile(r"\bAccess-Control-Allow-[A-Za-z-]+\b", re.IGNORECASE)),
    (
        "cors_wildcard",
        re.compile(r"\bAccess-Control-Allow-Origin\b.*['\"]\*['\"]", re.IGNORECASE),
    ),
    ("request_json", re.compile(r"\breq(?:uest)?\s*\.\s*json\s*\(", re.IGNORECASE)),
    ("external_fetch", re.compile(r"\bfetch\s*\(", re.IGNORECASE)),
)

_WORKFLOW_PATH_RE = re.compile(r"^\.github/workflows/[^/]+\.ya?ml\Z", re.IGNORECASE)
_VITE_CONFIG_PATH_RE = re.compile(r"^vite\.config\.[^/]+\Z", re.IGNORECASE)

_PACKAGE_SCRIPT_MARKERS = (
    ("script_test", "test"),
    ("script_build", "build"),
    ("script_lint", "lint"),
    ("script_typecheck", "typecheck"),
    ("script_audit", "audit"),
)

_WORKFLOW_MARKERS = (
    ("ci_npm_ci", re.compile(r"\bnpm\s+ci\b", re.IGNORECASE)),
    ("ci_test", re.compile(r"\b(?:npm|pnpm|yarn)\s+(?:run\s+)?test\b", re.IGNORECASE)),
    ("ci_build", re.compile(r"\b(?:npm|pnpm|yarn)\s+(?:run\s+)?build\b", re.IGNORECASE)),
    (
        "ci_typecheck",
        re.compile(r"\b(?:npm|pnpm|yarn)\s+(?:run\s+)?(?:typecheck|type-check)\b", re.IGNORECASE),
    ),
)


@dataclass(frozen=True)
class SignalRecord:
    """Canonical record for a Tier 1 static signal / heuristic marker.

    All fields are required at construction time for explicitness.
    The dataclass is frozen to prevent mutation after creation.
    """

    surface: str
    path: str
    line: int
    marker_type: str
    marker: str
    claim_type: str = CLAIM_TYPE
    semantic_status: str = SEMANTIC_STATUS
    boundary: str = DEFAULT_BOUNDARIES[0]

    def __getitem__(self, key: str):
        """Support dict-style access for compatibility (tests use rec["surface"])."""
        return getattr(self, key)

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key)


def make_signal_record(
    surface: str,
    path: str,
    line: int,
    marker_type: str,
    marker: str,
    claim_type: Optional[str] = None,
    semantic_status: Optional[str] = None,
    boundary: Optional[str] = None,
) -> Dict[str, Any]:
    """Factory for a SignalRecord (returns plain dict for JSON stability).

    Callers may omit claim_type/semantic_status/boundary; they are forced
    to the Tier 1 defaults (heuristic_signal / not_validated).
    This helper never permits validated / concrete claims for pure Tier 1 signals.
    """
    rec = SignalRecord(
        surface=surface,
        path=path,
        line=line,
        marker_type=marker_type,
        marker=marker,
        claim_type=claim_type or CLAIM_TYPE,
        semantic_status=semantic_status or SEMANTIC_STATUS,
        boundary=boundary or DEFAULT_BOUNDARIES[0],
    )
    return asdict(rec)


def _is_supabase_migration_path(rel_path: str) -> bool:
    """Return whether rel_path is a Supabase SQL migration surface."""
    normalized = str(rel_path).replace("\\", "/").lstrip("./")
    return bool(_SUPABASE_MIGRATION_PATH_RE.search(normalized))


def _normalize_rel_path(rel_path: str) -> str:
    normalized = str(rel_path).replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _is_supabase_edge_function_path(rel_path: str) -> bool:
    """Return whether rel_path is a supported Supabase Edge Function entrypoint."""
    return bool(_SUPABASE_EDGE_FUNCTION_PATH_RE.fullmatch(_normalize_rel_path(rel_path)))


def _package_config_kind(rel_path: str) -> Optional[str]:
    """Return the supported package/config file kind for rel_path, if any."""
    normalized = _normalize_rel_path(rel_path)
    if normalized == "package.json":
        return "package_json"
    if _WORKFLOW_PATH_RE.fullmatch(normalized):
        return "workflow"
    if _VITE_CONFIG_PATH_RE.fullmatch(normalized):
        return "vite_config"
    if normalized == "vercel.json":
        return "vercel"
    if normalized == "netlify.toml":
        return "netlify"
    return None


def _marker_snippet(line: str, limit: int = 240) -> str:
    snippet = " ".join(line.strip().split())
    if len(snippet) <= limit:
        return snippet
    return snippet[: limit - 3].rstrip() + "..."


def extract_supabase_migration_markers(
    rel_path: str,
    content: str,
    max_per_type: int = 50,
) -> List[Dict[str, Any]]:
    """Extract heuristic Supabase migration content markers.

    This is a line-oriented marker inventory only. It does not parse SQL and
    does not validate RLS, policy, auth, runtime, deployment, CI, or security
    semantics.
    """
    if not _is_supabase_migration_path(rel_path):
        return []

    try:
        cap = int(max_per_type)
    except (TypeError, ValueError):
        cap = 50
    if cap <= 0:
        return []

    signals: List[Dict[str, Any]] = []
    emitted_by_type: Dict[str, int] = {}

    for line_number, line in enumerate(str(content).splitlines(), start=1):
        if not line.strip():
            continue
        for marker_type, pattern in _SUPABASE_MIGRATION_MARKERS:
            if emitted_by_type.get(marker_type, 0) >= cap:
                continue
            if not pattern.search(line):
                continue
            signals.append(
                make_signal_record(
                    surface=SUPABASE_MIGRATION_SURFACE,
                    path=rel_path,
                    line=line_number,
                    marker_type=marker_type,
                    marker=_marker_snippet(line),
                )
            )
            emitted_by_type[marker_type] = emitted_by_type.get(marker_type, 0) + 1

    return signals


def extract_edge_function_markers(
    rel_path: str,
    content: str,
    max_per_type: int = 50,
) -> List[Dict[str, Any]]:
    """Extract heuristic Supabase Edge Function content markers.

    Only supabase/functions/*/index.ts and supabase/functions/*/index.js are
    scanned. This inventory does not validate auth, CORS, secrets, requests,
    runtime behavior, deployment readiness, CI success, or security semantics.
    """
    normalized_path = _normalize_rel_path(rel_path)
    if not _is_supabase_edge_function_path(normalized_path):
        return []

    try:
        cap = int(max_per_type)
    except (TypeError, ValueError):
        cap = 50
    if cap <= 0:
        return []

    signals: List[Dict[str, Any]] = []
    emitted_by_type: Dict[str, int] = {}

    for line_number, line in enumerate(str(content).splitlines(), start=1):
        if not line.strip():
            continue
        for marker_type, pattern in _SUPABASE_EDGE_FUNCTION_MARKERS:
            if emitted_by_type.get(marker_type, 0) >= cap:
                continue
            if not pattern.search(line):
                continue
            signals.append(
                make_signal_record(
                    surface=SUPABASE_EDGE_FUNCTION_SURFACE,
                    path=normalized_path,
                    line=line_number,
                    marker_type=marker_type,
                    marker=_marker_snippet(line),
                )
            )
            emitted_by_type[marker_type] = emitted_by_type.get(marker_type, 0) + 1

    return signals


def _extract_package_json_markers(normalized_path: str, content: str) -> List[Dict[str, Any]]:
    signals: List[Dict[str, Any]] = []
    emitted = set()
    script_patterns = [
        (marker_type, re.compile(rf'["\']{re.escape(script_name)}["\']\s*:', re.IGNORECASE))
        for marker_type, script_name in _PACKAGE_SCRIPT_MARKERS
    ]

    for line_number, line in enumerate(str(content).splitlines(), start=1):
        for marker_type, pattern in script_patterns:
            if marker_type in emitted or not pattern.search(line):
                continue
            signals.append(
                make_signal_record(
                    surface=PACKAGE_CONFIG_SURFACE,
                    path=normalized_path,
                    line=line_number,
                    marker_type=marker_type,
                    marker=_marker_snippet(line),
                    boundary=PACKAGE_CONFIG_BOUNDARY,
                )
            )
            emitted.add(marker_type)

    return signals


def _extract_workflow_markers(normalized_path: str, content: str) -> List[Dict[str, Any]]:
    signals: List[Dict[str, Any]] = []
    emitted = set()

    for line_number, line in enumerate(str(content).splitlines(), start=1):
        for marker_type, pattern in _WORKFLOW_MARKERS:
            if marker_type in emitted or not pattern.search(line):
                continue
            signals.append(
                make_signal_record(
                    surface=PACKAGE_CONFIG_SURFACE,
                    path=normalized_path,
                    line=line_number,
                    marker_type=marker_type,
                    marker=_marker_snippet(line),
                    boundary=PACKAGE_CONFIG_BOUNDARY,
                )
            )
            emitted.add(marker_type)

    return signals


def extract_package_config_markers(
    rel_path: str,
    content: str,
) -> List[Dict[str, Any]]:
    """Extract heuristic package/config gate declaration markers.

    These markers identify available or declared gates only. They do not prove
    that npm, audit, CI, Vite, Vercel, Netlify, browser, or external commands
    were executed or passed.
    """
    normalized_path = _normalize_rel_path(rel_path)
    kind = _package_config_kind(normalized_path)
    if kind is None:
        return []

    if kind == "package_json":
        return _extract_package_json_markers(normalized_path, content)
    if kind == "workflow":
        return _extract_workflow_markers(normalized_path, content)

    if kind == "vite_config":
        signals: List[Dict[str, Any]] = []
        for line_number, line in enumerate(str(content).splitlines(), start=1):
            if "VITE_" not in line:
                continue
            signals.append(
                make_signal_record(
                    surface=PACKAGE_CONFIG_SURFACE,
                    path=normalized_path,
                    line=line_number,
                    marker_type="vite_public_env",
                    marker=_marker_snippet(line),
                    boundary=PACKAGE_CONFIG_BOUNDARY,
                )
            )
            break
        return signals

    if not str(content).strip():
        return []

    marker_type = "vercel_config" if kind == "vercel" else "netlify_config"
    return [
        make_signal_record(
            surface=PACKAGE_CONFIG_SURFACE,
            path=normalized_path,
            line=1,
            marker_type=marker_type,
            marker=normalized_path,
            boundary=PACKAGE_CONFIG_BOUNDARY,
        )
    ]


def _normalize_signal(sig: Any) -> Dict[str, Any]:
    """Coerce incoming signal (dict or SignalRecord) into validated Tier 1 shape."""
    if isinstance(sig, SignalRecord):
        d = asdict(sig)
    elif isinstance(sig, dict):
        d = dict(sig)  # shallow copy
    else:
        raise TypeError(f"Signal must be dict or SignalRecord, got {type(sig)}")

    # Force Tier 1 contract on every signal, regardless of what caller supplied.
    # This is the overclaim-prevention mechanism.
    d["claim_type"] = CLAIM_TYPE
    d["semantic_status"] = SEMANTIC_STATUS

    # Ensure boundary text is present and carries the contract.
    if not d.get("boundary") or "does not prove security" not in str(d.get("boundary", "")):
        d["boundary"] = DEFAULT_BOUNDARIES[0]

    # Basic shape validation (minimal but sufficient for Tier 1)
    required = ("surface", "path", "line", "marker_type", "marker")
    for k in required:
        if k not in d:
            raise ValueError(f"Signal missing required field: {k}")

    # line must be int (or coercible)
    try:
        d["line"] = int(d["line"])
    except (TypeError, ValueError):
        raise ValueError("Signal 'line' must be integer")

    return d


def build_static_signals_artifact(
    signals: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    """Build the canonical static_signals.json document.

    Returns exactly the shape specified in the bead (empty case + populated).
    Always enforces:
        - schema_version = "1.0.0"
        - claim_type = "heuristic_signal"
        - semantic_status = "not_validated"
        - boundaries contain the exact required disclaimer text
    """
    if signals is None:
        signals = []

    normalized: List[Dict[str, Any]] = [_normalize_signal(s) for s in signals]

    # Compute summary (pure, deterministic)
    by_surface: Dict[str, int] = {}
    by_marker_type: Dict[str, int] = {}
    for s in normalized:
        surf = s["surface"]
        mt = s["marker_type"]
        by_surface[surf] = by_surface.get(surf, 0) + 1
        by_marker_type[mt] = by_marker_type.get(mt, 0) + 1

    summary = {
        "total_signals": len(normalized),
        "by_surface": by_surface,
        "by_marker_type": by_marker_type,
    }

    artifact: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "claim_type": CLAIM_TYPE,
        "semantic_status": SEMANTIC_STATUS,
        "signals": normalized,
        "summary": summary,
        "boundaries": list(DEFAULT_BOUNDARIES),  # copy
    }

    # Deterministic JSON round-trippability (no extra keys, stable order in practice)
    # We do not sort keys here; callers that need canonical bytes can do json.dumps(..., sort_keys=True)
    return artifact


# Convenience re-exports for consumers that want the canonical names
__all__ = [
    "build_static_signals_artifact",
    "extract_edge_function_markers",
    "extract_package_config_markers",
    "extract_supabase_migration_markers",
    "make_signal_record",
    "SignalRecord",
    "CLAIM_TYPE",
    "SEMANTIC_STATUS",
    "SCHEMA_VERSION",
    "DEFAULT_BOUNDARIES",
]
