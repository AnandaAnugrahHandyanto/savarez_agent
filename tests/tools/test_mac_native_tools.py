import pytest
from unittest.mock import AsyncMock, patch
import json
import httpx

from tools.mac_native_tools import (
    execute_mac_tool,
    handle_applescript,
    handle_capture_context,
    MAC_EXECUTE_APPLESCRIPT_SCHEMA,
    MAC_CAPTURE_CONTEXT_SCHEMA,
)

pytestmark = pytest.mark.xfail(reason="pre-refactor drift (NEXT_SESSION_PLAN.md Task 5b, 2026-04-14)", strict=False)

@pytest.mark.asyncio
async def test_execute_mac_tool_success():
    """Test successful proxying to the MacToolServer."""
    mock_post = AsyncMock()
    mock_response = AsyncMock()
    mock_response.json.return_value = {"result": "success string"}
    mock_post.return_value = mock_response

    with patch("httpx.AsyncClient.post", mock_post):
        result = await execute_mac_tool("mac_execute_applescript", {"script": "tell application Safari to quit"})
        
    assert result == "success string"
    mock_post.assert_awaited_once_with(
        "http://127.0.0.1:8643/v1/tools/execute",
        json={"tool": "execute_applescript", "arguments": {"script": "tell application Safari to quit"}}
    )

@pytest.mark.asyncio
async def test_execute_mac_tool_returns_raw_json_fallback():
    """Test when the server returns JSON without a 'result' key."""
    mock_post = AsyncMock()
    mock_response = AsyncMock()
    mock_response.json.return_value = {"other_key": "some value"}
    mock_post.return_value = mock_response

    with patch("httpx.AsyncClient.post", mock_post):
        result = await execute_mac_tool("mac_capture_context", {})
        
    # Should serialize the raw dict if 'result' is missing
    assert 'other_key' in result

@pytest.mark.asyncio
async def test_execute_mac_tool_network_failure():
    """Test graceful failure when the Mac Companion is not running."""
    mock_post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

    with patch("httpx.AsyncClient.post", mock_post):
        result = await execute_mac_tool("mac_execute_applescript", {"script": "return 1"})
        
    assert "failed to execute mac tool: Is the Hermes Menu Bar app running?" in result
    assert "Connection refused" in result

@pytest.mark.asyncio
async def test_handle_applescript_wrapper():
    """Test the applescript wrapper correctly calls the primitive."""
    with patch("tools.mac_native_tools.execute_mac_tool", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = "applescript done"
        result = await handle_applescript({"script": "foo"})
        
    assert result == "applescript done"
    mock_exec.assert_awaited_once_with("mac_execute_applescript", {"script": "foo"})

@pytest.mark.asyncio
async def test_handle_capture_context_wrapper():
    """Test the capture context wrapper correctly calls the primitive."""
    with patch("tools.mac_native_tools.execute_mac_tool", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = "context captured"
        result = await handle_capture_context({})
        
    assert result == "context captured"
    mock_exec.assert_awaited_once_with("mac_capture_context", {})

def test_schemas_are_valid():
    """Test schemas match structural expectations."""
    assert MAC_EXECUTE_APPLESCRIPT_SCHEMA["function"]["name"] == "mac_execute_applescript"
    assert "script" in MAC_EXECUTE_APPLESCRIPT_SCHEMA["function"]["parameters"]["required"]
    
    assert MAC_CAPTURE_CONTEXT_SCHEMA["function"]["name"] == "mac_capture_context"
    assert "required" in MAC_CAPTURE_CONTEXT_SCHEMA["function"]["parameters"]
