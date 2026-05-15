import pytest

from gateway.platforms.one_model_api.adapters.openai_chat import OpenAIChatAdapter
from gateway.platforms.one_model_api.conversions import (
    chat_payload_to_codex_responses_kwargs,
    codex_to_chat_payload,
    collect_codex_stream,
    responses_to_chat_payload,
)
from gateway.config import PlatformConfig
from gateway.platforms.api_server import APIServerAdapter
from gateway.platforms.one_model_api.streams import (
    _stream_stop_filter_piece,
    _stream_stop_flush,
    codex_event_to_chat_chunks,
    stream_openai_chat_as_chat_sse,
)


class _FakeChatResponse:
    def __init__(self, content="ok"):
        self.data = {
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "choices": [{"message": {"role": "assistant", "content": content}}],
        }

    def model_dump(self, exclude_none=True):
        return dict(self.data)


class _FakeChatCompletions:
    def __init__(self):
        self.payloads = []

    async def create(self, **payload):
        self.payloads.append(payload)
        return _FakeChatResponse("abc STOP def" if payload.get("stop") else "ok")


class _FakeClient:
    def __init__(self):
        self.chat = type("Chat", (), {"completions": _FakeChatCompletions()})()


class _FailingChatCompletions:
    async def create(self, **payload):
        raise RuntimeError("Unsupported parameter: temperature")


class _FailingClient:
    def __init__(self):
        self.chat = type("Chat", (), {"completions": _FailingChatCompletions()})()


class _IteratorFailingOnFirstChunk:
    def __aiter__(self):
        return self

    async def __anext__(self):
        raise RuntimeError("Unsupported parameter: temperature")


class _LazyFailingChatCompletions:
    async def create(self, **payload):
        return _IteratorFailingOnFirstChunk()


class _LazyFailingClient:
    def __init__(self):
        self.chat = type("Chat", (), {"completions": _LazyFailingChatCompletions()})()


@pytest.mark.asyncio
async def test_openai_chat_adapter_strips_sampling_controls_before_forwarding():
    adapter = OpenAIChatAdapter()
    client = _FakeClient()

    response = await adapter.chat_completion(
        server=object(),
        request=None,
        client=client,
        runtime={},
        payload={
            "model": "upstream-model",
            "messages": [{"role": "user", "content": "hi"}],
            "temperature": 0,
            "top_p": 1,
        },
        requested_model="public-model",
    )

    assert response.status == 200
    forwarded = client.chat.completions.payloads[0]
    assert "temperature" not in forwarded
    assert "top_p" not in forwarded
    assert forwarded["model"] == "upstream-model"


def test_chat_to_codex_conversion_does_not_forward_sampling_controls():
    kwargs = chat_payload_to_codex_responses_kwargs(
        {
            "model": "upstream-model",
            "messages": [{"role": "user", "content": "hi"}],
            "temperature": 0,
            "top_p": 1,
        },
        runtime={"base_url": "https://chatgpt.com/backend-api/codex"},
        default_model="public-model",
        stream=True,
    )

    assert "temperature" not in kwargs
    assert "top_p" not in kwargs
    assert kwargs["model"] == "upstream-model"


def test_chat_to_codex_conversion_maps_tools_instead_of_rejecting():
    kwargs = chat_payload_to_codex_responses_kwargs(
        {
            "model": "upstream-model",
            "messages": [{"role": "user", "content": "use a tool"}],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "description": "Get weather",
                        "parameters": {
                            "type": "object",
                            "properties": {"city": {"type": "string"}},
                            "required": ["city"],
                        },
                    },
                }
            ],
            "tool_choice": {"type": "function", "function": {"name": "get_weather"}},
        },
        runtime={"base_url": "https://chatgpt.com/backend-api/codex"},
        default_model="public-model",
        stream=True,
    )

    assert kwargs["tools"] == [
        {
            "type": "function",
            "name": "get_weather",
            "description": "Get weather",
            "strict": False,
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        }
    ]
    assert kwargs["tool_choice"] == {"type": "function", "name": "get_weather"}


def test_responses_to_chat_payload_does_not_copy_sampling_controls():
    payload = responses_to_chat_payload(
        {
            "model": "public-model",
            "input": "hi",
            "temperature": 0,
            "top_p": 1,
            "max_output_tokens": 8,
        },
        default_model="upstream-model",
    )

    assert "temperature" not in payload
    assert "top_p" not in payload
    assert payload["max_tokens"] == 8


