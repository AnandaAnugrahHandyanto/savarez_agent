"""Welcome banner, ASCII art, skills summary, and update check for the CLI.

Pure display functions with no HermesCLI state dependency.
"""

import json
import os  # noqa: F401 — tests mock hermes_cli.banner.os.getenv
import shutil
import subprocess
import threading
import time
from pathlib import Path
from hermes_constants import get_hermes_home
from typing import Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from prompt_toolkit import print_formatted_text as _pt_print
from prompt_toolkit.formatted_text import ANSI as _PT_ANSI

_DIM = "\033[2m"
_RST = "\033[0m"


def cprint(text: str):
    """Print ANSI-colored text through prompt_toolkit's renderer."""
    _pt_print(_PT_ANSI(text))



def _skin_color(key: str, fallback: str) -> str:
    """Get a color from the active skin, or return fallback."""
    try:
        from hermes_cli.skin_engine import get_active_skin
        return get_active_skin().get_color(key, fallback)
    except Exception:
        return fallback


def _skin_branding(key: str, fallback: str) -> str:
    """Get a branding string from the active skin, or return fallback."""
    try:
        from hermes_cli.skin_engine import get_active_skin
        return get_active_skin().get_branding(key, fallback)
    except Exception:
        return fallback



from hermes_cli import __version__ as VERSION, __release_date__ as RELEASE_DATE

HERMES_AGENT_LOGO = """[bold #FFD700]██╗  ██╗███████╗██████╗ ███╗   ███╗███████╗███████╗[/]
[bold #FFD700]██║  ██║██╔════╝██╔══██╗████╗ ████║██╔════╝██╔════╝[/]
[#FFBF00]███████║█████╗  ██████╔╝██╔████╔██║█████╗  ███████╗[/]
[#FFBF00]██╔══██║██╔══╝  ██╔══██╗██║╚██╔╝██║██╔══╝  ╚════██║[/]
[#CD7F32]██║  ██║███████╗██║  ██║██║ ╚═╝ ██║███████╗███████║[/]
[#CD7F32]╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝╚══════╝╚══════╝[/]"""

HERMES_CADUCEUS = """[dim #555577]  ✦  ⚕  ✦  [/]
[dim #3A3A6A]⠀⠀⠀⢰⣦⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣴⡆⠀⠀⠀[/]
[dim #3A3A6A]⠀⠀⢀⣿⠟⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠻⣿⡀⠀⠀[/]
[#555577]⠀⢀⣾⡏⠀⠀[#FFD700]⚡[/][#555577]⠀⠀⠀⠀⠀⠀⠀[#FFD700]⚡[/][#555577]⠀⠀⠀⢹⣷⡀⠀⠀[/]
[#C9A227]⠀⠸⣿⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠘⣿⠇⠀⠀[/]
[#C9A227]⠀⠀⠀⠀⠀⢀⣀⡀⠀⣀⣀⠀⢀⣀⡀⠀⠀⠀⠀⠀⠀⠀⠀[/]
[#FFD700]⠀⠀⠀⠀⠀⢀⣠⣴⣾⣿⣿⣇⠸⣿⣿⠇⣸⣿⣿⣷⣦⣄⡀[/]
[#C9A227]⢀⣠⣴⣶⠿⠋⣩⡿⣿⡿⠻⣿⡇⢠⡄⢸⣿⠟⢿⣿⢿⣍⠙[/]
[dim #555577]⠀⠉⠉⠁⠶⠟⠋⠀⠉⠀⢀⣈⣁⡈⢁⣈⣁⡀⠀⠉⠀⠙⠻[/]
[dim #3A3A6A]⠀⠀⠀⠀⠀⠀⠀⠀⠀⣴⣿⡿⠛⢁⡈⠛⢿⣿⣦⠀⠀⠀⠀[/]
[dim #3A3A6A]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠿⣿⣦⣤⣈⠁⢠⣴⣿⠿⠀⠀⠀⠀[/]
[dim #2A2A50]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠉⠻⢿⣿⣦⡉⠁⠀⠀⠀⠀⠀[/]
[dim #2A2A50]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠘⢷⣦⣈⠛⠃⠀⠀⠀⠀⠀⠀[/]
[dim #1A1A38]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢠⣴⠦⠈⠙⠿⣦⡄⠀⠀⠀⠀⠀[/]
[dim #1A1A38]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠸⣿⣤⡈⠁⢤⣿⠇⠀⠀⠀⠀⠀[/]
[dim #555577]  ✦  divine messenger  ✦[/]"""




