from hermes_cli._parser import build_top_level_parser


def test_top_level_chat_flags_survive_when_subcommand_comes_last() -> None:
    parser, _subparsers, _chat_parser = build_top_level_parser()

    args = parser.parse_args([
        "-m",
        "anthropic/claude-sonnet-4.6",
        "--provider",
        "anthropic",
        "-t",
        "web",
        "--tui",
        "chat",
    ])

    assert args.command == "chat"
    assert args.model == "anthropic/claude-sonnet-4.6"
    assert args.provider == "anthropic"
    assert args.toolsets == "web"
    assert args.tui is True


def test_chat_subparser_flags_still_work_when_subcommand_comes_first() -> None:
    parser, _subparsers, _chat_parser = build_top_level_parser()

    args = parser.parse_args([
        "chat",
        "-m",
        "anthropic/claude-sonnet-4.6",
        "--provider",
        "anthropic",
        "-t",
        "web",
        "--tui",
    ])

    assert args.command == "chat"
    assert args.model == "anthropic/claude-sonnet-4.6"
    assert args.provider == "anthropic"
    assert args.toolsets == "web"
    assert args.tui is True



def test_chat_subparser_defaults_still_exist_without_shared_top_level_flags() -> None:
    parser, _subparsers, _chat_parser = build_top_level_parser()

    args = parser.parse_args(["chat"])

    assert args.command == "chat"
    assert args.tui is False
    assert args.model is None
    assert args.provider is None
    assert args.toolsets is None