def test_responses_to_chat_payload_preserves_requested_model_for_validation():
    payload = responses_to_chat_payload(
        {"model": "definitely-not-a-model", "input": "hi"},
        default_model="public-model",
    )

    assert payload["model"] == "definitely-not-a-model"


def test_codex_to_chat_payload_applies_local_stop_truncation():
    response = {
        "status": "completed",
        "output_text": "abc STOP def",
        "usage": {"input_tokens": 1, "output_tokens": 3, "total_tokens": 4},
    }

    payload = codex_to_chat_payload(response, requested_model="public-model", default_model="fallback", stop="STOP")

    assert payload["choices"][0]["message"]["content"] == "abc "
    assert "STOP" not in payload["choices"][0]["message"]["content"]


@pytest.mark.asyncio
async def test_openai_chat_adapter_applies_local_stop_truncation():
    adapter = OpenAIChatAdapter()
    response = await adapter.chat_completion(
        server=object(),
        request=None,
        client=_FakeClient(),
        runtime={},
        payload={"model": "m", "messages": [], "stop": "STOP"},
        requested_model="public-model",
    )

    assert response.status == 200
    assert b"STOP" not in response.body
    assert b"abc " in response.body


def test_codex_to_chat_payload_emits_tool_calls_from_responses_function_calls():
    response = {
        "status": "completed",
        "output": [
            {
                "type": "function_call",
                "call_id": "call_123",
                "name": "get_weather",
                "arguments": '{"city":"Beijing"}',
            }
        ],
        "usage": {"input_tokens": 1, "output_tokens": 3, "total_tokens": 4},
    }

    payload = codex_to_chat_payload(response, requested_model="public-model", default_model="fallback")

    choice = payload["choices"][0]
    assert choice["finish_reason"] == "tool_calls"
    assert choice["message"]["tool_calls"] == [
        {
            "id": "call_123",
            "type": "function",
            "function": {"name": "get_weather", "arguments": '{"city":"Beijing"}'},
        }
    ]


@pytest.mark.asyncio
async def test_stream_creation_failure_returns_non_200_before_sse_starts():
    response = await stream_openai_chat_as_chat_sse(
        None,
        client=_FailingClient(),
        payload={"model": "m", "messages": [], "stream": True, "temperature": 0},
        requested_model="public-model",
    )

    assert response.status == 502


@pytest.mark.asyncio
async def test_stream_first_chunk_failure_returns_non_200_before_sse_starts():
    response = await stream_openai_chat_as_chat_sse(
        None,
        client=_LazyFailingClient(),
        payload={"model": "m", "messages": [], "stream": True, "temperature": 0},
        requested_model="public-model",
    )

    assert response.status == 502


class _FakeCodexStream:
    def __init__(self, events):
        self._events = list(events)
        self._idx = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._idx >= len(self._events):
            raise StopAsyncIteration
        event = self._events[self._idx]
        self._idx += 1
        return event


class _FakeResponses:
    def __init__(self, events):
        self.events = events
        self.payloads = []

    async def create(self, **kwargs):
        self.payloads.append(kwargs)
        return _FakeCodexStream(self.events)


class _FakeCodexClient:
    def __init__(self, events):
        self.responses = _FakeResponses(events)


def test_chat_to_codex_conversion_maps_legacy_function_call_to_tool_choice():
    kwargs = chat_payload_to_codex_responses_kwargs(
        {
            "model": "m",
            "messages": [{"role": "user", "content": "hi"}],
            "functions": [{"name": "get_weather", "parameters": {"type": "object"}}],
            "function_call": {"name": "get_weather"},
        },
        runtime={"base_url": "https://chatgpt.com/backend-api/codex"},
        default_model="fallback",
        stream=True,
    )

    assert kwargs["tool_choice"] == {"type": "function", "name": "get_weather"}


