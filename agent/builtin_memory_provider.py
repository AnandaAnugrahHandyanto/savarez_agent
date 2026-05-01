from __future__ import annotations

import json
from typing import Any, Dict, List

from agent.memory_provider import MemoryProvider


class BuiltinMemoryProvider(MemoryProvider):
    """Compatibility wrapper for Hermes built-in file-backed memory.

    The concrete MemoryStore is still owned by AIAgent; this provider exists so
    MemoryManager tests and plugin orchestration can treat the built-in memory
    backend like every other provider.
    """

    def __init__(self) -> None:
        self._session_id = ""
        self._init_kwargs: Dict[str, Any] = {}

    @property
    def name(self) -> str:
        return "builtin"

    def is_available(self) -> bool:
        return True

    def initialize(self, session_id: str, **kwargs) -> None:
        self._session_id = session_id
        self._init_kwargs = dict(kwargs)

    def system_prompt_block(self) -> str:
        return ""

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        return ""

    def sync_turn(self, user_content: str, assistant_content: str, *, session_id: str = "") -> None:
        return None

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return []

    def handle_tool_call(self, tool_name: str, args: Dict[str, Any], **kwargs) -> str:
        return json.dumps({"success": False, "error": f"Builtin memory provider does not handle {tool_name}"})

    def shutdown(self) -> None:
        return None
