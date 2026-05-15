"""Tests for ordered provider fallback chain (salvage of PR #1761).

Extends the single-fallback tests in test_fallback_model.py to cover
the new list-based ``fallback_providers`` config format and chain
advancement through multiple providers.
"""

from unittest.mock import MagicMock, patch

from run_agent import AIAgent, _pool_may_recover_from_rate_limit


def _make_agent(fallback_model=None):
    """Create a minimal AIAgent with optional fallback config."""
    with (
        patch("run_agent.get_tool_definitions", return_value=[]),
        patch("run_agent.check_toolset_requirements", return_value={}),
        patch("run_agent.OpenAI"),
    ):
        agent = AIAgent(
            api_key="test-key",
            base_url="https://openrouter.ai/api/v1",
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
            fallback_model=fallback_model,
        )
        agent.client = MagicMock()
        return agent


def _mock_client(base_url="https://openrouter.ai/api/v1", api_key="fb-key"):
    mock = MagicMock()
    mock.base_url = base_url
    mock.api_key = api_key
    return mock


# ── Chain initialisation ──────────────────────────────────────────────────


class TestFallbackChainInit:
    def test_no_fallback(self):
        agent = _make_agent(fallback_model=None)
        assert agent._fallback_chain == []
        assert agent._fallback_index == 0
        assert agent._fallback_model is None

    def test_single_dict_backwards_compat(self):
        fb = {"provider": "openai", "model": "gpt-4o"}
        agent = _make_agent(fallback_model=fb)
        assert agent._fallback_chain == [fb]
        assert agent._fallback_model == fb

    def test_list_of_providers(self):
        fbs = [
            {"provider": "openai", "model": "gpt-4o"},
            {"provider": "zai", "model": "glm-4.7"},
        ]
        agent = _make_agent(fallback_model=fbs)
        assert len(agent._fallback_chain) == 2
        assert agent._fallback_model == fbs[0]

    def test_invalid_entries_filtered(self):
        fbs = [
            {"provider": "openai", "model": "gpt-4o"},
            {"provider": "", "model": "glm-4.7"},
            {"provider": "zai"},
            "not-a-dict",
        ]
        agent = _make_agent(fallback_model=fbs)
        assert len(agent._fallback_chain) == 1
        assert agent._fallback_chain[0]["provider"] == "openai"

    def test_empty_list(self):
        agent = _make_agent(fallback_model=[])
        assert agent._fallback_chain == []
        assert agent._fallback_model is None

    def test_invalid_dict_no_provider(self):
        agent = _make_agent(fallback_model={"model": "gpt-4o"})
        assert agent._fallback_chain == []


# ── Chain advancement ─────────────────────────────────────────────────────


