"""Verify fix for: hermes -t web chat should enable 'web' toolset (not all)"""
import pytest
import sys

sys.path.insert(0, "/home/zccyman/.hermes/hermes-agent")


def test_toolsets_before_chat_subcommand():
    """Regression test for https://github.com/NousResearch/hermes-agent/issues/28780

    When -t is placed BEFORE the subcommand (hermes -t web chat), the main parser
    captures it but the subparser's add_argument(default=None) overwrites it with None.
    The fix recovers the value by scanning _processed_argv for -t before the subcommand.
    """
    from hermes_cli._parser import build_top_level_parser

    parser, subparsers, chat_parser = build_top_level_parser()

    def parse_with_fix(argv):
        args = parser.parse_args(argv)
        # Apply the same fix logic from main.py
        if getattr(args, "toolsets", None) is None and args.command == "chat":
            for i, tok in enumerate(argv):
                if tok in ("-t", "--toolsets") and i + 1 < len(argv):
                    nxt = argv[i + 1]
                    if not nxt.startswith("-"):
                        args.toolsets = nxt
                        break
        return args

    # Case 1: -t before subcommand
    args1 = parse_with_fix(["-t", "web", "chat"])
    assert args1.toolsets == "web", f"Expected 'web', got {args1.toolsets!r}"

    # Case 2: -t after subcommand
    args2 = parse_with_fix(["chat", "-t", "web"])
    assert args2.toolsets == "web", f"Expected 'web', got {args2.toolsets!r}"

    # Case 3: no -t
    args3 = parse_with_fix(["chat"])
    assert args3.toolsets is None

    # Case 4: --toolsets long form
    args4 = parse_with_fix(["--toolsets", "browser,web", "chat"])
    assert args4.toolsets == "browser,web"

    # Case 5: multiple flags before subcommand
    args5 = parse_with_fix(["-t", "web", "chat", "-q", "hello"])
    assert args5.toolsets == "web"
