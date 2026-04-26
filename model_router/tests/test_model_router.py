from pathlib import Path

import yaml

from model_router import (
    Mode,
    Model,
    Privacy,
    Priority,
    Quota,
    RouterInput,
    TaskType,
    load_config,
    route_model,
)


ROOT = Path(__file__).resolve().parent.parent


def get_config():
    return load_config(ROOT / "router_config.yaml")


def test_coding_execute_high_priority_selects_gpt_and_claude_reviewer():
    decision = route_model(
        RouterInput(
            task_type=TaskType.CODING,
            mode=Mode.EXECUTE,
            priority=Priority.HIGH,
            privacy=Privacy.NORMAL,
            quota=Quota.NORMAL,
            has_code=True,
            has_logs=True,
        ),
        get_config(),
    )

    assert decision.primary_model == Model.GPT
    assert decision.reviewer == Model.CLAUDE
    assert decision.fallback_models == [Model.CLAUDE, Model.DEEPSEEK, Model.OLLAMA]


def test_chat_medium_critical_uses_policy_override_to_claude():
    decision = route_model(
        RouterInput(
            task_type=TaskType.CHAT,
            mode=Mode.DRAFT,
            priority=Priority.MEDIUM,
            privacy=Privacy.NORMAL,
            quota=Quota.CRITICAL,
        ),
        get_config(),
    )

    assert decision.primary_model == Model.CLAUDE
    assert any("policy_override: auto-chat-medium-critical" in item for item in decision.trace)


def test_batch_local_only_forces_ollama():
    decision = route_model(
        RouterInput(
            task_type=TaskType.BATCH,
            mode=Mode.EXECUTE,
            priority=Priority.MEDIUM,
            privacy=Privacy.LOCAL_ONLY,
            quota=Quota.NORMAL,
        ),
        get_config(),
    )

    assert decision.primary_model == Model.OLLAMA


def test_review_mode_for_coding_prefers_claude():
    decision = route_model(
        RouterInput(
            task_type=TaskType.CODING,
            mode=Mode.REVIEW,
            priority=Priority.MEDIUM,
            privacy=Privacy.NORMAL,
            quota=Quota.NORMAL,
        ),
        get_config(),
    )

    assert decision.primary_model == Model.CLAUDE


def test_high_priority_disallows_cheap_primary():
    decision = route_model(
        RouterInput(
            task_type=TaskType.CHAT,
            mode=Mode.DRAFT,
            priority=Priority.HIGH,
            privacy=Privacy.NORMAL,
            quota=Quota.CRITICAL,
        ),
        get_config(),
    )

    assert decision.primary_model == Model.CLAUDE



def test_normalize_does_not_mutate_original_router_input():
    router_input = RouterInput(
        task_type=TaskType.CHAT,
        mode=Mode.EXECUTE,
        priority=Priority.MEDIUM,
        privacy=Privacy.NORMAL,
        quota=Quota.NORMAL,
        has_code=True,
    )

    decision = route_model(router_input, get_config())

    assert decision.primary_model == Model.GPT
    assert router_input.task_type == TaskType.CHAT



def test_route_model_handles_missing_fallbacks_without_keyerror(tmp_path: Path):
    config_dict = yaml.safe_load((ROOT / "router_config.yaml").read_text(encoding="utf-8"))
    del config_dict["fallbacks"]["claude-sonnet-4.6"]

    config_path = tmp_path / "router_config.yaml"
    config_path.write_text(yaml.safe_dump(config_dict, allow_unicode=True, sort_keys=False), encoding="utf-8")
    config = load_config(config_path)

    decision = route_model(
        RouterInput(
            task_type=TaskType.CHAT,
            mode=Mode.DRAFT,
            priority=Priority.MEDIUM,
            privacy=Privacy.NORMAL,
            quota=Quota.CRITICAL,
        ),
        config,
    )

    assert decision.primary_model == Model.CLAUDE
    assert decision.fallback_models == []
    assert any("fallbacks: missing for claude-sonnet-4.6 -> []" in item for item in decision.trace)
