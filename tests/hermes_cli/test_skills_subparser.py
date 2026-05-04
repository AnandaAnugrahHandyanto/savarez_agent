"""Test that skills subparser doesn't conflict (regression test for #898).

Also smoke-tests the four lifecycle subparsers added for #19384
(stats / archive / restore / prune) by replicating the argparse block
in isolation — same pattern used by test_subparser_routing_fallback.py
and test_argparse_flag_propagation.py.
"""

import argparse

import pytest


def test_no_duplicate_skills_subparser():
    """Ensure 'skills' subparser is only registered once to avoid Python 3.11+ crash.

    Python 3.11 changed argparse to raise an exception on duplicate subparser
    names instead of silently overwriting (see CPython #94331).

    This test will fail with:
        argparse.ArgumentError: argument command: conflicting subparser: skills

    if the duplicate 'skills' registration is reintroduced.
    """
    # Force fresh import of the module where parser is constructed
    # If there are duplicate 'skills' subparsers, this import will raise
    # argparse.ArgumentError at module load time
    import importlib
    import sys

    # Remove cached module if present
    if 'hermes_cli.main' in sys.modules:
        del sys.modules['hermes_cli.main']

    try:
        import hermes_cli.main  # noqa: F401
    except argparse.ArgumentError as e:
        if "conflicting subparser" in str(e):
            raise AssertionError(
                f"Duplicate subparser detected: {e}. "
                "See issue #898 for details."
            ) from e
        raise


# ─── Lifecycle subparser smoke tests (issue #19384) ──────────────────────────

def _build_skills_lifecycle_parser():
    """Minimal replica of the lifecycle block in hermes_cli/main.py.

    Mirrors stats/archive/restore/prune verbatim so argparse semantics can
    be verified without importing the full CLI (which has heavy module-load
    side effects).
    """
    parser = argparse.ArgumentParser(prog="hermes")
    sub = parser.add_subparsers(dest="command")
    skills = sub.add_parser("skills")
    skills_sub = skills.add_subparsers(dest="skills_action")

    stats = skills_sub.add_parser("stats")
    stats.add_argument("--days", type=int, default=None)

    archive = skills_sub.add_parser("archive")
    archive.add_argument("name")

    restore = skills_sub.add_parser("restore")
    restore.add_argument("name")

    prune = skills_sub.add_parser("prune")
    prune.add_argument("--days", type=int, default=90)
    prune.add_argument("--yes", "-y", action="store_true")
    prune.add_argument("--dry-run", action="store_true")

    return parser


def test_stats_subparser_no_days():
    args = _build_skills_lifecycle_parser().parse_args(["skills", "stats"])
    assert args.skills_action == "stats"
    assert args.days is None


def test_stats_subparser_with_days():
    args = _build_skills_lifecycle_parser().parse_args(
        ["skills", "stats", "--days", "7"]
    )
    assert args.skills_action == "stats"
    assert args.days == 7


def test_archive_subparser_requires_name():
    parser = _build_skills_lifecycle_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["skills", "archive"])


def test_archive_subparser_with_name():
    args = _build_skills_lifecycle_parser().parse_args(
        ["skills", "archive", "foo-skill"]
    )
    assert args.skills_action == "archive"
    assert args.name == "foo-skill"


def test_restore_subparser_with_name():
    args = _build_skills_lifecycle_parser().parse_args(
        ["skills", "restore", "foo-skill"]
    )
    assert args.skills_action == "restore"
    assert args.name == "foo-skill"


def test_prune_subparser_defaults():
    args = _build_skills_lifecycle_parser().parse_args(["skills", "prune"])
    assert args.skills_action == "prune"
    assert args.days == 90
    assert args.yes is False
    assert args.dry_run is False


def test_prune_subparser_full_flags():
    args = _build_skills_lifecycle_parser().parse_args(
        ["skills", "prune", "--days", "30", "--yes", "--dry-run"]
    )
    assert args.skills_action == "prune"
    assert args.days == 30
    assert args.yes is True
    assert args.dry_run is True


def test_prune_subparser_yes_short_flag():
    args = _build_skills_lifecycle_parser().parse_args(["skills", "prune", "-y"])
    assert args.yes is True
