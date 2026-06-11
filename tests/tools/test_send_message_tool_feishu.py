"""Tests for _send_feishu() lazy-install and import-rebind fix (v3).

These tests verify the fix that switched from ``from X import Y`` (value binding,
stale after lazy-install rebinds module globals) to ``import X as mod``
(module-namespace access, always reads the current value).

Independent of Telegram optional dependencies — does NOT importorskip("telegram").
"""

import asyncio
import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_mock_feishu_mod(*, feishu_available=False, feishu_domain=None,
                           lark_domain=None):
    """Build a mock ``gateway.platforms.feishu`` module.

    The returned module includes a real closure-based ``check_feishu_requirements``
    that behaves like the production function in ``feishu.py``:

    * If ``FEISHU_AVAILABLE`` is True → short-circuit: return True immediately.
    * If ``FEISHU_AVAILABLE`` is False → call ``tools.lazy_deps.ensure_and_bind``,
      and on success rebind ``FEISHU_DOMAIN`` / ``LARK_DOMAIN`` / ``FEISHU_AVAILABLE``
      on the mock module.

    This ensures that tests which verify short-circuit behaviour (test 2) and
    lazy-install failure (test 5) exercise the real branching logic, not a
    MagicMock stand-in.
    """
    mock_mod = MagicMock()
    mock_mod.FEISHU_AVAILABLE = feishu_available
    mock_mod.FEISHU_DOMAIN = feishu_domain
    mock_mod.LARK_DOMAIN = lark_domain

    def check_feishu_requirements():
        # Short-circuit: deps already available
        if mock_mod.FEISHU_AVAILABLE:
            return True

        # Lazy-install path – calls the real ensure_and_bind (which callers
        # should mock to control success / failure).
        from tools.lazy_deps import ensure_and_bind
        ok = ensure_and_bind("platform.feishu")
        if ok:
            mock_mod.FEISHU_DOMAIN = "https://open.feishu.cn"
            mock_mod.LARK_DOMAIN = "https://open.larksuite.com"
            mock_mod.FEISHU_AVAILABLE = True
        return ok

    mock_mod.check_feishu_requirements = check_feishu_requirements

    # Adapter class and instance
    mock_adapter_inst = MagicMock()
    mock_adapter_inst._domain_name = "feishu"
    mock_client = MagicMock()
    mock_adapter_inst._build_lark_client.return_value = mock_client
    mock_adapter_inst.send = AsyncMock(
        return_value=MagicMock(success=True, message_id="msg_test_123")
    )
    mock_adapter_inst.send_image_file = AsyncMock()
    mock_adapter_inst.send_video = AsyncMock()
    mock_adapter_inst.send_voice = AsyncMock()
    mock_adapter_inst.send_document = AsyncMock()

    mock_adapter_cls = MagicMock(return_value=mock_adapter_inst)
    mock_adapter_cls.MAX_MESSAGE_LENGTH = 8000
    mock_mod.FeishuAdapter = mock_adapter_cls

    return mock_mod, mock_adapter_cls, mock_adapter_inst


# ---------------------------------------------------------------------------
# 1. test_send_feishu_lazy_install_and_rebind
# ---------------------------------------------------------------------------

