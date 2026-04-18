import asyncio
import importlib
import sys
import types
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import agent.continuation_enforcer as continuation_enforcer
from agent.continuation_enforcer import get_continuation_record, reconcile_session_continuation, request_continuation_retry
from gateway.config import GatewayConfig, Platform, PlatformConfig
from gateway.platforms.base import BasePlatformAdapter, MessageEvent, MessageType, SendResult
from agent.orchestration_state import get_session_state
from gateway.session import SessionEntry, SessionSource, build_session_key


class _ContinuationAdapter(BasePlatformAdapter):
    def __init__(self):
        super().__init__(PlatformConfig(enabled=True, token="***"), Platform.TELEGRAM)
        self.sent = []

    async def connect(self) -> bool:
        return True

    async def disconnect(self) -> None:
        return None

    async def send(self, chat_id, content, reply_to=None, metadata=None) -> SendResult:
        self.sent.append(
            {
                "chat_id": chat_id,
                "content": content,
                "reply_to": reply_to,
                "metadata": metadata,
            }
        )
        return SendResult(success=True, message_id=f"sent-{len(self.sent)}")

    async def get_chat_info(self, chat_id):
        return {"id": chat_id, "type": "dm"}


class _BaseTodoAgent:
    outcome_status = "completed"
    run_result = {"final_response": "done", "messages": [], "api_calls": 1, "completed": True}

    def __init__(self, **kwargs):
        self.tool_progress_callback = kwargs.get("tool_progress_callback")
        self.session_id = kwargs.get("session_id") or "sess-1"
        self.tools = []
        self.model = "openai/test-model"
        self.context_compressor = SimpleNamespace(last_prompt_tokens=0)
        self.session_prompt_tokens = 0
        self.session_completion_tokens = 0

    def run_conversation(self, message, conversation_history=None, task_id=None):
        return dict(self.run_result)

    def get_orchestration_continuation_snapshot(self, result):
        return {
            "sessionId": self.session_id,
            "outcomeStatus": self.outcome_status,
            "todoItems": [
                {"id": "plan", "content": "Inspect the failing step", "status": "in_progress"},
            ],
            "activeTodos": [
                {"id": "plan", "content": "Inspect the failing step", "status": "in_progress"},
            ],
            "responsePreview": result.get("final_response") or result.get("error"),
        }


class _FailedTodoAgent(_BaseTodoAgent):
    outcome_status = "failed"
    run_result = {
        "final_response": None,
        "messages": [],
        "api_calls": 1,
        "completed": False,
        "failed": True,
        "error": "model backend crashed",
    }


class _InterruptedTodoAgent(_BaseTodoAgent):
    outcome_status = "interrupted"
    run_result = {
        "final_response": "Operation interrupted while work remained pending.",
        "messages": [],
        "api_calls": 1,
        "completed": False,
        "interrupted": True,
        "interrupt_message": "follow up",
    }


def _make_source() -> SessionSource:
    return SessionSource(
        platform=Platform.TELEGRAM,
        user_id="u1",
        chat_id="c1",
        user_name="tester",
        chat_type="dm",
    )


def _make_event(text: str = "hello") -> MessageEvent:
    return MessageEvent(
        text=text,
        source=_make_source(),
        message_id="m1",
        message_type=MessageType.TEXT,
    )


def _install_fake_agent(monkeypatch, agent_cls):
    fake_dotenv = types.ModuleType("dotenv")
    fake_dotenv.load_dotenv = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "dotenv", fake_dotenv)

    fake_run_agent = types.ModuleType("run_agent")
    fake_run_agent.AIAgent = agent_cls
    monkeypatch.setitem(sys.modules, "run_agent", fake_run_agent)


