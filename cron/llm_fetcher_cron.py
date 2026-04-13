#!/usr/bin/env python3
"""
Master Background Export Job.
Executes the playwright history dumps headlessly, then triggers Graphiti deduplication.
Intended to be scheduled gracefully at ~2 AM without interrupting the user.
"""

import os
import sys
import subprocess
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

HERMES_AGENT_PATH = Path(os.path.expanduser("~/.hermes/agents/hermes-agent"))
if not HERMES_AGENT_PATH.exists():
    # Fallback to local dev path if .hermes symlink architecture isn't fully scaffolded
    HERMES_AGENT_PATH = Path(os.path.expanduser("~/Desktop/MyCode/hermes/hermes-agent"))

PYTHON_BIN = HERMES_AGENT_PATH / ".venv" / "bin" / "python3"
PLAYWRIGHT_FETCHER = HERMES_AGENT_PATH / "agent" / "llm_fetcher_playwright.py"
INGESTOR_FETCHER = HERMES_AGENT_PATH / "cron" / "playwright_ingest.py"

def run_command(name: str, cmd: list) -> bool:
    logger.info(f"Starting Stage: {name}")
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        logger.info(f"{name} Completed. Output:\n{result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"{name} Failed with exit code {e.returncode}. Output:\n{e.output}\nStderr:\n{e.stderr}")
        return False
    except FileNotFoundError:
        logger.error(f"Cannot find script: {cmd[0]}")
        return False

def main():
    logger.info("Initializing Master LLM Sync...")
    
    # 1. Fetch ChatGPT History
    run_command("ChatGPT Export", [
        str(PYTHON_BIN), 
        str(PLAYWRIGHT_FETCHER), 
        "--fetch", 
        "chatgpt"
    ])
    
    # 2. Fetch Perplexity History
    run_command("Perplexity Export", [
        str(PYTHON_BIN), 
        str(PLAYWRIGHT_FETCHER), 
        "--fetch", 
        "perplexity"
    ])
    
    # 3. Graphiti Deduplication & Ingestion
    run_command("Graphiti Ingestion and Deduplication", [
        str(PYTHON_BIN), 
        str(INGESTOR_FETCHER)
    ])
    
    logger.info("Master Sync completed successfully.")

if __name__ == "__main__":
    main()
