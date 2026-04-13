import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class PassiveIngester:
    """
    Ingests background screenpipe/activity data to form semantic clips.
    This simulates AskJo's 'I notice things' feature.
    """
    def __init__(self, mcp_client, llm_provider, save_dir: str):
        self.mcp_client = mcp_client
        self.llm_provider = llm_provider
        self.save_dir = save_dir
        
    async def ingest_recent_activity(self, hours: int = 2) -> Optional[Dict[str, Any]]:
        """
        Poll Screenpipe MCP for recent OCR and accessibility events,
        pass them through an LLM to group into semantic 'Clips',
        and save to local disk.
        """
        if not self.mcp_client:
            logger.warning("No MCP client configured for passive ingestion.")
            return None
            
        try:
            logger.info(f"Querying screenpipe for the past {hours} hours of activity...")
            events = await self._fetch_screenpipe_events(hours=hours)
            
            if not events:
                logger.info("No screenpipe events found.")
                return None
                
            clip = await self._summarize_into_clip(events)
            if clip:
                self._save_clip(clip)
            return clip
            
        except Exception as e:
            logger.error(f"Error during passive ingestion: {e}")
            return None

    async def _fetch_screenpipe_events(self, hours: int) -> List[Dict[str, Any]]:
        """Wraps the actual MCP tool call"""
        # Placeholder for actual MCP invocation via self.mcp_client
        logger.debug(f"Calling MCP screenpipe server asking for {hours} hours. (Stub)")
        return [{"type": "ocr", "app": "Safari", "text": "Yosemite camping recreation.gov"}]

    async def _summarize_into_clip(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Summarizes low-level OCR/a11y events into a high-level intent clip using the LLM."""
        # For AskJo parity, create a named narrative clip like "Yosemite Weekend Trip"
        clip = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "title": "Implicit Context Clip",
            "summary": "User is researching Yosemite camping spots.",
            "entities": ["Yosemite", "recreation.gov", "camping"],
            "raw_event_count": len(events)
        }
        return clip
        
    def _save_clip(self, clip: Dict[str, Any]):
        os.makedirs(self.save_dir, exist_ok=True)
        filename = os.path.join(self.save_dir, f"clip_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.json")
        with open(filename, "w") as f:
            json.dump(clip, f, indent=2)
        logger.info(f"Saved passive clip: {filename}")