@pytest.mark.asyncio
async def test_collect_codex_stream_accumulates_function_call_deltas():
    client = _FakeCodexClient([
        {
            "type": "response.output_item.added",
            "output_index": 1,
            "item": {"type": "function_call", "call_id": "call_1", "name": "get_weather"},
        },
        {"type": "response.function_call_arguments.delta", "output_index": 1, "delta": '{"city"'},
        {"type": "response.function_call_arguments.delta", "output_index": 1, "delta": ':"北京"}'},
        {"type": "response.completed", "response": {"status": "completed", "output": []}},
    ])

    response = await collect_codex_stream(client, {"model": "m", "stream": True})

    assert response["output"] == [
        {"type": "function_call", "call_id": "call_1", "name": "get_weather", "arguments": '{"city":"北京"}'}
    ]
    chat = codex_to_chat_payload(response, requested_model="public", default_model="fallback")
    assert chat["choices"][0]["finish_reason"] == "tool_calls"
    assert chat["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"] == '{"city":"北京"}'


def test_codex_to_chat_payload_forced_tool_choice_fallback_uses_json_text_as_arguments():
    response = {"status": "completed", "output_text": '{"city":"北京"}', "output": []}

    chat = codex_to_chat_payload(
        response,
        requested_model="public",
        default_model="fallback",
        tool_choice={"type": "function", "function": {"name": "get_weather"}},
        tools=[{"type": "function", "name": "get_weather"}],
    )

    choice = chat["choices"][0]
    assert choice["finish_reason"] == "tool_calls"
    assert choice["message"]["content"] is None
    assert choice["message"]["tool_calls"][0]["function"] == {"name": "get_weather", "arguments": '{"city": "北京"}'}


def test_codex_stream_event_to_chat_chunks_emits_tool_call_deltas():
    state = {"output_index_to_tool_index": {}, "next_tool_index": 0, "text": ""}
    chunks = codex_event_to_chat_chunks(
        {"type": "response.output_item.added", "output_index": 2, "item": {"type": "function_call", "call_id": "call_1", "name": "get_weather"}},
        completion_id="chatcmpl-test",
        created=1,
        model="public",
        state=state,
    )
    assert chunks[0]["choices"][0]["delta"]["tool_calls"][0]["function"]["name"] == "get_weather"

    chunks = codex_event_to_chat_chunks(
        {"type": "response.function_call_arguments.delta", "output_index": 2, "delta": '{"city":"北京"}'},
        completion_id="chatcmpl-test",
        created=1,
        model="public",
        state=state,
    )
    assert chunks[0]["choices"][0]["delta"]["tool_calls"][0]["function"]["arguments"] == '{"city":"北京"}'


def test_stream_stop_filter_truncates_across_chunk_boundary():
    state = {}
    emitted = []
    for piece in ["abc S", "TO", "P def"]:
        out = _stream_stop_filter_piece(piece, state, "STOP")
        if out:
            emitted.append(out)
        if state.get("stop_seen"):
            break
    tail = _stream_stop_flush(state, "STOP")
    if tail:
        emitted.append(tail)

    text = "".join(emitted)
    assert text == "abc "
    assert "STOP" not in text
    assert "def" not in text


def test_codex_stream_event_to_chat_chunks_applies_stop_before_emitting():
    state = {"output_index_to_tool_index": {}, "next_tool_index": 0, "text": ""}
    chunks = []
    for piece in ["abc S", "TO", "P def"]:
        chunks.extend(codex_event_to_chat_chunks(
            {"type": "response.output_text.delta", "delta": piece},
            completion_id="chatcmpl-test",
            created=1,
            model="public",
            state=state,
            stop="STOP",
        ))
        if state.get("stop_seen"):
            break
    tail = _stream_stop_flush(state, "STOP")
    if tail:
        chunks.append({"choices": [{"delta": {"content": tail}}]})

    text = "".join(
        (chunk["choices"][0].get("delta") or {}).get("content", "")
        for chunk in chunks
    )
    assert text == "abc "
    assert "STOP" not in text
    assert "def" not in text


def test_api_server_passthrough_rejects_unknown_model():
    adapter = APIServerAdapter(PlatformConfig(enabled=True, extra={"model_name": "public-model"}))

    assert adapter._validate_passthrough_model("public-model") is None
    response = adapter._validate_passthrough_model("definitely-not-a-model")

    assert response is not None
    assert response.status == 400
    assert b"model_not_found" in response.body
    assert b"definitely-not-a-model" in response.body


def test_api_server_allowed_models_can_be_extended():
    adapter = APIServerAdapter(PlatformConfig(
        enabled=True,
        extra={"model_name": "public-model", "allowed_models": "public-model,alias-model"},
    ))

    assert adapter._validate_passthrough_model("alias-model") is None
