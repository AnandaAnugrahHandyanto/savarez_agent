from __future__ import annotations

import base64

import pytest
import yaml


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("IMAGE_GATEWAY_BASE_URL", raising=False)
    monkeypatch.delenv("IMAGE_GATEWAY_API_KEY", raising=False)


def _write_router_config(tmp_path, data):
    (tmp_path / "config.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests

            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)

    def json(self):
        return self._payload


class TestRouterImageGenProvider:
    def test_generates_with_configured_openai_compatible_alias(self, monkeypatch, tmp_path):
        from plugins.image_gen.router import RouterImageGenProvider

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        monkeypatch.setenv("IMAGE_GATEWAY_BASE_URL", "https://gateway.example/v1")
        monkeypatch.setenv("IMAGE_GATEWAY_API_KEY", "test-key")
        _write_router_config(
            tmp_path,
            {
                "image_gen": {
                    "provider": "router",
                    "router": {
                        "default_model": "nano-banana-pro",
                        "defaults": {
                            "provider": "openai-compatible",
                            "base_url_env": "IMAGE_GATEWAY_BASE_URL",
                            "api_key_env": "IMAGE_GATEWAY_API_KEY",
                        },
                        "models": {
                            "nano-banana-pro": {
                                "model": "gemini-3-pro-image-preview",
                                "display": "Nano Banana Pro",
                                "default_params": {"quality": "high"},
                            }
                        },
                    },
                }
            },
        )

        calls = []

        def fake_post(url, *, headers, json, timeout):
            calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
            png = base64.b64encode(b"fake png bytes").decode("ascii")
            return _FakeResponse({"data": [{"b64_json": png, "revised_prompt": "better"}]})

        monkeypatch.setattr("requests.post", fake_post)

        result = RouterImageGenProvider().generate("画一张中文海报", aspect_ratio="portrait")

        assert result["success"] is True
        assert result["provider"] == "router"
        assert result["model"] == "nano-banana-pro"
        assert result["backend_model"] == "gemini-3-pro-image-preview"
        assert result["image"].endswith(".png")
        assert (tmp_path / "cache" / "images").exists()
        assert calls == [
            {
                "url": "https://gateway.example/v1/images/generations",
                "headers": {
                    "Authorization": "Bearer test-key",
                    "Content-Type": "application/json",
                },
                "json": {
                    "model": "gemini-3-pro-image-preview",
                    "prompt": "画一张中文海报",
                    "size": "1024x1536",
                    "n": 1,
                    "quality": "high",
                },
                "timeout": 180,
            }
        ]

    def test_tool_model_alias_overrides_router_default(self, monkeypatch, tmp_path):
        from plugins.image_gen.router import RouterImageGenProvider

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        monkeypatch.setenv("IMAGE_GATEWAY_BASE_URL", "https://gateway.example/v1")
        monkeypatch.setenv("IMAGE_GATEWAY_API_KEY", "test-key")
        _write_router_config(
            tmp_path,
            {
                "image_gen": {
                    "provider": "router",
                    "router": {
                        "default_model": "nano-banana-pro",
                        "defaults": {
                            "provider": "openai-compatible",
                            "base_url_env": "IMAGE_GATEWAY_BASE_URL",
                            "api_key_env": "IMAGE_GATEWAY_API_KEY",
                        },
                        "models": {
                            "nano-banana-pro": {"model": "gemini-3-pro-image-preview"},
                            "gpt-image-2": {"model": "gpt-image-2"},
                        },
                    },
                }
            },
        )

        payloads = []

        def fake_post(url, *, headers, json, timeout):
            payloads.append(json)
            return _FakeResponse({"data": [{"url": "https://cdn.example/image.png"}]})

        monkeypatch.setattr("requests.post", fake_post)

        result = RouterImageGenProvider().generate(
            "product shot",
            aspect_ratio="square",
            model="gpt-image-2",
        )

        assert result["success"] is True
        assert result["model"] == "gpt-image-2"
        assert result["backend_model"] == "gpt-image-2"
        assert result["image"] == "https://cdn.example/image.png"
        assert payloads[0]["model"] == "gpt-image-2"
        assert payloads[0]["size"] == "1024x1024"

    def test_unknown_model_alias_returns_clear_error(self, monkeypatch, tmp_path):
        from plugins.image_gen.router import RouterImageGenProvider

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        monkeypatch.setenv("IMAGE_GATEWAY_BASE_URL", "https://gateway.example/v1")
        monkeypatch.setenv("IMAGE_GATEWAY_API_KEY", "test-key")
        _write_router_config(
            tmp_path,
            {
                "image_gen": {
                    "provider": "router",
                    "router": {
                        "default_model": "nano-banana-pro",
                        "models": {
                            "nano-banana-pro": {"model": "gemini-3-pro-image-preview"},
                        },
                    },
                }
            },
        )

        result = RouterImageGenProvider().generate("draw", model="does-not-exist")

        assert result["success"] is False
        assert result["error_type"] == "unknown_model"
        assert "does-not-exist" in result["error"]
        assert "nano-banana-pro" in result["error"]

    def test_uses_default_env_names_when_env_keys_omitted(self, monkeypatch, tmp_path):
        from plugins.image_gen.router import RouterImageGenProvider

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        monkeypatch.setenv("IMAGE_GATEWAY_BASE_URL", "https://gateway.example/v1")
        monkeypatch.setenv("IMAGE_GATEWAY_API_KEY", "test-key")
        _write_router_config(
            tmp_path,
            {
                "image_gen": {
                    "provider": "router",
                    "router": {
                        "models": {
                            "nano-banana-pro": {"model": "gemini-3-pro-image-preview"},
                        },
                    },
                }
            },
        )

        assert RouterImageGenProvider().is_available() is True

        def fake_post(url, *, headers, json, timeout):
            return _FakeResponse({"data": [{"url": "https://cdn.example/default-env.png"}]})

        monkeypatch.setattr("requests.post", fake_post)

        result = RouterImageGenProvider().generate("draw")

        assert result["success"] is True
        assert result["image"] == "https://cdn.example/default-env.png"

    def test_rejects_non_http_gateway_image_url(self, monkeypatch, tmp_path):
        from plugins.image_gen.router import RouterImageGenProvider

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        monkeypatch.setenv("IMAGE_GATEWAY_BASE_URL", "https://gateway.example/v1")
        monkeypatch.setenv("IMAGE_GATEWAY_API_KEY", "test-key")
        _write_router_config(
            tmp_path,
            {
                "image_gen": {
                    "provider": "router",
                    "router": {
                        "models": {
                            "nano-banana-pro": {"model": "gemini-3-pro-image-preview"},
                        },
                    },
                }
            },
        )

        def fake_post(url, *, headers, json, timeout):
            return _FakeResponse({"data": [{"url": "/etc/passwd"}]})

        monkeypatch.setattr("requests.post", fake_post)

        result = RouterImageGenProvider().generate("draw")

        assert result["success"] is False
        assert result["error_type"] == "invalid_response"
        assert "http(s)" in result["error"]
