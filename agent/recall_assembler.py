from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from hermes_constants import get_hermes_home

from agent.recall_receipt import RecallReceipt
from agent.supersession import suppress_derived_records
from agent.llm_wiki import render_wiki_prefetch
from tools.session_search_tool import session_search_compact


@dataclass
class RecallBundle:
    context_block: str
    receipt: RecallReceipt


class RecallAssembler:
    def __init__(self, *, memory_store: Any = None, session_db: Any = None, hermes_home: Path | None = None):
        self.memory_store = memory_store
        self.session_db = session_db
        self.hermes_home = Path(hermes_home or get_hermes_home())

    def _persist_receipt(self, receipt: RecallReceipt) -> None:
        state_dir = self.hermes_home / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        payload = receipt.to_dict()
        (state_dir / "last_recall_receipt.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _classify_routes(self, query: str, clerk_context: str) -> tuple[str, List[str]]:
        q = (query or "").lower()
        routes = ["sqlite_memory", "wiki_compiled"]
        transcript_markers = (
            "last time",
            "previous",
            "earlier session",
            "what did we",
            "remember when",
            "last week",
            "session",
        )
        reset_markers = ("reset", "clerk", "before reset", "handoff", "recovery")
        if any(marker in q for marker in transcript_markers):
            routes.append("session_search")
        if clerk_context or any(marker in q for marker in reset_markers):
            routes.append("clerk_reset")
        query_type = "hybrid" if len(routes) > 1 else routes[0]
        return query_type, routes

    def assemble(
        self,
        *,
        query: str,
        current_session_id: str | None = None,
        clerk_context: str = "",
        memory_limit: int = 2,
        user_limit: int = 2,
        session_limit: int = 2,
        wiki_limit: int = 3,
    ) -> RecallBundle:
        query_type, routes = self._classify_routes(query, clerk_context)
        lanes_considered = ["sqlite_memory", "wiki_compiled", "session_search", "clerk_reset"]
        records: List[Dict[str, Any]] = []
        degraded_flags: List[str] = []
        budget: Dict[str, Any] = {}

        if self.memory_store is not None:
            memory_hits = self.memory_store.search_for_recall("memory", query, limit=memory_limit)
            user_hits = self.memory_store.search_for_recall("user", query, limit=user_limit)
            budget["sqlite_hits"] = len(memory_hits) + len(user_hits)
            for item in memory_hits + user_hits:
                records.append({"lane": "sqlite_memory", "content": item["content"]})
        else:
            budget["sqlite_hits"] = 0

        wiki_block = render_wiki_prefetch(query, limit=wiki_limit)
        if wiki_block:
            records.append({"lane": "wiki_compiled", "content": wiki_block})
        else:
            degraded_flags.append("wiki_compiled_empty")

        session_payload = {"count": 0, "results": [], "block": ""}
        if "session_search" in routes:
            session_payload = session_search_compact(
                query,
                db=self.session_db,
                current_session_id=current_session_id,
                limit=session_limit,
            )
            budget["session_hits"] = session_payload.get("count", 0)
            if session_payload.get("block"):
                records.append({"lane": "session_search", "content": session_payload["block"]})
            else:
                degraded_flags.append("session_search_empty")
        else:
            budget["session_hits"] = 0

        if "clerk_reset" in routes:
            if clerk_context:
                records.append({"lane": "clerk_reset", "content": clerk_context.strip()})
            else:
                degraded_flags.append("clerk_reset_unavailable")

        winners, suppressed, suppression_reasons = suppress_derived_records(records)
        lanes_used: List[str] = []
        for record in winners:
            lane = record["lane"]
            if lane not in lanes_used:
                lanes_used.append(lane)

        context_sections: List[str] = []
        sqlite_hits = [record["content"] for record in winners if record["lane"] == "sqlite_memory"]
        if sqlite_hits:
            context_sections.append("Relevant memory recall:\n" + "\n".join(f"- {hit}" for hit in sqlite_hits))
        for lane_name in ("wiki_compiled", "session_search", "clerk_reset"):
            lane_records = [record["content"] for record in winners if record["lane"] == lane_name]
            if lane_records:
                context_sections.extend(lane_records)
        context_block = "\n\n".join(section for section in context_sections if section.strip())

        receipt = RecallReceipt(
            receipt_id=f"rr-{uuid.uuid4().hex[:12]}",
            query=query,
            query_type=query_type,
            routes=routes,
            lanes_considered=lanes_considered,
            lanes_used=lanes_used,
            winning_records=winners,
            suppressed_records=suppressed,
            suppression_reasons=suppression_reasons,
            degraded_flags=degraded_flags,
            budget=budget,
            context_block=context_block,
        )
        self._persist_receipt(receipt)
        return RecallBundle(context_block=context_block, receipt=receipt)
