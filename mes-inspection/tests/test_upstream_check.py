"""上游端点存活检查器单元测试。"""

import pytest
from unittest.mock import patch, MagicMock
from scripts.base_checker import ExitCode


class TestUpstreamChecker:
    def _make_checker(self, config=None):
        from scripts.upstream_check import UpstreamChecker
        return UpstreamChecker(config or {
            "targets": [
                {"name": "app-1", "url": "http://10.0.0.1:8080/health"},
                {"name": "app-2", "url": "http://10.0.0.2:8080/health"},
            ],
            "timeout": 5,
            "response_time_warn": 2.0,
            "response_time_critical": 5.0,
        })

    @patch("scripts.upstream_check.urllib.request.urlopen")
    def test_all_endpoints_healthy(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.getcode.return_value = 200
        mock_resp.read.return_value = b'{"status":"UP"}'
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        checker = self._make_checker()
        report = checker.check()
        assert report.status == ExitCode.NORMAL
        assert len(report.checks) == 2
        assert report.metadata["node_count"] == 2

    @patch("scripts.upstream_check.urllib.request.urlopen")
    def test_one_endpoint_down(self, mock_urlopen):
        def side_effect(req, timeout=5):
            if "10.0.0.1" in req.full_url:
                mock_resp = MagicMock()
                mock_resp.getcode.return_value = 200
                mock_resp.read.return_value = b'ok'
                mock_resp.__enter__ = MagicMock(return_value=mock_resp)
                mock_resp.__exit__ = MagicMock(return_value=False)
                return mock_resp
            raise ConnectionRefusedError("Connection refused")

        mock_urlopen.side_effect = side_effect
        checker = self._make_checker()
        report = checker.check()
        assert report.status == ExitCode.CRITICAL
        assert report.metadata["nodes"]["app-1"] == "NORMAL"
        assert report.metadata["nodes"]["app-2"] == "CRITICAL"

    @patch("scripts.upstream_check.urllib.request.urlopen")
    def test_endpoint_returns_5xx(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.getcode.return_value = 503
        mock_resp.read.return_value = b'Service Unavailable'
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        checker = self._make_checker({"targets": [{"name": "app-1", "url": "http://10.0.0.1:8080/health"}], "timeout": 5})
        report = checker.check()
        assert report.status == ExitCode.CRITICAL
        assert report.checks[0].status == ExitCode.CRITICAL

    @patch("scripts.upstream_check.urllib.request.urlopen")
    def test_response_time_warning(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.getcode.return_value = 200
        mock_resp.read.return_value = b'ok'
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        checker = self._make_checker({
            "targets": [{"name": "app-1", "url": "http://10.0.0.1:8080/health"}],
            "timeout": 5,
            "response_time_warn": 0.0,
            "response_time_critical": 5.0,
        })
        report = checker.check()
        assert report.checks[0].status == ExitCode.WARNING

    def test_no_targets_returns_critical(self):
        checker = self._make_checker({"targets": [], "timeout": 5})
        report = checker.check()
        assert report.status == ExitCode.CRITICAL

    def test_component_name(self):
        checker = self._make_checker()
        assert checker.component_name == "upstream"
