#!/usr/bin/env python3
"""Thin campaign manager over SessionDB campaign persistence."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from hermes_state import SessionDB


class CampaignManager:
    def __init__(self, db: SessionDB):
        self.db = db

    def start(self, goal: str, *, next_step: str = "", metadata: Optional[Dict[str, Any]] = None) -> str:
        return self.db.campaign_start(goal, next_step=next_step, metadata=metadata)

    def log(
        self,
        campaign_id: str,
        milestone: Any,
        *,
        status: Optional[str] = None,
        next_step: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        return self.db.campaign_log(
            campaign_id,
            milestone,
            status=status,
            next_step=next_step,
            metadata=metadata,
        )

    def resume(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self.db.campaign_resume(limit=limit)

    def close(self, campaign_id: str, verdict: str, *, next_step: str = "") -> bool:
        return self.db.campaign_close(campaign_id, verdict, next_step=next_step)
