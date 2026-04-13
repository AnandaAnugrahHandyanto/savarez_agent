#!/usr/bin/env python3
"""
Screenpipe Continuous Memory Ingestor

Queries the local Screenpipe API (port 3030), extracts recent OCR and audio transcripts,
scrubs them of obvious PII/Secrets, groups them into time-chunks, and injects them
into the Hermes Context Graph for implicit memory modeling.
"""

import sys
import os
import json
import logging
import re
import urllib.request
import asyncio
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("screenpipe_ingest")

# State tracker path
STATE_FILE = Path(os.path.expanduser("~/.hermes/cron/screenpipe_state.json"))
SCREENPIPE_URL = "http://localhost:3030/search"

# Basic PII scrubber patterns
SECRETS_PATTERNS = [
    re.compile(r'(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*["\'\b]?[A-Za-z0-9\-_]{16,}["\'\b]?'),
    re.compile(r'\b(?:\d[ -]*?){13,16}\b'), # Credit cards
    # Prevent aggressive base64 match from eating everything, but still mask extremely long alpha-num chunks
    re.compile(r'\b[A-Za-z0-9+\/]{40,}={0,2}\b') 
]

def scrub_pii(text: str) -> str:
    if not text:
        return ""
    for pattern in SECRETS_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text

def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {"last_offset": 0, "last_timestamp": None}

def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state))

def fetch_screenpipe_data(offset=0, limit=100):
    url = f"{SCREENPIPE_URL}?limit={limit}&offset={offset}&content_type=all"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        logger.error(f"Failed to fetch screenpipe data: {e}")
        return None

async def ingest_to_graph(text_chunks, last_timestamp):
    if not text_chunks:
        return
        
    try:
        from agent.graph_manager import GraphManager
        from hermes_cli.config import get_hermes_home
        import yaml
        
        llm_config = {}
        config_path = get_hermes_home() / "cli-config.yaml"
        if config_path.exists():
            with open(config_path) as f:
                llm_config = yaml.safe_load(f) or {}
                
        db_path = get_hermes_home() / "context-graph" / "kuzu_db"
        manager = GraphManager(db_path=db_path, llm_config=llm_config)
        
        # Combine chunks into a single "episode" context
        combined_text = "\n\n".join(text_chunks)
        # Limit to 10k chars to prevent Graphiti from maxing out the auxiliary model's context window
        combined_text = combined_text[:10000] 
        
        logger.info(f"Adding episode to context graph ({len(combined_text)} characters)...")
        await manager.add_episode(
            content=combined_text,
            source_type="text",
            name=f"Screenpipe Capture - {last_timestamp}",
            group_id="screenpipe"
        )
        logger.info("Episode added successfully.")
    except ImportError:
        logger.error("Hermes context graph code not found. Make sure this runs inside the pipenv.")
    except Exception as e:
        logger.error(f"Failed to ingest to graph: {e}")

async def main():
    logger.info("Starting Screenpipe Cognitive Ingestion...")
    state = load_state()
    offset = state.get("last_offset", 0)
    
    data = fetch_screenpipe_data(offset=offset, limit=100)
    if not data or not data.get("data"):
        logger.info("No new screenpipe data found or API is offline.")
        return
        
    items = data["data"]
    logger.info(f"Fetched {len(items)} items from Screenpipe.")
    
    text_chunks = []
    latest_timestamp = state.get("last_timestamp")
    
    for item in items:
        content = item.get("content", {})
        item_type = item.get("type", "unknown")
        
        # Extract meaningful text based on content type
        if item_type == "OCR":
            raw_text = content.get("text", "")
        elif item_type == "Audio":
            raw_text = content.get("transcription", "")
        else:
            continue
            
        if not raw_text or len(raw_text.strip()) < 10:
            continue
            
        scrubbed = scrub_pii(raw_text)
        text_chunks.append(f"[{item_type}] {scrubbed}")
        latest_timestamp = content.get("timestamp", latest_timestamp)
        
    if text_chunks:
        summarized_intro = "The following is raw OCR and audio data captured from the user's workflow:\n\n"
        text_chunks.insert(0, summarized_intro)
        await ingest_to_graph(text_chunks, latest_timestamp)
        
    # Update pagination bounds
    state["last_offset"] = offset + len(items)
    state["last_timestamp"] = latest_timestamp
    save_state(state)
    logger.info("Ingestion complete.")

if __name__ == "__main__":
    asyncio.run(main())
