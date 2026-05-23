"""
tests/test_api_server_reasoning.py

Tests that api_server_new.py correctly injects reasoning/thinking content
into API responses. Uses a fake agent result — no real LLM calls needed.

Run:
    python -m pytest tests/test_api_server_reasoning.py -v
    # or directly:
    python tests/test_api_server_reasoning.py
"""

import asyncio
import json
import sys
import types
import unittest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Minimal stubs so we can import api_server_new without the full hermes stack
# ---------------------------------------------------------------------------

def _make_stub_module(name, **attrs):
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    return mod


# aiohttp stub
web_mod = types.ModuleType("aiohttp.web")


class _FakeJsonResponse:
    def __init__(self, data, status=200, headers=None):
        self.data = data
        self.status = status
        self.headers = headers or {}

    def json(self):
        return self.data


class _FakeStreamResponse:
    def __init__(self, status=200, headers=None):
        self.status = status
        self.headers = headers or {}
        self._chunks = []

    async def prepare(self, request):
        pass

    async def write(self, data):
        self._chunks.append(data)

    def get_text(self):
        return b"".join(self._chunks).decode()


web_mod.json_response = lambda data, status=200, headers=None: _FakeJsonResponse(data, status, headers)
web_mod.StreamResponse = _FakeStreamResponse
aiohttp_mod = types.ModuleType("aiohttp")
aiohttp_mod.web = web_mod
sys.modules["aiohttp"] = aiohttp_mod
sys.modules["aiohttp.web"] = web_mod

# hermes stubs
_make_stub_module("hermes_bootstrap")
_make_stub_module("hermes_constants", get_hermes_home=lambda: "/tmp/.hermes")
_make_stub_module("utils", is_truthy_value=lambda v: bool(v), atomic_json_write=None,
                  atomic_yaml_write=None, base_url_host_matches=lambda *a: False)
_make_stub_module("hermes_cli.config", cfg_get=lambda cfg, *keys, default=None: default)
_make_stub_module("hermes_cli.env_loader", load_hermes_dotenv=lambda: None)
_make_stub_module("hermes_cli.tools_config", _get_platform_tools=lambda cfg, p: [])
_make_stub_module("gateway.config",
                  Platform=MagicMock(), GatewayConfig=MagicMock(),
                  PlatformConfig=MagicMock(), load_gateway_config=MagicMock(return_value={}),
                  _BUILTIN_PLATFORM_VALUES=set())
_make_stub_module("gateway.session", SessionStore=MagicMock(), SessionSource=MagicMock(),
                  SessionContext=MagicMock(), build_session_context=MagicMock(),
                  build_session_context_prompt=MagicMock(), build_session_key=MagicMock(),
                  is_shared_multi_user_session=MagicMock(return_value=False))
_make_stub_module("gateway.delivery", DeliveryRouter=MagicMock())
_make_stub_module("gateway.platforms.base",
                  BasePlatformAdapter=MagicMock(), EphemeralReply=MagicMock(),
                  MessageEvent=MagicMock(), MessageType=MagicMock(),
                  _reply_anchor_for_event=MagicMock(), merge_pending_message_event=MagicMock(),
                  SendResult=MagicMock(), is_network_accessible=MagicMock(return_value=True))
_make_stub_module("gateway.restart",
                  DEFAULT_GATEWAY_RESTART_DRAIN_TIMEOUT=30,
                  GATEWAY_SERVICE_RESTART_EXIT_CODE=75,
                  parse_restart_drain_timeout=lambda: 30)
_make_stub_module("gateway.whatsapp_identity",
                  canonical_whatsapp_identifier=MagicMock(),
                  expand_whatsapp_aliases=MagicMock(),
                  normalize_whatsapp_identifier=MagicMock())
_make_stub_module("run_agent", AIAgent=MagicMock())
_make_stub_module("hermes_state", SessionDB=MagicMock())
_make_stub_module("agent.account_usage",
                  fetch_account_usage=MagicMock(), render_account_usage_lines=MagicMock())
