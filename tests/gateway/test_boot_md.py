import sys
import types


def test_boot_md_agent_uses_runtime_request_options(monkeypatch):
    from gateway.builtin_hooks import boot_md

    captured = {}

    class _FakeAgent:
        def __init__(self, **kwargs):
            captured["kwargs"] = kwargs

        def run_conversation(self, prompt):
            captured["prompt"] = prompt
            return {"final_response": "[SILENT]"}

    monkeypatch.setitem(sys.modules, "run_agent", types.SimpleNamespace(AIAgent=_FakeAgent))
    monkeypatch.setattr("gateway.run._load_gateway_config", lambda: {"model": {"default": "gpt-5.4"}})
    monkeypatch.setattr("gateway.run._resolve_gateway_model", lambda config=None: "gpt-5.4")
    monkeypatch.setattr(
        "gateway.run._resolve_runtime_agent_kwargs",
        lambda: {
            "api_key": "sk-openai-direct",
            "base_url": "https://api.openai.com/v1",
            "provider": "custom",
            "api_mode": "codex_responses",
            "command": None,
            "args": [],
            "credential_pool": None,
        },
    )
    monkeypatch.setattr(
        "gateway.run._resolve_runtime_request_options",
        lambda runtime_kwargs, config=None: {"service_tier": "priority"},
    )

    boot_md._run_boot_agent("Check status")

    assert captured["kwargs"]["model"] == "gpt-5.4"
    assert captured["kwargs"]["request_options"] == {"service_tier": "priority"}
    assert captured["kwargs"]["base_url"] == "https://api.openai.com/v1"
