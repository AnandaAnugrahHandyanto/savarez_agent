"""End-to-end tests for HermesCLI._ensure_runtime_credentials() fallback
loop — exercises the exact ``hermes chat -q`` failure mode reported in
#33540 where one-shot CLI runs lost provider auth context for
fallback_providers that pointed at env-backed providers such as
``azure-foundry`` and ``openrouter``.

Each test drives a real HermesCLI instance with a configured
``fallback_providers`` chain plus a stub
``resolve_runtime_provider`` and asserts that:

* the per-fallback ``base_url`` / ``api_key`` / ``api_key_env`` are
  actually forwarded to the resolver (matching the gateway's
  long-lived path in ``gateway/run.py::_try_resolve_fallback_provider``),
* a fallback that returns an empty api_key is treated as a soft
  failure so later fallbacks still get a chance (the original bug:
  one hollow fallback short-circuited the loop and exited with
  ``Provider resolver returned an empty API key``),
* callable api_keys (Azure Foundry Entra ID bearer tokens) are
  accepted as usable without the string-only validation,
* ``target_model`` is forwarded so the resolver picks the right
  api_mode for the model being switched to.
"""

from __future__ import annotations

import importlib
import sys
import types
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from hermes_cli.auth import AuthError


# Module isolation: cli.py caches CLI_CONFIG at import time, so we wipe
# and reimport per test to keep config_overrides honest. Mirrors the
# pattern used by tests/cli/test_cli_provider_resolution.py.

def _reset_modules(prefixes: tuple[str, ...]) -> None:
    for name in list(sys.modules):
        if any(name == p or name.startswith(p + ".") for p in prefixes):
            sys.modules.pop(name, None)


@pytest.fixture(autouse=True)
def _restore_cli_modules():
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


def _install_prompt_toolkit_stubs() -> None:
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
    for mod_name, mod in [
        ("prompt_toolkit.history", history),
        ("prompt_toolkit.styles", styles),
        ("prompt_toolkit.patch_stdout", patch_stdout),
        ("prompt_toolkit.application", application),
        ("prompt_toolkit.layout", layout),
        ("prompt_toolkit.layout.processors", processors),
        ("prompt_toolkit.filters", filters),
        ("prompt_toolkit.layout.dimension", dimension),
        ("prompt_toolkit.layout.menus", menus),
        ("prompt_toolkit.widgets", widgets),
        ("prompt_toolkit.key_binding", key_binding),
        ("prompt_toolkit.completion", completion),
        ("prompt_toolkit.formatted_text", formatted_text),
    ]:
        sys.modules.setdefault(mod_name, mod)


def _import_cli():
    for name in list(sys.modules):
        if name in {"cli", "run_agent"} or name.startswith("tools"):
            sys.modules.pop(name, None)
    if "firecrawl" not in sys.modules:
        sys.modules["firecrawl"] = SimpleNamespace(Firecrawl=object)
    try:
        importlib.import_module("prompt_toolkit")
    except ModuleNotFoundError:
        _install_prompt_toolkit_stubs()
    return importlib.import_module("cli")


def _make_cli_with_fallback_chain(monkeypatch, chain):
    """Build a HermesCLI whose ``_fallback_model`` field equals *chain*.

    We bypass HermesCLI.__init__ by setting the attributes directly on a
    bare instance — the full init pulls in a lot of unrelated state
    (history file, session DB, prompt_toolkit) we don't need for these
    fallback-only tests.
    """
    cli_mod = _import_cli()
    shell = cli_mod.HermesCLI.__new__(cli_mod.HermesCLI)
    shell._fallback_model = list(chain)
    shell.requested_provider = "openai-codex"
    shell.provider = "openai-codex"
    shell.api_mode = "codex_responses"
    shell.base_url = "https://chatgpt.com/backend-api/codex"
    shell.api_key = "stale"
    shell.model = "gpt-5.4-mini"
    shell.acp_command = None
    shell.acp_args = []
    shell._credential_pool = None
    shell._provider_source = None
    shell._explicit_api_key = None
    shell._explicit_base_url = None
    shell.agent = object()
    shell._active_agent_route_signature = None
    # ``_model_is_default`` and ``_codex_codex_normalized_for`` are set by
    # HermesCLI.__init__ and read by the codex post-resolution path that
    # ``_ensure_runtime_credentials`` always calls. Seed them with the
    # values a normal init would produce so we can bypass the full init.
    shell._model_is_default = False
    return cli_mod, shell


