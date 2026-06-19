#!/usr/bin/env python3
"""
Resource limits for terminal and execute_code sandboxes (Layer 2 Defence).

Provides:
1. Heavy import detection — warns when numpy/pandas/etc are imported
2. Python script resource limit injection — sets memory/time caps via psutil
3. Memory estimation for execute_code scripts — estimates before execution

Windows uses psutil; Linux/macOS uses resource module directly.
"""

import logging
import os
import platform
import re
import sys
from typing import List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configurable thresholds (overridable via env vars at import time)
# ---------------------------------------------------------------------------

def _parse_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        logger.warning("Invalid value for %s: %r. Falling back to %d.", name, raw, default)
        return default


# Memory limit in MB for terminal-invoked Python scripts (0 = no limit).
TERMINAL_MEMORY_LIMIT_MB: int = _parse_int_env("HERMES_TERMINAL_MEMORY_LIMIT_MB", 8192)

# Memory warning threshold in MB — warn if estimated memory exceeds this.
MEMORY_WARNING_THRESHOLD_MB: int = _parse_int_env("HERMES_MEMORY_WARNING_MB", 4096)

# Memory limit in MB for execute_code subprocesses (0 = no limit).
EXECUTE_CODE_MEMORY_LIMIT_MB: int = _parse_int_env("HERMES_EXECUTE_CODE_MEMORY_LIMIT_MB", 4096)

# Runtime cap for Python scripts invoked via terminal (seconds; 0 = no override).
TERMINAL_PYTHON_TIMEOUT_DEFAULT: int = _parse_int_env("HERMES_TERMINAL_PYTHON_TIMEOUT_S", 600)


# ---------------------------------------------------------------------------
# Heavy import library list
# ---------------------------------------------------------------------------
# Libraries known to allocate significant memory on import or during
# typical usage.  Detection is regex-based so it works on piped heredocs,
# `python -c "import ..."`, and file-based invocations.
HEAVY_IMPORT_LIBRARIES: Set[str] = {
    # data science / ML
    "numpy", "pandas", "scipy", "scikit-learn", "sklearn",
    "tensorflow", "torch", "pytorch", "jax", "mxnet",
    "xgboost", "lightgbm", "catboost",
    # image / video
    "opencv", "cv2", "pillow", "PIL", "matplotlib", "seaborn",
    "plotly", "bokeh", "holoviews", "altair",
    # NLP / transformers
    "transformers", "datasets", "tokenizers", "spacy", "nltk",
    "gensim", "sentence-transformers", "huggingface_hub",
    # big data / DB
    "polars", "dask", "pyspark", "ray", "modin",
    "duckdb", "sqlalchemy",
    # scientific
    "astropy", "biopython", "networkx",
    # other heavy
    "statsmodels", "prophet", "pmdarima",
}

# Regex to find Python-style imports in shell commands.
# Matches: import X, from X import Y, python -c "import X", and heredoc patterns.
_PYTHON_IMPORT_RE = re.compile(
    r"(?:(?:^|[;&|`\s(])python[23]?(?:\.[0-9]+)?\s+(?:-c\s+[\"']|(?:<<['\"]?PY['\"]?\s*\n)))?"
    r"(?:import\s+(\w[\w.]*)|from\s+(\w[\w.]*)\s+import)",
    re.MULTILINE | re.IGNORECASE,
)


def detect_heavy_imports(command: str) -> Tuple[List[str], str]:
    """Check *command* for imports of heavy-memory libraries.

    Returns:
        (detected_libs, warning_message).  *warning_message* is empty when
        nothing is detected.
    """
    detected: List[str] = []
    warning = ""

    for match in _PYTHON_IMPORT_RE.finditer(command):
        module = (match.group(1) or match.group(2) or "").lower()
        if not module:
            continue
        # Normalize: pandas.core.common -> pandas
        top_level = module.split(".")[0]
        if top_level in HEAVY_IMPORT_LIBRARIES and top_level not in detected:
            detected.append(top_level)

    if detected:
        libs_str = ", ".join(sorted(set(detected)))
        warning = (
            f"[RESOURCE WARNING] Detected heavy import(s): {libs_str}. "
            f"These libraries may consume significant memory. "
            f"If you encounter OOM errors, reduce data size or use a sampled subset."
        )
        logger.debug("Heavy imports detected in command: %s", libs_str)

    return detected, warning


def _is_python_command(command: str) -> bool:
    """Heuristic: does *command* look like a Python invocation?"""
    stripped = command.strip()
    if not stripped:
        return False
    return bool(re.match(
        r"^(?:.*\s)?python[23]?(?:\.[0-9]+)?(?:\s|$)",
        stripped,
    ))


def _get_resource_limit_code(memory_mb: int) -> str:
    """Return a code snippet that sets a process memory limit.

    Uses psutil on all platforms for consistency (the resource module on
    Linux does RLIMIT_AS which also caps mmap, often breaking numpy/pandas
    at unexpectedly low limits).
    """
    if memory_mb <= 0:
        return ""

    return (
        "import psutil, os, sys\n"
        f"_hermes_mem_limit = {memory_mb} * 1024 * 1024\n"
        "try:\n"
        "    _hermes_proc = psutil.Process(os.getpid())\n"
        "    _hermes_proc.memory_limit(_hermes_mem_limit)\n"
        "except Exception as _e:\n"
        "    print(f'[resource_limits] Could not set memory limit ({_e})', file=sys.stderr)\n"
    )


