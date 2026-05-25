from __future__ import annotations

import asyncio
from types import SimpleNamespace

from cli import HermesCLI


def test_cli_whatsapp_outreach_keeps_adapter_lifecycle_on_one_event_loop(monkeypatch):
    captured = {}

    class LoopBoundAdapter:
        def __init__(self, _config):
            self.connect_loop = None
            self.execute_loop = None
            self.disconnect_loop = None

        async def connect(self):
            self.connect_loop = asyncio.get_running_loop()
            captured["adapter"] = self
            return True

        async def disconnect(self):
            self.disconnect_loop = asyncio.get_running_loop()

    async def _fake_execute(run_request, *, authorized, adapter):
        assert authorized is True
        adapter.execute_loop = asyncio.get_running_loop()
        assert adapter.execute_loop is adapter.connect_loop
        assert run_request["operator_ingress_surface"] == "cli_chat"
        return {"workflow_status": "ready"}

    class _Console:
        def print(self, *_args, **_kwargs):
            return None

    from gateway.config import Platform

    monkeypatch.setattr(
        "gateway.config.load_gateway_config",
        lambda: SimpleNamespace(
            platforms={Platform.WHATSAPP: SimpleNamespace(enabled=True)}
        ),
    )
    monkeypatch.setattr("gateway.platforms.whatsapp.WhatsAppAdapter", LoopBoundAdapter)
    monkeypatch.setattr("cli.execute_whatsapp_approved_outreach", _fake_execute)
    monkeypatch.setattr(
        "cli.format_whatsapp_approved_outreach_result",
        lambda result: f"Status: {result['workflow_status']}",
    )
    monkeypatch.setattr("cli.ChatConsole", lambda: _Console())
    monkeypatch.setattr(
        "cli._render_final_assistant_content",
        lambda text, mode=None: text,
    )

    hermes_cli = HermesCLI.__new__(HermesCLI)
    hermes_cli.session_id = "sess-cli-runtime"
    hermes_cli.conversation_history = []
    hermes_cli.final_response_markdown = "strip"
    hermes_cli._print_user_message_preview = lambda _text: None
    hermes_cli._scrollback_box_width = lambda: 80

    handled = hermes_cli._run_whatsapp_cli_chat_outreach(
        "whatsapp outreach approved_destination_chat_id=15551230000@s.whatsapp.net "
        'operator_objective="Request the first quote" '
        'message_text="Hello from Hermes."'
    )

    assert handled is True
    adapter = captured["adapter"]
    assert adapter.connect_loop is not None
    assert adapter.execute_loop is adapter.connect_loop
    assert adapter.disconnect_loop is adapter.connect_loop
    assert hermes_cli.conversation_history[0]["role"] == "user"
    assert hermes_cli.conversation_history[1]["content"] == "Status: ready"
