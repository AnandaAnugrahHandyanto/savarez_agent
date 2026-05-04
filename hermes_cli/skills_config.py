"""
Skills configuration for Hermes Agent.
`hermes skills` enters this module.

Toggle individual skills or categories on/off, globally or per-platform.
Config stored in ~/.hermes/config.yaml under:

  skills:
    disabled: [skill-a, skill-b]          # global disabled list
    platform_disabled:                    # per-platform overrides
      telegram: [skill-c]
      cli: []
"""
from typing import List, Optional, Set

from hermes_cli.config import cfg_get, load_config, save_config
from hermes_cli.colors import Colors, color
from hermes_cli.platforms import PLATFORMS as _PLATFORMS

# Backward-compatible view: {key: label_string} so existing code that
# iterates ``PLATFORMS.items()`` or calls ``PLATFORMS.get(key)`` keeps
# working without changes to every call site.
PLATFORMS = {k: info.label for k, info in _PLATFORMS.items() if k != "api_server"}

# ─── Config Helpers ───────────────────────────────────────────────────────────

def get_disabled_skills(config: dict, platform: Optional[str] = None) -> Set[str]:
    """Return disabled skill names. Platform-specific list falls back to global."""
    skills_cfg = config.get("skills", {})
    global_disabled = set(skills_cfg.get("disabled", []))
    if platform is None:
        return global_disabled
    platform_disabled = cfg_get(skills_cfg, "platform_disabled", platform)
    if platform_disabled is None:
        return global_disabled
    return set(platform_disabled)


def save_disabled_skills(config: dict, disabled: Set[str], platform: Optional[str] = None):
    """Persist disabled skill names to config."""
    config.setdefault("skills", {})
    if platform is None:
        config["skills"]["disabled"] = sorted(disabled)
    else:
        config["skills"].setdefault("platform_disabled", {})
        config["skills"]["platform_disabled"][platform] = sorted(disabled)
    save_config(config)


# ─── Skill Discovery ─────────────────────────────────────────────────────────

def _list_all_skills() -> List[dict]:
    """Return all installed skills (ignoring disabled state)."""
    try:
        from tools.skills_tool import _find_all_skills
        return _find_all_skills(skip_disabled=True)
    except Exception:
        return []


def _get_categories(skills: List[dict]) -> List[str]:
    """Return sorted unique category names (None -> 'uncategorized')."""
    return sorted({s["category"] or "uncategorized" for s in skills})


# ─── Platform Selection ──────────────────────────────────────────────────────

def _select_platform() -> Optional[str]:
    """Ask user which platform to configure, or global."""
    options = [("global", "All platforms (global default)")] + list(PLATFORMS.items())
    print()
    print(color("  Configure skills for:", Colors.BOLD))
    for i, (key, label) in enumerate(options, 1):
        print(f"  {i}. {label}")
    print()
    try:
        raw = input(color("  Select [1]: ", Colors.YELLOW)).strip()
    except (KeyboardInterrupt, EOFError):
        return None
    if not raw:
        return None  # global
    try:
        idx = int(raw) - 1
        if 0 <= idx < len(options):
            key = options[idx][0]
            return None if key == "global" else key
    except ValueError:
        pass
    return None


# ─── Category Toggle ─────────────────────────────────────────────────────────

def _toggle_by_category(skills: List[dict], disabled: Set[str]) -> Set[str]:
    """Toggle all skills in a category at once."""
    from hermes_cli.curses_ui import curses_checklist

    categories = _get_categories(skills)
    cat_labels = []
    # A category is "enabled" (checked) when NOT all its skills are disabled
    pre_selected = set()
    for i, cat in enumerate(categories):
        cat_skills = [s["name"] for s in skills if (s["category"] or "uncategorized") == cat]
        cat_labels.append(f"{cat} ({len(cat_skills)} skills)")
        if not all(s in disabled for s in cat_skills):
            pre_selected.add(i)

    chosen = curses_checklist(
        "Categories — toggle entire categories",
        cat_labels, pre_selected, cancel_returns=pre_selected,
    )

    new_disabled = set(disabled)
    for i, cat in enumerate(categories):
        cat_skills = {s["name"] for s in skills if (s["category"] or "uncategorized") == cat}
        if i in chosen:
            new_disabled -= cat_skills  # category enabled → remove from disabled
        else:
            new_disabled |= cat_skills  # category disabled → add to disabled
    return new_disabled


# ─── Entry Point ──────────────────────────────────────────────────────────────

