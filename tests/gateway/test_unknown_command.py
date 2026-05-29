"""Tests for gateway warning when an unrecognized /command is dispatched.

Without this warning, unknown slash commands get forwarded to the LLM as plain
text, which often leads to silent failure (e.g. the model inventing a bogus
delegate_task call instead of telling the user the command doesn't exist).
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.config import GatewayConfig, Platform, PlatformConfig
from gateway.platforms.base import MessageEvent
from gateway.session import SessionEntry, SessionSource, build_session_key


def _make_source() -> SessionSource:
    return SessionSource(
        platform=Platform.TELEGRAM,
        user_id="u1",
        chat_id="c1",
        user_name="tester",
        chat_type="dm",
    )


def _make_event(text: str) -> MessageEvent:
    return MessageEvent(text=text, source=_make_source(), message_id="m1")


def _make_runner():
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner.config = GatewayConfig(
        platforms={Platform.TELEGRAM: PlatformConfig(enabled=True, token="***")}
    )
    adapter = MagicMock()
    adapter.send = AsyncMock()
    runner.adapters = {Platform.TELEGRAM: adapter}
    runner._voice_mode = {}
    runner.hooks = SimpleNamespace(
        emit=AsyncMock(),
        emit_collect=AsyncMock(return_value=[]),
        loaded_hooks=False,
    )

    session_entry = SessionEntry(
        session_key=build_session_key(_make_source()),
        session_id="sess-1",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        platform=Platform.TELEGRAM,
        chat_type="dm",
    )
    runner.session_store = MagicMock()
    runner.session_store.get_or_create_session.return_value = session_entry
    runner.session_store.load_transcript.return_value = []
    runner.session_store.has_any_sessions.return_value = True
    runner.session_store.append_to_transcript = MagicMock()
    runner.session_store.rewrite_transcript = MagicMock()
    runner.session_store.update_session = MagicMock()
    runner._running_agents = {}
    runner._pending_messages = {}
    runner._pending_approvals = {}
    runner._session_db = None
    runner._reasoning_config = None
    runner._provider_routing = {}
    runner._fallback_model = None
    runner._show_reasoning = False
    runner._is_user_authorized = lambda _source: True
    runner._set_session_env = lambda _context: None
    runner._should_send_voice_reply = lambda *_args, **_kwargs: False
    runner._send_voice_reply = AsyncMock()
    runner._capture_gateway_honcho_if_configured = lambda *args, **kwargs: None
    runner._emit_gateway_run_progress = AsyncMock()
    return runner


@pytest.mark.asyncio
async def test_unknown_slash_command_returns_guidance(monkeypatch):
    """A genuinely unknown /foobar should return user-facing guidance, not
    silently drop through to the LLM."""
    import gateway.run as gateway_run

    runner = _make_runner()
    # If the LLM were called, this would fail: the guard must short-circuit
    # before _run_agent is invoked.
    runner._run_agent = AsyncMock(
        side_effect=AssertionError(
            "unknown slash command leaked through to the agent"
        )
    )

    monkeypatch.setattr(
        gateway_run, "_resolve_runtime_agent_kwargs", lambda: {"api_key": "***"}
    )

    result = await runner._handle_message(_make_event("/definitely-not-a-command"))

    assert result is not None
    assert "Unknown command" in result
    assert "/definitely-not-a-command" in result
    assert "/commands" in result
    runner._run_agent.assert_not_called()


@pytest.mark.asyncio
async def test_unknown_slash_command_underscored_form_also_guarded(monkeypatch):
    """Telegram may send /foo_bar — same guard must trigger for underscored
    commands that normalize to unknown hyphenated names."""
    import gateway.run as gateway_run

    runner = _make_runner()
    runner._run_agent = AsyncMock(
        side_effect=AssertionError(
            "unknown slash command leaked through to the agent"
        )
    )

    monkeypatch.setattr(
        gateway_run, "_resolve_runtime_agent_kwargs", lambda: {"api_key": "***"}
    )

    result = await runner._handle_message(_make_event("/made_up_thing"))

    assert result is not None
    assert "Unknown command" in result
    assert "/made_up_thing" in result
    runner._run_agent.assert_not_called()


@pytest.mark.asyncio
async def test_james_accented_license_command_prompts_for_renavam(monkeypatch):
    """/licença is a James direct shortcut, not an unknown Hermes command."""
    import gateway.run as gateway_run

    runner = _make_runner()
    runner._run_agent = AsyncMock(side_effect=AssertionError("James shortcut leaked to the agent"))
    runner._call_james_vehicle_direct_adapter = AsyncMock(side_effect=AssertionError("should not call adapter without RENAVAM"))

    monkeypatch.setattr(
        gateway_run, "_resolve_runtime_agent_kwargs", lambda: {"api_key": "***"}
    )

    result = await runner._handle_message(_make_event("/licença"))

    assert result is not None
    assert "Unknown command" not in result
    assert "Me manda o RENAVAM" in result
    assert "/licenca 123456789" in result
    runner._run_agent.assert_not_called()


@pytest.mark.asyncio
async def test_james_help_command_lists_direct_shortcuts(monkeypatch):
    """/james returns a compact James-only command menu for Telegram."""
    import gateway.run as gateway_run

    runner = _make_runner()
    runner._run_agent = AsyncMock(side_effect=AssertionError("James help leaked to the agent"))

    monkeypatch.setattr(
        gateway_run, "_resolve_runtime_agent_kwargs", lambda: {"api_key": "***"}
    )

    result = await runner._handle_message(_make_event("/james"))

    assert result is not None
    assert "Comandos do James" in result
    assert "/licenca" in result
    assert "/transferencia" in result
    assert "RENAVAM" in result
    assert "Unknown command" not in result
    runner._run_agent.assert_not_called()


@pytest.mark.asyncio
async def test_james_transfer_command_calls_adapter_directly(monkeypatch):
    """/transferência <renavam> bypasses the agent/Core and calls Adapter."""
    import gateway.run as gateway_run

    runner = _make_runner()
    runner._run_agent = AsyncMock(side_effect=AssertionError("James shortcut leaked to the agent"))
    runner._call_james_vehicle_direct_adapter = AsyncMock(
        return_value={
            "ok": True,
            "status": 200,
            "body": (
                '{'
                '"valorFinal":602.79,'
                '"valorTaxas":469.91,'
                '"valorMultas":132.88,'
                '"valorIpvas":0,'
                '"renavam":"123456789",'
                '"placa":"ABC1D23",'
                '"documento":"00000000000",'
                '"documentoTipo":"CPF",'
                '"nome":"CLIENTE TESTE",'
                '"ocorrencia":{"codigo":"00","categoria":"sucesso","descricao":"TRANSAÇÃO CONFIRMADA E APROVADA"}'
                '}'
            ),
        }
    )

    monkeypatch.setattr(
        gateway_run, "_resolve_runtime_agent_kwargs", lambda: {"api_key": "***"}
    )

    result = await runner._handle_message(_make_event("/trasnferencia 123.456.789"))

    assert result is not None
    assert "James direto — Transferência" in result
    assert "Status: OK (HTTP 200)" in result
    assert "TRANSAÇÃO CONFIRMADA E APROVADA" in result
    assert "Valor base retornado: R$ 602,79" in result
    assert "Taxas: R$ 469,91" in result
    assert "Multas: R$ 132,88" in result
    assert "Honorários do Despachante" in result
    assert "Dados sensíveis ocultados" in result
    assert "consultar-transferencia" not in result
    assert "123456789" not in result
    assert "ABC1D23" not in result
    assert "00000000000" not in result
    assert "CLIENTE TESTE" not in result
    assert "valorFinal" not in result
    runner._call_james_vehicle_direct_adapter.assert_awaited_once_with(
        "/api-interna/consultar-transferencia", {"renavam": "123456789"}
    )
    runner._run_agent.assert_not_called()


@pytest.mark.asyncio
async def test_james_direct_command_hides_non_json_adapter_body(monkeypatch):
    """Non-JSON adapter bodies may contain PII and must not be echoed to chat."""
    import gateway.run as gateway_run

    runner = _make_runner()
    runner._run_agent = AsyncMock(side_effect=AssertionError("James shortcut leaked to the agent"))
    runner._call_james_vehicle_direct_adapter = AsyncMock(
        return_value={
            "ok": False,
            "status": 502,
            "body": "erro RENAVAM 123456789 placa ABC1D23 cpf 00000000000 CLIENTE TESTE",
        }
    )

    monkeypatch.setattr(
        gateway_run, "_resolve_runtime_agent_kwargs", lambda: {"api_key": "***"}
    )

    result = await runner._handle_message(_make_event("/licenca 123456789"))

    assert result is not None
    assert "Retorno técnico sem JSON tratável ocultado" in result
    assert "123456789" not in result
    assert "ABC1D23" not in result
    assert "00000000000" not in result
    assert "CLIENTE TESTE" not in result
    runner._run_agent.assert_not_called()


@pytest.mark.asyncio
async def test_james_direct_command_sanitizes_occurrence_text(monkeypatch):
    """PII copied into occurrence text must be redacted before chat output."""
    import gateway.run as gateway_run

    runner = _make_runner()
    runner._run_agent = AsyncMock(side_effect=AssertionError("James shortcut leaked to the agent"))
    runner._call_james_vehicle_direct_adapter = AsyncMock(
        return_value={
            "ok": True,
            "status": 200,
            "body": (
                '{'
                '"valorFinal":602.79,'
                '"renavam":"123456789",'
                '"placa":"ABC1D23",'
                '"documento":"00000000000",'
                '"nome":"CLIENTE TESTE",'
                '"ocorrencia":{'
                '"codigo":"token=abc123456",'
                '"categoria":"placa ABC1D23",'
                '"descricao":"RENAVAM 123456789 CPF 00000000000 CLIENTE TESTE"'
                '}'
                '}'
            ),
        }
    )

    monkeypatch.setattr(
        gateway_run, "_resolve_runtime_agent_kwargs", lambda: {"api_key": "***"}
    )

    result = await runner._handle_message(_make_event("/licenca 123456789"))

    assert result is not None
    assert "token=abc123456" not in result
    assert "123456789" not in result
    assert "ABC1D23" not in result
    assert "00000000000" not in result
    assert "CLIENTE TESTE" not in result
    assert "[dado sensível ocultado]" in result
    runner._run_agent.assert_not_called()


@pytest.mark.asyncio
async def test_james_status_command_reports_local_lab_health(monkeypatch):
    """/status_james reports James lab health without invoking the agent."""
    import gateway.run as gateway_run

    runner = _make_runner()
    runner._run_agent = AsyncMock(side_effect=AssertionError("James status leaked to the agent"))
    runner._call_james_health_endpoint = AsyncMock(
        side_effect=[
            {"ok": True, "status": 200, "body": '{"ok":true}'},
            {"ok": False, "status": 503, "body": "degraded"},
        ]
    )

    monkeypatch.setattr(
        gateway_run, "_resolve_runtime_agent_kwargs", lambda: {"api_key": "***"}
    )

    result = await runner._handle_message(_make_event("/status_james"))

    assert result is not None
    assert "Status James 2.0" in result
    assert "API Server local/lab: OK (HTTP 200)" in result
    assert "Adapter James local/lab: Falha (HTTP 503)" in result
    assert "sem restart" in result
    assert "Unknown command" not in result
    runner._run_agent.assert_not_called()


@pytest.mark.asyncio
async def test_james_proposta_generates_sanitized_local_draft(monkeypatch):
    """/proposta <renavam> consults the lab adapter and returns only a local draft."""
    import gateway.run as gateway_run

    runner = _make_runner()
    runner._run_agent = AsyncMock(side_effect=AssertionError("James proposta leaked to the agent"))
    runner._call_james_vehicle_direct_adapter = AsyncMock(
        return_value={
            "ok": True,
            "status": 200,
            "body": (
                '{'
                '"valorFinal":602.79,'
                '"valorTaxas":469.91,'
                '"valorMultas":132.88,'
                '"renavam":"123456789",'
                '"placa":"ABC1D23",'
                '"documento":"00000000000",'
                '"nome":"CLIENTE TESTE",'
                '"ocorrencia":{"descricao":"TRANSAÇÃO CONFIRMADA E APROVADA"}'
                '}'
            ),
        }
    )

    monkeypatch.setattr(
        gateway_run, "_resolve_runtime_agent_kwargs", lambda: {"api_key": "***"}
    )

    result = await runner._handle_message(_make_event("/proposta 123.456.789"))

    assert result is not None
    assert "Rascunho local/lab — proposta James" in result
    assert "NÃO enviar ao cliente automaticamente" in result
    assert "Total base retornado: R$ 602,79" in result
    assert "Taxas: R$ 469,91" in result
    assert "Multas: R$ 132,88" in result
    assert "Honorários do Despachante" in result
    assert "Dados sensíveis ocultados" in result
    assert "123456789" not in result
    assert "ABC1D23" not in result
    assert "00000000000" not in result
    assert "CLIENTE TESTE" not in result
    assert "Unknown command" not in result
    runner._call_james_vehicle_direct_adapter.assert_awaited_once_with(
        "/api-interna/consultar-licenciamento", {"renavam": "123456789"}
    )
    runner._run_agent.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("text", "canonical"),
    [
        ("/james", "james"),
        ("/licenca 123456789", "licenca"),
        ("/licença 123456789", "licenca"),
        ("/transferencia 123456789", "transferencia"),
        ("/transferência 123456789", "transferencia"),
        ("/status_james", "status_james"),
        ("/proposta 123456789", "proposta"),
    ],
)
async def test_james_commands_require_admin_when_slash_admins_configured(monkeypatch, text, canonical):
    """James operational shortcuts stay admin-only even if a non-admin has slash commands."""
    import gateway.run as gateway_run

    runner = _make_runner()
    runner.config.platforms[Platform.TELEGRAM].extra = {
        "allow_admin_from": ["admin-user"],
        "user_allowed_commands": ["james", "status_james", "proposta", "licenca", "transferencia"],
    }
    runner._run_agent = AsyncMock(side_effect=AssertionError("James shortcut leaked to the agent"))
    runner._call_james_vehicle_direct_adapter = AsyncMock(side_effect=AssertionError("non-admin reached adapter"))
    runner._call_james_health_endpoint = AsyncMock(side_effect=AssertionError("non-admin reached health check"))

    monkeypatch.setattr(
        gateway_run, "_resolve_runtime_agent_kwargs", lambda: {"api_key": "***"}
    )

    result = await runner._handle_message(_make_event(text))

    assert result is not None
    assert "admin-only" in result
    assert f"/{canonical}" in result
    runner._call_james_vehicle_direct_adapter.assert_not_called()
    runner._call_james_health_endpoint.assert_not_called()
    runner.hooks.emit_collect.assert_not_awaited()
    runner._run_agent.assert_not_called()


@pytest.mark.asyncio
async def test_known_slash_command_not_flagged_as_unknown(monkeypatch):
    """A real built-in like /status must NOT hit the unknown-command guard."""
    runner = _make_runner()
    # Make _handle_status_command exist via the normal path by running a real
    # dispatch. If the guard fires, the return string will mention "Unknown".
    runner._running_agents[build_session_key(_make_source())] = MagicMock()

    result = await runner._handle_message(_make_event("/status"))

    assert result is not None
    assert "Unknown command" not in result


@pytest.mark.asyncio
async def test_underscored_alias_for_hyphenated_builtin_not_flagged(monkeypatch):
    """Telegram autocomplete sends /reload_mcp for the /reload-mcp built-in.
    That must NOT be flagged as unknown."""
    import gateway.run as gateway_run

    runner = _make_runner()
    # Prevent real MCP work; we only care that the unknown guard doesn't fire.
    async def _noop_reload(*_a, **_kw):
        return "mcp reloaded"

    runner._handle_reload_mcp_command = _noop_reload  # type: ignore[attr-defined]

    monkeypatch.setattr(
        gateway_run, "_resolve_runtime_agent_kwargs", lambda: {"api_key": "***"}
    )

    result = await runner._handle_message(_make_event("/reload_mcp"))

    # Whatever /reload_mcp returns, it must not be the unknown-command guard.
    if result is not None:
        assert "Unknown command" not in result


# ------------------------------------------------------------------
# command:<name> decision hook — deny / handled / rewrite
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_command_hook_can_deny_before_dispatch(monkeypatch):
    """A handler returning {"decision": "deny"} blocks a slash command early."""
    import gateway.run as gateway_run

    runner = _make_runner()
    runner._run_agent = AsyncMock(
        side_effect=AssertionError("denied slash command leaked to the agent")
    )
    runner._handle_status_command = AsyncMock(
        side_effect=AssertionError("denied slash command reached its handler")
    )
    runner.hooks.emit_collect = AsyncMock(
        return_value=[{"decision": "deny", "message": "Blocked by ACL"}]
    )

    monkeypatch.setattr(
        gateway_run, "_resolve_runtime_agent_kwargs", lambda: {"api_key": "***"}
    )

    result = await runner._handle_message(_make_event("/status"))

    assert result == "Blocked by ACL"
    runner._run_agent.assert_not_called()
    # The emit_collect call should use the canonical command name.
    call_args = runner.hooks.emit_collect.await_args
    assert call_args.args[0] == "command:status"


@pytest.mark.asyncio
async def test_command_hook_deny_without_message_uses_default(monkeypatch):
    """A deny decision with no message falls back to a generic blocked string."""
    import gateway.run as gateway_run

    runner = _make_runner()
    runner._handle_status_command = AsyncMock(
        side_effect=AssertionError("denied slash command reached its handler")
    )
    runner.hooks.emit_collect = AsyncMock(return_value=[{"decision": "deny"}])

    monkeypatch.setattr(
        gateway_run, "_resolve_runtime_agent_kwargs", lambda: {"api_key": "***"}
    )

    result = await runner._handle_message(_make_event("/status"))

    assert result is not None
    assert "blocked" in result.lower()


@pytest.mark.asyncio
async def test_command_hook_can_mark_command_as_handled(monkeypatch):
    """A handled decision short-circuits dispatch cleanly with a custom reply."""
    import gateway.run as gateway_run

    runner = _make_runner()
    runner._handle_status_command = AsyncMock(
        side_effect=AssertionError("handled slash command reached its handler")
    )
    runner.hooks.emit_collect = AsyncMock(
        return_value=[{"decision": "handled", "message": "Already handled upstream"}]
    )

    monkeypatch.setattr(
        gateway_run, "_resolve_runtime_agent_kwargs", lambda: {"api_key": "***"}
    )

    result = await runner._handle_message(_make_event("/status"))

    assert result == "Already handled upstream"


@pytest.mark.asyncio
async def test_command_hook_allow_decision_is_passthrough(monkeypatch):
    """A handler returning {"decision": "allow"} must NOT prevent normal dispatch."""
    import gateway.run as gateway_run

    runner = _make_runner()
    runner._handle_status_command = AsyncMock(return_value="status: ok")
    runner.hooks.emit_collect = AsyncMock(
        return_value=[{"decision": "allow"}]
    )

    monkeypatch.setattr(
        gateway_run, "_resolve_runtime_agent_kwargs", lambda: {"api_key": "***"}
    )

    result = await runner._handle_message(_make_event("/status"))

    assert result == "status: ok"
    runner._handle_status_command.assert_awaited_once()


@pytest.mark.asyncio
async def test_command_hook_non_dict_return_values_ignored(monkeypatch):
    """Hook return values that aren't dicts must not break dispatch."""
    import gateway.run as gateway_run

    runner = _make_runner()
    runner._handle_status_command = AsyncMock(return_value="status: ok")
    runner.hooks.emit_collect = AsyncMock(
        return_value=["some string", 42, None, {}]
    )

    monkeypatch.setattr(
        gateway_run, "_resolve_runtime_agent_kwargs", lambda: {"api_key": "***"}
    )

    result = await runner._handle_message(_make_event("/status"))

    assert result == "status: ok"


