"""
ektro_mv — generate a complete music video from one sentence via the
open-source EKTRO-MV CLI (a separate TypeScript engine).

Pipeline: a creative brief (LLM or a provided JSON) -> ACE-Step vocal song ->
Seedance video -> optional Whisper subtitles -> Remotion compositing -> a
delivery-compliant MP4. This tool shells out to the `ektro-mv` CLI and returns
the path to the rendered MP4.

Mirrors the external-CLI subprocess pattern of tools/claude_max.py.

EKTRO-MV: https://github.com/HorizonNowhere/EKTRO-MV
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Any, Dict, List, Optional


_DEFAULT_TIMEOUT_SEC = 900  # 15 min — song + video generation + render is slow


def _resolve_cmd() -> Optional[List[str]]:
    """Return the base command to invoke the EKTRO-MV CLI, or None if unresolvable.

    Resolution order:
      1. ``ektro-mv`` on PATH (global npm install).
      2. ``EKTRO_MV_BIN`` env — absolute path to the CLI entry (a ``.js`` file is
         run with node; anything else is executed directly).
      3. ``EKTRO_MV_DIR`` env — path to a cloned EKTRO-MV repo; runs
         ``node <dir>/packages/cli/dist/bin.js``.
    """
    on_path = shutil.which("ektro-mv")
    if on_path:
        return [on_path]

    bin_env = os.environ.get("EKTRO_MV_BIN")
    if bin_env and os.path.isfile(bin_env):
        if bin_env.endswith(".js"):
            node = shutil.which("node")
            if node:
                return [node, bin_env]
        else:
            return [bin_env]

    dir_env = os.environ.get("EKTRO_MV_DIR")
    if dir_env:
        entry = os.path.join(dir_env, "packages", "cli", "dist", "bin.js")
        node = shutil.which("node")
        if node and os.path.isfile(entry):
            return [node, entry]

    return None


def check_requirements() -> bool:
    """True iff the EKTRO-MV CLI is resolvable (PATH, EKTRO_MV_BIN, or EKTRO_MV_DIR)."""
    return _resolve_cmd() is not None


def _extract_output_path(stdout: str) -> str:
    """Pull the final MP4 path from CLI stdout (printed as a ``✅ <path>`` line)."""
    path = ""
    for raw in stdout.splitlines():
        line = raw.strip()
        if line.startswith("✅"):  # ✅
            path = line.lstrip("✅").strip()
    return path


def ektro_mv_create(
    prompt: str = "",
    *,
    brief: Optional[str] = None,
    out: Optional[str] = None,
    workdir: Optional[str] = None,
    skip_subtitles: bool = True,
    timeout: int = _DEFAULT_TIMEOUT_SEC,
    task_id: Optional[str] = None,
) -> str:
    """Render a music video from one sentence (or a brief JSON). Returns a JSON string.

    Either ``prompt`` (one sentence; the engine writes the song + shotlist, needs
    ANTHROPIC_API_KEY) or ``brief`` (path to a CreativeBrief JSON; no LLM needed) must
    be given. The engine also needs ARK_API_KEY (Seedance) and a running ComfyUI with
    ACE-Step for the vocal song — these come from the environment, not this tool.
    """
    base = _resolve_cmd()
    if base is None:
        return json.dumps({
            "ok": False, "error": "ektro_mv_not_found",
            "text": "EKTRO-MV CLI not found. Install it (npm i -g ektro-mv) or set "
                    "EKTRO_MV_BIN / EKTRO_MV_DIR.",
        })
    if not (prompt and prompt.strip()) and not brief:
        return json.dumps({
            "ok": False, "error": "empty_input",
            "text": "Provide either 'prompt' (one sentence) or 'brief' (path to a brief JSON).",
        })

    cmd = list(base)
    if brief:
        cmd += ["--brief", brief]
    elif prompt.strip():
        cmd.append(prompt.strip())
    if skip_subtitles:
        cmd.append("--skip-subtitles")
    if workdir:
        cmd += ["--workdir", workdir]
    if out:
        cmd += ["--out", out]

    try:
        proc = subprocess.run(
            cmd, text=True, capture_output=True, timeout=timeout, env=os.environ.copy(),
        )
    except subprocess.TimeoutExpired:
        return json.dumps({"ok": False, "error": "timeout",
                           "text": f"EKTRO-MV exceeded {timeout}s"})
    except FileNotFoundError:
        return json.dumps({"ok": False, "error": "exec_failed",
                           "text": f"could not execute: {cmd[0]}"})

    output_mp4 = _extract_output_path(proc.stdout) if proc.returncode == 0 else ""
    tail = (proc.stdout or proc.stderr or "")[-1500:]
    return json.dumps({
        "ok": proc.returncode == 0 and bool(output_mp4),
        "output_mp4": output_mp4,
        "exit_code": proc.returncode,
        "log_tail": tail,
        "error": None if proc.returncode == 0 else "cli_error",
    })


# ---------------------------------------------------------------------------
# Tool schema + registry wiring
# ---------------------------------------------------------------------------

EKTRO_MV_CREATE_SCHEMA: Dict[str, Any] = {
    "name": "ektro_mv_create",
    "description": (
        "Create a complete music video from one sentence using the open-source "
        "EKTRO-MV engine (https://github.com/HorizonNowhere/EKTRO-MV). It writes a "
        "song (lyrics + vocals via ACE-Step), generates video (Seedance), optionally "
        "captions it (Whisper), and renders a delivery-compliant MP4 (Remotion). "
        "Returns JSON with 'ok', 'output_mp4' (path to the finished MP4), 'exit_code', "
        "and 'log_tail'. Provide 'prompt' (one sentence — needs ANTHROPIC_API_KEY for "
        "the creative brain) OR 'brief' (path to a CreativeBrief JSON — no LLM needed). "
        "Requires ARK_API_KEY (Seedance) and a running ComfyUI with ACE-Step in the env. "
        "Generation takes minutes; raise 'timeout' for longer songs."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "One sentence describing the music video to make.",
            },
            "brief": {
                "type": "string",
                "description": "Optional path to a CreativeBrief JSON (skips the LLM brain; no ANTHROPIC_API_KEY needed).",
            },
            "out": {
                "type": "string",
                "description": "Optional output .mp4 path to move the finished video to.",
            },
            "workdir": {
                "type": "string",
                "description": "Optional working directory for intermediate + output files.",
            },
            "skip_subtitles": {
                "type": "boolean",
                "description": "Skip the Whisper subtitle stage (default true; subtitles need an optional dependency).",
            },
            "timeout": {
                "type": "integer",
                "description": "Seconds before killing the run (default 900).",
                "minimum": 60,
                "maximum": 3600,
            },
        },
        "required": ["prompt"],
    },
}


from tools.registry import registry  # noqa: E402

registry.register(
    name="ektro_mv_create",
    toolset="ektro_mv",
    schema=EKTRO_MV_CREATE_SCHEMA,
    handler=lambda args, **kw: ektro_mv_create(
        prompt=args.get("prompt", ""),
        brief=args.get("brief"),
        out=args.get("out"),
        workdir=args.get("workdir"),
        skip_subtitles=bool(args.get("skip_subtitles", True)),
        timeout=int(args.get("timeout") or _DEFAULT_TIMEOUT_SEC),
        task_id=kw.get("task_id"),
    ),
    check_fn=check_requirements,
    requires_env=["ARK_API_KEY"],
    emoji="\U0001f3ac",  # 🎬
)
