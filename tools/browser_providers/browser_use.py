"""Browser Use cloud browser provider."""

import logging
import os
import threading
import uuid
from typing import Any

import requests
import yaml

from hermes_constants import get_hermes_home
from tools.browser_providers.base import CloudBrowserProvider
from tools.managed_tool_gateway import resolve_managed_tool_gateway
from tools.tool_backend_helpers import managed_nous_tools_enabled

logger = logging.getLogger(__name__)
_pending_create_keys: dict[str, str] = {}
_pending_create_keys_lock = threading.Lock()

_BASE_URL = "https://api.browser-use.com/api/v3"
_DEFAULT_MANAGED_TIMEOUT_MINUTES = 5
_DEFAULT_MANAGED_PROXY_COUNTRY_CODE = "us"

# Maps snake_case config keys to camelCase API parameter names.
_CONFIG_KEY_TO_API_PARAM: dict[str, str] = {
    "profile_id": "profileId",
    "proxy_country_code": "proxyCountryCode",
    "timeout": "timeout",
    "screen_width": "browserScreenWidth",
    "screen_height": "browserScreenHeight",
    "allow_resizing": "allowResizing",
    "enable_recording": "enableRecording",
}


def _get_or_create_pending_create_key(task_id: str) -> str:
    with _pending_create_keys_lock:
        existing = _pending_create_keys.get(task_id)
        if existing:
            return existing

        created = f"browser-use-session-create:{uuid.uuid4().hex}"
        _pending_create_keys[task_id] = created
        return created


def _clear_pending_create_key(task_id: str) -> None:
    with _pending_create_keys_lock:
        _pending_create_keys.pop(task_id, None)


def _parse_env_value(value: str, api_key: str) -> Any:
    """Parse an environment variable string into the appropriate type."""
    if api_key in ("allowResizing", "enableRecording"):
        return value.lower() in ("1", "true", "yes")
    if api_key in ("timeout", "browserScreenWidth", "browserScreenHeight"):
        return int(value)
    return value


def _should_preserve_pending_create_key(response: requests.Response) -> bool:
    if response.status_code >= 500:
        return True

    if response.status_code != 409:
        return False

    try:
        payload = response.json()
    except Exception:
        return False

    if not isinstance(payload, dict):
        return False

    error = payload.get("error")
    if not isinstance(error, dict):
        return False

    message = str(error.get("message") or "").lower()
    return "already in progress" in message


