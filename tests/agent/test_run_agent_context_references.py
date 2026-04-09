from types import SimpleNamespace

import run_agent
from agent.turn_assembly import apply_turn_assembly_to_user_message
from run_agent import AIAgent


def test_run_conversation_preprocesses_context_references_for_api_messages_only(monkeypatch):
    captured = {}

    def fake_get_model_context_length(*args, **kwargs):
        captured["ctx_lookup"] = (args, kwargs)
        return 8192

    def fake_preprocess_context_references(message, *, cwd, context_length, **kwargs):
        captured["preprocess"] = {
            "message": message,
            "cwd": cwd,
            "context_length": context_length,
        }
        return SimpleNamespace(
            message="expanded message",
            original_message=message,
            references=[SimpleNamespace(kind="file")],
            warnings=[],
            injected_tokens=9,
            expanded=True,
            blocked=False,
        )

    original_assemble = run_agent.assemble_turn_context

    def wrapped_assemble(*args, **kwargs):
        captured["assemble_args"] = args
        assembly = original_assemble(*args, **kwargs)
        captured["turn_assembly"] = assembly
        raise RuntimeError("stop after assembly")

    monkeypatch.setattr("agent.model_metadata.get_model_context_length", fake_get_model_context_length)
    monkeypatch.setattr("run_agent.preprocess_context_references", fake_preprocess_context_references)
    monkeypatch.setattr("run_agent.assemble_turn_context", wrapped_assemble)

    agent = AIAgent(model="test-model", quiet_mode=True, max_iterations=1)
    try:
        agent.run_conversation("Check @file:README.md")
    except RuntimeError as exc:
        assert str(exc) == "stop after assembly"

    assert captured["assemble_args"][0] == "Check @file:README.md"
    assert captured["preprocess"]["message"] == "Check @file:README.md"
    assert captured["preprocess"]["context_length"] == 8192

    assembly = captured["turn_assembly"]
    api_user_message = apply_turn_assembly_to_user_message(
        {"role": "user", "content": "Check @file:README.md"},
        assembly,
    )
    assert api_user_message["content"] == "expanded message"
    assert assembly.original_user_message == "Check @file:README.md"