def get_available_skills() -> Dict[str, List[str]]:
    """Return skills grouped by category, filtered by platform and disabled state.

    Delegates to ``_find_all_skills()`` from ``tools/skills_tool`` which already
    handles platform gating (``platforms:`` frontmatter) and respects the
    user's ``skills.disabled`` config list.
    """
    try:
        from tools.skills_tool import _find_all_skills
        all_skills = _find_all_skills()  # already filtered
    except Exception:
        return {}

    skills_by_category: Dict[str, List[str]] = {}
    for skill in all_skills:
        category = skill.get("category") or "general"
        skills_by_category.setdefault(category, []).append(skill["name"])
    return skills_by_category



# Cache update check results for 6 hours to avoid repeated git fetches
_UPDATE_CHECK_CACHE_SECONDS = 6 * 3600


def check_for_updates() -> Optional[int]:
    """Check how many commits behind origin/main the local repo is.

    Does a ``git fetch`` at most once every 6 hours (cached to
    ``~/.hermes/.update_check``).  Returns the number of commits behind,
    or ``None`` if the check fails or isn't applicable.
    """
    hermes_home = get_hermes_home()
    repo_dir = hermes_home / "hermes-agent"
    cache_file = hermes_home / ".update_check"

    # Must be a git repo — fall back to project root for dev installs
    if not (repo_dir / ".git").exists():
        repo_dir = Path(__file__).parent.parent.resolve()
    if not (repo_dir / ".git").exists():
        return None

    # Read cache
    now = time.time()
    try:
        if cache_file.exists():
            cached = json.loads(cache_file.read_text())
            if now - cached.get("ts", 0) < _UPDATE_CHECK_CACHE_SECONDS:
                return cached.get("behind")
    except Exception:
        pass

    # Fetch latest refs (fast — only downloads ref metadata, no files)
    try:
        subprocess.run(
            ["git", "fetch", "origin", "--quiet"],
            capture_output=True, timeout=10,
            cwd=str(repo_dir),
        )
    except Exception:
        pass  # Offline or timeout — use stale refs, that's fine

    # Count commits behind
    try:
        result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD..origin/main"],
            capture_output=True, text=True, timeout=5,
            cwd=str(repo_dir),
        )
        if result.returncode == 0:
            behind = int(result.stdout.strip())
        else:
            behind = None
    except Exception:
        behind = None

    # Write cache
    try:
        cache_file.write_text(json.dumps({"ts": now, "behind": behind}))
    except Exception:
        pass

    return behind


def _resolve_repo_dir() -> Optional[Path]:
    """Return the active Hermes git checkout, or None if this isn't a git install."""
    hermes_home = get_hermes_home()
    repo_dir = hermes_home / "hermes-agent"
    if not (repo_dir / ".git").exists():
        repo_dir = Path(__file__).parent.parent.resolve()
    return repo_dir if (repo_dir / ".git").exists() else None


