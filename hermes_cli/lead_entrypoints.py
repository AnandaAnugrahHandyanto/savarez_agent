"""Pane-local Hermes lead launchers.

These entry points are intentionally tiny: they pin the current process to a
lead mode through HERMES_LEAD_MODE and then run the normal Hermes CLI.  They do
not write the global orchestrator-mode file, so two Wave panes can run Hugo and
Clara side by side without flipping each other or Slack.
"""

from __future__ import annotations

import os

from gateway.orchestrator_modes import ENV_LEAD_MODE, MODE_CLARA_LEAD, MODE_HUGO_LEAD
from hermes_cli.main import main


def main_hugo() -> None:
    os.environ[ENV_LEAD_MODE] = MODE_HUGO_LEAD
    main()


def main_clara() -> None:
    os.environ[ENV_LEAD_MODE] = MODE_CLARA_LEAD
    main()