def _make_run_agent_runner(adapter):
    gateway_run = importlib.import_module("gateway.run")
    GatewayRunner = gateway_run.GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner.adapters = {adapter.platform: adapter}
    runner.delivery_router = SimpleNamespace(adapters=runner.adapters)
    runner._voice_mode = {}
    runner._prefill_messages = []
    runner._ephemeral_system_prompt = ""
    runner._reasoning_config = None
    runner._provider_routing = {}
    runner._fallback_model = None
    runner._session_db = None
    runner._running_agents = {}
    runner._running_agents_ts = {}
    runner._pending_messages = {}
    runner._pending_approvals = {}
    runner._session_model_overrides = {}
    runner._draining = False
    runner._restart_requested = False
    runner._show_reasoning = False
    runner._agent_cache = {}
    runner._agent_cache_lock = None
    runner._busy_input_mode = "interrupt"
    runner._background_tasks = set()
    runner._update_runtime_status = lambda *args, **kwargs: None
    runner._evict_cached_agent = lambda *args, **kwargs: None
    runner._is_intentional_model_switch = lambda *args, **kwargs: False
    runner._capture_gateway_honcho_if_configured = lambda *args, **kwargs: None
    runner.hooks = SimpleNamespace(loaded_hooks=False)
    runner.config = SimpleNamespace(
        thread_sessions_per_user=False,
        group_sessions_per_user=False,
        stt_enabled=False,
    )
    return runner


def _make_handle_message_runner(session_entry: SessionEntry):
    gateway_run = importlib.import_module("gateway.run")
    GatewayRunner = gateway_run.GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner.config = GatewayConfig(
        platforms={Platform.TELEGRAM: PlatformConfig(enabled=True, token="***")}
    )
    adapter = _ContinuationAdapter()
    runner.adapters = {Platform.TELEGRAM: adapter}
    runner.delivery_router = SimpleNamespace(adapters=runner.adapters)
    runner._voice_mode = {}
    runner.hooks = SimpleNamespace(emit=AsyncMock(), loaded_hooks=False)
    runner.session_store = MagicMock()
    runner.session_store.get_or_create_session.return_value = session_entry
    runner.session_store.load_transcript.return_value = []
    runner.session_store.has_any_sessions.return_value = True
    runner.session_store.append_to_transcript = MagicMock()
    runner.session_store.rewrite_transcript = MagicMock()
    runner.session_store.update_session = MagicMock()
    runner._running_agents = {}
    runner._running_agents_ts = {}
    runner._pending_messages = {}
    runner._pending_approvals = {}
    runner._session_db = MagicMock()
    runner._session_db.get_session_title.return_value = None
    runner._reasoning_config = None
    runner._provider_routing = {}
    runner._fallback_model = None
    runner._show_reasoning = False
    runner._draining = False
    runner._restart_requested = False
    runner._background_tasks = set()
    runner._agent_cache = {}
    runner._agent_cache_lock = None
    runner._session_model_overrides = {}
    runner._update_prompt_pending = {}
    runner._failed_platforms = {}
    runner._busy_input_mode = "interrupt"
    runner._is_user_authorized = lambda _source: True
    runner._set_session_env = lambda _context: []
    runner._clear_session_env = lambda _tokens: None
    runner._should_send_voice_reply = lambda *_args, **_kwargs: False
    runner._send_voice_reply = AsyncMock()
    runner._capture_gateway_honcho_if_configured = lambda *args, **kwargs: None
    runner._emit_gateway_run_progress = AsyncMock()
    runner._prepare_inbound_message_text = AsyncMock(return_value="hello")
    return runner


def _make_auto_resume_runner(session_entry: SessionEntry):
    runner = _make_handle_message_runner(session_entry)
    runner.session_store.list_sessions.return_value = [session_entry]
    runner.session_store.load_transcript.return_value = [
        {"role": "user", "content": "Please investigate the failing step."},
        {"role": "assistant", "content": "I was interrupted before finishing."},
    ]
    runner._run_agent = AsyncMock()
    runner._build_auto_resume_message = lambda item: f"Resume work on: {item['openTodos'][0]['content']}"
    runner._prepare_inbound_message_text = AsyncMock(
        side_effect=lambda *args, **kwargs: (kwargs.get("event") or args[0]).text
    )
    return runner


