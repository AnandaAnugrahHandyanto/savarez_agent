import json

from plugins.memory import discover_memory_providers, load_memory_provider
from plugins.memory.hermes_api import (
    HermesApiMemoryProvider,
    _load_config,
)


def test_provider_discovery_loads_hermes_api(monkeypatch):
    def fake_request(method, path, *, query=None, body=None, timeout=5):
        if method == "GET" and path == "/api/health":
            return {"data": {"message": "ok", "features": ["agent-whoami"]}}
        raise AssertionError(f"unexpected request: {method} {path}")

    monkeypatch.setattr("plugins.memory.hermes_api._request_json", fake_request)

    providers = {name: (desc, available) for name, desc, available in discover_memory_providers()}

    assert "hermes_api" in providers
    assert providers["hermes_api"][1] is True

    provider = load_memory_provider("hermes_api")
    assert isinstance(provider, HermesApiMemoryProvider)
    assert provider.name == "hermes_api"


def test_initialize_uses_whoami_and_prefetches_session_scoped_context(monkeypatch):
    calls = []

    def fake_request(method, path, *, query=None, body=None, timeout=5):
        calls.append((method, path, query, body))
        if method == "GET" and path == "/api/v1/agent/whoami":
            assert query == {"platform": "telegram", "userId": "42", "userName": "Neeraj Dalal"}
            return {
                "data": {
                    "contact": {
                        "id": "contact-1",
                        "name": "Neeraj Dalal",
                        "username": "nrjdalal",
                        "contactMd": "Dalonic primary admin.",
                        "memoryMd": "Prefers short Hinglish updates.",
                        "tags": ["admin", "dalonic"],
                    },
                    "role": {"id": "role-1", "slug": "self", "name": "Self"},
                    "identities": [
                        {"id": "ident-1", "kind": "telegram", "value": "42", "isPrimary": True}
                    ],
                    "matchedIdentity": {"id": "ident-1", "kind": "telegram", "value": "42"},
                    "matchedBy": "identity",
                }
            }
        if method == "GET" and path == "/api/v1/contacts/contact-1/recall":
            return {
                "data": {
                    "contact": {"id": "contact-1", "name": "Neeraj Dalal"},
                    "interactions": [
                        {
                            "id": "i1",
                            "summary": "asked about GST filing",
                            "responseSummary": "shared deadline",
                            "score": 1,
                            "createdAt": "2026-05-26T00:00:00.000Z",
                        }
                    ],
                }
            }
        if method == "GET" and path == "/api/v1/contacts/search":
            return {"data": []}
        raise AssertionError(f"unexpected request: {method} {path}")

    monkeypatch.setattr("plugins.memory.hermes_api._request_json", fake_request)

    provider = HermesApiMemoryProvider()
    provider.initialize(
        session_id="sess-1",
        platform="telegram",
        user_id="42",
        user_name="Neeraj Dalal",
    )

    prompt = provider.system_prompt_block()
    context = provider.prefetch("GST filing", session_id="sess-1")

    assert calls[0] == (
        "GET",
        "/api/v1/agent/whoami",
        {"platform": "telegram", "userId": "42", "userName": "Neeraj Dalal"},
        None,
    )
    assert "Current contact: Neeraj Dalal" in prompt
    assert "role: Self (self)" in prompt
    assert "access tier: admin" in prompt
    assert "Dalonic primary admin." in prompt
    assert "Prefers short Hinglish updates." in prompt
    assert "Relevant past interactions" in context
    assert "asked about GST filing" in context


