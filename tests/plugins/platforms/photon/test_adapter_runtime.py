"""Runtime helper tests for PhotonAdapter."""
from __future__ import annotations

from pathlib import Path

import pytest

from gateway.config import PlatformConfig
from plugins.platforms.photon import adapter as adapter_mod
from plugins.platforms.photon.adapter import PhotonAdapter


def _make_adapter(monkeypatch: pytest.MonkeyPatch) -> PhotonAdapter:
    monkeypatch.setenv("PHOTON_PROJECT_ID", "test-project-id")
    monkeypatch.setenv("PHOTON_PROJECT_SECRET", "test-project-secret")
    monkeypatch.delenv("PHOTON_WEBHOOK_SECRET", raising=False)
    cfg = PlatformConfig(enabled=True, token="", extra={})
    return PhotonAdapter(cfg)


def test_active_hermes_home_label_uses_current_profile(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "hermes-profile"
    monkeypatch.setenv("HERMES_HOME", str(home))

    assert adapter_mod._active_hermes_home_label() == str(home)


def test_managed_tunnel_autostart_skips_user_owned_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "PHOTON_WEBHOOK_PUBLIC_URL",
        "https://example.com/photon/webhook",
    )
    adapter = _make_adapter(monkeypatch)

    assert adapter._should_autostart_tunnel() is False


def test_managed_tunnel_autostart_allows_trycloudflare_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "PHOTON_WEBHOOK_PUBLIC_URL",
        "https://current.trycloudflare.com/photon/webhook",
    )
    adapter = _make_adapter(monkeypatch)

    assert adapter._should_autostart_tunnel() is True


def test_is_connected_rejects_partial_quick_setup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PHOTON_PROJECT_ID", "test-project-id")
    monkeypatch.setenv("PHOTON_PROJECT_SECRET", "test-project-secret")
    monkeypatch.delenv("PHOTON_WEBHOOK_PUBLIC_URL", raising=False)
    monkeypatch.delenv("PHOTON_WEBHOOK_SECRET", raising=False)
    monkeypatch.delenv("PHOTON_ALLOWED_USERS", raising=False)
    monkeypatch.delenv("PHOTON_ALLOW_ALL_USERS", raising=False)
    monkeypatch.delenv("GATEWAY_ALLOW_ALL_USERS", raising=False)
    monkeypatch.setattr(adapter_mod, "check_requirements", lambda: True)

    cfg = PlatformConfig(enabled=True, token="", extra={})

    assert adapter_mod.validate_config(cfg) is True
    assert adapter_mod.is_connected(cfg) is False


def test_is_connected_accepts_complete_runtime_setup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PHOTON_PROJECT_ID", "test-project-id")
    monkeypatch.setenv("PHOTON_PROJECT_SECRET", "test-project-secret")
    monkeypatch.setenv(
        "PHOTON_WEBHOOK_PUBLIC_URL",
        "https://current.trycloudflare.com/photon/webhook",
    )
    monkeypatch.setenv("PHOTON_WEBHOOK_SECRET", "secret")
    monkeypatch.setenv("PHOTON_ALLOWED_USERS", "+15551234567")
    monkeypatch.setattr(adapter_mod, "check_requirements", lambda: True)

    cfg = PlatformConfig(enabled=True, token="", extra={})

    assert adapter_mod.is_connected(cfg) is True