_make_stub_module("agent.async_utils", safe_schedule_threadsafe=MagicMock())
_make_stub_module("agent.i18n", t=lambda k, **kw: k)
_make_stub_module("agent.display",
                  build_tool_preview=lambda n, a: n, get_tool_emoji=lambda n: "🔧")


# Minimal api_server stubs needed by api_server_new
class _FakeIdempotencyCache:
    async def get_or_set(self, key, fp, coro_fn):
        return await coro_fn()


api_server_mod = types.ModuleType("gateway.platforms.api_server")
api_server_mod.AIOHTTP_AVAILABLE = True
api_server_mod.web = web_mod
api_server_mod.DEFAULT_HOST = "127.0.0.1"
api_server_mod.DEFAULT_PORT = 8642
api_server_mod.CHAT_COMPLETIONS_SSE_KEEPALIVE_SECONDS = 30.0
api_server_mod._openai_error = lambda msg, err_type="invalid_request_error", code=None: {
    "error": {"message": msg, "type": err_type, **({"code": code} if code else {})}
}
api_server_mod._coerce_request_bool = lambda v, default=False: bool(v) if isinstance(v, bool) else default
api_server_mod._normalize_chat_content = lambda c, **kw: str(c or "")
api_server_mod._normalize_multimodal_content = lambda c: str(c or "")
api_server_mod._content_has_visible_payload = lambda c: bool(c)
api_server_mod._derive_chat_session_id = lambda sp, fu: "test-session-id"
api_server_mod._make_request_fingerprint = lambda body, keys=None: "fp"
api_server_mod._multimodal_validation_error = lambda exc, param="": _FakeJsonResponse({"error": str(exc)}, 400)
api_server_mod._idem_cache = _FakeIdempotencyCache()


class _FakeAPIServerAdapter:
    _api_key = None
    _model_name = "hermes-agent"
    _cors_origins = []
    _session_db = None

    def _check_auth(self, request):
        return None

    def _parse_session_key_header(self, request):
        return None, None

    def _ensure_session_db(self):
        return None

    def _cors_headers_for_origin(self, origin):
        return {}

    async def _run_agent(self, user_message, conversation_history, **kwargs):
        # Fake agent result with reasoning
        result = {
            "final_response": "The answer is 42.",
            "last_reasoning": "Let me think step by step.\nFirst, I consider the question.\nThen I arrive at 42.",
            "completed": True,
            "partial": False,
            "failed": False,
            "session_id": "test-session-id",
        }
        usage = {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30}
        return result, usage


api_server_mod.APIServerAdapter = _FakeAPIServerAdapter
sys.modules["gateway.platforms.api_server"] = api_server_mod

# gateway.run stub (needed by api_server_new._should_show_reasoning)
gateway_run_mod = types.ModuleType("gateway.run")
gateway_run_mod._load_gateway_config = lambda: {}
gateway_run_mod._resolve_runtime_agent_kwargs = lambda: {}
gateway_run_mod._resolve_gateway_model = lambda: "hermes-agent"
gateway_run_mod.GatewayRunner = MagicMock()
sys.modules["gateway.run"] = gateway_run_mod

# Now import the module under test directly from file path to avoid
# triggering gateway/__init__.py's real import chain.
import importlib.util, os as _os
_project_root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

_spec = importlib.util.spec_from_file_location(
    "gateway.platforms.api_server_new",
    _os.path.join(_project_root, "gateway", "platforms", "api_server_new.py"),
)
api_server_new = importlib.util.module_from_spec(_spec)
sys.modules["gateway.platforms.api_server_new"] = api_server_new
_spec.loader.exec_module(api_server_new)


# ---------------------------------------------------------------------------
# Fake aiohttp Request
# ---------------------------------------------------------------------------

