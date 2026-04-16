"""Tests for SSL certificate auto-detection in gateway/run.py."""

import ast
import os
from pathlib import Path
from unittest.mock import MagicMock, patch


def _load_ensure_ssl():
    """Load the real _ensure_ssl_certs() function from gateway/run.py source."""
    from types import ModuleType

    source = Path("gateway/run.py").read_text(encoding="utf-8")
    module_ast = ast.parse(source, filename="gateway/run.py")
    target = next(
        node for node in module_ast.body
        if isinstance(node, ast.FunctionDef) and node.name == "_ensure_ssl_certs"
    )
    code = ast.get_source_segment(source, target)
    mod = ModuleType("_ssl_helper")
    exec("import os\nimport ssl\n" + (code or ""), mod.__dict__)
    return mod._ensure_ssl_certs


class TestEnsureSslCerts:
    def test_respects_valid_existing_env_var(self, tmp_path):
        fn = _load_ensure_ssl()
        cert = tmp_path / "custom-ca.pem"
        cert.write_text("FAKE CERT")

        with patch.dict(os.environ, {"SSL_CERT_FILE": str(cert)}, clear=True):
            fn()
            assert os.environ["SSL_CERT_FILE"] == str(cert)
            assert os.environ["REQUESTS_CA_BUNDLE"] == str(cert)
            assert os.environ["CURL_CA_BUNDLE"] == str(cert)

    def test_replaces_invalid_existing_env_vars(self, tmp_path):
        fn = _load_ensure_ssl()
        cert = tmp_path / "ca.crt"
        cert.write_text("FAKE CERT")

        mock_paths = MagicMock()
        mock_paths.cafile = str(cert)
        mock_paths.openssl_cafile = None

        env = {
            "SSL_CERT_FILE": "/stale/python312/cacert.pem",
            "REQUESTS_CA_BUNDLE": "/stale/python312/cacert.pem",
            "CURL_CA_BUNDLE": "/stale/python312/cacert.pem",
        }
        with patch.dict(os.environ, env, clear=True), \
             patch("ssl.get_default_verify_paths", return_value=mock_paths):
            fn()
            assert os.environ.get("SSL_CERT_FILE") == str(cert)
            assert os.environ.get("REQUESTS_CA_BUNDLE") == str(cert)
            assert os.environ.get("CURL_CA_BUNDLE") == str(cert)

    def test_sets_from_ssl_default_paths(self, tmp_path):
        fn = _load_ensure_ssl()
        cert = tmp_path / "ca.crt"
        cert.write_text("FAKE CERT")

        mock_paths = MagicMock()
        mock_paths.cafile = str(cert)
        mock_paths.openssl_cafile = None

        env = {
            k: v
            for k, v in os.environ.items()
            if k not in {"SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"}
        }
        with patch.dict(os.environ, env, clear=True), \
             patch("ssl.get_default_verify_paths", return_value=mock_paths):
            fn()
            assert os.environ.get("SSL_CERT_FILE") == str(cert)
            assert os.environ.get("REQUESTS_CA_BUNDLE") == str(cert)
            assert os.environ.get("CURL_CA_BUNDLE") == str(cert)

    def test_no_op_when_nothing_found(self):
        fn = _load_ensure_ssl()
        mock_paths = MagicMock()
        mock_paths.cafile = None
        mock_paths.openssl_cafile = None

        env = {
            k: v
            for k, v in os.environ.items()
            if k not in {"SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"}
        }
        with patch.dict(os.environ, env, clear=True), \
             patch("ssl.get_default_verify_paths", return_value=mock_paths), \
             patch("os.path.exists", return_value=False), \
             patch.dict("sys.modules", {"certifi": None}):
            fn()
            assert "SSL_CERT_FILE" not in os.environ
            assert "REQUESTS_CA_BUNDLE" not in os.environ
            assert "CURL_CA_BUNDLE" not in os.environ