class TestFallbackChainAdvancement:
    def test_exhausted_returns_false(self):
        agent = _make_agent(fallback_model=None)
        assert agent._try_activate_fallback() is False

    def test_advances_index(self):
        fbs = [
            {"provider": "openai", "model": "gpt-4o"},
            {"provider": "zai", "model": "glm-4.7"},
        ]
        agent = _make_agent(fallback_model=fbs)
        with patch("agent.auxiliary_client.resolve_provider_client",
                    return_value=(_mock_client(), "gpt-4o")):
            assert agent._try_activate_fallback() is True
            assert agent._fallback_index == 1
            assert agent.model == "gpt-4o"
            assert agent._fallback_activated is True

    def test_second_fallback_works(self):
        fbs = [
            {"provider": "openai", "model": "gpt-4o"},
            {"provider": "zai", "model": "glm-4.7"},
        ]
        agent = _make_agent(fallback_model=fbs)
        with patch("agent.auxiliary_client.resolve_provider_client",
                    return_value=(_mock_client(), "resolved")):
            assert agent._try_activate_fallback() is True
            assert agent.model == "gpt-4o"
            assert agent._try_activate_fallback() is True
            assert agent.model == "glm-4.7"
            assert agent._fallback_index == 2

    def test_all_exhausted_returns_false(self):
        fbs = [{"provider": "openai", "model": "gpt-4o"}]
        agent = _make_agent(fallback_model=fbs)
        with patch("agent.auxiliary_client.resolve_provider_client",
                    return_value=(_mock_client(), "gpt-4o")):
            assert agent._try_activate_fallback() is True
            assert agent._try_activate_fallback() is False

    def test_skips_unconfigured_provider_to_next(self):
        """If resolve_provider_client returns None, skip to next in chain."""
        fbs = [
            {"provider": "broken", "model": "nope"},
            {"provider": "openai", "model": "gpt-4o"},
        ]
        agent = _make_agent(fallback_model=fbs)
        with patch("agent.auxiliary_client.resolve_provider_client") as mock_rpc:
            mock_rpc.side_effect = [
                (None, None),                    # broken provider
                (_mock_client(), "gpt-4o"),       # fallback succeeds
            ]
            assert agent._try_activate_fallback() is True
            assert agent.model == "gpt-4o"
            assert agent._fallback_index == 2

    def test_skips_provider_that_raises_to_next(self):
        """If resolve_provider_client raises, skip to next in chain."""
        fbs = [
            {"provider": "broken", "model": "nope"},
            {"provider": "openai", "model": "gpt-4o"},
        ]
        agent = _make_agent(fallback_model=fbs)
        with patch("agent.auxiliary_client.resolve_provider_client") as mock_rpc:
            mock_rpc.side_effect = [
                RuntimeError("auth failed"),
                (_mock_client(), "gpt-4o"),
            ]
            assert agent._try_activate_fallback() is True
            assert agent.model == "gpt-4o"

    def test_resolves_key_env_for_fallback_provider(self):
        fbs = [
            {
                "provider": "custom",
                "model": "fallback-model",
                "base_url": "https://fallback.example/v1",
                "key_env": "MY_FALLBACK_KEY",
            }
        ]
        agent = _make_agent(fallback_model=fbs)
        with (
            patch.dict("os.environ", {"MY_FALLBACK_KEY": "env-secret"}, clear=False),
            patch(
                "agent.auxiliary_client.resolve_provider_client",
                return_value=(
                    _mock_client(
                        base_url="https://fallback.example/v1",
                        api_key="env-secret",
                    ),
                    "fallback-model",
                ),
            ) as mock_rpc,
        ):
            assert agent._try_activate_fallback() is True
            assert mock_rpc.call_args.kwargs["explicit_api_key"] == "env-secret"


# ── Pool-rotation vs fallback gating (#11314) ────────────────────────────


def _pool(n_entries: int, has_available: bool = True):
    """Make a minimal credential-pool stand-in for rotation-room checks."""
    pool = MagicMock()
    pool.entries.return_value = [MagicMock() for _ in range(n_entries)]
    pool.has_available.return_value = has_available
    return pool


class TestPoolRotationRoom:
    def test_none_pool_returns_false(self):
        assert _pool_may_recover_from_rate_limit(None) is False

    def test_single_credential_returns_false(self):
        """With one credential that just 429'd, rotation has nowhere to go.

        The pool may still report has_available() True once cooldown expires,
        but retrying against the same entry will hit the same daily-quota
        429 and burn the retry budget.  Must fall back.
        """
        assert _pool_may_recover_from_rate_limit(_pool(1)) is False

    def test_single_credential_in_cooldown_returns_false(self):
        assert _pool_may_recover_from_rate_limit(_pool(1, has_available=False)) is False

    def test_two_credentials_available_returns_true(self):
        """With >1 credentials and at least one available, rotate instead of fallback."""
        assert _pool_may_recover_from_rate_limit(_pool(2)) is True

    def test_multiple_credentials_all_in_cooldown_returns_false(self):
        """All credentials cooling down — fall back rather than wait."""
        assert _pool_may_recover_from_rate_limit(_pool(3, has_available=False)) is False

    def test_many_credentials_available_returns_true(self):
        assert _pool_may_recover_from_rate_limit(_pool(10)) is True