def inject_resource_limits(command: str, memory_mb: int = 0) -> str:
    """If *command* invokes Python via ``-c``, inject a resource-limit preamble.

    Only injects for ``python -c \"...\"`` patterns — the most common pattern
    for LLM-generated Python.  For ``python script.py`` or ``python -m``
    invocations, the limit header cannot be safely injected without wrapping
    the script; those commands pass through unchanged (the heavy-import
    warning in ``detect_heavy_imports`` still fires).

    Returns the possibly-modified command string.
    """
    if memory_mb <= 0:
        return command

    if not _is_python_command(command):
        return command

    preamble = _get_resource_limit_code(memory_mb)
    if not preamble:
        return command

    # Idempotency: don't inject twice.
    if "_hermes_mem_limit" in command:
        return command

    # Only inject into `python -c "..."` invocations.
    # Capture: <prefix>python<version> -c <quote><code...>
    m = re.match(
        r'^((?:.*?)\bpython[23]?(?:\.[0-9]+)?\s+-c\s+)(["\'])(.*)',
        command,
        re.DOTALL | re.IGNORECASE,
    )
    if m:
        # python -c "original code..." → python -c "preamble\noriginal code..."
        prefix = m.group(1)
        quote = m.group(2)
        body = m.group(3)
        injected = f'{prefix}{quote}{preamble}{body}'
        logger.debug("Injected resource limits into python -c command")
        return injected

    # For `python script.py` or `python -m module`: pass through unchanged.
    # The pre-exec subprocess doesn't give us a way to inject per-process
    # resource limits without wrapping the entire invocation, which would
    # break argument quoting semantics.  The heavy-import warning still fires.
    logger.debug("Resource limit injection skipped (not a -c invocation)")
    return command


# ---------------------------------------------------------------------------
# Memory estimation for execute_code scripts
# ---------------------------------------------------------------------------

# Heuristic multipliers (bytes per unit) for common data patterns.
# Very rough — only useful as a warning, not a hard gate.
_ESTIMATION_PATTERNS = [
    # numpy/pandas: ndarray, DataFrame with N rows × M cols × 8 bytes (float64)
    (re.compile(r'(?:np\.(?:zeros|ones|empty|full|arange)|numpy\.(?:zeros|ones|empty|full|arange))\s*\(\s*(\d[\d_]*)\s*[,)]', re.I), 8),
    (re.compile(r'pd\.(?:read_csv|read_excel|read_parquet|read_json|read_sql|DataFrame)\s*\('), 100_000_000),  # assume ~100MB for any DataFrame op
    # torch: tensor of given size
    (re.compile(r'torch\.(?:zeros|ones|empty|rand|randn|tensor)\s*\(\s*(\d[\d_]*)\s*[,)]', re.I), 4),
    # open with 'rb' for potentially large files
    (re.compile(r'open\s*\(\s*[\"\'](.+?)[\"\']\s*,\s*[\"\']rb[\"\']'), 50_000_000),  # assume ~50MB for binary files
    # dlopen / import of heavy modules
    (re.compile(r'(?:import|from)\s+(tensorflow|torch|transformers)\b'), 500_000_000),  # 500MB for ML frameworks
]


def estimate_memory(code: str) -> Tuple[int, str]:
    """Crude heuristic memory estimator for Python code.

    Scans for known heavy patterns and returns (estimated_bytes, description).
    This is NOT a precise measurement — it's a warning system.
    """
    total_estimate = 0
    reasons: List[str] = []

    for pattern, bytes_per_unit in _ESTIMATION_PATTERNS:
        for m in pattern.finditer(code):
            if m.groups():
                try:
                    multiplier = int(m.group(1).replace("_", ""))
                    est = multiplier * bytes_per_unit
                except (ValueError, IndexError):
                    est = bytes_per_unit
            else:
                est = bytes_per_unit
            total_estimate += est
            if est >= 10_000_000:  # only report estimates >= 10MB
                reasons.append(f"~{est // 1_000_000}MB from {m.group(0)[:60]}")

    if reasons:
        reasons_str = "; ".join(reasons[:5])  # cap at 5
        if len(reasons) > 5:
            reasons_str += f" (+{len(reasons) - 5} more)"
    else:
        reasons_str = "no specific patterns detected"

    return total_estimate, reasons_str


def build_memory_warning(estimated_bytes: int, threshold_mb: int) -> str:
    """Return a human-readable memory warning string, or empty if under threshold."""
    if estimated_bytes == 0:
        return ""
    estimated_mb = estimated_bytes // 1_000_000
    if estimated_mb >= threshold_mb:
        return (
            f"[RESOURCE WARNING] Estimated memory usage: ~{estimated_mb}MB. "
            f"This exceeds the warning threshold of {threshold_mb}MB. "
            f"Consider reducing data size or using a sampled subset."
        )
    if estimated_mb > 0:
        return (
            f"[RESOURCE INFO] Estimated memory usage: ~{estimated_mb}MB "
            f"(threshold: {threshold_mb}MB)."
        )
    return ""


def get_psutil_memory_limit_bytes(memory_mb: int) -> Optional[int]:
    """Return the memory limit in bytes that psutil can enforce.

    Returns None if psutil is unavailable or memory_mb <= 0.
    """
    if memory_mb <= 0:
        return None
    try:
        import psutil  # noqa: F401  — already imported at module level for clarity
        return memory_mb * 1024 * 1024
    except ImportError:
        logger.debug("psutil not available — memory limits not enforced")
        return None
