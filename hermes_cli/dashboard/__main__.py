"""Allow `python -m hermes_cli.dashboard` to launch the dashboard."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.resolve()))

from hermes_cli.dashboard.app import run_dashboard

run_dashboard()
