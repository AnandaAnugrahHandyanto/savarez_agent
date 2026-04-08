#!/usr/bin/env python3
"""
Obsidian Ingestion Engine — Bidirectional sync between Obsidian and Hermes DB.

Scans the Obsidian vault for Markdown files, extracts metadata and content,
and updates the corresponding entries in the structured knowledge database.
Identifies new user-created notes for ingestion into the context graph.
"""

import json
import logging
import os
import re
import sys
import yaml
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add parent directory to sys.path to allow imports from hermes-agent root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hermes_state import SessionDB
from hermes_cli.config import load_config
from agent.wiki_paths import resolve_obsidian_vault_path

logger = logging.getLogger(__name__)

class ObsidianIngest:
    def __init__(self, db: SessionDB, vault_path: str, agent_prefix: str = "Hermes"):
        self.db = db
        self.vault_path = Path(os.path.expanduser(vault_path))
        self.agent_prefix = agent_prefix
        
    def _parse_frontmatter(self, content: str) -> Tuple[Dict[str, Any], str]:
        """Extract YAML frontmatter and the remaining body."""
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
        if match:
            fm_text = match.group(1)
            body = content[match.end():]
            try:
                fm = yaml.safe_load(fm_text)
                return fm or {}, body
            except Exception as e:
                logger.error("Failed to parse YAML frontmatter: %s", e)
                return {}, body
        return {}, content

    def ingest_all(self):
        """Scan and ingest all relevant files in the vault."""
        if not self.vault_path.exists():
            logger.warning("Vault path %s does not exist", self.vault_path)
            return
            
        print(f"🔍 Scanning Obsidian vault at {self.vault_path}...")
        
        counts = {"person": 0, "project": 0, "decision": 0, "note": 0}
        
        # 1. Process structured knowledge directories
        for folder, entity_type in [
            ("People", "person"),
            ("Projects", "project"),
            ("Decisions", "decision"),
            ("Notes", "note")
        ]:
            dir_path = self.vault_path / self.agent_prefix / folder
            if not dir_path.exists():
                continue
                
            for file_path in dir_path.glob("*.md"):
                if self._ingest_file(file_path, entity_type):
                    counts[entity_type] += 1

        # 2. NotebookLM-style Auto-Briefing for large documents
        research_dir = self.vault_path / self.agent_prefix / "Research"
        briefs_generated = 0
        if research_dir.exists():
            for doc_path in research_dir.glob("*.md"):
                if not doc_path.name.endswith("_Briefing.md"):
                    brief_path = doc_path.with_name(f"{doc_path.stem}_Briefing.md")
                    # If document is large enough (> 500 bytes) and no brief exists
                    if not brief_path.exists() and doc_path.stat().st_size > 500:
                        if self._generate_briefing(doc_path, brief_path):
                            briefs_generated += 1

        print(f"✅ Ingestion complete: {counts['person']} people, {counts['project']} projects, {counts['decision']} decisions, {counts['note']} notes.")
        if briefs_generated > 0:
            print(f"✅ NotebookLM Studio: Auto-generated {briefs_generated} new briefings.")

    def _generate_briefing(self, doc_path: Path, brief_path: Path) -> bool:
        """Generate a NotebookLM-style briefing and flashcards for a document."""
        print(f"🎙️ Generating Studio Briefing for {doc_path.name}...")
        api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            logger.warning("No API key found. Skipping briefing generation.")
            return False
            
        import urllib.request
        url = "https://openrouter.ai/api/v1/chat/completions" if "OPENROUTER" in os.environ else "https://api.openai.com/v1/chat/completions"
        model = "anthropic/claude-3-5-sonnet:beta" if "OPENROUTER" in os.environ else "gpt-4o-mini"
        
        try:
            text = doc_path.read_text(encoding="utf-8")[:50000]
            system_prompt = "You are an AI study assistant. Read the provided document and create a Study Briefing. Include:\n1. 3-bullet Executive Summary\n2. Key Entities & Concepts\n3. 3 Flashcards (Q&A format)."
            data = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ]
            }
            req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            })
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode("utf-8"))
                brief_content = result["choices"][0]["message"]["content"]
                
                # Write the briefing to the vault
                brief_path.write_text(f"---\ntags: [briefing, auto-generated]\nsource: {doc_path.name}\n---\n\n# Study Briefing: {doc_path.stem}\n\n{brief_content}", encoding="utf-8")
                return True
        except Exception as e:
            logger.error(f"Failed to generate briefing for {doc_path.name}: {e}")
            return False

    def _ingest_file(self, file_path: Path, entity_type: str) -> bool:
        """Ingest a single file and update the database. Returns True if successful."""
        try:
            content = file_path.read_text(encoding="utf-8")
            fm, body = self._parse_frontmatter(content)
            
            uuid_str = fm.get("uuid")
            if not uuid_str:
                return False # Skip files without UUID (not managed by Hermes)
                
            # Relative path for DB
            rel_path = str(file_path.relative_to(self.vault_path))
            
            # Update DB based on type
            if entity_type == "person":
                self.db.save_knowledge_person(
                    name=fm.get("name") or file_path.stem,
                    role=fm.get("role"),
                    organization=fm.get("organization"),
                    details=body.strip(),
                    uuid=uuid_str,
                    file_path=rel_path
                )
            elif entity_type == "project":
                self.db.save_knowledge_project(
                    name=fm.get("name") or file_path.stem,
                    description=body.strip(),
                    status=fm.get("status", "active"),
                    uuid=uuid_str,
                    file_path=rel_path
                )
            elif entity_type == "decision":
                self.db.save_knowledge_decision(
                    title=fm.get("title") or file_path.stem,
                    rationale=body.strip(),
                    status=fm.get("status", "active"),
                    uuid=uuid_str,
                    file_path=rel_path
                )
            elif entity_type == "note":
                self.db.save_knowledge_note(
                    content=body.strip(),
                    tags=fm.get("tags", []),
                    uuid=uuid_str,
                    file_path=rel_path
                )
            return True
        except Exception as e:
            logger.error("Failed to ingest %s: %s", file_path, e)
            return False

def main():
    try:
        config = load_config()
    except Exception:
        config = {}
        
    kn_config = config.get("knowledge", {})
    vault = resolve_obsidian_vault_path(config)
    vault_path = str(vault) if vault else None
    
    if not vault_path:
        print("⚠️ No Obsidian vault path configured. Skipping ingestion.")
        return
        
    db = SessionDB()
    ingestor = ObsidianIngest(
        db=db,
        vault_path=vault_path,
        agent_prefix=kn_config.get("agent_prefix", "Hermes")
    )
    ingestor.ingest_all()

if __name__ == "__main__":
    main()
