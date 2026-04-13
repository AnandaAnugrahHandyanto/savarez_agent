import importlib
import sys
import types
from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from hermes_cli.auth import AuthError
from hermes_cli import main as hermes_main


# ---------------------------------------------------------------------------
# Module isolation: _import_cli() wipes tools.* / cli / run_agent from
# sys.modules so it can re-import cli fresh.  Without cleanup the wiped
# modules leak into subsequent tests on the same xdist worker, breaking
# mock patches that target "tools.file_tools._get_file_ops" etc.
# ---------------------------------------------------------------------------

def _reset_modules(prefixes: tuple[str, ...]):
    for name in list(sys.modules):
        if any(name == p or name.startswith(p + ".") for p in prefixes):
            sys.modules.pop(name, None)


@pytest.fixture(autouse=True)
def _restore_cli_and_tool_modules():
    """Save and restore tools/cli/run_agent modules around every test."""
    prefixes = ("tools", "cli", "run_agent")
    original_modules = {
        name: module
        for name, module in sys.modules.items()
        if any(name == p or name.startswith(p + ".") for p in prefixes)
    }
    try:
        yield
    finally:
        _reset_modules(prefixes)
        sys.modules.update(original_modules)


def _install_prompt_toolkit_stubs():
    class _Dummy:
        def __init__(self, *args, **kwargs):
            pass

    class _Condition:
        def __init__(self, func):
            self.func = func

        def __bool__(self):
            return bool(self.func())

    class _ANSI(str):
        pass

    root = types.ModuleType("prompt_toolkit")
    history = types.ModuleType("prompt_toolkit.history")
    styles = types.ModuleType("prompt_toolkit.styles")
    patch_stdout = types.ModuleType("prompt_toolkit.patch_stdout")
    application = types.ModuleType("prompt_toolkit.application")
    layout = types.ModuleType("prompt_toolkit.layout")
    processors = types.ModuleType("prompt_toolkit.layout.processors")
    filters = types.ModuleType("prompt_toolkit.filters")
    dimension = types.ModuleType("prompt_toolkit.layout.dimension")
    menus = types.ModuleType("prompt_toolkit.layout.menus")
    widgets = types.ModuleType("prompt_toolkit.widgets")
    key_binding = types.ModuleType("prompt_toolkit.key_binding")
    completion = types.ModuleType("prompt_toolkit.completion")
    formatted_text = types.ModuleType("prompt_toolkit.formatted_text")

    history.FileHistory = _Dummy
    styles.Style = _Dummy
    patch_stdout.patch_stdout = lambda *args, **kwargs: nullcontext()
    application.Application = _Dummy
    layout.Layout = _Dummy
    layout.HSplit = _Dummy
    layout.Window = _Dummy
    layout.FormattedTextControl = _Dummy
    layout.ConditionalContainer = _Dummy
    processors.Processor = _Dummy
    processors.Transformation = _Dummy
    processors.PasswordProcessor = _Dummy
    processors.ConditionalProcessor = _Dummy
    filters.Condition = _Condition
    dimension.Dimension = _Dummy
    menus.CompletionsMenu = _Dummy
    widgets.TextArea = _Dummy
    key_binding.KeyBindings = _Dummy
    completion.Completer = _Dummy
    completion.Completion = _Dummy
    formatted_text.ANSI = _ANSI
    root.print_formatted_text = lambda *args, **kwargs: None

    sys.modules.setdefault("prompt_toolkit", root)
    sys.modules.setdefault("prompt_toolkit.history", history)
    sys.modules.setdefault("prompt_toolkit.styles", styles)
    sys.modules.setdefault("prompt_toolkit.patch_stdout", patch_stdout)
    sys.modules.setdefault("prompt_toolkit.application", application)
    sys.modules.setdefault("prompt_toolkit.layout", layout)
    sys.modules.setdefault("prompt_toolkit.layout.processors", processors)
    sys.modules.setdefault("prompt_toolkit.filters", filters)
    sys.modules.setdefault("prompt_toolkit.layout.dimension", dimension)
    sys.modules.setdefault("prompt_toolkit.layout.menus", menus)
    sys.modules.setdefault("prompt_toolkit.widgets", widgets)
    sys.modules.setdefault("prompt_toolkit.key_binding", key_binding)
    sys.modules.setdefault("prompt_toolkit.completion", completion)
    sys.modules.setdefault("prompt_toolkit.formatted_text", formatted_text)


