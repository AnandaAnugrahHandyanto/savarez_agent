from queue import Queue
from unittest.mock import MagicMock, patch


def _make_cli():
    from cli import HermesCLI

    cli = HermesCLI.__new__(HermesCLI)
    cli.config = {}
    cli.console = MagicMock()
    cli.agent = None
    cli.conversation_history = []
    cli.session_id = "test-session"
    cli._pending_input = Queue()
    return cli


def test_cli_notebooklm_empty_args_prints_usage():
    cli = _make_cli()

    with patch("cli._cprint") as cprint:
        result = cli.process_command("/notebooklm")

    assert result is True
    assert cli._pending_input.empty()
    assert "Usage: /notebooklm" in cprint.call_args[0][0]


def test_cli_notebooklm_queues_learnpack_prompt():
    cli = _make_cli()

    with patch("cli._cprint"):
        result = cli.process_command("/notebooklm kb vibe coding")

    assert result is True
    prompt = cli._pending_input.get_nowait()
    assert "Run the NotebookLM LearnPack workflow for: kb vibe coding" in prompt
    assert "Study Guide" in prompt


def test_cli_notebooklm_alias_preserves_payload():
    cli = _make_cli()

    with patch("cli._cprint"):
        cli.process_command("/nlm 知识库里的 agent memory")

    prompt = cli._pending_input.get_nowait()
    assert "知识库里的 agent memory" in prompt