def skills_command(args=None):
    """Entry point for `hermes skills`."""
    from hermes_cli.curses_ui import curses_checklist

    config = load_config()
    skills = _list_all_skills()

    if not skills:
        print(color("  No skills installed.", Colors.DIM))
        return

    # Step 1: Select platform
    platform = _select_platform()
    platform_label = PLATFORMS.get(platform, "All platforms") if platform else "All platforms"

    # Step 2: Select mode — individual or by category
    print()
    print(color(f"  Configure for: {platform_label}", Colors.DIM))
    print()
    print("  1. Toggle individual skills")
    print("  2. Toggle by category")
    print()
    try:
        mode = input(color("  Select [1]: ", Colors.YELLOW)).strip() or "1"
    except (KeyboardInterrupt, EOFError):
        return

    disabled = get_disabled_skills(config, platform)

    if mode == "2":
        new_disabled = _toggle_by_category(skills, disabled)
    else:
        # Build labels and map indices → skill names
        labels = [
            f"{s['name']}  ({s['category'] or 'uncategorized'})  —  {s['description'][:55]}"
            for s in skills
        ]
        # "selected" = enabled (not disabled) — matches the [✓] convention
        pre_selected = {i for i, s in enumerate(skills) if s["name"] not in disabled}
        chosen = curses_checklist(
            f"Skills for {platform_label}",
            labels, pre_selected, cancel_returns=pre_selected,
        )
        # Anything NOT chosen is disabled
        new_disabled = {skills[i]["name"] for i in range(len(skills)) if i not in chosen}

    if new_disabled == disabled:
        print(color("  No changes.", Colors.DIM))
        return

    save_disabled_skills(config, new_disabled, platform)
    enabled_count = len(skills) - len(new_disabled)
    print(color(f"✓ Saved: {enabled_count} enabled, {len(new_disabled)} disabled ({platform_label}).", Colors.GREEN))


# ─── Lifecycle Commands (stats / archive / restore / prune) ──────────────────
#
# These four verbs are the user-facing surface for the curator's sidecar
# telemetry (~/.hermes/skills/.usage.json). The curator background task
# (agent/curator.py) consumes the same data to decide auto-transitions; this
# CLI lets users inspect and override those decisions manually.

def skills_overflow_command(args):
    """Dispatch for `hermes skills {stats,archive,restore,prune}`."""
    action = args.skills_action
    if action == "stats":
        _cmd_stats(getattr(args, "days", None))
    elif action == "archive":
        _cmd_archive(args.name)
    elif action == "restore":
        _cmd_restore(args.name)
    elif action == "prune":
        _cmd_prune(
            getattr(args, "days", 90),
            getattr(args, "yes", False),
            getattr(args, "dry_run", False),
        )


def _parse_iso(ts):
    """Parse an ISO timestamp into a tz-aware datetime, or None on failure."""
    if not ts:
        return None
    import datetime as _dt
    try:
        dt = _dt.datetime.fromisoformat(str(ts))
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_dt.timezone.utc)
    return dt


def _format_relative(iso_ts: Optional[str]) -> str:
    """Render an ISO timestamp as a relative phrase (e.g. '3d ago')."""
    if not iso_ts:
        return "never"
    import datetime as _dt
    dt = _parse_iso(iso_ts)
    if dt is None:
        return "?"
    delta = (_dt.datetime.now(_dt.timezone.utc) - dt).total_seconds()
    if delta < 60:
        return "just now"
    if delta < 3600:
        return f"{int(delta / 60)}m ago"
    if delta < 86400:
        return f"{int(delta / 3600)}h ago"
    if delta < 172800:
        return "yesterday"
    if delta < 604800:
        return f"{int(delta / 86400)}d ago"
    return dt.strftime("%Y-%m-%d")


def _idle_days(record: dict) -> Optional[int]:
    """Days since last activity, falling back to created_at when no activity.

    Returns None only if both fields are missing/unparseable — never-tracked
    skills shouldn't get pruned by accident.
    """
    import datetime as _dt
    dt = _parse_iso(record.get("last_activity_at")) or _parse_iso(record.get("created_at"))
    if dt is None:
        return None
    return max(0, (_dt.datetime.now(_dt.timezone.utc) - dt).days)


def _activity_sort_key(iso_ts) -> float:
    """Convert an ISO timestamp to unix seconds for sorting; 0 if missing."""
    dt = _parse_iso(iso_ts)
    return dt.timestamp() if dt else 0.0