# ---------- Per-fallback base_url / api_key forwarding ----------


class TestFallbackBaseUrlForwarded:
    """The azure-foundry fallback in the bug report has its base_url ON
    the fallback entry, not in model.base_url. The CLI must pass it
    through to resolve_runtime_provider — otherwise Azure Foundry
    resolution raises ``Azure Foundry requires a base URL`` and we
    silently skip to the next entry. (#33540)"""

    def test_azure_foundry_base_url_is_forwarded(self, monkeypatch):
        cli_mod, shell = _make_cli_with_fallback_chain(monkeypatch, [
            {
                "provider": "azure-foundry",
                "model": "Kimi-K2.6",
                "base_url": "https://aoai.example.com/openai/v1",
                "api_key_env": "AZURE_FOUNDRY_TEST_KEY",
            },
        ])
        monkeypatch.setenv("AZURE_FOUNDRY_TEST_KEY", "azure-secret-from-env")
        captured = []

        def _primary_fail(**kwargs):
            raise AuthError("primary down", provider="openai-codex")

        def _resolver(**kwargs):
            captured.append(kwargs)
            return {
                "provider": "azure-foundry",
                "api_mode": "chat_completions",
                "base_url": kwargs["explicit_base_url"],
                "api_key": kwargs["explicit_api_key"],
                "source": "explicit",
            }

        # Two-call surface: primary raises, fallback returns.
        runtime_resolve = MagicMock(side_effect=[_primary_fail, _resolver])

        def _dispatch(**kwargs):
            requested = (kwargs.get("requested") or "").strip().lower()
            if requested == "openai-codex":
                raise AuthError("primary down", provider="openai-codex")
            return _resolver(**kwargs)

        monkeypatch.setattr(
            "hermes_cli.runtime_provider.resolve_runtime_provider",
            _dispatch,
        )
        monkeypatch.setattr(
            "hermes_cli.runtime_provider.format_runtime_provider_error",
            lambda exc: str(exc),
        )

        assert shell._ensure_runtime_credentials() is True
        assert shell.provider == "azure-foundry"
        assert shell.model == "Kimi-K2.6"
        assert shell.base_url == "https://aoai.example.com/openai/v1"
        assert shell.api_key == "azure-secret-from-env"
        # Most importantly — both the base_url and the env-resolved
        # api_key reached the resolver as explicit_* args.
        assert captured[0]["explicit_base_url"] == "https://aoai.example.com/openai/v1"
        assert captured[0]["explicit_api_key"] == "azure-secret-from-env"
        assert captured[0]["target_model"] == "Kimi-K2.6"

    def test_inline_api_key_is_forwarded(self, monkeypatch):
        cli_mod, shell = _make_cli_with_fallback_chain(monkeypatch, [
            {
                "provider": "openrouter",
                "model": "openrouter/owl-alpha",
                "api_key": "sk-or-inline-secret",
            },
        ])
        captured = []

        def _dispatch(**kwargs):
            requested = (kwargs.get("requested") or "").strip().lower()
            if requested == "openai-codex":
                raise AuthError("primary down", provider="openai-codex")
            captured.append(kwargs)
            return {
                "provider": "openrouter",
                "api_mode": "chat_completions",
                "base_url": "https://openrouter.ai/api/v1",
                "api_key": kwargs["explicit_api_key"],
                "source": "explicit",
            }

        monkeypatch.setattr(
            "hermes_cli.runtime_provider.resolve_runtime_provider",
            _dispatch,
        )
        monkeypatch.setattr(
            "hermes_cli.runtime_provider.format_runtime_provider_error",
            lambda exc: str(exc),
        )

        assert shell._ensure_runtime_credentials() is True
        assert captured[0]["explicit_api_key"] == "sk-or-inline-secret"
        assert shell.api_key == "sk-or-inline-secret"

    def test_key_env_alias_is_forwarded(self, monkeypatch):
        # custom_providers uses ``key_env`` historically; fallback_providers
        # entries should accept it so an operator can copy/paste straight.
        cli_mod, shell = _make_cli_with_fallback_chain(monkeypatch, [
            {
                "provider": "openrouter",
                "model": "openrouter/owl-alpha",
                "key_env": "OPENROUTER_TEST_KEY",
            },
        ])
        monkeypatch.setenv("OPENROUTER_TEST_KEY", "or-key-from-env")
        captured = []

        def _dispatch(**kwargs):
            requested = (kwargs.get("requested") or "").strip().lower()
            if requested == "openai-codex":
                raise AuthError("primary down", provider="openai-codex")
            captured.append(kwargs)
            return {
                "provider": "openrouter",
                "api_mode": "chat_completions",
                "base_url": "https://openrouter.ai/api/v1",
                "api_key": kwargs["explicit_api_key"],
                "source": "explicit",
            }

        monkeypatch.setattr(
            "hermes_cli.runtime_provider.resolve_runtime_provider",
            _dispatch,
        )
        monkeypatch.setattr(
            "hermes_cli.runtime_provider.format_runtime_provider_error",
            lambda exc: str(exc),
        )

        assert shell._ensure_runtime_credentials() is True
        assert captured[0]["explicit_api_key"] == "or-key-from-env"


