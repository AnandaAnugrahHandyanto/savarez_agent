"""Basic tests for OpenMemory memory provider plugin."""

import json
import os
import pytest
from unittest.mock import Mock, patch

# These tests verify the OpenMemory provider loads and has the right interface
# Integration tests would require a running OpenMemory instance


def test_plugin_can_be_imported():
    """OpenMemory plugin imports without errors."""
    from plugins.memory.openmemory import OpenMemoryProvider
    provider = OpenMemoryProvider()
    assert provider is not None


def test_provider_name():
    """Provider name is 'openmemory'."""
    from plugins.memory.openmemory import OpenMemoryProvider
    provider = OpenMemoryProvider()
    assert provider.name == "openmemory"


def test_provider_has_required_methods():
    """Provider implements MemoryProvider interface."""
    from plugins.memory.openmemory import OpenMemoryProvider
    provider = OpenMemoryProvider()
    
    assert hasattr(provider, "is_available")
    assert hasattr(provider, "initialize")
    assert hasattr(provider, "get_tool_schemas")
    assert hasattr(provider, "handle_tool_call")
    assert hasattr(provider, "prefetch")
    assert hasattr(provider, "queue_prefetch")


def test_get_tool_schemas():
    """Returns 3 tool schemas with correct names."""
    from plugins.memory.openmemory import OpenMemoryProvider
    provider = OpenMemoryProvider()
    
    schemas = provider.get_tool_schemas()
    assert len(schemas) == 3
    
    names = {s["name"] for s in schemas}
    assert names == {"openmemory_profile", "openmemory_search", "openmemory_conclude"}
    
    # Verify structure
    for schema in schemas:
        assert "name" in schema
        assert "description" in schema
        assert "parameters" in schema


def test_is_available_without_config():
    """Provider not available when OPENMEMORY_API_URL not set."""
    from plugins.memory.openmemory import OpenMemoryProvider, _load_config
    
    with patch.dict(os.environ, {}, clear=True):
        with patch("plugins.memory.openmemory._load_config", return_value={"api_url": ""}):
            provider = OpenMemoryProvider()
            assert provider.is_available() is False


def test_is_available_with_config():
    """Provider available when OPENMEMORY_API_URL is set."""
    from plugins.memory.openmemory import OpenMemoryProvider
    
    with patch("plugins.memory.openmemory._load_config", return_value={
        "api_url": "http://localhost:8765",
        "app_id": "hermes",
        "user_id": "test-user",
        "api_key": "",
    }):
        provider = OpenMemoryProvider()
        assert provider.is_available() is True


def test_get_missing_requirements():
    """Reports missing API URL requirement."""
    from plugins.memory.openmemory import OpenMemoryProvider
    
    with patch("plugins.memory.openmemory._load_config", return_value={"api_url": ""}):
        provider = OpenMemoryProvider()
        missing = provider.get_missing_requirements()
        
        assert len(missing) == 1
        assert missing[0]["var"] == "OPENMEMORY_API_URL"


def test_initialize():
    """Initialize loads config without errors."""
    from plugins.memory.openmemory import OpenMemoryProvider
    
    with patch("plugins.memory.openmemory._load_config", return_value={
        "api_url": "http://localhost:8765",
        "app_id": "hermes",
        "user_id": "test-user",
        "api_key": "",
    }):
        provider = OpenMemoryProvider()
        provider.initialize("test-session-123")
        
        assert provider._api_url == "http://localhost:8765"
        assert provider._app_id == "hermes"
        assert provider._user_id == "test-user"


def test_prefetch_returns_empty_when_no_cache():
    """Prefetch returns empty string when no cached result."""
    from plugins.memory.openmemory import OpenMemoryProvider
    
    provider = OpenMemoryProvider()
    result = provider.prefetch("test query")
    assert result == ""


def test_prefetch_returns_cached_result():
    """Prefetch returns and clears cached result."""
    from plugins.memory.openmemory import OpenMemoryProvider
    
    provider = OpenMemoryProvider()
    provider._prefetch_result = "cached memories"
    
    result = provider.prefetch("test query")
    assert result == "cached memories"
    assert provider._prefetch_result == ""  # Cache cleared


def test_circuit_breaker():
    """Circuit breaker opens after threshold failures."""
    from plugins.memory.openmemory import OpenMemoryProvider
    
    provider = OpenMemoryProvider()
    
    # Record failures
    for _ in range(5):
        provider._record_failure()
    
    assert provider._check_circuit_breaker() is True
    
    # Success resets it
    provider._record_success()
    assert provider._check_circuit_breaker() is False


def test_handle_tool_call_unknown_tool():
    """Unknown tool returns error."""
    from plugins.memory.openmemory import OpenMemoryProvider
    
    with patch("plugins.memory.openmemory._load_config", return_value={
        "api_url": "http://localhost:8765",
        "app_id": "hermes",
        "user_id": "test-user",
        "api_key": "",
    }):
        provider = OpenMemoryProvider()
        provider.initialize("test-session")
        
        result = provider.handle_tool_call("unknown_tool", {})
        assert "Unknown tool" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
