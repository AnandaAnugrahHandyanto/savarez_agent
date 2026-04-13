#!/usr/bin/env python3
"""
Playwright JSON deduplicator and ingestion script for Hermes Knowledge Graph.
Parses LLM exports (ChatGPT/Perplexity), chunks conversations heuristically, 
and injects novel nodes into the graph using `GraphManager`.
"""

import sys
import os
import json
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HERMES_HOME = Path(os.path.expanduser("~/.hermes"))
EXPORTS_DIR = HERMES_HOME / "knowledge" / "Hermes" / "LLM_Exports"
LEDGER_PATH = HERMES_HOME / "cron" / "llm_ingest_state.json"

# Import agent components dynamically
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent.graph_manager import GraphManager

class LLMIngestor:
    def __init__(self):
        self.ledger: Dict[str, Any] = self._load_ledger()
        
    def _load_ledger(self) -> Dict[str, Any]:
        if LEDGER_PATH.exists():
            try:
                return json.loads(LEDGER_PATH.read_text())
            except Exception as e:
                logger.warning(f"Ledger parse failed, starting fresh: {e}")
        return {"processed_ids": []}

    def _save_ledger(self):
        LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
        LEDGER_PATH.write_text(json.dumps(self.ledger, indent=2))

    def heuristic_extract_conversations(self, json_data: Any, provider: str) -> List[Dict[str, str]]:
        """
        Attempts to extract distinct conversation IDs and concatenated thread text 
        regardless of strict schema (resilient to API changes).
        """
        conversations = []
        
        # Heuristic for ChatGPT `items` array or similar
        if isinstance(json_data, dict):
            items = json_data.get("items", [])
            limit = json_data.get("limit")
        elif isinstance(json_data, list):
            items = json_data
        else:
            return []

        for item in items:
            if not isinstance(item, dict): continue
            
            chunk_id = item.get("id") or item.get("uuid") or item.get("conversation_id")
            if not chunk_id: continue

            # recursive extraction of strings from common keys
            text_blocks = []
            def _extract_strs(obj):
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        if k in ("text", "content", "parts", "mapping", "message"):
                            _extract_strs(v)
                        elif isinstance(v, (dict, list)):
                            _extract_strs(v)
                elif isinstance(obj, list):
                    for sub in obj: _extract_strs(sub)
                elif isinstance(obj, str):
                    text_blocks.append(obj)
                    
            _extract_strs(item)
            
            # Combine
            filtered = [t for t in text_blocks if len(t.strip()) > 30] # Skip short gibberish
            if not filtered: continue
            
            # Sub-chunk if excessively large
            full_text = "\n\n".join(filtered)
            conversations.append({"id": f"{provider}_{chunk_id}", "text": full_text[:15000]}) # Hard limit 15k chars (~4k tokens) per episode to save context
            
        return conversations

    async def run(self):
        if not EXPORTS_DIR.exists():
            logger.info("No LLM exports directory found. Skipping.")
            return

        import yaml
        llm_config = {}
        config_path = HERMES_HOME / "cli-config.yaml"
        if config_path.exists():
            with open(config_path) as f:
                llm_config = yaml.safe_load(f) or {}

        db_path = HERMES_HOME / "context-graph" / "kuzu_db"
        manager = GraphManager(db_path=db_path, llm_config=llm_config)

        for file_path in EXPORTS_DIR.glob("*.json"):
            provider = file_path.stem.split("_")[0] # chatgpt or perplexity
            logger.info(f"Processing export: {file_path.name} (Provider: {provider})")
            
            try:
                data = json.loads(file_path.read_text())
                conversations = self.heuristic_extract_conversations(data, provider)
            except Exception as e:
                logger.error(f"Failed to parse {file_path.name}: {e}")
                continue

            for conv in conversations:
                c_id = conv["id"]
                if c_id in self.ledger["processed_ids"]:
                    continue # Deduplicated
                
                try:
                    logger.info(f"Ingesting new conversation: {c_id}")
                    await manager.add_episode(
                        content=conv["text"],
                        source_type=provider,
                        name=f"{provider.capitalize()} LLM Memory"
                    )
                    self.ledger["processed_ids"].append(c_id)
                except Exception as e:
                    logger.error(f"Failed to ingest conversation {c_id}: {e}")
                
                # Frequent ledger checkpoint saving token burn if interrupted
                self._save_ledger()

        logger.info("Ingestion pass complete.")

if __name__ == "__main__":
    asyncio.run(LLMIngestor().run())
