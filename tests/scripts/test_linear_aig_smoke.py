from types import SimpleNamespace

import pytest

from scripts import linear_aig_smoke


def _args(**kwargs):
    values = {
        "client_credentials_scope": "",
        "client_credentials_token_url": linear_aig_smoke.DEFAULT_TOKEN_URL,
    }
    values.update(kwargs)
    return SimpleNamespace(**values)


def test_client_credentials_scope_is_required(monkeypatch):
    monkeypatch.setenv("HERMES_LINEAR_AIG_CLIENT_ID", "client-id")
    monkeypatch.setenv("HERMES_LINEAR_AIG_CLIENT_SECRET", "client-secret")
    monkeypatch.delenv("HERMES_LINEAR_AIG_CLIENT_CREDENTIALS_SCOPE", raising=False)
    monkeypatch.delenv("LINEAR_CLIENT_CREDENTIALS_SCOPE", raising=False)

    client_id, client_secret, scope, source = (
        linear_aig_smoke._client_credentials_config(_args())
    )

    assert client_id == "client-id"
    assert client_secret == "client-secret"
    assert scope == ""
    assert "scope=missing" in source


def test_client_credentials_cli_scope_takes_priority(monkeypatch):
    monkeypatch.setenv("HERMES_LINEAR_AIG_CLIENT_ID", "client-id")
    monkeypatch.setenv("HERMES_LINEAR_AIG_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("HERMES_LINEAR_AIG_CLIENT_CREDENTIALS_SCOPE", "read,write")

    client_id, client_secret, scope, source = (
        linear_aig_smoke._client_credentials_config(
            _args(client_credentials_scope="read,write,app:assignable")
        )
    )

    assert client_id == "client-id"
    assert client_secret == "client-secret"
    assert scope == "read,write,app:assignable"
    assert "scope=--client-credentials-scope" in source


def test_linear_hermes_env_aliases_are_supported(monkeypatch):
    monkeypatch.setenv("LINEAR_HERMES_CLIENT_ID", "client-id")
    monkeypatch.setenv("LINEAR-HERMES_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("LINEAR_HERMES_CLIENT_CREDENTIALS_SCOPE", "read,write")

    client_id, client_secret, scope, source = (
        linear_aig_smoke._client_credentials_config(_args())
    )

    assert client_id == "client-id"
    assert client_secret == "client-secret"
    assert scope == "read,write"
    assert "client_id=LINEAR_HERMES_CLIENT_ID" in source
    assert "client_secret=LINEAR-HERMES_CLIENT_SECRET" in source
    assert "scope=LINEAR_HERMES_CLIENT_CREDENTIALS_SCOPE" in source


@pytest.mark.asyncio
async def test_client_credentials_fetch_skips_when_incomplete(monkeypatch):
    monkeypatch.delenv("HERMES_LINEAR_AIG_CLIENT_ID", raising=False)
    monkeypatch.delenv("HERMES_LINEAR_AIG_CLIENT_SECRET", raising=False)

    source, token = await linear_aig_smoke._fetch_client_credentials_token(_args())

    assert source == ""
    assert token == ""