async def _run_real_gateway_agent(monkeypatch, tmp_path, agent_cls, *, pending_event=None, interrupt_depth=0):
    _install_fake_agent(monkeypatch, agent_cls)

    adapter = _ContinuationAdapter()
    runner = _make_run_agent_runner(adapter)
    gateway_run = importlib.import_module("gateway.run")
    monkeypatch.setattr(gateway_run, "_hermes_home", tmp_path)
    monkeypatch.setattr(gateway_run, "_resolve_runtime_agent_kwargs", lambda: {"api_key": "***"})

    source = _make_source()
    session_key = build_session_key(source)
    if pending_event is not None:
        adapter._pending_messages[session_key] = pending_event

    return await runner._run_agent(
        message="hello",
        context_prompt="",
        history=[],
        source=source,
        session_id="sess-1",
        session_key=session_key,
        _interrupt_depth=interrupt_depth,
    )


def test_run_agent_failed_result_keeps_orchestration_snapshot(monkeypatch, tmp_path):
    result = asyncio.run(_run_real_gateway_agent(monkeypatch, tmp_path, _FailedTodoAgent))

    assert result["orchestration"]["outcomeStatus"] == "failed"
    assert result["orchestration"]["activeTodos"] == [
        {"id": "plan", "content": "Inspect the failing step", "status": "in_progress"},
    ]
    assert result["orchestration"]["responsePreview"] == "model backend crashed"


def test_run_agent_depth_capped_interrupt_still_returns_orchestration_snapshot(monkeypatch, tmp_path):
    pending_event = MessageEvent(
        text="follow up",
        source=_make_source(),
        message_id="q1",
        message_type=MessageType.TEXT,
    )

    result = asyncio.run(
        _run_real_gateway_agent(
            monkeypatch,
            tmp_path,
            _InterruptedTodoAgent,
            pending_event=pending_event,
            interrupt_depth=importlib.import_module("gateway.run").GatewayRunner._MAX_INTERRUPT_DEPTH,
        )
    )

    assert result["orchestration"]["outcomeStatus"] == "interrupted"
    assert result["orchestration"]["activeTodos"] == [
        {"id": "plan", "content": "Inspect the failing step", "status": "in_progress"},
    ]