def test_prefetch_searches_related_contacts_and_resolves_send_patterns(monkeypatch):
    calls = []

    def fake_request(method, path, *, query=None, body=None, timeout=5):
        calls.append((method, path, query, body))
        if path == "/api/v1/contacts/search":
            assert query == {"q": "send Disha on whatsapp", "limit": "5"}
            return {
                "data": [
                    {
                        "contact": {"id": "c2", "name": "Disha", "username": "disha"},
                        "role": {"id": "r2", "slug": "cofounder", "name": "Cofounder"},
                        "identities": [{"id": "w2", "kind": "whatsapp", "value": "9199@s.whatsapp.net"}],
                    }
                ]
            }
        if path == "/api/v1/routes/resolve":
            assert body == {"query": "Disha", "platform": "whatsapp"}
            return {
                "data": {
                    "contact": {"id": "c2", "name": "Disha"},
                    "identity": {"id": "w2", "kind": "whatsapp", "value": "9199@s.whatsapp.net"},
                    "target": "whatsapp:9199@s.whatsapp.net",
                }
            }
        raise AssertionError(f"unexpected request: {method} {path}")

    monkeypatch.setattr("plugins.memory.hermes_api._request_json", fake_request)
    provider = HermesApiMemoryProvider()

    context = provider.prefetch("send Disha on whatsapp", session_id="sess-1")

    assert "Relevant contacts" in context
    assert "Disha" in context
    assert "Resolved route" in context
    assert "whatsapp:9199@s.whatsapp.net" in context


def test_sync_turn_posts_one_interaction_with_matched_identity(monkeypatch):
    posts = []

    def fake_request(method, path, *, query=None, body=None, timeout=5):
        if method == "POST" and path == "/api/v1/interactions":
            assert isinstance(body, dict)
            posts.append(body)
            return {"data": {"id": "interaction-1", **body}}
        raise AssertionError(f"unexpected request: {method} {path}")

    monkeypatch.setattr("plugins.memory.hermes_api._request_json", fake_request)
    provider = HermesApiMemoryProvider()
    provider._session_id = "sess-1"
    provider._cache["sess-1"] = {
        "platform": "telegram",
        "chatId": "chat-1",
        "threadId": "thread-1",
        "agent_context": "primary",
        "whoami": {
            "contact": {"id": "contact-1", "name": "Neeraj"},
            "matchedIdentity": {"id": "ident-1", "kind": "telegram", "value": "42"},
            "identities": [],
            "matchedBy": "identity",
        },
    }

    provider.sync_turn("please remind me", "done boss", session_id="sess-1")
    provider.shutdown()

    assert posts == [
        {
            "contactId": "contact-1",
            "identityId": "ident-1",
            "platform": "telegram",
            "chatId": "chat-1",
            "threadId": "thread-1",
            "sessionId": "sess-1",
            "direction": "inbound",
            "summary": "please remind me",
            "responseSummary": "done boss",
            "metadata": {"source": "hermes_api_memory_provider"},
        }
    ]


def test_sync_turn_skips_cron_subagent_flush_contexts(monkeypatch):
    posts = []

    monkeypatch.setattr(
        "plugins.memory.hermes_api._request_json",
        lambda *args, **kwargs: posts.append((args, kwargs)),
    )
    provider = HermesApiMemoryProvider()
    provider._session_id = "sess-1"
    provider._cache["sess-1"] = {
        "platform": "cron",
        "agent_context": "cron",
        "whoami": {"contact": {"id": "contact-1"}, "matchedIdentity": None},
    }

    provider.sync_turn("user", "assistant", session_id="sess-1")
    provider.shutdown()

    assert posts == []