# ---------- Soft-failure: empty api_key tries next fallback ----------


class TestEmptyApiKeyIsSoftFailure:
    """The original bug: a fallback that returned without raising but
    with an empty api_key (env-backed provider where the env var was
    unset) short-circuited the loop and tripped the ``Provider resolver
    returned an empty API key`` exit below. The fix treats that as a
    soft failure and tries the next entry. (#33540)"""

    def test_first_fallback_empty_key_falls_through_to_second(
        self, monkeypatch
    ):
        cli_mod, shell = _make_cli_with_fallback_chain(monkeypatch, [
            {
                "provider": "azure-foundry",
                "model": "Kimi-K2.6",
                "base_url": "https://aoai.example.com/openai/v1",
                "api_key_env": "AZURE_UNSET_KEY",
            },
            {
                "provider": "openrouter",
                "model": "openrouter/owl-alpha",
                "api_key": "sk-or-second-fallback",
            },
        ])
        # The first env var is intentionally unset — azure-foundry would
        # come back with api_key="" from the resolver's static-key path.
        monkeypatch.delenv("AZURE_UNSET_KEY", raising=False)

        provider_results = {
            "azure-foundry": {
                "provider": "azure-foundry",
                "api_mode": "chat_completions",
                "base_url": "https://aoai.example.com/openai/v1",
                "api_key": "",  # ← the failure mode
                "source": "config",
            },
            "openrouter": {
                "provider": "openrouter",
                "api_mode": "chat_completions",
                "base_url": "https://openrouter.ai/api/v1",
                "api_key": "sk-or-second-fallback",
                "source": "explicit",
            },
        }

        def _dispatch(**kwargs):
            requested = (kwargs.get("requested") or "").strip().lower()
            if requested == "openai-codex":
                raise AuthError("primary down", provider="openai-codex")
            return provider_results[requested]

        monkeypatch.setattr(
            "hermes_cli.runtime_provider.resolve_runtime_provider",
            _dispatch,
        )
        monkeypatch.setattr(
            "hermes_cli.runtime_provider.format_runtime_provider_error",
            lambda exc: str(exc),
        )

        assert shell._ensure_runtime_credentials() is True
        assert shell.provider == "openrouter"
        assert shell.api_key == "sk-or-second-fallback"
        assert shell.model == "openrouter/owl-alpha"

    def test_all_fallbacks_empty_returns_false_with_clear_signal(
        self, monkeypatch
    ):
        cli_mod, shell = _make_cli_with_fallback_chain(monkeypatch, [
            {"provider": "openrouter", "model": "openrouter/owl-alpha"},
            {"provider": "azure-foundry", "model": "Kimi-K2.6",
             "base_url": "https://aoai.example.com/openai/v1"},
        ])

        def _dispatch(**kwargs):
            requested = (kwargs.get("requested") or "").strip().lower()
            if requested == "openai-codex":
                raise AuthError("primary down", provider="openai-codex")
            return {
                "provider": requested,
                "api_mode": "chat_completions",
                "base_url": "https://example.invalid",
                "api_key": "",
                "source": "config",
            }

        monkeypatch.setattr(
            "hermes_cli.runtime_provider.resolve_runtime_provider",
            _dispatch,
        )
        monkeypatch.setattr(
            "hermes_cli.runtime_provider.format_runtime_provider_error",
            lambda exc: str(exc),
        )

        # All fallbacks come back with empty api_keys → method exits False
        # (and leaves the primary error message in place for the caller).
        assert shell._ensure_runtime_credentials() is False