def test_send_feishu_lazy_install_and_rebind():
    """FEISHU_AVAILABLE=False triggers lazy-install; _build_lark_client gets rebound domain.

    Before the fix, ``from gateway.platforms.feishu import FEISHU_DOMAIN`` would
    capture ``None`` at import time, and ``ensure_and_bind()`` rebinding the
    module global would not update the local variable.  After the fix,
    ``feishu_mod.FEISHU_DOMAIN`` reads the current value from the module namespace,
    so the rebound ``"https://open.feishu.cn"`` is passed to ``_build_lark_client``.
    """
    mock_mod, mock_cls, mock_inst = _build_mock_feishu_mod(
        feishu_available=False,
        feishu_domain=None,
        lark_domain=None,
    )

    # Ensure gateway / gateway.platforms packages are in sys.modules so the
    # import inside _send_feishu() can find them.
    import gateway  # noqa: F401
    import gateway.platforms  # noqa: F401

    with patch.dict(sys.modules, {"gateway.platforms.feishu": mock_mod}), \
         patch("tools.lazy_deps.ensure_and_bind", return_value=True):
        from tools.send_message_tool import _send_feishu
        result = asyncio.run(_send_feishu(
            pconfig=MagicMock(),
            chat_id="oc_test123",
            message="Hello from test",
        ))

    assert result["success"] is True
    assert result["platform"] == "feishu"
    assert result["message_id"] == "msg_test_123"
    # Critical assertion: _build_lark_client received the REBOUND domain, not None
    mock_inst._build_lark_client.assert_called_once_with("https://open.feishu.cn")
    mock_inst.send.assert_awaited_once()


# ---------------------------------------------------------------------------
# 2. test_feishu_available_true_short_circuits
# ---------------------------------------------------------------------------

def test_feishu_available_true_short_circuits():
    """FEISHU_AVAILABLE=True: check_feishu_requirements() short-circuits internally.

    The v3 fix deliberately calls ``check_feishu_requirements()`` every time (unlike
    the v1 proposal that tested ``FEISHU_AVAILABLE`` inline before calling it).
    The short-circuit is *inside* ``check_feishu_requirements()`` at
    ``feishu.py:1353``: ``if FEISHU_AVAILABLE: return True``.  This test verifies
    that when deps are already available, ``ensure_and_bind()`` is never reached.

    ``check_feishu_requirements`` on the mock module is a real closure (not a
    MagicMock stand-in), so the short-circuit assertion is genuine — if it didn't
    short-circuit, it *would* call ``ensure_and_bind``.
    """
    mock_mod, mock_cls, mock_inst = _build_mock_feishu_mod(
        feishu_available=True,
        feishu_domain="https://open.feishu.cn",
        lark_domain="https://open.larksuite.com",
    )

    import gateway  # noqa: F401
    import gateway.platforms  # noqa: F401

    with patch.dict(sys.modules, {"gateway.platforms.feishu": mock_mod}), \
         patch("tools.lazy_deps.ensure_and_bind") as mock_ensure:
        from tools.send_message_tool import _send_feishu
        result = asyncio.run(_send_feishu(
            pconfig=MagicMock(),
            chat_id="oc_test456",
            message="Deps already available",
        ))

    assert result["success"] is True
    mock_inst._build_lark_client.assert_called_once_with("https://open.feishu.cn")
    # The real short-circuit inside check_feishu_requirements() skipped lazy install
    mock_ensure.assert_not_called()


# ---------------------------------------------------------------------------
# 3. test_deliver_result_no_adapter_feishu_fallback
# ---------------------------------------------------------------------------

def test_deliver_result_no_adapter_feishu_fallback():
    """No live adapter: _deliver_result falls back to standalone _send_to_platform → _send_feishu().

    When adapters and loop are not provided (standalone cron tick from CLI or
    dashboard), _deliver_result() must call _send_to_platform() which dispatches
    to _send_feishu().  This test verifies the standalone path is taken.
    """
    from gateway.config import Platform, PlatformConfig

    mock_pconfig = PlatformConfig(enabled=True, token="test-token")

    mock_mod, mock_cls, mock_inst = _build_mock_feishu_mod(
        feishu_available=True,
        feishu_domain="https://open.feishu.cn",
        lark_domain="https://open.larksuite.com",
    )

    # Build a job that delivers to feishu with explicit target resolution
    job = {
        "id": "job_test_standalone",
        "deliver": "feishu:oc_standalone_test",
    }

    import gateway  # noqa: F401
    import gateway.platforms  # noqa: F401

    with patch.dict(sys.modules, {"gateway.platforms.feishu": mock_mod}):
        from cron.scheduler import _deliver_result

        # _deliver_result() does "from gateway.config import load_gateway_config"
        # inside the function body, so the patch target must be gateway.config.
        with patch("gateway.config.load_gateway_config") as mock_load_cfg:
            mock_cfg = MagicMock()
            mock_cfg.platforms = {Platform.FEISHU: mock_pconfig}
            mock_load_cfg.return_value = mock_cfg

            with patch("cron.scheduler.load_config", return_value={}):
                # _deliver_result returns None on success
                error = _deliver_result(
                    job,
                    "Standalone fallback test message",
                    adapters=None,   # no live adapter → standalone path
                    loop=None,
                )

    assert error is None