def test_tools_call_current_agent_endpoints(monkeypatch):
    requests = []

    def fake_request(method, path, *, query=None, body=None, timeout=5):
        requests.append((method, path, query, body))
        if method == "GET" and path == "/api/v1/contacts/search":
            return {"data": [{"contact": {"id": "c1", "name": "Neeraj"}, "role": None, "identities": []}]}
        if method == "GET" and path == "/api/v1/contacts/c1":
            return {"data": {"id": "c1", "name": "Neeraj", "memoryMd": "admin"}}
        if method == "POST" and path == "/api/v1/contacts/c1/memory/append":
            return {"data": {"id": "c1", "name": "Neeraj", "memoryMd": "admin\n- likes concise"}}
        if method == "POST" and path == "/api/v1/routes/resolve":
            return {"data": {"target": "whatsapp:123", "identity": {"id": "w1"}}}
        if method == "POST" and path == "/api/v1/followups":
            assert isinstance(body, dict)
            return {"data": {"id": "f1", **body}}
        if method == "GET" and path == "/api/v1/followups":
            return {"data": [{"id": "f1", "title": "pay GST"}]}
        raise AssertionError(f"unexpected request: {method} {path}")

    monkeypatch.setattr("plugins.memory.hermes_api._request_json", fake_request)
    provider = HermesApiMemoryProvider()

    searched = json.loads(provider.handle_tool_call("hermes_api_contacts_search", {"query": "nrj", "limit": 5}))
    appended = json.loads(
        provider.handle_tool_call(
            "hermes_api_contact_memory_append", {"contact_id": "c1", "content": "likes concise"}
        )
    )
    route = json.loads(
        provider.handle_tool_call(
            "hermes_api_route_resolve", {"query": "Neeraj", "platform": "whatsapp"}
        )
    )
    created = json.loads(
        provider.handle_tool_call("hermes_api_followup_create", {"title": "pay GST"})
    )
    listed = json.loads(provider.handle_tool_call("hermes_api_followup_list", {"status": "open"}))

    assert searched["data"][0]["contact"]["id"] == "c1"
    assert appended["data"]["memoryMd"].endswith("- likes concise")
    assert route["data"]["target"] == "whatsapp:123"
    assert created["data"]["id"] == "f1"
    assert listed["data"][0]["title"] == "pay GST"
    assert requests == [
        ("GET", "/api/v1/contacts/search", {"q": "nrj", "limit": "5"}, None),
        ("POST", "/api/v1/contacts/c1/memory/append", None, {"content": "likes concise"}),
        ("POST", "/api/v1/routes/resolve", None, {"query": "Neeraj", "platform": "whatsapp"}),
        ("POST", "/api/v1/followups", None, {"title": "pay GST"}),
        ("GET", "/api/v1/followups", {"status": "open"}, None),
    ]


def test_get_tool_schemas_are_gated_by_health_features(monkeypatch):
    def fake_request(method, path, *, query=None, body=None, timeout=5):
        if method == "GET" and path == "/api/health":
            return {"data": {"message": "ok", "features": ["agent-whoami", "contact-search"]}}
        raise AssertionError(f"unexpected request: {method} {path}")

    monkeypatch.setattr("plugins.memory.hermes_api._request_json", fake_request)
    provider = HermesApiMemoryProvider()

    assert provider.is_available() is True
    assert [schema["name"] for schema in provider.get_tool_schemas()] == ["hermes_api_contacts_search"]


def test_save_config_persists_base_url(tmp_path):
    provider = HermesApiMemoryProvider()
    provider.save_config({"base_url": "http://127.0.0.1:4000/"}, str(tmp_path))

    assert _load_config(str(tmp_path)) == {"base_url": "http://127.0.0.1:4000"}


def test_on_memory_write_mirrors_active_contact(monkeypatch):
    updates = []

    provider = HermesApiMemoryProvider()
    provider._session_id = "sess-1"
    provider._cache["sess-1"] = {"whoami": {"contact": {"id": "c1", "name": "Neeraj"}}}

    def fake_request(method, path, *, query=None, body=None, timeout=5):
        updates.append((method, path, body))
        return {"data": {"id": "c1", "memoryMd": "existing\n- User prefers concise replies"}}

    monkeypatch.setattr("plugins.memory.hermes_api._request_json", fake_request)

    provider.on_memory_write("add", "user", "User prefers concise replies")

    assert updates == [
        ("POST", "/api/v1/contacts/c1/memory/append", {"content": "User prefers concise replies"})
    ]
