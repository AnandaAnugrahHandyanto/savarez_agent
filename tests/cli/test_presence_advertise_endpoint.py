"""Tests for the dashboard's presence-endpoint advertisement (channels Phase 2).

When the dashboard binds beyond loopback, session-presence records should
carry a dialable ws endpoint so other devices that discover a live session
know where to attach. Loopback binds advertise nothing.
"""

from unittest.mock import patch

from hermes_cli.web_server import _presence_advertise_endpoint


class TestPresenceAdvertiseEndpoint:
    def test_loopback_binds_advertise_nothing(self):
        assert _presence_advertise_endpoint("127.0.0.1", 8664) == ""
        assert _presence_advertise_endpoint("localhost", 8664) == ""
        assert _presence_advertise_endpoint("::1", 8664) == ""
        assert _presence_advertise_endpoint("", 8664) == ""

    def test_explicit_lan_bind_advertises_itself(self):
        assert (
            _presence_advertise_endpoint("192.168.1.20", 8664)
            == "ws://192.168.1.20:8664/api/ws"
        )

    def test_explicit_tailscale_style_host_advertises_itself(self):
        assert (
            _presence_advertise_endpoint("ko-mac.tailnet.ts.net", 8664)
            == "ws://ko-mac.tailnet.ts.net:8664/api/ws"
        )

    def test_wildcard_bind_advertises_primary_lan_ip(self):
        with patch("hermes_cli.web_server._primary_lan_ip", return_value="10.10.20.5"):
            assert (
                _presence_advertise_endpoint("0.0.0.0", 8664)
                == "ws://10.10.20.5:8664/api/ws"
            )

    def test_wildcard_bind_without_detectable_ip_advertises_nothing(self):
        with patch("hermes_cli.web_server._primary_lan_ip", return_value=""):
            assert _presence_advertise_endpoint("0.0.0.0", 8664) == ""
            assert _presence_advertise_endpoint("::", 8664) == ""
