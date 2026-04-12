import queue
import sys
from unittest.mock import MagicMock, patch

from hermes_state import SessionDB
from tests.cli.test_cli_new_session import _make_cli


class TestLiveCliSessions:
    def _make_cli(self, tmp_path, session_id="sess_sender"):
        with patch.dict(sys.modules, {"fire": MagicMock()}):
            cli = _make_cli()
        cli.config = {"quick_commands": {}}
        cli.console = MagicMock()
        cli._session_db = SessionDB(db_path=tmp_path / "state.db")
        cli.session_id = session_id
        cli.model = "gpt-5.4"
        cli.provider = "openai"
        cli._pending_input = queue.Queue()
        cli._agent_running = False
        cli.session_start = None
        cli.agent = None
        cli.conversation_history = []
        cli._should_exit = False
        return cli

    def test_role_command_sets_live_role(self, tmp_path):
        cli = self._make_cli(tmp_path)
        cli._session_db.upsert_live_session(cli.session_id, source="cli")

        with patch("cli._cprint"):
            cli.process_command("/role orchestrator")

        row, error = cli._session_db.resolve_live_session(cli.session_id)
        assert error is None
        assert row["role"] == "orchestrator"
        assert cli._live_role == "orchestrator"

    def test_send_command_queues_message_for_target(self, tmp_path):
        sender = self._make_cli(tmp_path, session_id="sess_sender")
        receiver = self._make_cli(tmp_path, session_id="sess_receiver")
        sender._session_db.upsert_live_session(sender.session_id, source="cli", role="orchestrator")
        sender._live_role = "orchestrator"
        receiver._session_db.upsert_live_session(receiver.session_id, source="cli", role="executor")

        with patch("cli._cprint"):
            sender.process_command("/send executor Implement the feature")

        claimed = receiver._session_db.claim_live_messages(receiver.session_id)
        assert len(claimed) == 1
        assert claimed[0]["body"] == "Implement the feature"
        assert claimed[0]["sender_label"] == "orchestrator"

    def test_drain_live_messages_enqueues_received_prompt(self, tmp_path):
        receiver = self._make_cli(tmp_path, session_id="sess_receiver")
        receiver._session_db.upsert_live_session(receiver.session_id, source="cli", role="executor")
        receiver._session_db.queue_live_message(
            target_session_id=receiver.session_id,
            sender_session_id="sess_sender",
            sender_label="orchestrator",
            sender_model="gpt-5.4",
            body="Do the implementation",
        )

        with patch("cli._cprint"):
            events = receiver._drain_live_session_messages()

        assert len(events) == 1
        assert receiver._pending_input.get_nowait() == "Do the implementation"
