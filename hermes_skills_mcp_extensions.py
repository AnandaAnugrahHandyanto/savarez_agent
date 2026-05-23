"""
Extended MCP tools for Hermes fleet context.

Import and register these alongside the base hermes_skills_mcp tools.
These provide consolidated session-start context and health summaries.
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _resolve_agents_dir() -> Optional[Path]:
    """Resolve the agents directory using the standard priority chain."""
    if env := os.environ.get("HERMES_AGENTS_DIR"):
        p = Path(env)
        if p.is_dir():
            return p
    if env := os.environ.get("HERMES_REPO"):
        p = Path(env) / "agents"
        if p.is_dir():
            return p
    home = os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes"))
    p = Path(home) / "hermes-agent" / "agents"
    if p.is_dir():
        return p
    return None


def _resolve_artifacts_dir() -> Optional[Path]:
    """Resolve the artifacts/ops directory."""
    if env := os.environ.get("HERMES_REPO"):
        p = Path(env) / "artifacts" / "ops"
        if p.is_dir():
            return p
    home = os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes"))
    p = Path(home) / "hermes-agent" / "artifacts" / "ops"
    if p.is_dir():
        return p
    return None


def _resolve_learnings_dir() -> Optional[Path]:
    """Resolve the .learnings directory."""
    if env := os.environ.get("HERMES_REPO"):
        p = Path(env) / ".learnings"
        if p.is_dir():
            return p
    return None


def _read_json_safe(path: Path) -> Optional[Dict]:
    """Read a JSON file, returning None on any error."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _read_text_safe(path: Path, max_bytes: int = 50000) -> Optional[str]:
    """Read a text file up to max_bytes, returning None on error."""
    try:
        content = path.read_text(encoding="utf-8")
        return content[:max_bytes]
    except OSError:
        return None


def _parse_heartbeat_age(agents_dir: Path, agent_name: str) -> Optional[float]:
    """Return hours since last heartbeat update, or None if unavailable."""
    hb = agents_dir / agent_name / "HEARTBEAT.md"
    if not hb.exists():
        return None
    try:
        mtime = hb.stat().st_mtime
        return (time.time() - mtime) / 3600.0
    except OSError:
        return None


def fleet_context_snapshot() -> Dict[str, Any]:
    """
    Single-call session bootstrap: agents registry, heartbeat status,
    HOT-tier learnings, latest operational state, and held spec ledger.

    Replaces the 5-call session-start checklist with one consolidated response.
    """
    result: Dict[str, Any] = {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "agents": None,
        "heartbeat_summary": None,
        "learnings_hot": None,
        "latest_state": None,
        "held_spec_ledger": None,
        "errors": [],
    }

    # --- Agents registry ---
    agents_dir = _resolve_agents_dir()
    if agents_dir:
        registry_path = agents_dir / "AGENT_REGISTRY.json"
        registry = _read_json_safe(registry_path)
        if registry:
            result["agents"] = {
                "total": len(registry),
                "registry": registry,
            }
        else:
            result["errors"].append("AGENT_REGISTRY.json not found or invalid")

        # --- Heartbeat summary ---
        heartbeats = {}
        stale = []
        if registry:
            for name in registry:
                age_hours = _parse_heartbeat_age(agents_dir, name)
                if age_hours is not None:
                    heartbeats[name] = round(age_hours, 1)
                    if age_hours > 48:
                        stale.append({"name": name, "hours_since_heartbeat": round(age_hours, 1)})
        result["heartbeat_summary"] = {
            "stale_agents": stale,
            "stale_count": len(stale),
            "total_with_heartbeat": len(heartbeats),
        }
    else:
        result["errors"].append("agents directory not found")

    # --- Learnings (HOT tier) ---
    learnings_dir = _resolve_learnings_dir()
    if learnings_dir:
        memory_path = learnings_dir / "memory.md"
        content = _read_text_safe(memory_path)
        if content:
            lines = content.splitlines()
            result["learnings_hot"] = {
                "content": content,
                "line_count": len(lines),
                "at_cap": len(lines) >= 100,
            }
        else:
            result["errors"].append(".learnings/memory.md not found or empty")
    else:
        result["errors"].append(".learnings directory not found")

    # --- Knowledge layer: latest_state ---
    artifacts_dir = _resolve_artifacts_dir()
    if artifacts_dir:
        state_path = artifacts_dir / "knowledge_layer" / "latest_state.json"
        state = _read_json_safe(state_path)
        if state:
            result["latest_state"] = state
        else:
            # Try markdown fallback
            state_md = artifacts_dir / "knowledge_layer" / "latest_state.md"
            md_content = _read_text_safe(state_md)
            if md_content:
                result["latest_state"] = {"format": "markdown", "content": md_content}
            else:
                result["errors"].append("latest_state not found (tried .json and .md)")

        # --- Held spec ledger ---
        held_path = artifacts_dir / "held_spec_ledger" / "latest.json"
        held = _read_json_safe(held_path)
        if held:
            result["held_spec_ledger"] = held
        else:
            held_md = artifacts_dir / "held_spec_ledger" / "latest.md"
            md_content = _read_text_safe(held_md)
            if md_content:
                result["held_spec_ledger"] = {"format": "markdown", "content": md_content}
            else:
                result["errors"].append("held_spec_ledger not found")
    else:
        result["errors"].append("artifacts/ops directory not found")

    if not result["errors"]:
        del result["errors"]

    return result


