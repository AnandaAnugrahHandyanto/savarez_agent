import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any


def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64d(data: str) -> bytes:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def _now_ts(now: datetime | None) -> int:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return int(current.timestamp())


class CallTokenService:
    def __init__(self, secret: str):
        self.secret = str(secret or "").encode("utf-8")

    def mint(
        self,
        platform: str,
        chat_id: str,
        user_id: str,
        call_id: str,
        *,
        now: datetime | None = None,
        ttl_seconds: int = 600,
    ) -> str:
        payload = {
            "platform": str(platform),
            "chat_id": str(chat_id),
            "user_id": str(user_id),
            "call_id": str(call_id),
            "exp": _now_ts(now) + int(ttl_seconds),
        }
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        sig = hmac.new(self.secret, body, hashlib.sha256).digest()
        return f"{_b64e(body)}.{_b64e(sig)}"

    def verify(
        self,
        token: str,
        platform: str,
        chat_id: str,
        user_id: str,
        call_id: str,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any] | None:
        try:
            body_part, sig_part = str(token or "").split(".", 1)
            body = _b64d(body_part)
            expected = hmac.new(self.secret, body, hashlib.sha256).digest()
            actual = _b64d(sig_part)
            if not hmac.compare_digest(expected, actual):
                return None
            payload = json.loads(body.decode("utf-8"))
        except Exception:
            return None
        if int(payload.get("exp", 0)) < _now_ts(now):
            return None
        expected_scope = {
            "platform": str(platform),
            "chat_id": str(chat_id),
            "user_id": str(user_id),
            "call_id": str(call_id),
        }
        for key, value in expected_scope.items():
            if str(payload.get(key)) != value:
                return None
        return payload