class FakeRequest:
    def __init__(self, body: dict, headers: dict = None):
        self._body = body
        self.headers = headers or {}

    async def json(self):
        return self._body


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestReasoningNonStreaming(unittest.IsolatedAsyncioTestCase):

    def _make_adapter(self):
        adapter = _FakeAPIServerAdapter()
        # Bind patched method
        import types as _t
        adapter._handle_chat_completions = _t.MethodType(
            api_server_new._patched_handle_chat_completions, adapter
        )
        return adapter

    async def test_reasoning_in_message_field(self):
        """last_reasoning should appear in choices[0].message.reasoning."""
        adapter = self._make_adapter()
        request = FakeRequest({
            "messages": [{"role": "user", "content": "What is the answer?"}],
            "stream": False,
        })
        resp = await adapter._handle_chat_completions(request)
        data = resp.data
        msg = data["choices"][0]["message"]
        self.assertIn("reasoning", msg, "reasoning field missing from message")
        self.assertIn("step by step", msg["reasoning"])

    async def test_content_unchanged_when_show_reasoning_false(self):
        """When show_reasoning=false, content should NOT be prepended with reasoning block."""
        adapter = self._make_adapter()
        request = FakeRequest({
            "messages": [{"role": "user", "content": "What is the answer?"}],
            "stream": False,
        })
        with patch.object(api_server_new, "_should_show_reasoning", return_value=False):
            resp = await adapter._handle_chat_completions(request)
        content = resp.data["choices"][0]["message"]["content"]
        self.assertEqual(content, "The answer is 42.")
        self.assertNotIn("Reasoning", content)

    async def test_content_prepended_when_show_reasoning_true(self):
        """When show_reasoning=true, content should be prepended with reasoning block."""
        adapter = self._make_adapter()
        request = FakeRequest({
            "messages": [{"role": "user", "content": "What is the answer?"}],
            "stream": False,
        })
        with patch.object(api_server_new, "_should_show_reasoning", return_value=True):
            resp = await adapter._handle_chat_completions(request)
        content = resp.data["choices"][0]["message"]["content"]
        self.assertIn("💭 **Reasoning:**", content)
        self.assertIn("The answer is 42.", content)

    async def test_no_reasoning_field_when_agent_returns_none(self):
        """When agent returns no reasoning, message should not have reasoning field."""
        adapter = self._make_adapter()

        async def _run_no_reasoning(self_inner, user_message, conversation_history, **kwargs):
            result = {
                "final_response": "42.",
                "last_reasoning": None,
                "completed": True,
                "partial": False,
                "failed": False,
                "session_id": "s1",
            }
            return result, {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}

        import types as _t
        adapter._run_agent = _t.MethodType(_run_no_reasoning, adapter)

        request = FakeRequest({
            "messages": [{"role": "user", "content": "hi"}],
            "stream": False,
        })
        resp = await adapter._handle_chat_completions(request)
        msg = resp.data["choices"][0]["message"]
        self.assertNotIn("reasoning", msg)


class TestReasoningStreaming(unittest.IsolatedAsyncioTestCase):

    async def test_reasoning_sse_event_emitted(self):
        """Streaming path should emit a hermes.reasoning SSE event."""
        import queue
        import asyncio

        adapter = _FakeAPIServerAdapter()

        stream_q: queue.Queue = queue.Queue()
        stream_q.put("The answer")
        stream_q.put(" is 42.")
        stream_q.put(None)  # end sentinel

        fake_result = {
            "final_response": "The answer is 42.",
            "last_reasoning": "I thought carefully.",
            "completed": True,
        }
        fake_usage = {"input_tokens": 5, "output_tokens": 10, "total_tokens": 15}

        agent_task = asyncio.get_event_loop().create_future()
        agent_task.set_result((fake_result, fake_usage))

        request = FakeRequest({}, headers={"Origin": ""})
        stream_resp = _FakeStreamResponse()

        with patch.object(web_mod, "StreamResponse", return_value=stream_resp):
            import types as _t
            bound = _t.MethodType(api_server_new._patched_write_sse_chat_completion, adapter)
            await bound(
                request, "chatcmpl-test", "hermes-agent", 1234567890,
                stream_q, agent_task,
            )

        full_text = stream_resp.get_text()
        self.assertIn("hermes.reasoning", full_text, "hermes.reasoning SSE event not found")
        self.assertIn("I thought carefully.", full_text)
        self.assertIn("[DONE]", full_text)


# ---------------------------------------------------------------------------
# Quick manual runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)