# ---------------------------------------------------------------------------
# 4. test_handle_send_to_feishu_hits_fixed_path
# ---------------------------------------------------------------------------

def test_handle_send_to_feishu_hits_fixed_path():
    """_handle_send() targeting feishu routes through the repaired _send_feishu().

    When a send_message tool call targets ``feishu:chat_xxx``, _handle_send()
    calls _send_to_platform(Platform.FEISHU, ...) which dispatches to
    _send_feishu().  This test verifies the full chain reaches the fixed
    function and the lazy-install pathway works end-to-end.
    """
    from gateway.config import Platform, PlatformConfig

    mock_pconfig = PlatformConfig(enabled=True, token="test-token")
    mock_cfg = MagicMock()
    mock_cfg.platforms = {Platform.FEISHU: mock_pconfig}
    mock_cfg.get_home_channel.return_value = MagicMock(chat_id="oc_home_fallback")

    mock_mod, mock_cls, mock_inst = _build_mock_feishu_mod(
        feishu_available=False,
        feishu_domain=None,
        lark_domain=None,
    )

    import gateway  # noqa: F401
    import gateway.platforms  # noqa: F401

    # _handle_send() does "from gateway.config import load_gateway_config, ..."
    # inside the function body → patch gateway.config, not tools.send_message_tool.
    with patch.dict(sys.modules, {"gateway.platforms.feishu": mock_mod}), \
         patch("gateway.config.load_gateway_config", return_value=mock_cfg), \
         patch("tools.lazy_deps.ensure_and_bind", return_value=True):
        from tools.send_message_tool import _handle_send

        result_json = _handle_send({
            "target": "feishu:oc_test123",
            "message": "Fixed path test",
        })
        result = json.loads(result_json)

    assert result["success"] is True
    assert result["platform"] == "feishu"
    assert result["message_id"] == "msg_test_123"
    mock_cls.assert_called_once()
    mock_inst.send.assert_awaited_once()
    # _build_lark_client received the rebound domain (not None)
    mock_inst._build_lark_client.assert_called_once_with("https://open.feishu.cn")


# ---------------------------------------------------------------------------
# 5. test_lazy_install_fails_returns_error
# ---------------------------------------------------------------------------

def test_lazy_install_fails_returns_error():
    """When check_feishu_requirements() returns False, _send_feishu() returns an error dict.

    Covers the failure branch promised by v3 doc §5.2: if lazy-install cannot
    satisfy the feishu dependencies, the caller gets a clear error message
    instead of an unhandled exception.
    """
    mock_mod, mock_cls, mock_inst = _build_mock_feishu_mod(
        feishu_available=False,
        feishu_domain=None,
        lark_domain=None,
    )

    import gateway  # noqa: F401
    import gateway.platforms  # noqa: F401

    with patch.dict(sys.modules, {"gateway.platforms.feishu": mock_mod}), \
         patch("tools.lazy_deps.ensure_and_bind", return_value=False):
        from tools.send_message_tool import _send_feishu
        result = asyncio.run(_send_feishu(
            pconfig=MagicMock(),
            chat_id="oc_test789",
            message="This should fail",
        ))

    assert result.get("error") is not None
    assert "Feishu requirements not met" in result["error"]