def agent_health_summary() -> Dict[str, Any]:
    """
    Quick health check returning only actionable anomalies:
    stale agents, missed crons, active contradictions, and freeze status.

    Use this when you need a fast "is anything broken?" answer without
    loading the full registry.
    """
    result: Dict[str, Any] = {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "status": "healthy",  # overridden if issues found
        "stale_agents": [],
        "contradiction_count": 0,
        "held_spec_count": 0,
        "freeze_active": None,
        "issues": [],
    }

    # --- Stale agents ---
    agents_dir = _resolve_agents_dir()
    if agents_dir:
        registry_path = agents_dir / "AGENT_REGISTRY.json"
        registry = _read_json_safe(registry_path)
        if registry:
            for name, meta in registry.items():
                if meta.get("retired") or meta.get("suppressed"):
                    continue
                age = _parse_heartbeat_age(agents_dir, name)
                if age is not None and age > 48:
                    result["stale_agents"].append({
                        "name": name,
                        "hours_stale": round(age, 1),
                        "lane": meta.get("lane", "?"),
                    })
            if result["stale_agents"]:
                result["status"] = "degraded"
                result["issues"].append(
                    f"{len(result['stale_agents'])} agent(s) stale (>48h without heartbeat)"
                )

    # --- Contradictions ---
    artifacts_dir = _resolve_artifacts_dir()
    if artifacts_dir:
        contradiction_path = artifacts_dir / "contradiction_ledger" / "latest.md"
        if contradiction_path.exists():
            content = _read_text_safe(contradiction_path)
            if content:
                # Count "hard" contradictions (lines starting with "- HARD:" or similar)
                hard = sum(1 for line in content.splitlines()
                          if "hard" in line.lower() and line.strip().startswith("-"))
                possible = sum(1 for line in content.splitlines()
                              if "drift" in line.lower() and line.strip().startswith("-"))
                result["contradiction_count"] = hard + possible
                if hard > 0:
                    result["status"] = "degraded"
                    result["issues"].append(f"{hard} hard contradiction(s) detected")

        # --- Held specs ---
        held_path = artifacts_dir / "held_spec_ledger" / "latest.json"
        held = _read_json_safe(held_path)
        if held:
            if isinstance(held, list):
                result["held_spec_count"] = len(held)
            elif isinstance(held, dict):
                result["held_spec_count"] = len(held)

        # --- Freeze status from latest_state ---
        state_path = artifacts_dir / "knowledge_layer" / "latest_state.json"
        state = _read_json_safe(state_path)
        if state:
            # Look for freeze indicators
            freeze = state.get("architecture_freeze") or state.get("freeze")
            if freeze:
                result["freeze_active"] = freeze
            elif "freeze" in json.dumps(state).lower():
                result["freeze_active"] = "possible (check latest_state manually)"

    if not result["issues"]:
        del result["issues"]

    return result


