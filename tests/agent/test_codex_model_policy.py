from agent.codex_model_policy import (
    CODEX_AUX_MODEL,
    CODEX_PRIMARY_MODEL,
    CODEX_PROVIDER,
    apply_codex_policy,
    choose_codex_model,
    codex_policy_payload,
)


def test_choose_codex_model_routes_heavy_work_to_primary():
    route = choose_codex_model("implementation debugging")

    assert route.provider == CODEX_PROVIDER
    assert route.model == CODEX_PRIMARY_MODEL
    assert route.role == "primary"


def test_choose_codex_model_routes_aux_work_to_mini():
    route = choose_codex_model("codex-monitor smoke classification")

    assert route.provider == CODEX_PROVIDER
    assert route.model == CODEX_AUX_MODEL
    assert route.role == "auxiliary"


def test_choose_codex_model_critical_overrides_low_budget():
    route = choose_codex_model("triage", budget="low", critical=True)

    assert route.model == CODEX_PRIMARY_MODEL
    assert route.reason.startswith("critical")


def test_apply_codex_policy_preserves_explicit_main_model_and_fills_aux():
    cfg = apply_codex_policy({"model": {"provider": "openai-codex", "model": "custom-main"}, "auxiliary": {"title": {"model": "custom-title"}}})

    assert cfg["model"]["model"] == "custom-main"
    assert cfg["auxiliary"]["title"]["model"] == "custom-title"
    assert cfg["auxiliary"]["title"]["provider"] == CODEX_PROVIDER
    assert cfg["auxiliary"]["compression"]["model"] == CODEX_AUX_MODEL


def test_policy_payload_is_machine_readable():
    payload = codex_policy_payload()

    assert payload["provider"] == CODEX_PROVIDER
    assert payload["primary_model"] == CODEX_PRIMARY_MODEL
    assert payload["auxiliary_model"] == CODEX_AUX_MODEL
    assert payload["routing_examples"]["compression"]["model"] == CODEX_AUX_MODEL