# ---------- Callable api_key (Entra ID bearer-token provider) ----------


class TestCallableApiKeyAccepted:
    """Azure Foundry Entra ID resolution returns a callable for api_key
    (the OpenAI SDK invokes it before every request to mint a fresh
    Entra ID JWT). The fallback loop must treat a callable as usable
    even though the empty-string check would reject it."""

    def test_callable_api_key_is_usable(self, monkeypatch):
        cli_mod, shell = _make_cli_with_fallback_chain(monkeypatch, [
            {
                "provider": "azure-foundry",
                "model": "gpt-5.4",
                "base_url": "https://aoai.example.com/openai/v1",
                "auth_mode": "entra_id",
            },
        ])

        def _entra_token():
            return "fresh-bearer-jwt"

        def _dispatch(**kwargs):
            requested = (kwargs.get("requested") or "").strip().lower()
            if requested == "openai-codex":
                raise AuthError("primary down", provider="openai-codex")
            return {
                "provider": "azure-foundry",
                "api_mode": "chat_completions",
                "base_url": kwargs["explicit_base_url"],
                "api_key": _entra_token,  # ← callable, not a string
                "auth_mode": "entra_id",
                "source": "entra_id",
            }

        monkeypatch.setattr(
            "hermes_cli.runtime_provider.resolve_runtime_provider",
            _dispatch,
        )
        monkeypatch.setattr(
            "hermes_cli.runtime_provider.format_runtime_provider_error",
            lambda exc: str(exc),
        )

        assert shell._ensure_runtime_credentials() is True
        assert shell.provider == "azure-foundry"
        assert callable(shell.api_key)
        # Sanity: the callable is the same one the resolver returned.
        assert shell.api_key() == "fresh-bearer-jwt"


# ---------- Primary success path — fallback never tried ----------


class TestPrimarySuccessDoesNotTriggerFallback:
    def test_primary_success_skips_fallback_resolver_entirely(
        self, monkeypatch
    ):
        cli_mod, shell = _make_cli_with_fallback_chain(monkeypatch, [
            {
                "provider": "openrouter",
                "model": "openrouter/owl-alpha",
                "api_key": "should-not-be-used",
            },
        ])
        calls = []

        def _dispatch(**kwargs):
            calls.append(kwargs)
            return {
                "provider": "openai-codex",
                "api_mode": "codex_responses",
                "base_url": "https://chatgpt.com/backend-api/codex",
                "api_key": "codex-token",
                "source": "hermes-auth-store",
            }

        monkeypatch.setattr(
            "hermes_cli.runtime_provider.resolve_runtime_provider",
            _dispatch,
        )
        monkeypatch.setattr(
            "hermes_cli.runtime_provider.format_runtime_provider_error",
            lambda exc: str(exc),
        )

        assert shell._ensure_runtime_credentials() is True
        assert shell.provider == "openai-codex"
        assert shell.api_key == "codex-token"
        # Only ONE resolver call — the primary. Fallback path skipped.
        assert len(calls) == 1
        assert calls[0].get("requested") == "openai-codex"
