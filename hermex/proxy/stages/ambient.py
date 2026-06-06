from __future__ import annotations

from typing import Any

from hermex.core.embedding import embed_text
from hermex.core.store.base import CoreStore, Session


class AmbientContextInjector:
    _HEADER = "\n\n[HERMEX_AMBIENT - cross-session intelligence, advisory only]\n"
    _FOOTER = "\n[END HERMEX_AMBIENT]\n"

    def __init__(
        self,
        store: CoreStore,
        token_budget: int = 512,
        min_sim: float = 0.2,
        min_confidence: float = 0.4,
    ) -> None:
        self._store = store
        self._token_budget = token_budget
        self._min_sim = min_sim
        self._min_confidence = min_confidence

    async def process(self, body: dict[str, Any], session: Session) -> dict[str, Any]:
        last_user = self._last_user_text(body)
        if not last_user:
            return body

        hits = await self._store.telemetry.search_similar(
            embed_text(last_user),
            top_k=8,
            exclude_session=session.session_id,
        )
        lines: list[str] = []
        token_count = 0
        for hit in hits:
            confidence = hit.score * hit.source_accuracy
            if hit.score < self._min_sim or hit.source_accuracy < self._min_confidence:
                continue
            line = f"- [{hit.session_id[:8]}] sim={confidence:.2f}: {hit.summary}"
            cost = max(1, len(line) // 4)
            if token_count + cost > self._token_budget:
                break
            lines.append(line)
            token_count += cost

        if not lines:
            return body

        return {
            **body,
            "system": str(body.get("system") or "") + self._HEADER + "\n".join(lines) + self._FOOTER,
        }

    @staticmethod
    def _last_user_text(body: dict[str, Any]) -> str:
        for message in reversed(body.get("messages") or []):
            if message.get("role") != "user":
                continue
            content = message.get("content", "")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                return " ".join(
                    str(block.get("text", ""))
                    for block in content
                    if isinstance(block, dict) and block.get("type") == "text"
                )
        return ""
