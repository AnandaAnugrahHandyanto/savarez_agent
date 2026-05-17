"""
Session-level automatic skill preloading.

Analyzes the current execution context (project files, working directory) at
session initialization time and automatically loads relevant skills — without
requiring manual ``--skills`` flags or model-level skill selection.

This closes the gap between Hermes's stated capabilities and its actual
behaviour: skills exist in ``~/.hermes/skills/`` but are never loaded at
session start unless explicitly requested.

Architecture
------------
::

    Session init (AIAgent.__init__ / run_conversation)
        │
        ▼
    _analyze_session_context(cwd)        ← deterministic, no LLM call
        │
        ├─ Phase 1: Project-file scan
        │     CONTEXT.md  → extract project.type / skill hints
        │     AGENTS.md   → load skills declared under ``agent:`` section
        │     .cursorrules / package.json / Dockerfile → infer project type
        │
        ├─ Phase 2: Skill-condition matching
        │     evaluate each installed skill's ``conditions`` frontmatter
        │     deterministic boolean match → add to preload list
        │
        └─ returns list[str] of skill identifiers

    Caller merges the list with explicit ``--skills`` preloads and calls
    ``build_preloaded_skills_prompt()`` → injects content into system prompt.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Project-type → skill-identifier mappings
# These are the "terminal nodes" that Phase 2 expands into full skill names.
# ---------------------------------------------------------------------------

_PROJECT_TYPE_TO_SKILLS: dict[str, list[str]] = {
    "research": ["arxiv", "knowledge-logging"],
    "dev": ["systematic-debugging", "test-driven-development"],
    "ml": ["llama-cpp", "gguf-quantization", "fine-tuning-with-trl"],
    "frontend": ["claude-design"],
    "docker": ["gitlab-ci-docker-build-push"],
    "ci": ["gitlab-ci-k8s-gitops-pattern"],
}


def _read_text_file(path: Path, limit: int = 4096) -> str:
    """Read at most ``limit`` bytes from a text file, ignoring errors."""
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:limit]
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Phase 1 – project-file scanner
# ---------------------------------------------------------------------------

def _scan_project_files(cwd: Path) -> dict[str, set[str]]:
    """
    Scan ``cwd`` for project-intent files and return a dict of signals.

    Returns:
        {
            "project_types": {"research", "dev", ...},
            "declared_skills": {"skill-name-1", ...},   # from AGENTS.md
            "file_hints": {"docker", "torch", ...},
        }
    """
    signals: dict[str, set[str]] = {
        "project_types": set(),
        "declared_skills": set(),
        "file_hints": set(),
    }

    if not cwd or not cwd.is_dir():
        return signals

    try:
        entries = {p.name for p in cwd.iterdir()}
    except Exception:
        return signals

    # ----- CONTEXT.md -------------------------------------------------------
    ctx = cwd / "CONTEXT.md"
    if ctx.exists():
        text = _read_text_file(ctx)
        # project.type: research|dev|ml|frontend|...
        for m in re.finditer(r"project\.type:\s*(\w+)", text):
            pt = m.group(1).strip().lower()
            if pt in _PROJECT_TYPE_TO_SKILLS:
                signals["project_types"].add(pt)
        # explicit skill hints: ``skill: <name>``
        for m in re.finditer(r"(?:skill|use_skill):\s*(\S+)", text):
            sig = m.group(1).strip().lower()
            if sig:
                signals["declared_skills"].add(sig)

    # ----- AGENTS.md --------------------------------------------------------
    agents = cwd / "AGENTS.md"
    if agents.exists():
        text = _read_text_file(agents)
        # agent: <name> blocks with skills: [...]
        in_agent_block = False
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("agent:"):
                in_agent_block = True
                continue
            if in_agent_block:
                if re.match(r"^\w+:", line):  # new top-level key
                    in_agent_block = False
                if line.startswith("skills:"):
                    # skills: [skill-a, skill-b, ...]
                    for m in re.finditer(r"(\w[\w-]*)", line):
                        signals["declared_skills"].add(m.group(1).lower())
        # Also match bare ``- skill: <name>`` list items
        for m in re.finditer(r"^\s*-\s*skill:\s*(\S+)", text, re.MULTILINE):
            signals["declared_skills"].add(m.group(1).strip().lower())

    # ----- .cursorrules ------------------------------------------------------
    if ".cursorrules" in entries:
        signals["file_hints"].add("cursorrules")

    # ----- package.json ------------------------------------------------------
    pkg = cwd / "package.json"
    if pkg.exists():
        text = _read_text_file(pkg)
        if '"react"' in text or '"next"' in text:
            signals["project_types"].add("frontend")
        if '"torch"' in text or '"tensorflow"' in text:
            signals["project_types"].add("ml")

    # ----- Dockerfile ---------------------------------------------------------
    if "Dockerfile" in entries or "Dockerfile.dev" in entries:
        signals["file_hints"].add("docker")
        signals["project_types"].add("docker")

    # ----- *.py files --------------------------------------------------------
    # Heuristic: if any .py file in cwd root imports a known heavy framework,
    # tag the project type.  Full recursive scan would be too slow.
    for py_file in cwd.glob("*.py"):
        text = _read_text_file(py_file, limit=512)
        if "import torch" in text or "from torch" in text:
            signals["project_types"].add("ml")
            break
        if "import tensorflow" in text or "import keras" in text:
            signals["project_types"].add("ml")
            break
        if "import fastapi" in text or "import flask" in text:
            signals["file_hints"].add("api")
            break

    return signals


# ---------------------------------------------------------------------------
# Phase 2 – skill-condition matcher
# ---------------------------------------------------------------------------

def _match_skill_conditions(
    skills_dir: Path,
    signals: dict[str, set[str]],
) -> list[str]:
    """
    Evaluate every installed skill's ``conditions`` frontmatter against
    ``signals`` and return an ordered list of matching skill identifiers.

    ``conditions`` format (in SKILL.md frontmatter)::

        conditions:
          - type: project_file
            patterns: ["*.md", "*.py"]
            content_keywords: ["bug", "debug", "fix", "error"]
          - type: project_type
            types: ["research", "dev"]
          - type: file_hint
            hints: ["docker", "cursorrules"]

    A skill matches if ANY of its conditions is satisfied.
    """
    from functools import lru_cache

    @lru_cache(maxsize=1)
    def _all_skill_dirs() -> list[Path]:
        """Discover all skill directories once."""
        dirs = []
        if skills_dir and skills_dir.is_dir():
            dirs.append(skills_dir)
        # Check external skill dirs from config
        try:
            from hermes_cli.config import load_cli_config
            cfg = load_cli_config()
            external = cfg.get("skills", {}).get("external_dirs", [])
            for d in external:
                p = Path(d).expanduser().resolve()
                if p.is_dir() and p not in dirs:
                    dirs.append(p)
        except Exception:
            pass
        return dirs

    matched: list[str] = []
    seen: set[str] = set()

    for skill_dir in _all_skill_dirs():
        try:
            for entry in skill_dir.iterdir():
                if not entry.is_dir():
                    continue
                skill_name = entry.name
                if skill_name in seen:
                    continue
                seen.add(skill_name)

                skill_md = entry / "SKILL.md"
                if not skill_md.exists():
                    continue

                text = _read_text_file(skill_md, limit=8192)

                # Extract YAML frontmatter
                if not text.startswith("---"):
                    continue
                end = text.find("\n---\n", 3)
                if end == -1:
                    continue
                frontmatter = text[3:end]

                # Parse a minimal subset of YAML: ``key: value`` and list items
                in_conditions = False
                condition_blocks: list[dict] = []
                current_block: dict = {}
                in_list_item = False

                for line in frontmatter.splitlines():
                    stripped = line.strip()

                    # Enter conditions block
                    if stripped == "conditions:":
                        in_conditions = True
                        continue

                    if in_conditions:
                        # Check for new top-level key (end of conditions)
                        if re.match(r"^\w+:", stripped) and not stripped.startswith("-"):
                            in_conditions = False

                        # List item
                        if stripped.startswith("- type:"):
                            if current_block:
                                condition_blocks.append(current_block)
                            current_block = {"type": stripped.split(":", 1)[1].strip()}
                            in_list_item = True
                        elif in_list_item and stripped.startswith("patterns:"):
                            vals = re.findall(r"\[([^\]]+)\]", stripped)
                            current_block["patterns"] = []
                            for v in vals:
                                current_block["patterns"].extend(
                                    x.strip() for x in v.split(",")
                                )
                        elif in_list_item and stripped.startswith("content_keywords:"):
                            vals = re.findall(r"\[([^\]]+)\]", stripped)
                            current_block["content_keywords"] = []
                            for v in vals:
                                current_block["content_keywords"].extend(
                                    x.strip().strip('"').strip("'")
                                    for x in v.split(",")
                                )
                        elif in_list_item and stripped.startswith("types:"):
                            vals = re.findall(r"\[([^\]]+)\]", stripped)
                            current_block["types"] = [
                                x.strip() for x in vals[0].split(",")
                            ] if vals else []
                        elif in_list_item and stripped.startswith("hints:"):
                            vals = re.findall(r"\[([^\]]+)\]", stripped)
                            current_block["hints"] = [
                                x.strip() for x in vals[0].split(",")
                            ] if vals else []

                if current_block:
                    condition_blocks.append(current_block)

                # Evaluate conditions
                for cond in condition_blocks:
                    ctype = cond.get("type", "")
                    if ctype == "project_type":
                        types = set(cond.get("types", []))
                        if signals["project_types"] & types:
                            matched.append(skill_name)
                            break
                    elif ctype == "file_hint":
                        hints = set(cond.get("hints", []))
                        if signals["file_hints"] & hints:
                            matched.append(skill_name)
                            break
                    elif ctype == "project_file":
                        # project_file conditions require content scanning — skip in v1
                        # to keep startup fast and deterministic.
                        # Defer to v2 LLM-assisted fallback.
                        pass

        except Exception:
            continue

    return matched


# ---------------------------------------------------------------------------
# Phase 3 – public API
# ---------------------------------------------------------------------------

def _analyze_session_context(
    cwd: Optional[str | Path] = None,
) -> list[str]:
    """
    Analyze the session context and return an ordered list of skill identifiers
    that should be auto-preloaded.

    This function is deterministic — no LLM calls, only file I/O and pattern
    matching. It is safe to call on every new session without latency concerns.

    Args:
        cwd: Working directory to scan. Defaults to ``TERMINAL_CWD`` env var
              if not provided.

    Returns:
        List of skill identifiers (e.g. ``["arxiv", "knowledge-logging"]``).
        Empty list if no skills match the current context or if ``cwd`` is
        unavailable.
    """
    if cwd is None:
        cwd = os.getenv("TERMINAL_CWD")

    if not cwd:
        return []

    cwd_path = Path(cwd).expanduser().resolve()

    # Phase 1: gather signals
    signals = _scan_project_files(cwd_path)

    # If AGENTS.md declared skills explicitly, return those directly
    if signals["declared_skills"]:
        return sorted(signals["declared_skills"])

    # If project types found, map to skills
    if signals["project_types"]:
        result: list[str] = []
        for pt in signals["project_types"]:
            for skill in _PROJECT_TYPE_TO_SKILLS.get(pt, []):
                if skill not in result:
                    result.append(skill)
        if result:
            return result

    # Phase 2: condition-based matching
    try:
        from hermes_cli.config import get_skills_dir
        skills_dir = get_skills_dir()
    except Exception:
        skills_dir = Path.home() / ".hermes" / "skills"

    matched = _match_skill_conditions(skills_dir, signals)
    return matched


# ---------------------------------------------------------------------------
# Convenience: merge auto-preload with explicit CLI preloads
# ---------------------------------------------------------------------------

def merge_preloads(
    auto_preloads: list[str],
    explicit_preloads: list[str],
    max_auto: int = 5,
) -> list[str]:
    """
    Merge auto-discovered and explicitly-requested skill preloads.

    Priority: auto-preloads first (up to ``max_auto``), then explicit.
    Deduplication preserves first occurrence ordering.

    Args:
        auto_preloads: Skills discovered by ``_analyze_session_context()``.
        explicit_preloads: Skills passed via ``--skills`` CLI flag.
        max_auto: Maximum number of auto-preloads to include.

    Returns:
        Merged, deduplicated list of skill identifiers.
    """
    seen: set[str] = set()
    result: list[str] = []

    for s in auto_preloads[:max_auto]:
        if s and s not in seen:
            seen.add(s)
            result.append(s)

    for s in explicit_preloads:
        if s and s not in seen:
            seen.add(s)
            result.append(s)

    return result
