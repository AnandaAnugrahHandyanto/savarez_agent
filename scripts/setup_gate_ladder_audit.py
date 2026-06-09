#!/usr/bin/env python3
"""
Read-only Hermes setup gate ladder audit (M2a).

Writes receipt.json + synthesis.md to an output directory.
Does not mutate config, profiles, gateway, or cron.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

SCHEMA_VERSION = 1
SECRET_ENV_HINTS = (
    "API_KEY",
    "TOKEN",
    "SECRET",
    "PASSWORD",
    "PRIVATE",
    "OAUTH",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _gate(status: str = "pass", evidence: dict | None = None, blockers: list | None = None) -> dict:
    return {
        "status": status,
        "evidence": evidence or {},
        "blockers": blockers or [],
    }


def _run(
    cmd: list[str],
    *,
    env: dict[str, str] | None = None,
    timeout: int = 30,
    cwd: Path | None = None,
) -> dict[str, Any]:
    started = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            cwd=str(cwd) if cwd else None,
        )
        elapsed = round(time.monotonic() - started, 3)
        out = (proc.stdout or "") + (proc.stderr or "")
        if len(out) > 12000:
            out = out[:12000] + "\n... [truncated]"
        return {
            "exit_code": proc.returncode,
            "elapsed_s": elapsed,
            "output": out,
            "error": None,
        }
    except subprocess.TimeoutExpired as exc:
        elapsed = round(time.monotonic() - started, 3)
        partial = ""
        if exc.stdout:
            partial += exc.stdout if isinstance(exc.stdout, str) else exc.stdout.decode("utf-8", "replace")
        if exc.stderr:
            partial += exc.stderr if isinstance(exc.stderr, str) else exc.stderr.decode("utf-8", "replace")
        return {
            "exit_code": 124,
            "elapsed_s": elapsed,
            "output": (partial[:8000] + "\n... [timeout]") if partial else "",
            "error": "timeout",
        }
    except OSError as exc:
        return {"exit_code": -1, "elapsed_s": 0.0, "output": "", "error": str(exc)}


def _load_yaml(path: Path) -> dict:
    if not path.is_file():
        return {}
    if yaml is None:
        return {"_error": "PyYAML not installed"}
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        return {"_error": str(exc)}


def _env_key_shapes(env_path: Path) -> dict[str, str]:
    shapes: dict[str, str] = {}
    if not env_path.is_file():
        return shapes
    for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, _val = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        if any(h in key.upper() for h in SECRET_ENV_HINTS):
            shapes[key] = "set"
    return shapes


def _redact_deliver(target: str) -> str:
    if not target:
        return target
    # Keep last segment visible for operator recognition
    parts = re.split(r"(:|@)", target)
    if len(parts) >= 2 and len(parts[-1]) > 4:
        tail = parts[-1]
        parts[-1] = "***" + tail[-4:]
        return "".join(parts)
    return target


def _grep_smart_routing_symbols(source_repo: Path) -> dict[str, Any]:
    """Search main source tree only (exclude .worktrees noise)."""
    patterns = ("smart_model_routing", "SmartModelRouter", "route_turn")
    hits: dict[str, list[str]] = {p: [] for p in patterns}
    if not source_repo.is_dir():
        return {"status": "skipped", "reason": "source_repo missing", "hits": hits}
    search_roots = [
        source_repo / "hermes_cli",
        source_repo / "agent",
        source_repo / "run_agent.py",
    ]
    files: list[Path] = []
    for root in search_roots:
        if root.is_file():
            files.append(root)
        elif root.is_dir():
            files.extend(root.rglob("*.py"))
    for py in files:
        if ".worktrees" in py.parts:
            continue
        try:
            text = py.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for pat in patterns:
            if pat in text:
                try:
                    rel = str(py.relative_to(source_repo))
                except ValueError:
                    rel = str(py)
                hits[pat].append(rel)
    canonical = source_repo / "hermes_cli" / "smart_routing.py"
    return {"hits": hits, "canonical_smart_routing_py": canonical.is_file()}


def _synthesis(receipt: dict) -> str:
    lines = [
        "# Setup gate ladder audit",
        "",
        f"- run_id: `{receipt.get('run_id')}`",
        f"- started: {receipt.get('started_at_utc')}",
        f"- hermes_home: `{receipt.get('hermes_home')}`",
        f"- overall: **{receipt.get('overall')}**",
        "",
    ]
    for gname, gdata in (receipt.get("gates") or {}).items():
        lines.append(f"## {gname} — {gdata.get('status')}")
        blockers = gdata.get("blockers") or []
        if blockers:
            for b in blockers:
                lines.append(f"- BLOCKER: {b}")
        ev = gdata.get("evidence") or {}
        for k, v in ev.items():
            if k in ("output",):
                continue
            lines.append(f"- {k}: {v}")
        lines.append("")
    if receipt.get("next_actions"):
        lines.append("## Next actions")
        for na in receipt["next_actions"]:
            lines.append(f"- {na}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only Hermes setup gate ladder audit")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory (default: /tmp/hermes-workflows/setup-gate-ladder/<run-id>)",
    )
    parser.add_argument(
        "--hermes-home",
        type=Path,
        default=None,
        help="Profile home (default: $HERMES_HOME or ~/.hermes)",
    )
    parser.add_argument(
        "--source-repo",
        type=Path,
        default=Path("/home/khall/.hermes/hermes-agent"),
        help="Hermes source checkout for G0 git anchor",
    )
    parser.add_argument(
        "--pythonpath",
        type=Path,
        default=None,
        help="Optional PYTHONPATH prefix (e.g. M1 worktree) for faster profile list",
    )
    parser.add_argument("--skip-cli-probes", action="store_true", help="Skip hermes subprocess probes")
    args = parser.parse_args()

    run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_dir = args.out_dir or Path(f"/tmp/hermes-workflows/setup-gate-ladder/{run_id}")
    out_dir.mkdir(parents=True, exist_ok=True)

    hermes_home = args.hermes_home or Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
    config_path = hermes_home / "config.yaml"
    env_path = hermes_home / ".env"

    env = os.environ.copy()
    env["HERMES_HOME"] = str(hermes_home)
    if args.pythonpath:
        prev = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = f"{args.pythonpath}{os.pathsep}{prev}" if prev else str(args.pythonpath)

    receipt: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "workflow": "setup-gate-ladder",
        "run_id": run_id,
        "started_at_utc": _utc_now(),
        "hermes_home": str(hermes_home),
        "permission_boundary": "read-only",
        "gates": {},
        "overall": "pass",
        "approval_gates": [
            "push",
            "gateway_restart",
            "cron_create",
            "profile_edit",
            "live_provider_smoke",
        ],
        "next_actions": [],
    }

    blockers_all: list[str] = []

    # G0
    g0: dict[str, Any] = {}
    if not args.skip_cli_probes:
        ver = _run(["hermes", "--version"], env=env, timeout=15)
        g0["cli_version"] = ver
        plist = _run(["hermes", "profile", "list"], env=env, timeout=8)
        g0["profile_list"] = {
            "exit_code": plist["exit_code"],
            "elapsed_s": plist["elapsed_s"],
            "error": plist["error"],
            "output_lines": len((plist.get("output") or "").splitlines()),
        }
        if plist["exit_code"] == 124 or plist.get("error") == "timeout":
            blockers_all.append("G0: hermes profile list exceeded timeout budget")
    g0["hermes_home_exists"] = hermes_home.is_dir()
    g0["config_exists"] = config_path.is_file()
    if args.source_repo.is_dir():
        g0["git"] = _run(
            ["git", "-C", str(args.source_repo), "status", "--short", "--branch"],
            timeout=15,
        )
        head = _run(["git", "-C", str(args.source_repo), "rev-parse", "HEAD"], timeout=10)
        g0["git_head"] = (head.get("output") or "").strip()
    sym = _grep_smart_routing_symbols(args.source_repo)
    g0["smart_routing_symbols"] = sym
    cfg = _load_yaml(config_path)
    smr = cfg.get("smart_model_routing") if isinstance(cfg, dict) else None
    g0["smart_model_routing_config"] = "present" if smr else "absent"
    if smr and not sym.get("canonical_smart_routing_py") and not any(sym.get("hits", {}).get(k) for k in sym.get("hits", {})):
        blockers_all.append(
            "G0: smart_model_routing in config but no runtime symbols in source_repo (main tree)"
        )

    g0_status = "fail" if any(b.startswith("G0:") for b in blockers_all) else "pass"
    if g0.get("profile_list", {}).get("exit_code") == 124:
        g0_status = "warn"
    receipt["gates"]["G0_version_source"] = _gate(
        g0_status,
        g0,
        [b for b in blockers_all if b.startswith("G0:")],
    )

    # G1
    model = cfg.get("model", {}) if isinstance(cfg, dict) else {}
    g1_ev = {
        "model_default": model.get("default") if isinstance(model, dict) else model,
        "model_provider": model.get("provider") if isinstance(model, dict) else None,
        "env_secret_keys": _env_key_shapes(env_path),
        "smart_model_routing_enabled": bool(smr and isinstance(smr, dict) and smr.get("enabled")),
        "label": "config-only",
    }
    if isinstance(smr, dict):
        g1_ev["smart_model_routing_lanes"] = {
            k: smr.get(k)
            for k in ("cheap_model", "routine_coding_model", "hard_model")
            if k in smr
        }
    sec = cfg.get("security", {}) if isinstance(cfg, dict) else {}
    if isinstance(sec, dict):
        g1_ev["security"] = {
            "redact_secrets": sec.get("redact_secrets"),
            "tirith_enabled": sec.get("tirith_enabled"),
        }
    receipt["gates"]["G1_provider_routing"] = _gate("pass", g1_ev)

    # G2–G6 CLI probes
    for gate_key, cmd, timeout in (
        ("G2_tools", ["hermes", "tools"], 20),
        ("G3_mcp", ["hermes", "mcp", "list"], 20),
        ("G5_cron", ["hermes", "cron", "list"], 20),
        ("G6_gateway", ["hermes", "gateway", "status"], 15),
    ):
        if args.skip_cli_probes:
            receipt["gates"][gate_key] = _gate("skipped", {"reason": "skip_cli_probes"})
            continue
        probe = _run(cmd, env=env, timeout=timeout)
        status = "pass" if probe["exit_code"] == 0 else "warn"
        if probe.get("error") == "timeout":
            status = "warn"
        receipt["gates"][gate_key] = _gate(
            status,
            {
                "command": " ".join(cmd),
                "exit_code": probe["exit_code"],
                "elapsed_s": probe["elapsed_s"],
                "output_preview": (probe.get("output") or "")[:2000],
            },
        )

    # G4 memory from config
    mem = cfg.get("memory", {}) if isinstance(cfg, dict) else {}
    g4_ev = {"label": "config-only"}
    if isinstance(mem, dict):
        g4_ev["memory_provider"] = mem.get("provider") or mem.get("type")
        g4_ev["honcho"] = "honcho" in json.dumps(mem).lower()
    receipt["gates"]["G4_memory"] = _gate("pass", g4_ev)

    # G3 supplement from config mcp servers
    mcp_cfg = cfg.get("mcp_servers") or cfg.get("mcp") if isinstance(cfg, dict) else None
    if mcp_cfg and "G3_mcp" in receipt["gates"]:
        receipt["gates"]["G3_mcp"]["evidence"]["config_server_names"] = (
            list(mcp_cfg.keys()) if isinstance(mcp_cfg, dict) else str(type(mcp_cfg))
        )

    if blockers_all:
        receipt["overall"] = "needs_operator"
        receipt["next_actions"].append("Resolve G0 blockers before setup mutations")
    elif any(
        receipt["gates"].get(k, {}).get("status") == "warn"
        for k in ("G2_tools", "G5_cron", "G6_gateway")
    ):
        receipt["overall"] = "needs_operator"
        receipt["next_actions"].append("Review warn gates; approve live probes if needed")

    (out_dir / "receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    (out_dir / "synthesis.md").write_text(_synthesis(receipt), encoding="utf-8")
    print(str(out_dir))
    return 0 if receipt["overall"] == "pass" else 2


if __name__ == "__main__":
    sys.exit(main())