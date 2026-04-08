import json
import httpx
from tools.registry import registry

MAC_EXECUTE_APPLESCRIPT_SCHEMA = {
    "type": "function",
    "function": {
        "name": "mac_execute_applescript",
        "description": "Execute AppleScript on the local macOS machine (e.g. control Music app, Safari, System Events). Requires the Mac Companion App to be running.",
        "parameters": {
            "type": "object",
            "properties": {
                "script": {"type": "string", "description": "The raw AppleScript to execute."}
            },
            "required": ["script"]
        }
    }
}

MAC_CAPTURE_CONTEXT_SCHEMA = {
    "type": "function",
    "function": {
        "name": "mac_capture_context",
        "description": "Capture the user's current screen context (selected text, active app) using macOS Accessibility APIs.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
}

async def execute_mac_tool(tool_name: str, arguments: dict) -> str:
    """Proxy request to MacToolServer running in hermes-companion"""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "http://127.0.0.1:8643/v1/tools/execute",
                json={"tool": tool_name.replace("mac_", ""), "arguments": arguments}
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("result", json.dumps(data))
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        return f"failed to execute mac tool: Is the Hermes Menu Bar app running? Error: {e}"

async def handle_applescript(arguments: dict):
    return await execute_mac_tool("mac_execute_applescript", arguments)

async def handle_capture_context(arguments: dict):
    return await execute_mac_tool("mac_capture_context", arguments)

registry.register(
    name="mac_execute_applescript",
    emoji="🍎",
    toolset="mac",
    schema=MAC_EXECUTE_APPLESCRIPT_SCHEMA,
    handler=handle_applescript
)

registry.register(
    name="mac_capture_context",
    emoji="👁️",
    toolset="mac",
    schema=MAC_CAPTURE_CONTEXT_SCHEMA,
    handler=handle_capture_context
)
