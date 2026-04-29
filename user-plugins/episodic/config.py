"""Configuration defaults for the Sidecar Episodic Memory system."""

from pathlib import Path

from hermes_constants import get_hermes_home


def load_config():
    from hermes_cli.config import load_config as _load_config

    return _load_config()

# ── Directories ──────────────────────────────────────────────────────────────
MEMORY_DIR = get_hermes_home() / "memory"
DB_PATH = MEMORY_DIR / "index.db"
SESSIONS_DIR = MEMORY_DIR / "sessions"
EPISODES_DIR = MEMORY_DIR / "episodes"
ENTITIES_DIR = MEMORY_DIR / "entities"
DAG_DIR = MEMORY_DIR / "dag"
HEALTH_FILE = MEMORY_DIR / "health.json"
CONFIG_FILE = MEMORY_DIR / "config.json"

# ── Extraction settings ─────────────────────────────────────────────────────
EXTRACT_BATCH_SIZE = 10        # turns per extraction pass
EXTRACT_TIMEOUT = 30           # seconds
EXTRACT_MODEL = "gpt-5.4-mini"
EXTRACT_PROVIDER = "openai-codex"
ENABLE_LLM_EXTRACTION = False  # disabled — using lightweight journal instead

# ── Journal settings ────────────────────────────────────────────────────────
JOURNAL_DIR = Path.home() / "wiki" / "session-recordings"
ENABLE_SESSION_JOURNAL = True

# ── Skill candidate settings ────────────────────────────────────────────────
ENABLE_SKILL_CANDIDATES = True
SKILL_CANDIDATE_MODE = "detect-only"
SKILL_CANDIDATE_AUTO_PUBLISH = False
SKILL_CANDIDATE_MIN_OCCURRENCES = 3
SKILL_CANDIDATE_REVIEW_LIMIT = 10
SKILL_CANDIDATE_SCAN_SOURCE = "jsonl"
SKILL_CANDIDATE_DRAFT_MODEL = ""

# ── Merge settings ──────────────────────────────────────────────────────────
MERGE_TIMEOUT = 60
MERGE_MODEL = "gpt-5.4"
MERGE_PROVIDER = "openai-codex"

# ── Compress settings ───────────────────────────────────────────────────────
COMPRESS_TIMEOUT = 60
COMPRESS_MODEL = "gpt-5.4"
COMPRESS_PROVIDER = "openai-codex"

# ── Wiki synthesis settings ─────────────────────────────────────────────────
WIKI_TIMEOUT = 120
WIKI_MODEL = "gpt-5.4"
WIKI_PROVIDER = "openai-codex"
WIKI_OUTPUT_DIR = Path.home() / "wiki" / "session-memory"


def _derive_extract_model(main_model: str) -> str:
    """Map the configured primary model to an extraction-friendly variant."""
    model = (main_model or "").strip()
    if not model:
        return EXTRACT_MODEL
    if model.startswith("gpt-5") and not model.endswith("-mini"):
        return f"{model}-mini"
    return model


def get_memory_model_settings(stage: str) -> tuple[str, str]:
    """Resolve provider/model for a memory pipeline stage.

    Uses the current main model/provider from config.yaml when available so the
    memory pipeline follows the active runtime instead of drifting on hardcoded
    slugs. Falls back to stage defaults when config is unavailable.
    """
    stage = (stage or "").strip().lower()
    stage_defaults = {
        "extract": (EXTRACT_PROVIDER, EXTRACT_MODEL),
        "merge": (MERGE_PROVIDER, MERGE_MODEL),
        "compress": (COMPRESS_PROVIDER, COMPRESS_MODEL),
        "wiki": (WIKI_PROVIDER, WIKI_MODEL),
    }
    default_provider, default_model = stage_defaults.get(stage, (WIKI_PROVIDER, WIKI_MODEL))

    try:
        cfg = load_config() or {}
    except Exception:
        cfg = {}

    model_cfg = cfg.get("model") if isinstance(cfg, dict) else {}
    main_provider = default_provider
    main_model = default_model
    if isinstance(model_cfg, dict):
        main_provider = (model_cfg.get("provider") or main_provider or "").strip() or default_provider
        main_model = (model_cfg.get("default") or main_model or "").strip() or default_model

    if stage == "extract":
        return main_provider, _derive_extract_model(main_model)
    if stage in {"merge", "compress", "wiki"}:
        return main_provider, main_model
    return default_provider, default_model


def get_skill_candidate_settings() -> dict:
    """Resolve user-facing feature flags for optional skill-candidate mining."""

    def _coerce_bool(value, default: bool) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off", ""}:
                return False
        return default

    def _coerce_int(value, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    try:
        cfg = load_config() or {}
    except Exception:
        cfg = {}

    mem_cfg = cfg.get("memory") if isinstance(cfg, dict) else {}
    if not isinstance(mem_cfg, dict):
        mem_cfg = {}
    episodic_cfg = mem_cfg.get("episodic")
    if not isinstance(episodic_cfg, dict):
        episodic_cfg = {}

    mode = str(episodic_cfg.get("skill_candidate_mode", SKILL_CANDIDATE_MODE)).strip().lower()
    if mode not in {"off", "detect-only", "draft"}:
        mode = SKILL_CANDIDATE_MODE

    scan_source = str(episodic_cfg.get("skill_candidate_scan_source", SKILL_CANDIDATE_SCAN_SOURCE)).strip().lower()
    if scan_source not in {"jsonl", "journal", "both"}:
        scan_source = SKILL_CANDIDATE_SCAN_SOURCE

    return {
        "enabled": _coerce_bool(episodic_cfg.get("skill_candidates_enabled", ENABLE_SKILL_CANDIDATES), ENABLE_SKILL_CANDIDATES),
        "mode": mode,
        "auto_publish": _coerce_bool(episodic_cfg.get("skill_candidate_auto_publish", SKILL_CANDIDATE_AUTO_PUBLISH), SKILL_CANDIDATE_AUTO_PUBLISH),
        "min_occurrences": _coerce_int(episodic_cfg.get("skill_candidate_min_occurrences", SKILL_CANDIDATE_MIN_OCCURRENCES), SKILL_CANDIDATE_MIN_OCCURRENCES),
        "review_limit": _coerce_int(episodic_cfg.get("skill_candidate_review_limit", SKILL_CANDIDATE_REVIEW_LIMIT), SKILL_CANDIDATE_REVIEW_LIMIT),
        "scan_source": scan_source,
        "draft_model": str(episodic_cfg.get("skill_candidate_draft_model", SKILL_CANDIDATE_DRAFT_MODEL)).strip(),
    }

# ── Context injection budget ────────────────────────────────────────────────
MAX_MEMORY_INJECTION_TOKENS = 2000
TOP_EPISODES = 3
TOP_ENTITIES = 3

# ── Health check ─────────────────────────────────────────────────────────────
HEALTH_CHECK_INTERVAL = 50     # turns between health checks

# ── Temporal & Quality (Phase 4) ────────────────────────────────────────────
STALENESS_THRESHOLD_DAYS = 30        # facts not confirmed in N days are stale
STALENESS_CHECK_SESSIONS = 10        # check staleness every N sessions
CONTRADICTION_CONFIDENCE = "medium"  # minimum confidence to flag contradictions
MAX_CONTRADICTIONS_REPORT = 10       # max contradictions to return per query