@pytest.mark.asyncio
async def test_command_hook_fires_for_plugin_registered_command(monkeypatch):
    """Plugin-registered slash commands should also trigger command:<name> hooks."""
    import gateway.run as gateway_run

    runner = _make_runner()
    runner._run_agent = AsyncMock(
        side_effect=AssertionError("plugin command leaked to the agent")
    )
    runner.hooks.emit_collect = AsyncMock(
        return_value=[{"decision": "handled", "message": "intercepted"}]
    )

    monkeypatch.setattr(
        gateway_run, "_resolve_runtime_agent_kwargs", lambda: {"api_key": "***"}
    )
    # Stub plugin command lookup so is_gateway_known_command() recognizes /metricas.
    from hermes_cli import plugins as _plugins_mod

    monkeypatch.setattr(
        _plugins_mod,
        "get_plugin_commands",
        lambda: {"metricas": {"description": "Metrics", "args_hint": "dias:7"}},
    )

    result = await runner._handle_message(_make_event("/metricas dias:7"))

    assert result == "intercepted"
    # Hook event name uses the plugin command as canonical.
    call_args = runner.hooks.emit_collect.await_args
    assert call_args.args[0] == "command:metricas"
    # Args are passed through in both "args" and "raw_args" keys.
    ctx = call_args.args[1]
    assert ctx["raw_args"] == "dias:7"


