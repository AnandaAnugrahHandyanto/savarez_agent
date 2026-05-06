import pytest
from unittest.mock import MagicMock
from gateway.run import GatewayRunner
from gateway.config import GatewayConfig, PlatformConfig, Platform
from gateway.session import SessionSource

def test_is_user_authorized_reads_plugin_config(tmp_path):
    config = GatewayConfig()
    config.platforms[Platform("teams")] = PlatformConfig(
        enabled=True,
        extra={"allowed_users": ["config_user", "test@example.com"]}
    )
    
    runner = GatewayRunner(config)
    runner.pairing_store = MagicMock()
    runner.pairing_store.is_approved.return_value = False
    
    # 1. Config user matches
    source1 = SessionSource(platform=Platform("teams"), chat_id="1", user_id="config_user")
    assert runner._is_user_authorized(source1) is True
    
    # 2. Config user matches via email in user_id
    source2 = SessionSource(platform=Platform("teams"), chat_id="2", user_id="test@example.com")
    assert runner._is_user_authorized(source2) is True
    
    # 3. Config user matches via user_id_alt (email alias resolution)
    source3 = SessionSource(platform=Platform("teams"), chat_id="3", user_id="uuid", user_id_alt="test@example.com")
    assert runner._is_user_authorized(source3) is True
    
    # 4. Unknown user rejected
    source4 = SessionSource(platform=Platform("teams"), chat_id="4", user_id="other_user")
    assert runner._is_user_authorized(source4) is False

def test_is_user_authorized_env_var_precedence(tmp_path, monkeypatch):
    monkeypatch.setenv("TEAMS_ALLOWED_USERS", "env_user")
    
    config = GatewayConfig()
    config.platforms[Platform("teams")] = PlatformConfig(
        enabled=True,
        extra={"allowed_users": ["config_user"]}
    )
    
    runner = GatewayRunner(config)
    runner.pairing_store = MagicMock()
    runner.pairing_store.is_approved.return_value = False
    
    source1 = SessionSource(platform=Platform("teams"), chat_id="1", user_id="config_user")
    source2 = SessionSource(platform=Platform("teams"), chat_id="2", user_id="env_user")
    
    # config_user is ignored because env_user took precedence
    assert runner._is_user_authorized(source1) is False
    assert runner._is_user_authorized(source2) is True