def test_handle_message_reconciles_failed_status_and_agent_end_hook(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    result = asyncio.run(_run_real_gateway_agent(monkeypatch, tmp_path, _FailedTodoAgent))

    session_entry = SessionEntry(
        session_key=build_session_key(_make_source()),
        session_id="sess-1",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        platform=Platform.TELEGRAM,
        chat_type="dm",
    )
    runner = _make_handle_message_runner(session_entry)
    runner._run_agent = AsyncMock(return_value=result)

    response = asyncio.run(runner._handle_message(_make_event()))

    assert response == "⚠️ model backend crashed"
    end_call = runner.hooks.emit.await_args_list[-1]
    assert end_call.args[0] == "agent:end"
    assert end_call.args[1]["status"] == "failed"

    from agent.continuation_enforcer import get_pending_continuations

    queue = get_pending_continuations()
    assert len(queue) == 1
    assert queue[0]["sessionId"] == "sess-1"
    assert queue[0]["reason"] == "failed"


def test_handle_message_reconciles_interrupted_status_and_agent_end_hook(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    pending_event = MessageEvent(
        text="follow up",
        source=_make_source(),
        message_id="q1",
        message_type=MessageType.TEXT,
    )
    result = asyncio.run(
        _run_real_gateway_agent(
            monkeypatch,
            tmp_path,
            _InterruptedTodoAgent,
            pending_event=pending_event,
            interrupt_depth=importlib.import_module("gateway.run").GatewayRunner._MAX_INTERRUPT_DEPTH,
        )
    )

    session_entry = SessionEntry(
        session_key=build_session_key(_make_source()),
        session_id="sess-1",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        platform=Platform.TELEGRAM,
        chat_type="dm",
    )
    runner = _make_handle_message_runner(session_entry)
    runner._run_agent = AsyncMock(return_value=result)

    response = asyncio.run(runner._handle_message(_make_event()))

    assert response == "Operation interrupted while work remained pending."
    end_call = runner.hooks.emit.await_args_list[-1]
    assert end_call.args[0] == "agent:end"
    assert end_call.args[1]["status"] == "interrupted"

    from agent.continuation_enforcer import get_pending_continuations

    queue = get_pending_continuations()
    assert len(queue) == 1
    assert queue[0]["sessionId"] == "sess-1"
    assert queue[0]["reason"] == "interrupted"


def test_retry_requested_auto_resume_runs_agent_and_resolves_queue(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    source = _make_source()
    session_entry = SessionEntry(
        session_key=build_session_key(source),
        session_id="sess-1",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        origin=source,
        platform=Platform.TELEGRAM,
        chat_type="dm",
    )
    runner = _make_auto_resume_runner(session_entry)
    runner._run_agent.return_value = {
        "final_response": "Auto-resume complete",
        "messages": [],
        "api_calls": 1,
        "orchestration": {
            "sessionId": "sess-1",
            "outcomeStatus": "completed",
            "activeTodos": [],
            "responsePreview": "Auto-resume complete",
        },
    }

    reconcile_session_continuation(
        "sess-1",
        outcome_status="interrupted",
        todos=[{"id": "plan", "content": "Inspect the failing step", "status": "in_progress"}],
        response_preview="Need another pass.",
    )
    request_continuation_retry("sess-1", requested_by="pan")

    processed = asyncio.run(runner._process_retry_requested_continuations_once())

    assert processed == 1
    runner._run_agent.assert_awaited_once()
    run_call = runner._run_agent.await_args
    assert run_call.kwargs["message"] == "Resume work on: Inspect the failing step"
    assert run_call.kwargs["session_id"] == "sess-1"
    assert run_call.kwargs["session_key"] == session_entry.session_key
    assert runner.adapters[Platform.TELEGRAM].sent[-1]["content"] == "Auto-resume complete"

    record = get_continuation_record("sess-1")
    assert record is not None
    assert record["status"] == "resolved"
    assert record["resolution"] == "completed"
    assert record["events"][-1]["type"] == "auto_resume_delivered"
    assert 'Auto-resume complete' in record["events"][-1]["message"]


def test_retry_requested_auto_resume_skips_busy_session_without_double_execution(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    source = _make_source()
    session_entry = SessionEntry(
        session_key=build_session_key(source),
        session_id="sess-busy",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        origin=source,
        platform=Platform.TELEGRAM,
        chat_type="dm",
    )
    runner = _make_auto_resume_runner(session_entry)
    runner._running_agents[session_entry.session_key] = object()

    reconcile_session_continuation(
        "sess-busy",
        outcome_status="failed",
        todos=[{"id": "plan", "content": "Retry the failed step", "status": "pending"}],
        response_preview="Need another pass.",
    )
    request_continuation_retry("sess-busy", requested_by="pan")

    processed = asyncio.run(runner._process_retry_requested_continuations_once())

    assert processed == 0
    runner._run_agent.assert_not_awaited()
    record = get_continuation_record("sess-busy")
    assert record is not None
    assert record["status"] == "retry_requested"
    assert record["events"][-1]["type"] == 'retry_released'
    assert record["events"][-1]["message"] == 'session_busy'


def test_builtin_agent_end_hook_records_interrupted_status(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    from gateway.builtin_hooks.orchestration_state import handle

    asyncio.run(
        handle(
            "agent:end",
            {
                "session_id": "sess-1",
                "status": "interrupted",
                "response": "Paused with work still pending.",
            },
        )
    )

    state = get_session_state("sess-1")
    assert state is not None
    assert state["status"] == "interrupted"
    assert state["responsePreview"] == "Paused with work still pending."