@pytest.mark.asyncio
async def test_command_hook_rewrite_routes_to_plugin(monkeypatch):
    """A rewrite decision should re-resolve the command and route to the new one."""
    import gateway.run as gateway_run

    runner = _make_runner()
    runner._run_agent = AsyncMock(
        side_effect=AssertionError("rewritten command leaked to the agent")
    )

    call_log = []

    async def _emit_collect(event_type, ctx):
        call_log.append(event_type)
        if event_type == "command:status":
            return [
                {
                    "decision": "rewrite",
                    "command_name": "metricas",
                    "raw_args": "dias:7",
                }
            ]
        return []

    runner.hooks.emit_collect = AsyncMock(side_effect=_emit_collect)

    monkeypatch.setattr(
        gateway_run, "_resolve_runtime_agent_kwargs", lambda: {"api_key": "***"}
    )
    from hermes_cli import plugins as _plugins_mod

    monkeypatch.setattr(
        _plugins_mod,
        "get_plugin_commands",
        lambda: {"metricas": {"description": "Metrics", "args_hint": "dias:7"}},
    )
    monkeypatch.setattr(
        _plugins_mod,
        "get_plugin_command_handler",
        lambda name: (lambda args: f"metrics {args}") if name == "metricas" else None,
    )

    result = await runner._handle_message(_make_event("/status"))

    assert result == "metrics dias:7"
    # First emit_collect fires on the original command; after rewrite the
    # dispatcher does NOT re-fire for the new command (one decision per turn).
    assert call_log == ["command:status"]
