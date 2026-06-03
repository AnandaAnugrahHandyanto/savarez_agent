"""Regression test: ``hermes mcp add --env`` must accumulate values across
repeated flag occurrences instead of overwriting them.

When a user runs:
    hermes mcp add myserver --command npx --env A=1 --env B=2

argparse with ``nargs="*"`` and no explicit action defaults to ``"store"``
which overwrites the previous value.  The fix is ``action="extend"``.

We replicate the relevant parser shape here rather than importing the real
builder, mirroring ``test_mcp_add_command_dest.py``.
"""

import argparse


def _build_parser():
    """Minimal replica of the ``hermes mcp add`` parser slice that exhibits
    the ``--env`` accumulation bug.
    """
    parser = argparse.ArgumentParser(prog="hermes")
    subparsers = parser.add_subparsers(dest="command")

    mcp_p = subparsers.add_parser("mcp")
    mcp_sub = mcp_p.add_subparsers(dest="mcp_action")

    mcp_add = mcp_sub.add_parser("add")
    mcp_add.add_argument("name")
    mcp_add.add_argument("--url")
    mcp_add.add_argument("--command", dest="mcp_command")
    mcp_add.add_argument(
        "--env",
        nargs="*",
        action="extend",
        default=[],
        help="Environment variables for stdio servers (KEY=VALUE).",
    )

    return parser


class TestMcpEnvParsing:
    """--env flag must accumulate all KEY=VALUE pairs across repetitions."""

    def test_single_env_flag_single_value(self):
        """`--env A=1` → args.env == ['A=1']."""
        parser = _build_parser()
        args = parser.parse_args(["mcp", "add", "srv", "--env", "A=1"])
        assert args.env == ["A=1"]

    def test_single_env_flag_multiple_values(self):
        """`--env A=1 B=2` (multiple values after one flag) → ['A=1', 'B=2']."""
        parser = _build_parser()
        args = parser.parse_args(["mcp", "add", "srv", "--env", "A=1", "B=2"])
        assert args.env == ["A=1", "B=2"]

    def test_repeated_env_flag_accumulates(self):
        """`--env A=1 --env B=2` must yield BOTH values (regression guard).

        Before the ``action="extend"`` fix, argparse with ``nargs="*"``
        and the default ``action="store"`` would overwrite the first
        occurrence, leaving only ``['B=2']``.
        """
        parser = _build_parser()
        args = parser.parse_args(
            ["mcp", "add", "srv", "--command", "npx", "--env", "A=1", "--env", "B=2"]
        )
        assert args.env == ["A=1", "B=2"], (
            "--env flag must accumulate all values; "
            f"got {args.env!r} — action='extend' may be missing"
        )

    def test_repeated_env_flag_three_values(self):
        """`--env A=1 --env B=2 --env C=3` must preserve all three entries."""
        parser = _build_parser()
        args = parser.parse_args(
            ["mcp", "add", "srv", "--env", "A=1", "--env", "B=2", "--env", "C=3"]
        )
        assert args.env == ["A=1", "B=2", "C=3"]

    def test_no_env_flag_yields_empty_list(self):
        """`hermes mcp add srv --url ...` with no --env must yield []."""
        parser = _build_parser()
        args = parser.parse_args(
            ["mcp", "add", "srv", "--url", "https://example.com/mcp"]
        )
        assert args.env == []

    def test_env_flag_does_not_clobber_top_level_command(self):
        """Passing --env must not affect args.command (top-level dispatch key)."""
        parser = _build_parser()
        args = parser.parse_args(
            ["mcp", "add", "srv", "--env", "X=1", "--env", "Y=2"]
        )
        assert args.command == "mcp"
        assert args.mcp_action == "add"