def test_delete_stale_managed_webhooks_deletes_only_owned(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes"))
    adapter = _make_adapter(monkeypatch)
    deleted: list[str] = []

    def fake_delete_webhook(
        project_id: str,
        project_secret: str,
        *,
        webhook_id: str,
    ) -> None:
        assert project_id == "test-project-id"
        assert project_secret == "test-project-secret"
        deleted.append(webhook_id)

    monkeypatch.setattr(adapter_mod, "delete_webhook", fake_delete_webhook)
    adapter_mod.photon_tunnel.record_owned_webhook(
        "old-managed",
        "https://old.trycloudflare.com/photon/webhook",
    )

    hooks = [
        {
            "id": "old-managed",
            "webhookUrl": "https://old.trycloudflare.com/photon/webhook",
        },
        {
            "id": "unowned-managed",
            "webhookUrl": "https://other.trycloudflare.com/photon/webhook",
        },
        {
            "id": "current-managed",
            "webhookUrl": "https://current.trycloudflare.com/photon/webhook",
        },
        {
            "id": "manual",
            "webhookUrl": "https://example.com/photon/webhook",
        },
    ]

    remaining = adapter._delete_stale_managed_webhooks(
        hooks,
        keep_url="https://current.trycloudflare.com/photon/webhook",
    )

    assert deleted == ["old-managed"]
    assert [hook["id"] for hook in remaining] == [
        "unowned-managed",
        "current-managed",
        "manual",
    ]


def test_reused_managed_tunnel_is_not_owned_or_stopped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _make_adapter(monkeypatch)
    adapter._webhook_secret = "secret"
    stopped: list[bool] = []

    monkeypatch.setattr(
        adapter_mod.photon_tunnel,
        "start",
        lambda **_kwargs: adapter_mod.photon_tunnel.TunnelStartResult(
            success=True,
            public_url="https://current.trycloudflare.com",
            webhook_url="https://current.trycloudflare.com/photon/webhook",
            reused=True,
            pid=123,
        ),
    )
    monkeypatch.setattr(
        adapter_mod,
        "list_webhooks",
        lambda *_args, **_kwargs: [
            {
                "id": "current-managed",
                "webhookUrl": "https://current.trycloudflare.com/photon/webhook",
            }
        ],
    )
    monkeypatch.setattr(adapter_mod, "_save_env_value", lambda *_args: None)
    monkeypatch.setattr(adapter_mod.photon_tunnel, "stop", lambda: stopped.append(True))

    adapter._ensure_managed_tunnel_webhook()
    adapter._stop_owned_managed_tunnel()

    assert adapter._managed_tunnel_started is False
    assert stopped == []


def test_started_managed_tunnel_is_stopped_on_registration_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _make_adapter(monkeypatch)
    adapter._stop_tunnel_on_disconnect = False
    stopped: list[bool] = []

    monkeypatch.setattr(
        adapter_mod.photon_tunnel,
        "start",
        lambda **_kwargs: adapter_mod.photon_tunnel.TunnelStartResult(
            success=True,
            public_url="https://current.trycloudflare.com",
            webhook_url="https://current.trycloudflare.com/photon/webhook",
            reused=False,
            pid=123,
        ),
    )
    monkeypatch.setattr(
        adapter_mod,
        "list_webhooks",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    monkeypatch.setattr(
        adapter_mod.photon_tunnel,
        "stop",
        lambda: stopped.append(True) or {"message": "stopped"},
    )

    with pytest.raises(RuntimeError, match="boom"):
        adapter._ensure_managed_tunnel_webhook()

    assert adapter._managed_tunnel_started is False
    assert stopped == [True]


@pytest.mark.asyncio
async def test_connect_stops_started_tunnel_when_sidecar_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _make_adapter(monkeypatch)
    adapter._stop_tunnel_on_disconnect = False
    stopped: list[bool] = []
    webhook_stopped: list[bool] = []

    async def fake_start_webhook_server() -> None:
        return None

    async def fake_stop_webhook_server() -> None:
        webhook_stopped.append(True)

    def fake_ensure_tunnel() -> None:
        adapter._managed_tunnel_started = True

    async def fake_start_sidecar() -> None:
        raise RuntimeError("sidecar down")

    monkeypatch.setattr(adapter, "_start_webhook_server", fake_start_webhook_server)
    monkeypatch.setattr(adapter, "_stop_webhook_server", fake_stop_webhook_server)
    monkeypatch.setattr(adapter, "_ensure_managed_tunnel_webhook", fake_ensure_tunnel)
    monkeypatch.setattr(adapter, "_start_sidecar", fake_start_sidecar)
    monkeypatch.setattr(
        adapter_mod.photon_tunnel,
        "stop",
        lambda: stopped.append(True) or {"message": "stopped"},
    )

    assert await adapter.connect() is False
    assert adapter._managed_tunnel_started is False
    assert stopped == [True]
    assert webhook_stopped == [True]