def _git_short_hash(repo_dir: Path, rev: str) -> Optional[str]:
    """Resolve a git revision to an 8-character short hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short=8", rev],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(repo_dir),
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    value = (result.stdout or "").strip()
    return value or None


def get_git_banner_state(repo_dir: Optional[Path] = None) -> Optional[dict]:
    """Return upstream/local git hashes for the startup banner."""
    repo_dir = repo_dir or _resolve_repo_dir()
    if repo_dir is None:
        return None

    upstream = _git_short_hash(repo_dir, "origin/main")
    local = _git_short_hash(repo_dir, "HEAD")
    if not upstream or not local:
        return None

    ahead = 0
    try:
        result = subprocess.run(
            ["git", "rev-list", "--count", "origin/main..HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(repo_dir),
        )
        if result.returncode == 0:
            ahead = int((result.stdout or "0").strip() or "0")
    except Exception:
        ahead = 0

    return {"upstream": upstream, "local": local, "ahead": max(ahead, 0)}


def format_banner_version_label() -> str:
    """Return the version label shown in the startup banner title."""
    base = f"Hermes Agent v{VERSION} ({RELEASE_DATE})"
    state = get_git_banner_state()
    if not state:
        return base

    upstream = state["upstream"]
    local = state["local"]
    ahead = int(state.get("ahead") or 0)

    if ahead <= 0 or upstream == local:
        return f"{base} · upstream {upstream}"

    carried_word = "commit" if ahead == 1 else "commits"
    return f"{base} · upstream {upstream} · local {local} (+{ahead} carried {carried_word})"

_update_result: Optional[int] = None
_update_check_done = threading.Event()


def prefetch_update_check():
    """Kick off update check in a background daemon thread."""
    def _run():
        global _update_result
        _update_result = check_for_updates()
        _update_check_done.set()
    t = threading.Thread(target=_run, daemon=True)
    t.start()


def get_update_result(timeout: float = 0.5) -> Optional[int]:
    """Get result of prefetched check. Returns None if not ready."""
    _update_check_done.wait(timeout=timeout)
    return _update_result



def _format_context_length(tokens: int) -> str:
    """Format a token count for display (e.g. 128000 → '128K', 1048576 → '1M')."""
    if tokens >= 1_000_000:
        val = tokens / 1_000_000
        rounded = round(val)
        if abs(val - rounded) < 0.05:
            return f"{rounded}M"
        return f"{val:.1f}M"
    elif tokens >= 1_000:
        val = tokens / 1_000
        rounded = round(val)
        if abs(val - rounded) < 0.05:
            return f"{rounded}K"
        return f"{val:.1f}K"
    return str(tokens)


def _display_toolset_name(toolset_name: str) -> str:
    """Normalize internal/legacy toolset identifiers for banner display."""
    if not toolset_name:
        return "unknown"
    return (
        toolset_name[:-6]
        if toolset_name.endswith("_tools")
        else toolset_name
    )


def build_welcome_banner(console: Console, model: str, cwd: str,
                         tools: List[dict] = None,
                         enabled_toolsets: List[str] = None,
                         session_id: str = None,
                         get_toolset_for_tool=None,
                         context_length: int = None):
    """Build and print a welcome banner with caduceus on left and info on right.

    Args:
        console: Rich Console instance.
        model: Current model name.
        cwd: Current working directory.
        tools: List of tool definitions.
        enabled_toolsets: List of enabled toolset names.
        session_id: Session identifier.
        get_toolset_for_tool: Callable to map tool name -> toolset name.
        context_length: Model's context window size in tokens.
    """
    from model_tools import check_tool_availability, TOOLSET_REQUIREMENTS
    if get_toolset_for_tool is None:
        from model_tools import get_toolset_for_tool

    tools = tools or []
    enabled_toolsets = enabled_toolsets or []

    _, unavailable_toolsets = check_tool_availability(quiet=True)
    disabled_tools = set()
    # Tools whose toolset has a check_fn are lazy-initialized (e.g. honcho,
    # homeassistant) — they show as unavailable at banner time because the
    # check hasn't run yet, but they aren't misconfigured.
    lazy_tools = set()
    for item in unavailable_toolsets:
        toolset_name = item.get("name", "")
        ts_req = TOOLSET_REQUIREMENTS.get(toolset_name, {})
        tools_in_ts = item.get("tools", [])
        if ts_req.get("check_fn"):
            lazy_tools.update(tools_in_ts)
        else:
            disabled_tools.update(tools_in_ts)

    layout_table = Table.grid(padding=(0, 2))
    layout_table.add_column("left", justify="center")
    layout_table.add_column("right", justify="left")

    # Resolve skin colors once for the entire banner
    accent = _skin_color("banner_accent", "#FFBF00")
    dim = _skin_color("banner_dim", "#B8860B")
    text = _skin_color("banner_text", "#FFF8DC")
    session_color = _skin_color("session_border", "#8B8682")
    ok_color    = _skin_color("ui_ok",    "#7FFFD4")
    err_color   = _skin_color("ui_error", "#FF6B8A")
    label_color = _skin_color("ui_label", "#5F87D4")

    # Use skin's custom caduceus art if provided
    # Check if we'll show a bento banner (which already has the hero art)
    try:
        from hermes_cli.skin_engine import get_active_skin
        _bskin = get_active_skin()
        _hero = _bskin.banner_hero if hasattr(_bskin, 'banner_hero') and _bskin.banner_hero else HERMES_CADUCEUS
        # If banner_logo is empty/None, we'll show bento banner with hero art, so skip it here
        _show_bento = not (_bskin.banner_logo if hasattr(_bskin, 'banner_logo') and _bskin.banner_logo else None)
    except Exception:
        _bskin = None
        _hero = HERMES_CADUCEUS
        _show_bento = False
    
    # Only include hero art in main panel if we're NOT showing the bento banner
    if _show_bento:
        left_lines = [""]  # Skip hero art - it's in the bento banner above
    else:
        left_lines = ["", _hero, ""]
    model_short = model.split("/")[-1] if "/" in model else model
    if model_short.endswith(".gguf"):
        model_short = model_short[:-5]
    if len(model_short) > 28:
        model_short = model_short[:25] + "..."
    ctx_str = f" [dim {dim}]·[/] [dim {dim}]{_format_context_length(context_length)} context[/]" if context_length else ""
    left_lines.append(f"[{accent}]{model_short}[/]{ctx_str} [dim {dim}]·[/] [dim {dim}]Nous Research[/]")
    left_lines.append(f"[dim {dim}]{cwd}[/]")
    if session_id:
        left_lines.append(f"[dim {session_color}]Session: {session_id}[/]")
    left_content = "\n".join(left_lines)

    toolsets_dict: Dict[str, list] = {}

    for tool in tools:
        tool_name = tool["function"]["name"]
        toolset = _display_toolset_name(get_toolset_for_tool(tool_name) or "other")
        toolsets_dict.setdefault(toolset, []).append(tool_name)

    for item in unavailable_toolsets:
        toolset_id = item.get("id", item.get("name", "unknown"))
        display_name = _display_toolset_name(toolset_id)
        if display_name not in toolsets_dict:
            toolsets_dict[display_name] = []
        for tool_name in item.get("tools", []):
            if tool_name not in toolsets_dict[display_name]:
                toolsets_dict[display_name].append(tool_name)

    sorted_toolsets = sorted(toolsets_dict.keys())
    display_toolsets = sorted_toolsets[:8]
    remaining_toolsets = len(sorted_toolsets) - 8

    active_tool_count = sum(
        1 for n in (t["function"]["name"] for t in tools)
        if n not in disabled_tools
    )
    right_lines = [f"[bold {accent}]TOOLS[/]  [dim {dim}]{active_tool_count} active · {len(tools)} total[/]"]

    for toolset in display_toolsets:
        tool_names = toolsets_dict[toolset]
        all_off   = bool(tool_names) and all(n in disabled_tools for n in tool_names)
        any_lazy  = any(n in lazy_tools for n in tool_names)

        if all_off:
            dot   = f"[{err_color}]×[/]"
            ts_markup = f"[{err_color}]{toolset:<11}[/]"
            body  = f"[dim {err_color}]offline[/]"
        elif any_lazy:
            dot   = f"[dim {dim}]~[/]"
            ts_markup = f"[dim {label_color}]{toolset:<11}[/]"
            avail = [n for n in sorted(tool_names) if n not in disabled_tools]
            parts = [f"[dim {text}]{n}[/]" for n in avail[:5]]
            if len(avail) > 5:
                parts.append(f"[dim {dim}]+{len(avail)-5}[/]")
            body  = " ".join(parts)
        else:
            dot   = f"[{ok_color}]·[/]"
            ts_markup = f"[{label_color}]{toolset:<11}[/]"
            names = sorted(n for n in tool_names if n not in disabled_tools)
            parts = [f"[{text}]{n}[/]" for n in names[:5]]
            if len(names) > 5:
                parts.append(f"[dim {dim}]+{len(names)-5}[/]")
            body  = " ".join(parts)

        right_lines.append(f" {dot} {ts_markup}  {body}")

    if remaining_toolsets > 0:
        right_lines.append(f"[dim {dim}]   … +{remaining_toolsets} more toolsets[/]")

    # MCP Servers section (only if configured)
    try:
        from tools.mcp_tool import get_mcp_status
        mcp_status = get_mcp_status()
    except Exception:
        mcp_status = []

    if mcp_status:
        right_lines.append("")
        mcp_ok = sum(1 for s in mcp_status if s["connected"])
        right_lines.append(f"[bold {accent}]MCP[/]  [dim {dim}]{mcp_ok}/{len(mcp_status)} connected[/]")
        for srv in mcp_status:
            if srv["connected"]:
                dot = f"[{ok_color}]·[/]"
                right_lines.append(
                    f" {dot} [{label_color}]{srv['name']:<11}[/]  [{text}]{srv['tools']} tools[/]"
                    f"  [dim {dim}]{srv['transport']}[/]"
                )
            else:
                dot = f"[{err_color}]×[/]"
                right_lines.append(
                    f" {dot} [{err_color}]{srv['name']:<11}[/]  [dim {err_color}]failed · {srv['transport']}[/]"
                )

    right_lines.append("")
    skills_by_category = get_available_skills()
    total_skills = sum(len(s) for s in skills_by_category.values())
    right_lines.append(f"[bold {accent}]SKILLS[/]  [dim {dim}]{total_skills} available[/]")

    if skills_by_category:
        for category in sorted(skills_by_category.keys()):
            skill_names = sorted(skills_by_category[category])
            max_show = 6
            shown = skill_names[:max_show]
            parts = [f"[{text}]/{n}[/]" for n in shown]
            overflow = len(skill_names) - max_show
            if overflow > 0:
                parts.append(f"[dim {dim}]+{overflow}[/]")
            right_lines.append(
                f" [dim {dim}]{category:<10}[/]  " + "  ".join(parts)
            )
    else:
        right_lines.append(f" [dim {dim}]no skills installed[/]")

    # Pantheon Registry — only rendered when the active skin defines one
    try:
        from hermes_cli.skin_engine import get_active_skin
        _pskin = get_active_skin()
        _pantheon = _pskin.pantheon if hasattr(_pskin, 'pantheon') else []
    except Exception:
        _pantheon = []

    if _pantheon:
        # Try to get live god status from fleet monitor
        _god_status: Dict[str, str] = {}
        try:
            from agent.fleet_monitor import get_fleet_monitor
            _fm = get_fleet_monitor()
            if _fm:
                with _fm._lock:
                    for _aname, _astate in _fm._state.agents.items():
                        _god_status[_aname] = _astate.status
        except Exception:
            pass

        _pantheon_style = ""
        try:
            _pantheon_style = _pskin.pantheon_style if hasattr(_pskin, 'pantheon_style') else ""
        except Exception:
            pass

        if _pantheon_style == "strip":
            right_lines.append("")
            right_lines.append(f"[bold {accent}]PANTHEON[/]")
            strip_parts = []
            for g in _pantheon:
                icon = g.get("icon", "·")
                name = g.get("name", "?").upper()[:4]
                rank = g.get("rank", "")[:4]
                raw_s = _god_status.get(g.get("name", ""), "idle")
                if raw_s in ("thinking", "querying", "processing", "responding", "spawning", "retrying"):
                    col = ok_color
                elif raw_s == "failed":
                    col = err_color
                else:
                    col = dim
                strip_parts.append(f"[{col}]{icon}[/][dim {dim}]{name}[/]")
            right_lines.append(" " + " · ".join(strip_parts))
        else:
            def _god_cell(g):
                """Return (hat+name row, face+status row) each exactly 11 visible chars."""
                if g is None:
                    return "           ", "           "
                hat  = g.get("hat",  "/^\\")[:3]
                face = g.get("face", "(-_-)")[:5]
                name = g.get("name", "")[:8].upper()
                rank = g.get("rank", "    ")[:4]
                raw_s = _god_status.get(g.get("name", ""), "idle")
                if raw_s in ("thinking", "querying", "processing", "responding", "spawning", "retrying"):
                    dot, tag, col = "*", "ACTV", accent
                elif raw_s == "failed":
                    dot, tag, col = "!", "FAIL", err_color
                elif raw_s == "complete":
                    dot, tag, col = "+", "DONE", ok_color
                else:
                    dot, tag, col = ".", rank, dim
                row1 = f"[bold {accent}]{hat:<3}{name:<8}[/]"
                row2 = f"[{text}]{face:<5}[/] [{col}]{dot}{tag:<4}[/]"
                return row1, row2

            _CSEP = "-----------"
            right_lines.append("")
            right_lines.append(f"[bold {accent}]-- GODS OF OLYMPUS --[/]")
            right_lines.append(f"[{dim}].{_CSEP}.{_CSEP}.{_CSEP}.[/]")
            for j in range(0, len(_pantheon), 3):
                g1 = _pantheon[j]
                g2 = _pantheon[j + 1] if j + 1 < len(_pantheon) else None
                g3 = _pantheon[j + 2] if j + 2 < len(_pantheon) else None
                r1a, r2a = _god_cell(g1)
                r1b, r2b = _god_cell(g2)
                r1c, r2c = _god_cell(g3)
                right_lines.append(
                    f"[{dim}]|[/]{r1a}[{dim}]|[/]{r1b}[{dim}]|[/]{r1c}[{dim}]|[/]"
                )
                right_lines.append(
                    f"[{dim}]|[/]{r2a}[{dim}]|[/]{r2b}[{dim}]|[/]{r2c}[{dim}]|[/]"
                )
                is_last = j + 3 >= len(_pantheon)
                if is_last:
                    right_lines.append(f"[{dim}]'{_CSEP}'{_CSEP}'{_CSEP}'[/]")
                else:
                    right_lines.append(f"[{dim}]|{_CSEP}|{_CSEP}|{_CSEP}|[/]")

    # Execution Lanes section (only if skin defines them)
    try:
        from hermes_cli.skin_engine import get_active_skin
        _lskin = get_active_skin()
        _lanes = _lskin.execution_lanes if hasattr(_lskin, 'execution_lanes') and _lskin.execution_lanes else []
    except Exception:
        _lanes = []

    if _lanes:
        right_lines.append("")
        right_lines.append(f"[bold {accent}]EXECUTION LANES[/]")
        lane_parts = []
        for lane in _lanes[:6]:  # Show up to 6 lanes
            icon = lane.get("icon", "·")
            name = lane.get("name", "?")[:4]
            color = lane.get("color", dim)
            lane_parts.append(f"[{color}]{icon}[/][dim {dim}]{name}[/]")
        right_lines.append(" " + " → ".join(lane_parts))

    # Divine Quote — random quote from a random god
    try:
        import random
        from hermes_cli.skin_engine import get_active_skin
        _qskin = get_active_skin()
        if _qskin and hasattr(_qskin, 'pantheon') and _qskin.pantheon:
            _gods_with_quotes = [g for g in _qskin.pantheon if _qskin.get_god_quotes(g.get("name", ""))]
            if _gods_with_quotes:
                _qgod = random.choice(_gods_with_quotes)
                _qgod_name = _qgod.get("name", "")
                _qgod_icon = _qgod.get("icon", "✦")
                _quotes = _qskin.get_god_quotes(_qgod_name)
                if _quotes:
                    _quote = random.choice(_quotes)
                    _qgod_color = _qskin.get_god_color(_qgod_name) if hasattr(_qskin, 'get_god_color') else accent
                    right_lines.append("")
                    right_lines.append(f"[{_qgod_color}]{_qgod_icon}[/] [italic dim #555577]\"{_quote}\"[/]")
                    right_lines.append(f"[dim #555577]  — {_qgod_name}[/]")
    except Exception:
        pass  # Never break the banner over quotes

    right_lines.append("")
    mcp_connected = sum(1 for s in mcp_status if s["connected"]) if mcp_status else 0
    summary_parts = [f"{len(tools)} tools", f"{total_skills} skills"]
    if mcp_connected:
        summary_parts.append(f"{mcp_connected} MCP servers")
    summary_parts.append("/help for commands")
    # Show active profile name when not 'default'
    try:
        from hermes_cli.profiles import get_active_profile_name
        _profile_name = get_active_profile_name()
        if _profile_name and _profile_name != "default":
            right_lines.append(f"[bold {accent}]Profile:[/] [{text}]{_profile_name}[/]")
    except Exception:
        pass  # Never break the banner over a profiles.py bug

    right_lines.append(f"[dim {dim}]{' · '.join(summary_parts)}[/]")

    # Update check — use prefetched result if available
    try:
        behind = get_update_result(timeout=0.5)
        if behind and behind > 0:
            from hermes_cli.config import recommended_update_command
            commits_word = "commit" if behind == 1 else "commits"
            right_lines.append(
                f"[bold yellow]⚠ {behind} {commits_word} behind[/]"
                f"[dim yellow] — run [bold]{recommended_update_command()}[/bold] to update[/]"
            )
    except Exception:
        pass  # Never break the banner over an update check

    right_content = "\n".join(right_lines)
    layout_table.add_row(left_content, right_content)

    agent_name = _skin_branding("agent_name", "Hermes Agent")
    title_color = _skin_color("banner_title", "#FFD700")
    border_color = _skin_color("banner_border", "#CD7F32")
    outer_panel = Panel(
        layout_table,
        title=f"[bold {title_color}]{format_banner_version_label()}[/]",
        border_style=border_color,
        padding=(0, 2),
    )

    console.print()
    term_width = shutil.get_terminal_size().columns
    if term_width >= 80:
        # Check if skin has a custom banner_logo
        _custom_logo = _bskin.banner_logo if _bskin and hasattr(_bskin, 'banner_logo') and _bskin.banner_logo else None
        
        if _custom_logo:
            # Use Rich Panel for custom logo to ensure proper rendering
            from rich.panel import Panel as LogoPanel
            logo_panel = LogoPanel(
                _custom_logo.strip(),
                border_style="dim #2A2A50",
                padding=(0, 1),
            )
            console.print(logo_panel)
        else:
            # Default: Build a bento-style banner with god art + logo side by side
            from rich.table import Table as BentoTable
            from rich.panel import Panel as BentoPanel
            
            # Get the hero art (caduceus) from skin or use default
            _hero = _bskin.banner_hero if _bskin and hasattr(_bskin, 'banner_hero') and _bskin.banner_hero else HERMES_CADUCEUS
            
            bento = BentoTable(show_header=False, show_edge=False, box=None, padding=(0, 2))
            bento.add_column("art", width=28, no_wrap=True)
            bento.add_column("logo", no_wrap=True)
            bento.add_row(_hero.strip(), HERMES_AGENT_LOGO)
            
            bento_panel = BentoPanel(
                bento,
                border_style="dim #2A2A50",
                padding=(0, 1),
            )
            console.print(bento_panel)
        console.print()
    console.print(outer_panel)