class BrowserUseProvider(CloudBrowserProvider):
    """Browser Use (https://browser-use.com) cloud browser backend."""

    def provider_name(self) -> str:
        return "Browser Use"

    def is_configured(self) -> bool:
        return self._get_config_or_none() is not None

    def _get_config_or_none(self) -> dict[str, Any] | None:
        api_key = os.environ.get("BROWSER_USE_API_KEY")
        if api_key:
            return {
                "api_key": api_key,
                "base_url": _BASE_URL,
                "managed_mode": False,
            }

        managed = resolve_managed_tool_gateway("browser-use")
        if managed is None:
            return None

        return {
            "api_key": managed.nous_user_token,
            "base_url": managed.gateway_origin.rstrip("/"),
            "managed_mode": True,
        }

    def _get_config(self) -> dict[str, Any]:
        config = self._get_config_or_none()
        if config is None:
            message = (
                "Browser Use requires a direct BROWSER_USE_API_KEY credential."
            )
            if managed_nous_tools_enabled():
                message = (
                    "Browser Use requires either a direct BROWSER_USE_API_KEY "
                    "credential or a managed Browser Use gateway configuration."
                )
            raise ValueError(message)
        return config

    def _resolve_session_settings(self) -> dict[str, Any]:
        """Resolve Browser Use session settings from config YAML and env vars.

        Reads ``browser.browser_use`` from ``~/.hermes/config.yaml``, then
        applies environment variable overrides (``BROWSER_USE_<UPPER_KEY>``).
        Returns a dict with camelCase keys matching the Browser Use API.
        """
        settings: dict[str, Any] = {}

        config_path = get_hermes_home() / "config.yaml"
        if config_path.exists():
            try:
                with open(config_path) as f:
                    cfg = yaml.safe_load(f) or {}
                bu_cfg = cfg.get("browser", {}).get("browser_use", {})
                if isinstance(bu_cfg, dict):
                    for config_key, api_key in _CONFIG_KEY_TO_API_PARAM.items():
                        if config_key in bu_cfg:
                            settings[api_key] = bu_cfg[config_key]
            except Exception:
                logger.debug("Could not read browser_use settings from config.yaml", exc_info=True)

        for config_key, api_key in _CONFIG_KEY_TO_API_PARAM.items():
            env_var = f"BROWSER_USE_{config_key.upper()}"
            value = os.environ.get(env_var)
            if value is not None:
                try:
                    settings[api_key] = _parse_env_value(value, api_key)
                except (ValueError, TypeError):
                    logger.warning("Invalid value for %s: %r, skipping", env_var, value)

        # Remove None values (explicit null in YAML means "don't send")
        return {k: v for k, v in settings.items() if v is not None}

    def _headers(self, config: dict[str, Any]) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "X-Browser-Use-API-Key": config["api_key"],
        }
        return headers

    def create_session(self, task_id: str) -> dict[str, object]:
        config = self._get_config()
        managed_mode = bool(config.get("managed_mode"))

        headers = self._headers(config)
        if managed_mode:
            headers["X-Idempotency-Key"] = _get_or_create_pending_create_key(task_id)

        # Keep gateway-backed sessions short so billing authorization does not
        # default to a long Browser-Use timeout when Hermes only needs a task-
        # scoped ephemeral browser.
        # Start with managed defaults if applicable, then overlay user settings.
        payload: dict[str, Any] = {}
        if managed_mode:
            payload["timeout"] = _DEFAULT_MANAGED_TIMEOUT_MINUTES
            payload["proxyCountryCode"] = _DEFAULT_MANAGED_PROXY_COUNTRY_CODE

        user_settings = self._resolve_session_settings()
        payload.update(user_settings)

        response = requests.post(
            f"{config['base_url']}/browsers",
            headers=headers,
            json=payload,
            timeout=30,
        )

        if not response.ok:
            if managed_mode and not _should_preserve_pending_create_key(response):
                _clear_pending_create_key(task_id)
            raise RuntimeError(
                f"Failed to create Browser Use session: "
                f"{response.status_code} {response.text}"
            )

        session_data = response.json()
        if managed_mode:
            _clear_pending_create_key(task_id)
        session_name = f"hermes_{task_id}_{uuid.uuid4().hex[:8]}"
        external_call_id = response.headers.get("x-external-call-id") if managed_mode else None

        logger.info("Created Browser Use session %s", session_name)

        cdp_url = session_data.get("cdpUrl") or session_data.get("connectUrl") or ""

        return {
            "session_name": session_name,
            "bb_session_id": session_data["id"],
            "cdp_url": cdp_url,
            "features": {"browser_use": True},
            "external_call_id": external_call_id,
        }

    def close_session(self, session_id: str) -> bool:
        try:
            config = self._get_config()
        except ValueError:
            logger.warning("Cannot close Browser Use session %s — missing credentials", session_id)
            return False

        try:
            response = requests.patch(
                f"{config['base_url']}/browsers/{session_id}",
                headers=self._headers(config),
                json={"action": "stop"},
                timeout=10,
            )
            if response.status_code in (200, 201, 204):
                logger.debug("Successfully closed Browser Use session %s", session_id)
                return True
            else:
                logger.warning(
                    "Failed to close Browser Use session %s: HTTP %s - %s",
                    session_id,
                    response.status_code,
                    response.text[:200],
                )
                return False
        except Exception as e:
            logger.error("Exception closing Browser Use session %s: %s", session_id, e)
            return False

    def emergency_cleanup(self, session_id: str) -> None:
        config = self._get_config_or_none()
        if config is None:
            logger.warning("Cannot emergency-cleanup Browser Use session %s — missing credentials", session_id)
            return
        try:
            requests.patch(
                f"{config['base_url']}/browsers/{session_id}",
                headers=self._headers(config),
                json={"action": "stop"},
                timeout=5,
            )
        except Exception as e:
            logger.debug("Emergency cleanup failed for Browser Use session %s: %s", session_id, e)
