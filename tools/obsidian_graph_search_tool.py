"""QMD semantic search paired with Obsidian graph expansion."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Mapping

from hermes_constants import get_hermes_home
from plugins.memory.obsidian_vault.graph import (
    build_note_lookup,
    expand_graph,
    slugify_path,
)
from plugins.memory.obsidian_vault.paths import load_provider_config, resolve_vault_root
from tools.registry import registry


OBSIDIAN_GRAPH_SEARCH_SCHEMA = {
    "name": "obsidian_graph_search",
    "description": (
        "Search QMD semantically for seed notes, then expand through the Obsidian note graph "
        "using wikilinks, backlinks, and optional shared tags. Use this for source-backed "
        "memory recall across the Hermes Memory Vault."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural-language search query for QMD semantic/hybrid retrieval.",
            },
            "collections": {
                "type": "array",
                "items": {"type": "string"},
                "description": "QMD collections to search. Defaults to hermes-memory.",
                "default": ["hermes-memory"],
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of semantic seed notes from QMD.",
                "default": 5,
            },
            "graph_depth": {
                "type": "integer",
                "description": "How many Obsidian graph hops to expand from semantic seeds.",
                "default": 1,
            },
            "max_neighbors": {
                "type": "integer",
                "description": "Maximum graph-neighbor notes to add beyond QMD seeds.",
                "default": 12,
            },
            "include_wikilinks": {
                "type": "boolean",
                "description": "Include notes linked from semantic seeds.",
                "default": True,
            },
            "include_backlinks": {
                "type": "boolean",
                "description": "Include notes that link back to semantic seeds.",
                "default": True,
            },
            "include_tag_neighbors": {
                "type": "boolean",
                "description": "Include notes sharing Obsidian tags with seeds. Off by default because tags can be broad.",
                "default": False,
            },
            "max_excerpt_chars": {
                "type": "integer",
                "description": "Maximum excerpt length per returned note.",
                "default": 700,
            },
        },
        "required": ["query"],
    },
}


def _load_config() -> dict[str, Any]:
    try:
        from hermes_cli.config import load_config

        cfg = load_config() or {}
        return cfg if isinstance(cfg, dict) else {}
    except Exception:
        return {}


def _resolve_tool_vault_root() -> Path | None:
    hermes_home = get_hermes_home()
    settings = _load_config()
    provider_cfg = load_provider_config(hermes_home)
    if provider_cfg:
        merged = dict(settings)
        merged.update(provider_cfg)
    else:
        merged = settings

    root = resolve_vault_root(merged, hermes_home=hermes_home)
    if root:
        return root

    fallback = Path(os.environ.get("OBSIDIAN_VAULT_PATH", "") or "~/Documents/Hermes Memory Vault").expanduser().resolve()
    if fallback.exists() and fallback.is_dir():
        return fallback
    return None


def _parse_json_from_qmd(output: str) -> Any:
    stripped = output.strip()
    if not stripped:
        raise ValueError("qmd returned no output")
    for opener, closer in (("[", "]"), ("{", "}")):
        start = stripped.find(opener)
        end = stripped.rfind(closer)
        if start != -1 and end != -1 and end > start:
            return json.loads(stripped[start : end + 1])
    raise ValueError("qmd output did not contain JSON")


def _run_qmd_query(query: str, collections: list[str], limit: int) -> list[dict[str, Any]]:
    qmd = shutil.which("qmd") or "/opt/homebrew/bin/qmd"
    cmd = [qmd, "query", query, "--json", "-n", str(max(1, min(limit, 25)))]
    for collection in collections:
        if collection:
            cmd.extend(["-c", str(collection)])
    last_error = ""
    for attempt in range(2):
        try:
            proc = subprocess.run(
                cmd,
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=90,
            )
        except (InterruptedError, OSError) as exc:
            last_error = str(exc)
            if attempt == 0 and "Interrupted" in last_error:
                continue
            raise RuntimeError(f"qmd query failed: {last_error}") from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("qmd query timed out") from exc

        output = proc.stdout or ""
        if proc.returncode == 0:
            data = _parse_json_from_qmd(output)
            if isinstance(data, list):
                return [item for item in data if isinstance(item, dict)]
            raise RuntimeError("qmd JSON response was not a list")
        last_error = output.strip() or f"exit code {proc.returncode}"
        if attempt == 0 and "Interrupted system call" in last_error:
            continue
        raise RuntimeError(f"qmd query failed: {last_error}")
    raise RuntimeError(f"qmd query failed: {last_error}")


def _strip_qmd_uri(file_value: str, collections: list[str]) -> str:
    text = str(file_value or "").strip()
    if text.startswith("qmd://"):
        rest = text[len("qmd://") :]
        if "/" in rest:
            collection, path = rest.split("/", 1)
            if not collections or collection in collections:
                return path
            return path
    return text


def _seed_path_from_qmd_result(
    result: Mapping[str, Any],
    vault_root: Path,
    lookup: Mapping[str, str],
    collections: list[str],
) -> str | None:
    raw_candidates = [
        result.get("file"),
        result.get("path"),
        result.get("filepath"),
        result.get("url"),
    ]
    for raw in raw_candidates:
        if not raw:
            continue
        candidate = _strip_qmd_uri(str(raw), collections)
        candidate = candidate.split(":", 1)[0] if candidate.startswith("#") else candidate
        keys = [candidate, candidate.lower(), slugify_path(candidate)]
        if candidate.endswith(".md"):
            keys.append(candidate[:-3])
            keys.append(slugify_path(candidate[:-3]))
        for key in keys:
            match = lookup.get(key)
            if match:
                return match
        direct = Path(candidate)
        if direct.is_absolute():
            try:
                resolved = direct.resolve()
                if vault_root in resolved.parents or resolved == vault_root:
                    return resolved.relative_to(vault_root).as_posix()
            except Exception:
                pass
    return None


def _bool_arg(args: Mapping[str, Any], key: str, default: bool) -> bool:
    value = args.get(key, default)
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off"}
    return bool(value)


def obsidian_graph_search_tool(**kwargs) -> str:
    args = kwargs.get("args") if "args" in kwargs else kwargs
    if not isinstance(args, Mapping):
        args = {}
    query = str(args.get("query") or "").strip()
    if not query:
        return json.dumps({"error": "query is required"})

    collections_raw = args.get("collections") or ["hermes-memory"]
    if isinstance(collections_raw, str):
        collections = [collections_raw]
    else:
        collections = [str(item) for item in collections_raw if str(item).strip()]
    if not collections:
        collections = ["hermes-memory"]

    limit = max(1, min(int(args.get("limit") or 5), 25))
    graph_depth = max(0, min(int(args.get("graph_depth") or 1), 3))
    max_neighbors = max(0, min(int(args.get("max_neighbors") or 12), 50))
    max_excerpt_chars = max(120, min(int(args.get("max_excerpt_chars") or 700), 2500))

    vault_root = _resolve_tool_vault_root()
    if not vault_root:
        return json.dumps({"error": "Obsidian vault path is not configured or does not exist"})

    try:
        qmd_results = _run_qmd_query(query, collections, limit)
    except Exception as exc:
        return json.dumps({"error": str(exc), "query": query, "collections": collections})

    lookup = build_note_lookup(vault_root)
    seed_scores: dict[str, float] = {}
    seeds: list[dict[str, Any]] = []
    for item in qmd_results:
        rel = _seed_path_from_qmd_result(item, vault_root, lookup, collections)
        if not rel:
            continue
        score = float(item.get("score") or 0.0)
        seed_scores[rel] = max(seed_scores.get(rel, 0.0), score)
        seeds.append(
            {
                "path": rel,
                "score": score,
                "title": item.get("title") or Path(rel).stem,
                "docid": item.get("docid"),
                "qmd_file": item.get("file") or item.get("path"),
                "snippet": item.get("snippet"),
            }
        )

    expanded = expand_graph(
        vault_root,
        seed_scores,
        depth=graph_depth,
        max_neighbors=max_neighbors,
        include_wikilinks=_bool_arg(args, "include_wikilinks", True),
        include_backlinks=_bool_arg(args, "include_backlinks", True),
        include_tag_neighbors=_bool_arg(args, "include_tag_neighbors", False),
        max_excerpt_chars=max_excerpt_chars,
    )

    payload = {
        "query": query,
        "collections": collections,
        "vault_root": str(vault_root),
        "seed_count": len(seed_scores),
        "qmd_result_count": len(qmd_results),
        "results": [
            {
                "path": note.path,
                "title": note.title,
                "score": round(note.score, 4),
                "depth": note.depth,
                "reasons": sorted(note.reasons),
                "snippet": note.snippet,
            }
            for note in expanded
        ],
        "seeds": seeds[:limit],
    }
    return json.dumps(payload, ensure_ascii=False)


def _handle_obsidian_graph_search(args: dict, **kwargs) -> str:
    return obsidian_graph_search_tool(args=args)


def _check_obsidian_graph_search() -> bool:
    return bool((shutil.which("qmd") or Path("/opt/homebrew/bin/qmd").exists()) and _resolve_tool_vault_root())


registry.register(
    name="obsidian_graph_search",
    toolset="memory_graph",
    schema=OBSIDIAN_GRAPH_SEARCH_SCHEMA,
    handler=_handle_obsidian_graph_search,
    check_fn=_check_obsidian_graph_search,
    emoji="🕸️",
    max_result_size_chars=50_000,
)