# ── Skip-self dedup (#22548) ───────────────────────────────────────────────


class TestFallbackChainDedup:
    """A fallback chain entry that resolves to the current provider/model
    (or the same custom-provider base_url) must be skipped, not retried.
    Otherwise a misconfigured chain or two custom_providers entries pointing
    at the same shim loop the same failure. See issue #22548."""

    def test_skips_entry_matching_current_provider_and_model(self):
        """Chain has [same-as-current, real-fallback]; activate must skip
        the first and use the second."""
        fbs = [
            # First entry == current state. Should be skipped.
            {"provider": "openrouter", "model": "z-ai/glm-4.7"},
            # Second entry: real fallback.
            {"provider": "zai", "model": "glm-4.7"},
        ]
        agent = _make_agent(fallback_model=fbs)
        agent.provider = "openrouter"
        agent.model = "z-ai/glm-4.7"
        agent.base_url = "https://openrouter.ai/api/v1"

        # Stub out resolve_provider_client so we can assert which entry was
        # actually used — return a MagicMock client tagged with the provider.
        called = []
        def _resolve(provider, model=None, raw_codex=False, **kwargs):
            called.append((provider, model))
            return _mock_client(), model
        with patch("agent.auxiliary_client.resolve_provider_client", side_effect=_resolve):
            with patch("hermes_cli.model_normalize.normalize_model_for_provider", side_effect=lambda m, p: m):
                ok = agent._try_activate_fallback()

        assert ok is True
        # The first entry was skipped — only the second reached resolve.
        assert called == [("zai", "glm-4.7")], (
            f"expected fallback to skip same-state entry, got call order: {called}"
        )

    def test_skips_entry_matching_current_base_url_and_model(self):
        """Two custom_providers entries pointing at the same shim URL
        with the same model should dedup even if their provider names differ."""
        fbs = [
            # Different provider name but same shim URL + model — same backend.
            {"provider": "claude-cli-alt", "model": "claude-opus-4.7",
             "base_url": "http://127.0.0.1:7891/v1"},
            # Real different fallback.
            {"provider": "openrouter", "model": "anthropic/claude-opus-4.7"},
        ]
        agent = _make_agent(fallback_model=fbs)
        agent.provider = "claude-cli"
        agent.model = "claude-opus-4.7"
        agent.base_url = "http://127.0.0.1:7891/v1"

        called = []
        def _resolve(provider, model=None, raw_codex=False, **kwargs):
            called.append((provider, model))
            return _mock_client(), model
        with patch("agent.auxiliary_client.resolve_provider_client", side_effect=_resolve):
            with patch("hermes_cli.model_normalize.normalize_model_for_provider", side_effect=lambda m, p: m):
                ok = agent._try_activate_fallback()

        assert ok is True
        # Same shim/base_url+model entry skipped, second one used.
        assert called == [("openrouter", "anthropic/claude-opus-4.7")], (
            f"expected base_url-aware dedup, got call order: {called}"
        )

    def test_returns_false_when_only_self_matching_entries(self):
        """A chain with only self-matching entries exhausts to False."""
        fbs = [
            {"provider": "openrouter", "model": "z-ai/glm-4.7"},
        ]
        agent = _make_agent(fallback_model=fbs)
        agent.provider = "openrouter"
        agent.model = "z-ai/glm-4.7"
        agent.base_url = "https://openrouter.ai/api/v1"

        with patch("agent.auxiliary_client.resolve_provider_client") as mock_resolve:
            ok = agent._try_activate_fallback()

        assert ok is False
        mock_resolve.assert_not_called()


# ── Fallback-entry extra_body forwarding (#26460) ─────────────────────────


