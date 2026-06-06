from __future__ import annotations

import hashlib
from typing import Any


class SessionFingerprintor:
    """Derives a stable session id without requiring Hermes runtime changes."""

    def derive(self, body: dict[str, Any]) -> str:
        system = str(body.get("system") or "")[:512]
        first_user = ""
        for message in body.get("messages") or []:
            if message.get("role") != "user":
                continue
            content = message.get("content", "")
            if isinstance(content, str):
                first_user = content[:200]
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        first_user = str(block.get("text", ""))[:200]
                        break
            break
        raw = f"{system}||{first_user}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
