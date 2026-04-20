"""
Gateway configuration management.

Handles loading and validating configuration for:
- Connected platforms (Telegram, Discord, WhatsApp)
- Home channels for each platform
- Session reset policies
- Delivery preferences
"""

from __future__ import annotations

import logging

from hermes_cli.config import get_hermes_home

from gateway.config_env import _apply_env_overrides
from gateway.config_models import (
    GatewayConfig,
    HomeChannel,
    Platform,
    PlatformConfig,
    SessionResetPolicy,
    StreamingConfig,
    _coerce_bool,
    _normalize_unauthorized_dm_behavior,
)
from gateway.config_validation import validate_gateway_config
from gateway.config_yaml_bridge import (
    apply_config_yaml_overrides,
    load_legacy_gateway_json,
)

logger = logging.getLogger(__name__)


# Backward-compatible private alias for existing imports/tests.
_validate_gateway_config = validate_gateway_config


def load_gateway_config() -> GatewayConfig:
    """
    Load gateway configuration from multiple sources.

    Priority (highest to lowest):
    1. Environment variables
    2. ~/.hermes/config.yaml (primary user-facing config)
    3. ~/.hermes/gateway.json (legacy — provides defaults under config.yaml)
    4. Built-in defaults
    """
    _home = get_hermes_home()
    gw_data = load_legacy_gateway_json(_home)
    apply_config_yaml_overrides(_home, gw_data)

    config = GatewayConfig.from_dict(gw_data)

    # Override with environment variables
    _apply_env_overrides(config)

    # --- Validate loaded values ---
    _validate_gateway_config(config)

    return config


__all__ = [
    "GatewayConfig",
    "HomeChannel",
    "Platform",
    "PlatformConfig",
    "SessionResetPolicy",
    "StreamingConfig",
    "_apply_env_overrides",
    "_coerce_bool",
    "_normalize_unauthorized_dm_behavior",
    "_validate_gateway_config",
    "load_gateway_config",
]
