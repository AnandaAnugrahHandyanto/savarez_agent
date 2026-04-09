"""hermes hierarchy — CLI dispatcher for the hierarchy system."""
from __future__ import annotations
import sys


def cmd_hierarchy(args) -> None:
    """Dispatch hermes hierarchy subcommands."""
    try:
        from hierarchy.core.cli import main as hierarchy_main
    except ImportError:
        print("Hierarchy system not available. Run: pip install -e '.[hierarchy-ui]'")
        sys.exit(1)

    subcmd = getattr(args, "hierarchy_command", None)
    if not subcmd:
        print("Usage: hermes hierarchy <command>")
        print("Commands: show-org-chart, list-profiles, ipc-stats, sync-profiles, gateway, ui")
        return

    # Map subcommand to argv and call hierarchy CLI
    argv_map = {
        "show-org-chart": ["show-org-chart"],
        "list-profiles": ["list-profiles"],
        "ipc-stats": ["ipc-stats"],
        "sync-profiles": ["sync-profiles"],
    }

    if subcmd in argv_map:
        sys.argv = ["hermes-hierarchy"] + argv_map[subcmd]
        hierarchy_main()
    elif subcmd == "gateway":
        action = getattr(args, "gateway_action", "start")
        profile = getattr(args, "gateway_profile", "")
        from hierarchy.scripts.hierarchy_gateway import main as gw_main
        sys.argv = ["hermes-hierarchy-gateway", action, profile]
        gw_main()
    elif subcmd == "ui":
        from hierarchy.ui.__main__ import main as ui_main
        ui_main()