class TestFallbackEntryExtraBodyForwarded:
    """When a fallback entry carries ``extra_body`` (e.g. OpenRouter
    ``provider.order`` for request-scoped routing), activating that entry
    must merge it into ``request_overrides`` so the chat_completions
    transport forwards it on the very next request — without mutating the
    agent's global ``provider_routing`` knobs (``providers_allowed`` etc.)
    and without persisting past the next ``_restore_primary_runtime``.
    See issue #26460."""

    def _activate(self, agent):
        with (
            patch(
                "agent.auxiliary_client.resolve_provider_client",
                return_value=(_mock_client(), agent._fallback_chain[0]["model"]),
            ),
            patch(
                "hermes_cli.model_normalize.normalize_model_for_provider",
                side_effect=lambda m, p: m,
            ),
        ):
            return agent._try_activate_fallback()

    def test_fallback_extra_body_forwarded_to_request_overrides(self):
        fb_extra = {
            "provider": {
                "order": ["baidu/fp8", "gmicloud/fp8", "deepinfra/fp4"],
                "allow_fallbacks": False,
            }
        }
        fbs = [{
            "provider": "openrouter",
            "model": "z-ai/glm-5.1",
            "key_env": "OPENROUTER_API_KEY",
            "extra_body": fb_extra,
        }]
        agent = _make_agent(fallback_model=fbs)
        assert "extra_body" not in (agent.request_overrides or {})

        assert self._activate(agent) is True
        eb = agent.request_overrides.get("extra_body")
        assert isinstance(eb, dict)
        assert eb["provider"] == fb_extra["provider"]

    def test_global_provider_routing_unchanged(self):
        """Activating a fallback entry's request-scoped extra_body must not
        touch the agent-level provider_routing knobs — those still apply to
        unrelated OpenRouter requests."""
        fbs = [{
            "provider": "openrouter",
            "model": "z-ai/glm-5.1",
            "extra_body": {"provider": {"order": ["baidu/fp8"], "allow_fallbacks": False}},
        }]
        agent = _make_agent(fallback_model=fbs)
        # Snapshot the global routing knobs before activation.
        before = (
            list(agent.providers_allowed or []),
            list(agent.providers_ignored or []),
            list(agent.providers_order or []),
            agent.provider_sort,
        )

        assert self._activate(agent) is True

        after = (
            list(agent.providers_allowed or []),
            list(agent.providers_ignored or []),
            list(agent.providers_order or []),
            agent.provider_sort,
        )
        assert before == after

    def test_fallback_without_extra_body_does_not_inject_key(self):
        fbs = [{"provider": "openrouter", "model": "z-ai/glm-5.1"}]
        agent = _make_agent(fallback_model=fbs)
        agent.request_overrides = {}

        assert self._activate(agent) is True
        assert "extra_body" not in agent.request_overrides

    def test_fallback_extra_body_merges_with_existing_extra_body(self):
        """If primary config already populated request_overrides['extra_body'],
        the fallback's extra_body should merge on top (fallback wins on
        key collision) rather than replace the whole dict."""
        fbs = [{
            "provider": "openrouter",
            "model": "z-ai/glm-5.1",
            "extra_body": {"provider": {"order": ["baidu/fp8"], "allow_fallbacks": False}},
        }]
        agent = _make_agent(fallback_model=fbs)
        agent.request_overrides = {"extra_body": {"some_user_field": 42}}

        assert self._activate(agent) is True
        eb = agent.request_overrides["extra_body"]
        # Pre-existing user extra_body field preserved.
        assert eb["some_user_field"] == 42
        # Fallback-entry extra_body merged in.
        assert eb["provider"]["order"] == ["baidu/fp8"]

    def test_invalid_extra_body_type_is_ignored(self):
        """Defensive: a non-dict extra_body in the chain entry must not
        crash activation or mutate request_overrides."""
        fbs = [{
            "provider": "openrouter",
            "model": "z-ai/glm-5.1",
            "extra_body": "not-a-dict",  # invalid shape
        }]
        agent = _make_agent(fallback_model=fbs)
        agent.request_overrides = {}

        assert self._activate(agent) is True
        assert "extra_body" not in agent.request_overrides

    def test_empty_extra_body_dict_does_not_inject_key(self):
        """An explicit ``"extra_body": {}`` on a chain entry must behave the
        same as an absent key — no override injected. Guards against a
        regression if the ``and fb_extra_body`` truthiness check is later
        removed."""
        fbs = [{
            "provider": "openrouter",
            "model": "z-ai/glm-5.1",
            "extra_body": {},  # explicit empty
        }]
        agent = _make_agent(fallback_model=fbs)
        agent.request_overrides = {}

        assert self._activate(agent) is True
        assert "extra_body" not in agent.request_overrides

    def test_fallback_extra_body_deep_merges_nested_provider_dict(self):
        """When primary request_overrides already carry ``extra_body.provider``
        (e.g. OpenRouter ``require_parameters: true`` baked in by config),
        the fallback's ``provider.order`` / ``allow_fallbacks`` must merge
        into that nested dict instead of replacing it wholesale."""
        fbs = [{
            "provider": "openrouter",
            "model": "z-ai/glm-5.1",
            "extra_body": {"provider": {"order": ["baidu/fp8"], "allow_fallbacks": False}},
        }]
        agent = _make_agent(fallback_model=fbs)
        agent.request_overrides = {
            "extra_body": {"provider": {"require_parameters": True, "data_collection": "deny"}}
        }

        assert self._activate(agent) is True
        eb = agent.request_overrides["extra_body"]
        # Pre-existing nested keys preserved.
        assert eb["provider"]["require_parameters"] is True
        assert eb["provider"]["data_collection"] == "deny"
        # Fallback-entry nested keys merged in (fallback wins on collisions).
        assert eb["provider"]["order"] == ["baidu/fp8"]
        assert eb["provider"]["allow_fallbacks"] is False

    def test_restore_primary_runtime_clears_fallback_extra_body(self):
        fbs = [{
            "provider": "openrouter",
            "model": "z-ai/glm-5.1",
            "extra_body": {"provider": {"order": ["baidu/fp8"], "allow_fallbacks": False}},
        }]
        agent = _make_agent(fallback_model=fbs)
        # Snapshot baseline overrides at init (typically empty).
        baseline_overrides = dict(agent.request_overrides or {})

        assert self._activate(agent) is True
        assert "extra_body" in agent.request_overrides

        # Simulate the start of the next turn — restore from snapshot.
        with patch.object(
            agent, "_create_openai_client", return_value=MagicMock(),
        ):
            assert agent._restore_primary_runtime() is True

        assert agent.request_overrides == baseline_overrides

    def test_primary_runtime_snapshot_includes_request_overrides(self):
        """Fix #26460 requires the snapshot to capture request_overrides at
        init so restoration after fallback activation doesn't leak the
        fallback-entry override into the primary route."""
        agent = _make_agent(fallback_model=None)
        assert "request_overrides" in agent._primary_runtime
        assert isinstance(agent._primary_runtime["request_overrides"], dict)

    def test_restore_from_older_snapshot_preserves_current_overrides(self):
        """Older sessions persisted ``_primary_runtime`` without the
        ``request_overrides`` field. On restore, code paths that need to
        operate on those sessions must NOT overwrite the current
        ``self.request_overrides`` with ``{}`` — that would silently drop
        user-set overrides applied after the snapshot was taken."""
        fbs = [{"provider": "openrouter", "model": "z-ai/glm-5.1"}]
        agent = _make_agent(fallback_model=fbs)
        assert self._activate(agent) is True
        # Simulate an older session whose snapshot predates #26460 by
        # dropping the request_overrides key after activation.
        agent._primary_runtime.pop("request_overrides", None)
        # User set an override AFTER the (older) snapshot was taken.
        agent.request_overrides = {"extra_body": {"user_field": "preserved"}}

        with patch.object(
            agent, "_create_openai_client", return_value=MagicMock(),
        ):
            assert agent._restore_primary_runtime() is True

        # Override survives the restore — older snapshot didn't carry the key.
        assert agent.request_overrides == {"extra_body": {"user_field": "preserved"}}