def knowledge_query(question: str) -> Dict[str, Any]:
    """
    Query the knowledge graph with a natural language question.

    Loads nodes.jsonl and edges.jsonl from the knowledge graph directory,
    performs keyword matching against node labels and edge descriptions,
    and returns relevant subgraph paths.

    NOTE: This is a keyword-based implementation. Full semantic search
    requires an embedding index (future enhancement).

    Examples:
        "what specs block score_rank_pct?"
        "what agents touch the catalyst resolution table?"
        "what depends on spec 087?"
    """
    result: Dict[str, Any] = {
        "question": question,
        "as_of": datetime.now(timezone.utc).isoformat(),
        "matches": [],
        "related_edges": [],
    }

    artifacts_dir = _resolve_artifacts_dir()
    if not artifacts_dir:
        result["error"] = "artifacts/ops directory not found"
        return result

    kg_dir = artifacts_dir / "knowledge_graph"
    if not kg_dir.is_dir():
        result["error"] = "knowledge_graph directory not found"
        return result

    # Load nodes
    nodes_path = kg_dir / "nodes.jsonl"
    edges_path = kg_dir / "edges.jsonl"

    nodes = []
    edges = []

    if nodes_path.exists():
        try:
            for line in nodes_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    nodes.append(json.loads(line))
        except (OSError, json.JSONDecodeError) as e:
            result["error"] = f"Failed to parse nodes.jsonl: {e}"
            return result

    if edges_path.exists():
        try:
            for line in edges_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    edges.append(json.loads(line))
        except (OSError, json.JSONDecodeError) as e:
            result["error"] = f"Failed to parse edges.jsonl: {e}"
            return result

    # Keyword extraction from question
    stop_words = {"what", "which", "who", "how", "does", "do", "is", "are", "the",
                  "a", "an", "in", "on", "of", "to", "for", "and", "or", "that",
                  "this", "from", "with", "by", "at", "it", "its", "my"}
    keywords = [w.lower().strip("?.,\!") for w in question.split()
                if w.lower().strip("?.,\!") not in stop_words and len(w) > 2]

    # Match nodes
    matched_node_ids = set()
    for node in nodes:
        node_text = json.dumps(node).lower()
        score = sum(1 for kw in keywords if kw in node_text)
        if score > 0:
            node["_relevance"] = score
            result["matches"].append(node)
            matched_node_ids.add(node.get("id", node.get("name", "")))

    # Sort by relevance
    result["matches"].sort(key=lambda x: x.get("_relevance", 0), reverse=True)
    result["matches"] = result["matches"][:20]  # Top 20

    # Find related edges
    for edge in edges:
        source = edge.get("source", edge.get("from", ""))
        target = edge.get("target", edge.get("to", ""))
        if source in matched_node_ids or target in matched_node_ids:
            result["related_edges"].append(edge)
        else:
            edge_text = json.dumps(edge).lower()
            if any(kw in edge_text for kw in keywords):
                result["related_edges"].append(edge)

    result["related_edges"] = result["related_edges"][:30]  # Cap

    result["stats"] = {
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "matched_nodes": len(result["matches"]),
        "related_edges": len(result["related_edges"]),
        "keywords_used": keywords,
    }

    # Clean up internal scoring
    for match in result["matches"]:
        match.pop("_relevance", None)

    return result