def _cmd_stats(since_days: Optional[int]) -> None:
    """Print a per-skill usage table, ranked by activity_count desc."""
    from tools.skill_usage import agent_created_report

    rows = agent_created_report()
    if not rows:
        print(color("  No agent-created skills tracked yet.", Colors.DIM))
        print("  (Bundled and hub-installed skills are excluded from curator stats.)")
        return

    if since_days is not None:
        import datetime as _dt
        cutoff = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=since_days)
        rows = [
            r for r in rows
            if (dt := _parse_iso(r.get("last_activity_at"))) is not None and dt >= cutoff
        ]
        if not rows:
            print(color(f"  No activity in the last {since_days} day(s).", Colors.DIM))
            return

    rows.sort(key=lambda r: (
        -int(r.get("activity_count") or 0),
        -_activity_sort_key(r.get("last_activity_at")),
    ))

    title = f"Skill usage (last {since_days} days)" if since_days is not None else "Skill usage"

    try:
        from rich.console import Console
        from rich.table import Table
    except ImportError:
        # Plain-text fallback — unlikely (rich is a runtime dep) but defensive.
        print(f"\n{title}")
        print(f"{'Skill':<30} {'Uses':>5} {'Views':>5} {'Patch':>5} "
              f"{'Last activity':<14} {'Idle':>6} {'State':<10} Pin")
        print("─" * 90)
        for r in rows:
            idle = _idle_days(r)
            print(
                f"{str(r['name'])[:29]:<30} "
                f"{(r.get('use_count') or 0):>5} "
                f"{(r.get('view_count') or 0):>5} "
                f"{(r.get('patch_count') or 0):>5} "
                f"{_format_relative(r.get('last_activity_at'))[:13]:<14} "
                f"{('—' if idle is None else f'{idle}d'):>6} "
                f"{str(r.get('state') or 'active')[:9]:<10} "
                f"{'pinned' if r.get('pinned') else ''}"
            )
        print(f"\n{len(rows)} skill(s)")
        return

    c = Console()
    t = Table(title=title)
    t.add_column("Skill", style="bold")
    t.add_column("Uses", justify="right")
    t.add_column("Views", justify="right")
    t.add_column("Patches", justify="right")
    t.add_column("Last activity")
    t.add_column("Idle", justify="right")
    t.add_column("State")
    t.add_column("Pin")
    for r in rows:
        idle = _idle_days(r)
        t.add_row(
            str(r["name"]),
            str(r.get("use_count") or 0),
            str(r.get("view_count") or 0),
            str(r.get("patch_count") or 0),
            _format_relative(r.get("last_activity_at")),
            "—" if idle is None else f"{idle}d",
            str(r.get("state") or "active"),
            "📌" if r.get("pinned") else "",
        )
    c.print(t)


def _cmd_archive(name: str) -> None:
    """Archive a single skill. Refuses if the skill is pinned."""
    import sys
    from tools.skill_usage import archive_skill, get_record

    if get_record(name).get("pinned"):
        print(
            color(
                f"Refusing: '{name}' is pinned. "
                f"Unpin first: hermes curator unpin {name}",
                Colors.RED,
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    ok, msg = archive_skill(name)
    if ok:
        print(color(f"✓ {msg}", Colors.GREEN))
    else:
        print(color(f"✗ {msg}", Colors.RED), file=sys.stderr)
        sys.exit(1)


def _cmd_restore(name: str) -> None:
    """Restore a single archived skill."""
    import sys
    from tools.skill_usage import restore_skill

    ok, msg = restore_skill(name)
    if ok:
        print(color(f"✓ {msg}", Colors.GREEN))
    else:
        print(color(f"✗ {msg}", Colors.RED), file=sys.stderr)
        sys.exit(1)


def _cmd_prune(days: int, skip_confirm: bool, dry_run: bool) -> None:
    """Bulk-archive skills idle for ≥ N days. Pinned skills are exempt."""
    import sys
    if days < 1:
        print(
            color(f"--days must be ≥ 1 (got {days})", Colors.RED),
            file=sys.stderr,
        )
        sys.exit(2)
    from tools.skill_usage import agent_created_report, archive_skill

    candidates = []
    for r in agent_created_report():
        if r.get("pinned"):
            continue
        if r.get("state") == "archived":
            continue
        idle = _idle_days(r)
        if idle is None or idle < days:
            continue
        candidates.append((r["name"], idle, r.get("last_activity_at")))

    if not candidates:
        print(color(f"  Nothing to prune (no skills idle ≥ {days} days).", Colors.DIM))
        return

    candidates.sort(key=lambda c: -c[1])

    print(color(
        f"\nSkills idle ≥ {days} days ({len(candidates)} candidate(s)):",
        Colors.BOLD,
    ))
    print(f"  {'Skill':<32} {'Idle':>8}  Last activity")
    print("  " + "─" * 70)
    for name, idle, last in candidates:
        print(f"  {name[:31]:<32} {f'{idle}d':>8}  {_format_relative(last)}")
    print()

    if dry_run:
        print(color("  Dry run — no changes made.", Colors.DIM))
        return

    if not skip_confirm:
        try:
            answer = input(
                color(f"Archive these {len(candidates)} skill(s)? [y/N]: ", Colors.YELLOW)
            ).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.")
            return
        if answer not in ("y", "yes"):
            print("Aborted.")
            return

    archived = 0
    failed = 0
    for name, _idle, _last in candidates:
        ok, msg = archive_skill(name)
        if ok:
            print(color(f"  ✓ {name}: {msg}", Colors.GREEN))
            archived += 1
        else:
            print(color(f"  ✗ {name}: {msg}", Colors.RED))
            failed += 1

    summary = f"\nArchived {archived}/{len(candidates)}"
    if failed:
        summary += f" — {failed} failed"
    print(color(summary, Colors.GREEN if not failed else Colors.YELLOW))
