"""Tests for Spotify multi-account auth resolution.

Covers the v2 ``providers.spotify`` shape with named ``accounts`` and
``routing.telegram[user_id] -> account_id`` lookups, alongside the legacy
flat-state compatibility path.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict

import pytest

from hermes_cli import auth as auth_mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _spotify_state(access_token: str, *, expires_at: str = "2099-01-01T00:00:00+00:00") -> Dict[str, Any]:
    """Stub Spotify per-account token bundle used in tests."""
    return {
        "auth_type": "oauth_pkce",
        "client_id": "spotify-client",
        "redirect_uri": "http://127.0.0.1:43827/spotify/callback",
        "api_base_url": auth_mod.DEFAULT_SPOTIFY_API_BASE_URL,
        "accounts_base_url": auth_mod.DEFAULT_SPOTIFY_ACCOUNTS_BASE_URL,
        "scope": auth_mod.DEFAULT_SPOTIFY_SCOPE,
        "access_token": access_token,
        "refresh_token": f"{access_token}-refresh",
        "token_type": "Bearer",
        "expires_at": expires_at,
    }


def _write_spotify_provider(tmp_path, provider_state: Dict[str, Any]) -> None:
    """Persist a providers.spotify state into the HERMES_HOME-rooted auth store.

    Caller must have set ``HERMES_HOME`` via monkeypatch first.
    """
    with auth_mod._auth_store_lock():
        store = auth_mod._load_auth_store()
        store["active_provider"] = "nous"
        auth_mod._store_provider_state(store, "spotify", provider_state, set_active=False)
        auth_mod._save_auth_store(store)


# ---------------------------------------------------------------------------
# Pure helper tests
# ---------------------------------------------------------------------------

class TestNormalizeAccountId:
    def test_accepts_simple_slugs(self) -> None:
        assert auth_mod._normalize_spotify_account_id("mark") == "mark"
        assert auth_mod._normalize_spotify_account_id("amy") == "amy"
        assert auth_mod._normalize_spotify_account_id("user_1") == "user_1"
        assert auth_mod._normalize_spotify_account_id("user-1") == "user-1"

    def test_lowercases(self) -> None:
        assert auth_mod._normalize_spotify_account_id("MARK") == "mark"
        assert auth_mod._normalize_spotify_account_id("  Amy  ") == "amy"

    def test_blank_returns_none(self) -> None:
        assert auth_mod._normalize_spotify_account_id(None) is None
        assert auth_mod._normalize_spotify_account_id("") is None
        assert auth_mod._normalize_spotify_account_id("   ") is None

    def test_rejects_invalid_chars(self) -> None:
        for bad in ("mark!", "mark.amy", "mark amy", "mark/amy", "-mark", "_mark"):
            with pytest.raises(auth_mod.AuthError) as exc:
                auth_mod._normalize_spotify_account_id(bad)
            assert exc.value.code == "spotify_account_id_invalid"


class TestShapeDetection:
    def test_legacy_state_is_not_multi_account(self) -> None:
        assert not auth_mod._is_spotify_multi_account_state({"access_token": "abc"})
        assert not auth_mod._is_spotify_multi_account_state({})
        assert not auth_mod._is_spotify_multi_account_state(None)

    def test_v2_state_with_accounts_is_multi_account(self) -> None:
        assert auth_mod._is_spotify_multi_account_state(
            {"schema_version": 2, "accounts": {"mark": {}}}
        )

    def test_legacy_state_round_trip(self) -> None:
        state = {"access_token": "abc", "refresh_token": "def"}
        wrapped = auth_mod._spotify_legacy_state_as_account(state)
        assert wrapped == state
        # Make sure it's a copy, not the same object.
        assert wrapped is not state

    def test_legacy_state_without_tokens_returns_none(self) -> None:
        assert auth_mod._spotify_legacy_state_as_account({"client_id": "x"}) is None
        assert auth_mod._spotify_legacy_state_as_account({}) is None


class TestEnsureMultiAccountState:
    def test_idempotent_on_v2_state(self) -> None:
        original = {"schema_version": 2, "accounts": {"mark": {"access_token": "x"}}}
        result = auth_mod._ensure_spotify_multi_account_state(original)
        assert result["schema_version"] == 2
        assert result["accounts"]["mark"]["access_token"] == "x"
        assert "routing" in result

    def test_converts_legacy_to_v2(self) -> None:
        legacy = {"access_token": "legacy-access", "refresh_token": "legacy-refresh"}
        result = auth_mod._ensure_spotify_multi_account_state(legacy, legacy_account_id="mark")
        assert result["schema_version"] == 2
        assert result["default_account"] == "mark"
        assert result["accounts"]["mark"]["access_token"] == "legacy-access"
        assert result["routing"] == {}


# ---------------------------------------------------------------------------
# Resolver tests
# ---------------------------------------------------------------------------

class TestResolveSpotifyRuntimeCredentials:
    """Behavioural tests for ``resolve_spotify_runtime_credentials``.

    Each test sets HERMES_HOME to a tmp dir, writes a providers.spotify state
    into the auth store, then asserts the resolver picks the right account.
    """

    def test_legacy_single_account_resolves(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        _write_spotify_provider(tmp_path, _spotify_state("legacy-access"))

        runtime = auth_mod.resolve_spotify_runtime_credentials(refresh_if_expiring=False)

        assert runtime["access_token"] == "legacy-access"
        assert runtime["account_id"] is None
        assert runtime["account_source"] == "legacy"

    def test_explicit_account_selection(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        _write_spotify_provider(tmp_path, {
            "schema_version": 2,
            "default_account": "mark",
            "accounts": {
                "mark": _spotify_state("mark-access"),
                "amy": _spotify_state("amy-access"),
            },
            "routing": {},
        })

        runtime = auth_mod.resolve_spotify_runtime_credentials(
            account_id="amy", refresh_if_expiring=False,
        )

        assert runtime["access_token"] == "amy-access"
        assert runtime["account_id"] == "amy"
        assert runtime["account_source"] == "explicit"

    def test_uses_default_account_when_no_routing(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        _write_spotify_provider(tmp_path, {
            "schema_version": 2,
            "default_account": "mark",
            "accounts": {
                "mark": _spotify_state("mark-access"),
                "amy": _spotify_state("amy-access"),
            },
            "routing": {},
        })

        runtime = auth_mod.resolve_spotify_runtime_credentials(refresh_if_expiring=False)

        assert runtime["access_token"] == "mark-access"
        assert runtime["account_id"] == "mark"
        assert runtime["account_source"] == "default"

    def test_routes_by_telegram_user_id(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The whole point of multi-account: Amy's Telegram messages -> Amy's Spotify."""
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        _write_spotify_provider(tmp_path, {
            "schema_version": 2,
            "default_account": "mark",
            "accounts": {
                "mark": _spotify_state("mark-access"),
                "amy": _spotify_state("amy-access"),
            },
            "routing": {
                "telegram": {
                    "8610423590": "mark",
                    "8634968316": "amy",
                },
            },
        })

        amy = auth_mod.resolve_spotify_runtime_credentials(
            platform="telegram", user_id="8634968316", refresh_if_expiring=False,
        )
        assert amy["access_token"] == "amy-access"
        assert amy["account_id"] == "amy"
        assert amy["account_source"] == "source"

        mark = auth_mod.resolve_spotify_runtime_credentials(
            platform="telegram", user_id="8610423590", refresh_if_expiring=False,
        )
        assert mark["access_token"] == "mark-access"
        assert mark["account_id"] == "mark"
        assert mark["account_source"] == "source"

    def test_session_contextvars_route_when_kwargs_unset(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When platform/user_id aren't passed explicitly, the resolver falls
        back to the gateway's per-task ContextVars (HERMES_SESSION_PLATFORM
        / HERMES_SESSION_USER_ID). This is the path that lets gateway-origin
        Spotify tool calls auto-route without touching model_tools/run_agent.
        """
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        # get_session_env falls back to os.environ when the ContextVar was
        # never set in this task (which is the case for synchronous tests).
        monkeypatch.setenv("HERMES_SESSION_PLATFORM", "telegram")
        monkeypatch.setenv("HERMES_SESSION_USER_ID", "8634968316")
        _write_spotify_provider(tmp_path, {
            "schema_version": 2,
            "default_account": "mark",
            "accounts": {
                "mark": _spotify_state("mark-access"),
                "amy": _spotify_state("amy-access"),
            },
            "routing": {
                "telegram": {
                    "8610423590": "mark",
                    "8634968316": "amy",
                },
            },
        })

        runtime = auth_mod.resolve_spotify_runtime_credentials(refresh_if_expiring=False)

        assert runtime["access_token"] == "amy-access"
        assert runtime["account_id"] == "amy"
        assert runtime["account_source"] == "source"

    def test_explicit_kwargs_override_contextvars(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Explicit platform/user_id kwargs beat the ContextVar fallback."""
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        monkeypatch.setenv("HERMES_SESSION_PLATFORM", "telegram")
        monkeypatch.setenv("HERMES_SESSION_USER_ID", "8634968316")  # Amy in env
        _write_spotify_provider(tmp_path, {
            "schema_version": 2,
            "default_account": "mark",
            "accounts": {
                "mark": _spotify_state("mark-access"),
                "amy": _spotify_state("amy-access"),
            },
            "routing": {
                "telegram": {
                    "8610423590": "mark",
                    "8634968316": "amy",
                },
            },
        })

        # Even though env says Amy, explicit kwargs say Mark.
        runtime = auth_mod.resolve_spotify_runtime_credentials(
            platform="telegram",
            user_id="8610423590",
            refresh_if_expiring=False,
        )

        assert runtime["access_token"] == "mark-access"
        assert runtime["account_id"] == "mark"

    def test_env_override_beats_default(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        monkeypatch.setenv("HERMES_SPOTIFY_ACCOUNT", "amy")
        _write_spotify_provider(tmp_path, {
            "schema_version": 2,
            "default_account": "mark",
            "accounts": {
                "mark": _spotify_state("mark-access"),
                "amy": _spotify_state("amy-access"),
            },
            "routing": {},
        })

        runtime = auth_mod.resolve_spotify_runtime_credentials(refresh_if_expiring=False)

        assert runtime["account_id"] == "amy"
        assert runtime["access_token"] == "amy-access"

    def test_refresh_updates_only_selected_account(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A refresh of Amy's token must not touch Mark's stored state."""
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        _write_spotify_provider(tmp_path, {
            "schema_version": 2,
            "default_account": "mark",
            "accounts": {
                "mark": _spotify_state("mark-old", expires_at="2000-01-01T00:00:00+00:00"),
                "amy": _spotify_state("amy-old", expires_at="2000-01-01T00:00:00+00:00"),
            },
            "routing": {},
        })
        monkeypatch.setattr(
            auth_mod,
            "_refresh_spotify_oauth_state",
            lambda state, timeout_seconds=20.0: {
                **state,
                "access_token": f"{state['access_token']}-refreshed",
                "expires_at": "2099-01-01T00:00:00+00:00",
            },
        )

        runtime = auth_mod.resolve_spotify_runtime_credentials(account_id="amy")

        assert runtime["access_token"] == "amy-old-refreshed"
        persisted = auth_mod.get_provider_auth_state("spotify")
        assert persisted["accounts"]["amy"]["access_token"] == "amy-old-refreshed"
        # Mark's state must be untouched.
        assert persisted["accounts"]["mark"]["access_token"] == "mark-old"

    def test_unknown_explicit_account_raises(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        _write_spotify_provider(tmp_path, {
            "schema_version": 2,
            "default_account": "mark",
            "accounts": {"mark": _spotify_state("mark-access")},
            "routing": {},
        })

        with pytest.raises(auth_mod.AuthError) as exc:
            auth_mod.resolve_spotify_runtime_credentials(account_id="ghost")
        assert exc.value.code == "spotify_account_missing"

    def test_route_to_missing_account_raises(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A routing rule pointing at an account that no longer exists is loud, not silent."""
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        _write_spotify_provider(tmp_path, {
            "schema_version": 2,
            "default_account": "mark",
            "accounts": {"mark": _spotify_state("mark-access")},
            "routing": {"telegram": {"8634968316": "amy"}},  # amy doesn't exist
        })

        with pytest.raises(auth_mod.AuthError) as exc:
            auth_mod.resolve_spotify_runtime_credentials(
                platform="telegram", user_id="8634968316",
            )
        assert exc.value.code == "spotify_route_account_missing"

    def test_ambiguous_state_no_default_raises(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Multi-account state with no default + no routing + no explicit pick = error."""
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        _write_spotify_provider(tmp_path, {
            "schema_version": 2,
            "default_account": None,
            "accounts": {
                "mark": _spotify_state("mark-access"),
                "amy": _spotify_state("amy-access"),
            },
            "routing": {},
        })

        with pytest.raises(auth_mod.AuthError) as exc:
            auth_mod.resolve_spotify_runtime_credentials(refresh_if_expiring=False)
        assert exc.value.code == "spotify_account_ambiguous"

    def test_legacy_with_explicit_account_raises(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Asking for `--account` on legacy auth requires migrating first."""
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        _write_spotify_provider(tmp_path, _spotify_state("legacy-access"))

        with pytest.raises(auth_mod.AuthError) as exc:
            auth_mod.resolve_spotify_runtime_credentials(account_id="mark")
        assert exc.value.code == "spotify_legacy_no_named_account"


# ---------------------------------------------------------------------------
# CLI subcommand tests (storage logic only; no network)
# ---------------------------------------------------------------------------

class TestSpotifyMigrateLegacy:
    def test_migrate_wraps_legacy_under_named_account(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        _write_spotify_provider(tmp_path, _spotify_state("legacy-access"))

        auth_mod.spotify_migrate_legacy_command(SimpleNamespace(
            account="mark",
            owner_name="Mark",
            telegram_user_id="8610423590",
            user_id=None,
            platform=None,
            set_default=True,
        ))

        persisted = auth_mod.get_provider_auth_state("spotify")
        assert persisted is not None
        assert auth_mod._is_spotify_multi_account_state(persisted)
        assert persisted["default_account"] == "mark"
        assert persisted["accounts"]["mark"]["access_token"] == "legacy-access"
        assert persisted["accounts"]["mark"]["owner_name"] == "Mark"
        assert persisted["routing"]["telegram"]["8610423590"] == "mark"

        out = capsys.readouterr().out
        assert "Migrated legacy single-account state to account 'mark'" in out

    def test_migrate_requires_existing_state(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))

        with pytest.raises(SystemExit) as exc:
            auth_mod.spotify_migrate_legacy_command(SimpleNamespace(
                account="mark", owner_name=None, telegram_user_id=None,
                user_id=None, platform=None, set_default=False,
            ))
        assert "not authenticated" in str(exc.value)

    def test_migrate_idempotent_on_v2(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        _write_spotify_provider(tmp_path, {
            "schema_version": 2,
            "default_account": "mark",
            "accounts": {"mark": _spotify_state("mark-access")},
            "routing": {},
        })

        auth_mod.spotify_migrate_legacy_command(SimpleNamespace(
            account="mark", owner_name="Mark Baker",
            telegram_user_id="8610423590", user_id=None, platform=None,
            set_default=False,
        ))

        out = capsys.readouterr().out
        assert "already in multi-account mode" in out
        persisted = auth_mod.get_provider_auth_state("spotify")
        # Owner metadata and routing got layered on top.
        assert persisted["accounts"]["mark"]["owner_name"] == "Mark Baker"
        assert persisted["routing"]["telegram"]["8610423590"] == "mark"


class TestSpotifyRouteCommand:
    def test_route_adds_telegram_rule(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        _write_spotify_provider(tmp_path, {
            "schema_version": 2,
            "default_account": "mark",
            "accounts": {
                "mark": _spotify_state("mark-access"),
                "amy": _spotify_state("amy-access"),
            },
            "routing": {},
        })

        auth_mod.spotify_route_account_command(SimpleNamespace(
            account="amy", platform="telegram",
            user_id="8634968316", telegram_user_id=None,
        ))

        persisted = auth_mod.get_provider_auth_state("spotify")
        assert persisted["routing"]["telegram"]["8634968316"] == "amy"

    def test_route_rejects_missing_account(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        _write_spotify_provider(tmp_path, {
            "schema_version": 2,
            "default_account": "mark",
            "accounts": {"mark": _spotify_state("mark-access")},
            "routing": {},
        })

        with pytest.raises(SystemExit) as exc:
            auth_mod.spotify_route_account_command(SimpleNamespace(
                account="amy", platform="telegram",
                user_id="8634968316", telegram_user_id=None,
            ))
        assert "'amy' is not configured" in str(exc.value)


class TestSpotifySetDefault:
    def test_set_default_changes_active_default(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        _write_spotify_provider(tmp_path, {
            "schema_version": 2,
            "default_account": "mark",
            "accounts": {
                "mark": _spotify_state("mark-access"),
                "amy": _spotify_state("amy-access"),
            },
            "routing": {},
        })

        auth_mod.spotify_set_default_account_command(SimpleNamespace(account="amy"))

        persisted = auth_mod.get_provider_auth_state("spotify")
        assert persisted["default_account"] == "amy"


class TestSpotifyListAccounts:
    def test_list_shows_accounts_and_routes(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        _write_spotify_provider(tmp_path, {
            "schema_version": 2,
            "default_account": "mark",
            "accounts": {
                "mark": {**_spotify_state("mark-access"), "owner_name": "Mark"},
                "amy": {**_spotify_state("amy-access"), "owner_name": "Amy"},
            },
            "routing": {
                "telegram": {
                    "8610423590": "mark",
                    "8634968316": "amy",
                },
            },
        })

        auth_mod.spotify_list_accounts_command(SimpleNamespace())

        out = capsys.readouterr().out
        assert "Spotify accounts (2 configured)" in out
        assert "mark: Mark * default" in out
        assert "amy: Amy" in out
        assert "telegram:8634968316 -> amy" in out
        # No bare token leakage in human output.
        assert "amy-access" not in out
        assert "mark-access" not in out

    def test_list_flags_broken_route(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        _write_spotify_provider(tmp_path, {
            "schema_version": 2,
            "default_account": "mark",
            "accounts": {"mark": _spotify_state("mark-access")},
            "routing": {"telegram": {"8634968316": "amy"}},  # amy doesn't exist
        })

        auth_mod.spotify_list_accounts_command(SimpleNamespace())

        out = capsys.readouterr().out
        assert "BROKEN" in out


class TestSpotifyLogoutPerAccount:
    def test_logout_account_removes_account_and_routes(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        _write_spotify_provider(tmp_path, {
            "schema_version": 2,
            "default_account": "amy",
            "accounts": {
                "mark": _spotify_state("mark-access"),
                "amy": _spotify_state("amy-access"),
            },
            "routing": {
                "telegram": {
                    "8610423590": "mark",
                    "8634968316": "amy",
                },
            },
        })

        auth_mod.spotify_logout_command(SimpleNamespace(account="amy"))

        persisted = auth_mod.get_provider_auth_state("spotify")
        assert "amy" not in persisted["accounts"]
        assert "mark" in persisted["accounts"]
        # Default falls back to the remaining account.
        assert persisted["default_account"] == "mark"
        # Routing rule pointing at amy is gone.
        assert "8634968316" not in persisted["routing"].get("telegram", {})
        # Mark's routing untouched.
        assert persisted["routing"]["telegram"]["8610423590"] == "mark"

    def test_logout_last_account_clears_default(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        _write_spotify_provider(tmp_path, {
            "schema_version": 2,
            "default_account": "mark",
            "accounts": {"mark": _spotify_state("mark-access")},
            "routing": {},
        })

        auth_mod.spotify_logout_command(SimpleNamespace(account="mark"))

        persisted = auth_mod.get_provider_auth_state("spotify")
        assert persisted["accounts"] == {}
        assert persisted.get("default_account") is None

    def test_logout_rejects_account_in_legacy_mode(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        _write_spotify_provider(tmp_path, _spotify_state("legacy-access"))

        with pytest.raises(SystemExit) as exc:
            auth_mod.spotify_logout_command(SimpleNamespace(account="mark"))
        assert "legacy single-account mode" in str(exc.value)


class TestSpotifyStatusAccountFilter:
    def test_status_with_account_shows_just_that_account(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        _write_spotify_provider(tmp_path, {
            "schema_version": 2,
            "default_account": "mark",
            "accounts": {
                "mark": {**_spotify_state("mark-access"), "owner_name": "Mark"},
                "amy": {**_spotify_state("amy-access"), "owner_name": "Amy"},
            },
            "routing": {},
        })

        auth_mod.spotify_status_command(SimpleNamespace(account="amy"))

        out = capsys.readouterr().out
        assert "spotify[amy]: logged in" in out
        assert "owner_name: Amy" in out
        # No token leakage.
        assert "amy-access" not in out
        # Mark's owner_name should NOT appear when filtering by Amy.
        assert "Mark" not in out

    def test_status_without_account_shows_summary(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        _write_spotify_provider(tmp_path, {
            "schema_version": 2,
            "default_account": "mark",
            "accounts": {
                "mark": _spotify_state("mark-access"),
                "amy": _spotify_state("amy-access"),
            },
            "routing": {},
        })

        auth_mod.spotify_status_command(SimpleNamespace(account=None))

        out = capsys.readouterr().out
        assert "multi-account" in out
        assert "default_account: mark" in out
        assert "- mark" in out
        assert "- amy" in out
