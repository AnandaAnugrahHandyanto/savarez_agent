import json

import httpx
import pytest

from hermex.core.embedding import embed_text
from hermex.core.session import SessionFingerprintor
from hermex.core.store import SQLiteStoreConfig, build_sqlite_core_store
from hermex.core.store.base import TelemetryEvent
from hermex.proxy.pipeline import ProxyPipeline
from hermex.proxy.stages.ambient import AmbientContextInjector
from hermex.proxy.trace import TraceExtractor


def test_session_fingerprint_is_stable_for_same_conversation_shape():
    body = {
        "system": "You are Hermes.",
        "model": "anthropic/claude-3.5-sonnet",
        "messages": [{"role": "user", "content": "Build a proxy"}],
    }

    first = SessionFingerprintor().derive(body)
    second = SessionFingerprintor().derive({**body, "max_tokens": 4096})

    assert first == second
    assert len(first) == 24


@pytest.mark.asyncio
async def test_ambient_injector_appends_relevant_cross_session_memory(tmp_path):
    store = build_sqlite_core_store(SQLiteStoreConfig(path=tmp_path / "hermex.sqlite3"))
    await store.telemetry.emit(
        TelemetryEvent(
            session_id="prior-session",
            summary="Use UPSTREAM_BASE=https://openrouter.ai/api/v1 and do not rewrite model strings.",
            embedding=embed_text("openrouter upstream base model strings"),
            success=True,
        )
    )
    session = await store.sessions.load_or_create("current-session")
    body = {
        "system": "You are Hermes.",
        "messages": [{"role": "user", "content": "How should OpenRouter proxy model strings work?"}],
    }

    injected = await AmbientContextInjector(store, token_budget=256, min_sim=0.01).process(body, session)

    assert injected["system"].startswith("You are Hermes.")
    assert "[HERMEX_AMBIENT" in injected["system"]
    assert "do not rewrite model strings" in injected["system"]


@pytest.mark.asyncio
async def test_trace_extractor_stores_tool_failure_summary(tmp_path):
    store = build_sqlite_core_store(SQLiteStoreConfig(path=tmp_path / "hermex.sqlite3"))
    raw = b"\n".join(
        [
            b'data: {"type":"content_block_start","content_block":{"type":"tool_use","id":"toolu_1","name":"shell"}}',
            b'data: {"type":"content_block_delta","delta":{"type":"input_json_delta","partial_json":"{\\"cmd\\": \\"pytest\\"}"}}',
            b'data: {"type":"content_block_stop"}',
            b'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"The test failed with database locked."}}',
        ]
    )

    await TraceExtractor(store).process(raw, session_id="session-a")

    failures = await store.telemetry.search_failures(embed_text("database locked pytest"), top_k=5)
    assert len(failures) == 1
    assert failures[0].session_id == "session-a"
    assert failures[0].tool_name == "shell"


@pytest.mark.asyncio
async def test_proxy_forwards_to_upstream_without_rewriting_model(tmp_path):
    store = build_sqlite_core_store(SQLiteStoreConfig(path=tmp_path / "hermex.sqlite3"))
    seen_requests = []

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        seen_requests.append((str(request.url), payload))
        return httpx.Response(
            200,
            content=b'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"}}\n\n',
            headers={"content-type": "text/event-stream"},
        )

    pipeline = ProxyPipeline(
        store=store,
        upstream_base="https://openrouter.ai/api/v1",
        api_key="test-key",
        http_client_factory=lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    body = {
        "system": "You are Hermes.",
        "model": "anthropic/claude-3.5-sonnet",
        "messages": [{"role": "user", "content": "hello"}],
        "max_tokens": 1024,
    }

    chunks = [chunk async for chunk in pipeline.handle(body)]

    assert b"".join(chunks).startswith(b"data:")
    assert seen_requests[0][0] == "https://openrouter.ai/api/v1/v1/messages"
    assert seen_requests[0][1]["model"] == "anthropic/claude-3.5-sonnet"
