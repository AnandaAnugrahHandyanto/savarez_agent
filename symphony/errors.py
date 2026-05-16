"""Typed errors for Symphony orchestration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SymphonyError(Exception):
    """Exception carrying a stable machine-readable Symphony error code."""

    code: str
    message: str

    def __str__(self) -> str:
        return self.message

    def to_payload(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}