def _import_cli():
    for name in list(sys.modules):
        if name == "cli" or name == "run_agent" or name == "tools" or name.startswith("tools."):
            sys.modules.pop(name, None)

    if "firecrawl" not in sys.modules:
        sys.modules["firecrawl"] = types.SimpleNamespace(Firecrawl=object)

    try:
        importlib.import_module("prompt_toolkit")
    except ModuleNotFoundError:
        _install_prompt_toolkit_stubs()
    return importlib.import_module("cli")


def test_hermes_cli_init_does_not_eagerly_resolve_runtime_provider(monkeypatch):
    cli = _import_cli()
    calls = {"count": 0}

    def _unexpected_runtime_resolve(**kwargs):
        calls["count"] += 1
        raise AssertionError("resolve_runtime_provider should not be called in HermesCLI.__init__")

    monkeypatch.setattr("hermes_cli.runtime_provider.resolve_runtime_provider", _unexpected_runtime_resolve)
    monkeypatch.setattr("hermes_cli.runtime_provider.format_runtime_provider_error", lambda exc: str(exc))

    shell = cli.HermesCLI(model="gpt-5", compact=True, max_turns=1)

    assert shell is not None
    assert calls["count"] == 0


def test_runtime_resolution_failure_is_not_sticky(monkeypatch):
    cli = _import_cli()
    calls = {"count": 0}

    def _runtime_resolve(**kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("temporary auth failure")
        return {
            "provider": "openrouter",
            "api_mode": "chat_completions",
            "base_url": "https://openrouter.ai/api/v1",
            "api_key": "test-key",
            "source": "env/config",
        }

    class _DummyAgent:
        def __init__(self, *args, **kwargs):
            self.kwargs = kwargs

    monkeypatch.setattr("hermes_cli.runtime_provider.resolve_runtime_provider", _runtime_resolve)
    monkeypatch.setattr("hermes_cli.runtime_provider.format_runtime_provider_error", lambda exc: str(exc))
    monkeypatch.setattr(cli, "AIAgent", _DummyAgent)

    shell = cli.HermesCLI(model="gpt-5", compact=True, max_turns=1)

    assert shell._init_agent() is False
    assert shell._init_agent() is True
    assert calls["count"] == 2
    assert shell.agent is not None


def test_runtime_resolution_rebuilds_agent_on_routing_change(monkeypatch):
    cli = _import_cli()

    def _runtime_resolve(**kwargs):
        return {
            "provider": "openai-codex",
            "api_mode": "codex_responses",
            "base_url": "https://same-endpoint.example/v1",
            "api_key": "same-key",
            "source": "env/config",
        }

    monkeypatch.setattr("hermes_cli.runtime_provider.resolve_runtime_provider", _runtime_resolve)
    monkeypatch.setattr("hermes_cli.runtime_provider.format_runtime_provider_error", lambda exc: str(exc))

    shell = cli.HermesCLI(model="gpt-5", compact=True, max_turns=1)
    shell.provider = "openrouter"
    shell.api_mode = "chat_completions"
    shell.base_url = "https://same-endpoint.example/v1"
    shell.api_key = "same-key"
    shell.agent = object()

    assert shell._ensure_runtime_credentials() is True
    assert shell.agent is None
    assert shell.provider == "openai-codex"
    assert shell.api_mode == "codex_responses"


def test_cli_turn_routing_uses_primary_when_disabled(monkeypatch):
    cli = _import_cli()
    shell = cli.HermesCLI(model="gpt-5", compact=True, max_turns=1)
    shell.provider = "openrouter"
    shell.api_mode = "chat_completions"
    shell.base_url = "https://openrouter.ai/api/v1"
    shell.api_key = "sk-primary"
    shell._smart_model_routing = {"enabled": False}

    result = shell._resolve_turn_agent_config("what time is it in tokyo?")

    assert result["model"] == "gpt-5"
    assert result["runtime"]["provider"] == "openrouter"
    assert result["label"] is None


def test_cli_turn_routing_uses_cheap_model_when_simple(monkeypatch):
    cli = _import_cli()

    def _runtime_resolve(**kwargs):
        assert kwargs["requested"] == "zai"
        return {
            "provider": "zai",
            "api_mode": "chat_completions",
            "base_url": "https://open.z.ai/api/v1",
            "api_key": "cheap-key",
            "source": "env/config",
        }

    monkeypatch.setattr("hermes_cli.runtime_provider.resolve_runtime_provider", _runtime_resolve)

    shell = cli.HermesCLI(model="anthropic/claude-sonnet-4", compact=True, max_turns=1)
    shell.provider = "openrouter"
    shell.api_mode = "chat_completions"
    shell.base_url = "https://openrouter.ai/api/v1"
    shell.api_key = "primary-key"
    shell._smart_model_routing = {
        "enabled": True,
        "cheap_model": {"provider": "zai", "model": "glm-5-air"},
        "max_simple_chars": 160,
        "max_simple_words": 28,
    }

    result = shell._resolve_turn_agent_config("what time is it in tokyo?")

    assert result["model"] == "glm-5-air"
    assert result["runtime"]["provider"] == "zai"
    assert result["runtime"]["api_key"] == "cheap-key"
    assert result["label"] is not None


def test_cli_prefers_config_provider_over_stale_env_override(monkeypatch):
    cli = _import_cli()

    monkeypatch.setenv("HERMES_INFERENCE_PROVIDER", "openrouter")
    config_copy = dict(cli.CLI_CONFIG)
    model_copy = dict(config_copy.get("model", {}))
    model_copy["provider"] = "custom"
    model_copy["base_url"] = "https://api.fireworks.ai/inference/v1"
    config_copy["model"] = model_copy
    monkeypatch.setattr(cli, "CLI_CONFIG", config_copy)

    shell = cli.HermesCLI(model="fireworks/minimax-m2p5", compact=True, max_turns=1)

    assert shell.requested_provider == "custom"


def test_codex_provider_replaces_incompatible_default_model(monkeypatch):
    """When provider resolves to openai-codex and no model was explicitly
    chosen, the global config default (e.g. anthropic/claude-opus-4.6) must
    be replaced with a Codex-compatible model.  Fixes #651."""
    cli = _import_cli()

    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    # Ensure local user config does not leak a model into the test
    monkeypatch.setitem(cli.CLI_CONFIG, "model", {
        "default": "",
        "base_url": "https://openrouter.ai/api/v1",
    })

    def _runtime_resolve(**kwargs):
        return {
            "provider": "openai-codex",
            "api_mode": "codex_responses",
            "base_url": "https://chatgpt.com/backend-api/codex",
            "api_key": "test-key",
            "source": "env/config",
        }

    monkeypatch.setattr("hermes_cli.runtime_provider.resolve_runtime_provider", _runtime_resolve)
    monkeypatch.setattr("hermes_cli.runtime_provider.format_runtime_provider_error", lambda exc: str(exc))
    monkeypatch.setattr(
        "hermes_cli.codex_models.get_codex_model_ids",
        lambda access_token=None: ["gpt-5.2-codex", "gpt-5.1-codex-mini"],
    )

    shell = cli.HermesCLI(compact=True, max_turns=1)

    assert shell._model_is_default is True
    assert shell._ensure_runtime_credentials() is True
    assert shell.provider == "openai-codex"
    assert "anthropic" not in shell.model
    assert "claude" not in shell.model
    assert shell.model == "gpt-5.2-codex"


def test_model_flow_nous_prints_subscription_guidance_without_mutating_explicit_tts(monkeypatch, capsys):
    monkeypatch.setenv("HERMES_ENABLE_NOUS_MANAGED_TOOLS", "1")
    config = {
        "model": {"provider": "nous", "default": "claude-opus-4-6"},
        "tts": {"provider": "elevenlabs"},
        "browser": {"cloud_provider": "browser-use"},
    }

    monkeypatch.setattr(
        "hermes_cli.auth.get_provider_auth_state",
        lambda provider: {"access_token": "nous-token"},
    )
    monkeypatch.setattr(
        "hermes_cli.auth.resolve_nous_runtime_credentials",
        lambda *args, **kwargs: {
            "base_url": "https://inference.example.com/v1",
            "api_key": "nous-key",
        },
    )
    monkeypatch.setattr(
        "hermes_cli.auth.fetch_nous_models",
        lambda *args, **kwargs: ["claude-opus-4-6"],
    )
    monkeypatch.setattr("hermes_cli.auth._prompt_model_selection", lambda model_ids, current_model="", pricing=None, **kw: "claude-opus-4-6")
    monkeypatch.setattr("hermes_cli.auth._save_model_choice", lambda model: None)
    monkeypatch.setattr("hermes_cli.auth._update_config_for_provider", lambda provider, url: None)
    monkeypatch.setattr(
        "hermes_cli.nous_subscription.get_nous_subscription_explainer_lines",
        lambda: ["Nous subscription enables managed web tools."],
    )

    hermes_main._model_flow_nous(config, current_model="claude-opus-4-6")

    out = capsys.readouterr().out
    assert "Nous subscription enables managed web tools." in out
    assert config["tts"]["provider"] == "elevenlabs"
    assert config["browser"]["cloud_provider"] == "browser-use"


def test_model_flow_nous_applies_managed_tts_default_when_unconfigured(monkeypatch, capsys):
    monkeypatch.setenv("HERMES_ENABLE_NOUS_MANAGED_TOOLS", "1")
    config = {
        "model": {"provider": "nous", "default": "claude-opus-4-6"},
        "tts": {"provider": "edge"},
    }

    monkeypatch.setattr(
        "hermes_cli.auth.get_provider_auth_state",
        lambda provider: {"access_token": "nous-token"},
    )
    monkeypatch.setattr(
        "hermes_cli.auth.resolve_nous_runtime_credentials",
        lambda *args, **kwargs: {
            "base_url": "https://inference.example.com/v1",
            "api_key": "nous-key",
        },
    )
    monkeypatch.setattr(
        "hermes_cli.auth.fetch_nous_models",
        lambda *args, **kwargs: ["claude-opus-4-6"],
    )
    monkeypatch.setattr("hermes_cli.auth._prompt_model_selection", lambda model_ids, current_model="", pricing=None, **kw: "claude-opus-4-6")
    monkeypatch.setattr("hermes_cli.auth._save_model_choice", lambda model: None)
    monkeypatch.setattr("hermes_cli.auth._update_config_for_provider", lambda provider, url: None)
    monkeypatch.setattr(
        "hermes_cli.nous_subscription.get_nous_subscription_explainer_lines",
        lambda: ["Nous subscription enables managed web tools."],
    )

    hermes_main._model_flow_nous(config, current_model="claude-opus-4-6")

    out = capsys.readouterr().out
    assert "Nous subscription enables managed web tools." in out
    assert "OpenAI TTS via your Nous subscription" in out
    assert config["tts"]["provider"] == "openai"


def test_codex_provider_uses_config_model(monkeypatch):
    """Model comes from config.yaml, not LLM_MODEL env var.
    Config.yaml is the single source of truth to avoid multi-agent conflicts."""
    cli = _import_cli()

    # LLM_MODEL env var should be IGNORED (even if set)
    monkeypatch.setenv("LLM_MODEL", "should-be-ignored")
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    # Set model via config
    monkeypatch.setitem(cli.CLI_CONFIG, "model", {
        "default": "gpt-5.2-codex",
        "provider": "openai-codex",
        "base_url": "https://chatgpt.com/backend-api/codex",
    })

    def _runtime_resolve(**kwargs):
        return {
            "provider": "openai-codex",
            "api_mode": "codex_responses",
            "base_url": "https://chatgpt.com/backend-api/codex",
            "api_key": "fake-codex-token",
            "source": "env/config",
        }

    monkeypatch.setattr("hermes_cli.runtime_provider.resolve_runtime_provider", _runtime_resolve)
    monkeypatch.setattr("hermes_cli.runtime_provider.format_runtime_provider_error", lambda exc: str(exc))
    # Prevent live API call from overriding the config model
    monkeypatch.setattr(
        "hermes_cli.codex_models.get_codex_model_ids",
        lambda access_token=None: ["gpt-5.2-codex"],
    )

    shell = cli.HermesCLI(compact=True, max_turns=1)

    assert shell._ensure_runtime_credentials() is True
    assert shell.provider == "openai-codex"
    # Model from config (may be normalized by codex provider logic)
    assert "codex" in shell.model.lower()
    # LLM_MODEL env var is NOT used
    assert shell.model != "should-be-ignored"


def test_codex_config_model_not_replaced_by_normalization(monkeypatch):
    """When the user sets model.default in config.yaml to a specific codex
    model, _normalize_model_for_provider must NOT replace it with the latest
    available model from the API.  Regression test for #1887."""
    cli = _import_cli()

    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    # User explicitly configured gpt-5.3-codex in config.yaml
    monkeypatch.setitem(cli.CLI_CONFIG, "model", {
        "default": "gpt-5.3-codex",
        "provider": "openai-codex",
        "base_url": "https://chatgpt.com/backend-api/codex",
    })

    def _runtime_resolve(**kwargs):
        return {
            "provider": "openai-codex",
            "api_mode": "codex_responses",
            "base_url": "https://chatgpt.com/backend-api/codex",
            "api_key": "fake-key",
            "source": "env/config",
        }

    monkeypatch.setattr("hermes_cli.runtime_provider.resolve_runtime_provider", _runtime_resolve)
    monkeypatch.setattr("hermes_cli.runtime_provider.format_runtime_provider_error", lambda exc: str(exc))
    # API returns a DIFFERENT model than what the user configured
    monkeypatch.setattr(
        "hermes_cli.codex_models.get_codex_model_ids",
        lambda access_token=None: ["gpt-5.4", "gpt-5.3-codex"],
    )

    shell = cli.HermesCLI(compact=True, max_turns=1)

    # Config model is NOT the global default — user made a deliberate choice
    assert shell._model_is_default is False
    assert shell._ensure_runtime_credentials() is True
    assert shell.provider == "openai-codex"
    # Model must stay as user configured, not replaced by gpt-5.4
    assert shell.model == "gpt-5.3-codex"


def test_codex_provider_preserves_explicit_codex_model(monkeypatch):
    """If the user explicitly passes a Codex-compatible model, it must be
    preserved even when the provider resolves to openai-codex."""
    cli = _import_cli()

    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    def _runtime_resolve(**kwargs):
        return {
            "provider": "openai-codex",
            "api_mode": "codex_responses",
            "base_url": "https://chatgpt.com/backend-api/codex",
            "api_key": "test-key",
            "source": "env/config",
        }

    monkeypatch.setattr("hermes_cli.runtime_provider.resolve_runtime_provider", _runtime_resolve)
    monkeypatch.setattr("hermes_cli.runtime_provider.format_runtime_provider_error", lambda exc: str(exc))

    shell = cli.HermesCLI(model="gpt-5.1-codex-mini", compact=True, max_turns=1)

    assert shell._model_is_default is False
    assert shell._ensure_runtime_credentials() is True
    assert shell.model == "gpt-5.1-codex-mini"


def test_codex_provider_strips_provider_prefix_from_model(monkeypatch):
    """openai/gpt-5.3-codex should become gpt-5.3-codex — the Codex
    Responses API does not accept provider-prefixed model slugs."""
    cli = _import_cli()

    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    def _runtime_resolve(**kwargs):
        return {
            "provider": "openai-codex",
            "api_mode": "codex_responses",
            "base_url": "https://chatgpt.com/backend-api/codex",
            "api_key": "test-key",
            "source": "env/config",
        }

    monkeypatch.setattr("hermes_cli.runtime_provider.resolve_runtime_provider", _runtime_resolve)
    monkeypatch.setattr("hermes_cli.runtime_provider.format_runtime_provider_error", lambda exc: str(exc))

    shell = cli.HermesCLI(model="openai/gpt-5.3-codex", compact=True, max_turns=1)

    assert shell._ensure_runtime_credentials() is True
    assert shell.model == "gpt-5.3-codex"


def test_cmd_model_falls_back_to_auto_on_invalid_provider(monkeypatch, capsys):
    monkeypatch.setattr(
        "hermes_cli.config.load_config",
        lambda: {"model": {"default": "gpt-5", "provider": "invalid-provider"}},
    )
    monkeypatch.setattr("hermes_cli.config.save_config", lambda cfg: None)
    monkeypatch.setattr("hermes_cli.config.get_env_value", lambda key: "")
    monkeypatch.setattr("hermes_cli.config.save_env_value", lambda key, value: None)

    def _resolve_provider(requested, **kwargs):
        if requested == "invalid-provider":
            raise AuthError("Unknown provider 'invalid-provider'.", code="invalid_provider")
        return "openrouter"

    monkeypatch.setattr("hermes_cli.auth.resolve_provider", _resolve_provider)
    monkeypatch.setattr(hermes_main, "_prompt_provider_choice", lambda choices, **kwargs: len(choices) - 1)
    monkeypatch.setattr("sys.stdin", type("FakeTTY", (), {"isatty": lambda self: True})())

    hermes_main.cmd_model(SimpleNamespace())
    output = capsys.readouterr().out

    assert "Warning:" in output
    assert "falling back to auto provider detection" in output.lower()
    assert "No change." in output


def test_model_flow_custom_saves_verified_v1_base_url(monkeypatch, capsys):
    monkeypatch.setattr(
        "hermes_cli.config.get_env_value",
        lambda key: "" if key in {"OPENAI_BASE_URL", "OPENAI_API_KEY"} else "",
    )
    saved_env = {}
    monkeypatch.setattr("hermes_cli.config.save_env_value", lambda key, value: saved_env.__setitem__(key, value))
    monkeypatch.setattr("hermes_cli.auth._save_model_choice", lambda model: saved_env.__setitem__("MODEL", model))
    monkeypatch.setattr("hermes_cli.auth.deactivate_provider", lambda: None)
    monkeypatch.setattr("hermes_cli.main._save_custom_provider", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "hermes_cli.models.probe_api_models",
        lambda api_key, base_url: {
            "models": ["llm"],
            "probed_url": "http://localhost:8000/v1/models",
            "resolved_base_url": "http://localhost:8000/v1",
            "suggested_base_url": "http://localhost:8000/v1",
            "used_fallback": True,
        },
    )
    monkeypatch.setattr(
        "hermes_cli.config.load_config",
        lambda: {"model": {"default": "", "provider": "custom", "base_url": ""}},
    )
    monkeypatch.setattr("hermes_cli.config.save_config", lambda cfg: None)

    # After the probe detects a single model ("llm"), the flow asks
    # "Use this model? [Y/n]:" — confirm with Enter, then context length.
    answers = iter(["http://localhost:8000", "local-key", "", ""])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    monkeypatch.setattr("getpass.getpass", lambda _prompt="": next(answers))

    hermes_main._model_flow_custom({})
    output = capsys.readouterr().out

    assert "Saving the working base URL instead" in output
    assert "Detected model: llm" in output
    # OPENAI_BASE_URL is no longer saved to .env — config.yaml is authoritative
    assert "OPENAI_BASE_URL" not in saved_env
    assert saved_env["MODEL"] == "llm"


def test_cmd_model_forwards_nous_login_tls_options(monkeypatch):
    monkeypatch.setattr(hermes_main, "_require_tty", lambda *a: None)
    monkeypatch.setattr(
        "hermes_cli.config.load_config",
        lambda: {"model": {"default": "gpt-5", "provider": "nous"}},
    )
    monkeypatch.setattr("hermes_cli.config.save_config", lambda cfg: None)
    monkeypatch.setattr("hermes_cli.config.get_env_value", lambda key: "")
    monkeypatch.setattr("hermes_cli.config.save_env_value", lambda key, value: None)
    monkeypatch.setattr("hermes_cli.auth.resolve_provider", lambda requested, **kwargs: "nous")
    monkeypatch.setattr("hermes_cli.auth.get_provider_auth_state", lambda provider_id: None)
    monkeypatch.setattr(hermes_main, "_prompt_provider_choice", lambda choices, **kwargs: 0)

    captured = {}

    def _fake_login(login_args, provider_config):
        captured["portal_url"] = login_args.portal_url
        captured["inference_url"] = login_args.inference_url
        captured["client_id"] = login_args.client_id
        captured["scope"] = login_args.scope
        captured["no_browser"] = login_args.no_browser
        captured["timeout"] = login_args.timeout
        captured["ca_bundle"] = login_args.ca_bundle
        captured["insecure"] = login_args.insecure

    monkeypatch.setattr("hermes_cli.auth._login_nous", _fake_login)

    hermes_main.cmd_model(
        SimpleNamespace(
            portal_url="https://portal.nousresearch.com",
            inference_url="https://inference.nousresearch.com/v1",
            client_id="hermes-local",
            scope="openid profile",
            no_browser=True,
            timeout=7.5,
            ca_bundle="/tmp/local-ca.pem",
            insecure=True,
        )
    )

    assert captured == {
        "portal_url": "https://portal.nousresearch.com",
        "inference_url": "https://inference.nousresearch.com/v1",
        "client_id": "hermes-local",
        "scope": "openid profile",
        "no_browser": True,
        "timeout": 7.5,
        "ca_bundle": "/tmp/local-ca.pem",
        "insecure": True,
    }


def test_select_provider_and_model_hides_separate_xiaomi_token_plan_entry(monkeypatch):
    monkeypatch.setattr(
        "hermes_cli.config.load_config",
        lambda: {"model": {"default": "claude-sonnet-4.6", "provider": "anthropic"}},
    )
    monkeypatch.setattr("hermes_cli.config.save_config", lambda cfg: None)
    monkeypatch.setattr("hermes_cli.config.get_env_value", lambda key: "")
    monkeypatch.setattr("hermes_cli.config.save_env_value", lambda key, value: None)
    monkeypatch.setattr("hermes_cli.auth.resolve_provider", lambda requested, **kwargs: "anthropic")

    prompt_calls = []

    def _prompt_choice(choices, *, default=0):
        prompt_calls.append((list(choices), default))
        if len(prompt_calls) == 1:
            return len(choices) - 2  # More providers...
        return len(choices) - 1  # Cancel

    monkeypatch.setattr(hermes_main, "_prompt_provider_choice", _prompt_choice)

    hermes_main.select_provider_and_model()

    assert len(prompt_calls) == 2
    extended_choices = prompt_calls[1][0]
    assert any("Xiaomi MiMo (MiMo-V2 models" in choice for choice in extended_choices)
    assert not any("Token Plan" in choice for choice in extended_choices)


def test_select_provider_and_model_collapses_active_xiaomi_token_plan_into_xiaomi(monkeypatch):
    monkeypatch.setattr(
        "hermes_cli.config.load_config",
        lambda: {"model": {"default": "mimo-v2-pro", "provider": "xiaomi-token-plan"}},
    )
    monkeypatch.setattr("hermes_cli.config.save_config", lambda cfg: None)
    monkeypatch.setattr("hermes_cli.config.get_env_value", lambda key: "")
    monkeypatch.setattr("hermes_cli.config.save_env_value", lambda key, value: None)
    monkeypatch.setattr("hermes_cli.auth.resolve_provider", lambda requested, **kwargs: "xiaomi-token-plan")

    prompt_calls = []

    def _prompt_choice(choices, *, default=0):
        prompt_calls.append((list(choices), default))
        return len(choices) - 1  # Cancel from top menu

    monkeypatch.setattr(hermes_main, "_prompt_provider_choice", _prompt_choice)

    hermes_main.select_provider_and_model()

    top_choices, default_idx = prompt_calls[0]
    assert any("Xiaomi MiMo" in choice and "currently active" in choice for choice in top_choices)
    assert not any("Token Plan" in choice for choice in top_choices)
    assert "Xiaomi MiMo" in top_choices[default_idx]


def _configure_xiaomi_flow_test(monkeypatch):
    for key in (
        "XIAOMI_API_KEY",
        "XIAOMI_BASE_URL",
        "XIAOMI_TOKEN_PLAN_API_KEY",
        "XIAOMI_TOKEN_PLAN_BASE_URL",
    ):
        monkeypatch.delenv(key, raising=False)

    saved_env = {}
    saved_config = {}
    chosen_models = []
    deactivated = []
    prompts = []

    def _get_env_value(key):
        return saved_env.get(key, "")

    def _save_env_value(key, value):
        saved_env[key] = value

    def _save_config(cfg):
        saved_config.clear()
        saved_config.update(cfg)

    monkeypatch.setattr("hermes_cli.config.get_env_value", _get_env_value)
    monkeypatch.setattr("hermes_cli.config.save_env_value", _save_env_value)
    monkeypatch.setattr(
        "hermes_cli.config.load_config",
        lambda: {"model": {"default": "", "provider": "xiaomi", "base_url": ""}},
    )
    monkeypatch.setattr("hermes_cli.config.save_config", _save_config)
    monkeypatch.setattr("hermes_cli.auth._save_model_choice", lambda model: chosen_models.append(model))
    monkeypatch.setattr("hermes_cli.auth.deactivate_provider", lambda: deactivated.append(True))
    monkeypatch.setattr(
        "hermes_cli.auth._prompt_model_selection",
        lambda models, current_model="", pricing=None: models[0] if models else None,
    )
    monkeypatch.setattr(
        "agent.models_dev.list_agentic_models",
        lambda provider_id: ["mimo-v2-pro", "mimo-v2-omni"],
    )
    monkeypatch.setattr("hermes_cli.models.fetch_api_models", lambda api_key, base_url: ["mimo-v2-pro"])

    def _prompt_choice(choices, *, default=0):
        prompts.append((list(choices), default))
        return default

    monkeypatch.setattr(hermes_main, "_prompt_provider_choice", _prompt_choice)

    return saved_env, saved_config, chosen_models, deactivated, prompts


def test_model_flow_xiaomi_ignores_redacted_placeholder_key(monkeypatch):
    saved_env, saved_config, chosen_models, deactivated, prompts = _configure_xiaomi_flow_test(monkeypatch)
    saved_env["XIAOMI_API_KEY"] = "***"

    answers = iter([""])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    monkeypatch.setattr("getpass.getpass", lambda _prompt="": "tp-live-key")

    hermes_main._model_flow_api_key_provider({}, "xiaomi")

    assert saved_env["XIAOMI_API_KEY"] == "tp-live-key"
    assert saved_env["XIAOMI_BASE_URL"] == "https://token-plan-sgp.xiaomimimo.com/v1"
    assert saved_config["model"]["provider"] == "xiaomi"
    assert saved_config["model"]["base_url"] == "https://token-plan-sgp.xiaomimimo.com/v1"
    assert chosen_models == ["mimo-v2-pro"]
    assert deactivated == [True]
    assert prompts == [(
        [
            "Xiaomi MiMo API (https://api.xiaomimimo.com/v1)",
            "Xiaomi Token Plan API (https://token-plan-sgp.xiaomimimo.com/v1)",
            "Custom Xiaomi-compatible URL",
        ],
        1,
    )]



def test_model_flow_xiaomi_tp_key_defaults_to_token_plan_endpoint(monkeypatch):
    saved_env, saved_config, chosen_models, deactivated, prompts = _configure_xiaomi_flow_test(monkeypatch)

    answers = iter([""])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    monkeypatch.setattr("getpass.getpass", lambda _prompt="": "tp-live-key")

    hermes_main._model_flow_api_key_provider({}, "xiaomi")

    assert saved_env["XIAOMI_API_KEY"] == "tp-live-key"
    assert saved_env["XIAOMI_BASE_URL"] == "https://token-plan-sgp.xiaomimimo.com/v1"
    assert saved_config["model"]["provider"] == "xiaomi"
    assert saved_config["model"]["base_url"] == "https://token-plan-sgp.xiaomimimo.com/v1"
    assert chosen_models == ["mimo-v2-pro"]
    assert deactivated == [True]
    assert prompts == [(
        [
            "Xiaomi MiMo API (https://api.xiaomimimo.com/v1)",
            "Xiaomi Token Plan API (https://token-plan-sgp.xiaomimimo.com/v1)",
            "Custom Xiaomi-compatible URL",
        ],
        1,
    )]


def test_model_flow_xiaomi_non_tp_key_defaults_to_standard_endpoint(monkeypatch):
    saved_env, saved_config, chosen_models, deactivated, prompts = _configure_xiaomi_flow_test(monkeypatch)

    answers = iter([""])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    monkeypatch.setattr("getpass.getpass", lambda _prompt="": "user-generated-key")

    hermes_main._model_flow_api_key_provider({}, "xiaomi")

    assert saved_env["XIAOMI_API_KEY"] == "user-generated-key"
    assert "XIAOMI_BASE_URL" not in saved_env
    assert saved_config["model"]["provider"] == "xiaomi"
    assert saved_config["model"]["base_url"] == "https://api.xiaomimimo.com/v1"
    assert chosen_models == ["mimo-v2-pro"]
    assert deactivated == [True]
    assert prompts == [(
        [
            "Xiaomi MiMo API (https://api.xiaomimimo.com/v1)",
            "Xiaomi Token Plan API (https://token-plan-sgp.xiaomimimo.com/v1)",
            "Custom Xiaomi-compatible URL",
        ],
        0,
    )]


def test_model_flow_xiaomi_custom_endpoint_prompts_for_manual_url(monkeypatch):
    saved_env, saved_config, chosen_models, deactivated, _ = _configure_xiaomi_flow_test(monkeypatch)

    answers = iter(["https://token-plan-ams.xiaomimimo.com/v1"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    monkeypatch.setattr("getpass.getpass", lambda _prompt="": "tp-live-key")

    prompts = []

    def _prompt_choice(choices, *, default=0):
        prompts.append((list(choices), default))
        return 2

    monkeypatch.setattr(hermes_main, "_prompt_provider_choice", _prompt_choice)

    hermes_main._model_flow_api_key_provider({}, "xiaomi")

    assert saved_env["XIAOMI_API_KEY"] == "tp-live-key"
    assert saved_env["XIAOMI_BASE_URL"] == "https://token-plan-ams.xiaomimimo.com/v1"
    assert saved_config["model"]["base_url"] == "https://token-plan-ams.xiaomimimo.com/v1"
    assert chosen_models == ["mimo-v2-pro"]
    assert deactivated == [True]
    assert prompts == [(
        [
            "Xiaomi MiMo API (https://api.xiaomimimo.com/v1)",
            "Xiaomi Token Plan API (https://token-plan-sgp.xiaomimimo.com/v1)",
            "Custom Xiaomi-compatible URL",
        ],
        1,
    )]
