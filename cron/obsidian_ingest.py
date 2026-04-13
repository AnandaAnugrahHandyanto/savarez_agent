#!/usr/bin/env python3
"""
Obsidian Ingestion Engine — Bidirectional sync between Obsidian and Hermes DB.

Scans the Obsidian vault for Markdown files, extracts metadata and content,
and updates the corresponding entries in the structured knowledge database.
Identifies new user-created notes for ingestion into the context graph.
"""

import asyncio
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
from hermes_constants import get_hermes_dir
from hermes_cli.config import load_config
from agent.graph_manager import GraphManager
from tools.podcast_tool import podcast_generate_tool
from agent.obsidian_sync import (
    MANAGED_FOLDERS,
    compute_content_hash,
    ensure_managed_structure,
    extract_canvas_refs,
    extract_markdown_metadata,
)
from agent.wiki_paths import resolve_obsidian_vault_path
from agent.semantic_chunker import semantic_chunk_text
from agent.file_resolver import FileResolver
from agent.llm_history_parser import LLMHistoryParser

logger = logging.getLogger(__name__)

class ObsidianIngest:
    def __init__(self, db: SessionDB, vault_path: str, agent_prefix: str = "Hermes"):
        self.db = db
        self.vault_path = Path(os.path.expanduser(vault_path))
        self.agent_prefix = agent_prefix
        self.graph_manager = GraphManager(get_hermes_dir("context-graph/kuzu_db", "kuzu_db"))
        self.file_resolver = FileResolver()
        ensure_managed_structure(str(self.vault_path), self.agent_prefix)
        
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

    def _parse_knowledge_body(self, body: str) -> Tuple[str, str]:
        """Split body into Compiled Truth and Timeline using a horizontal rule separator."""
        # Match standard markdown horizontal rules on their own lines
        parts = re.split(r'\n---\n|\n___\n|\n\*\*\*\n', body, maxsplit=1)
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()
        return body.strip(), ""

    def _filter_pii_and_secrets(self, content: str) -> str:
        """Sanitize raw content by redacting sensitive secrets before ingestion."""
        # AWS Access Keys (AKIA[0-9A-Z]{16})
        aws_pattern = r"AKIA[0-9A-Z]{16}"
        # Generic Bearer Tokens / JWTs (rough heuristic)
        bearer_pattern = r"(?i)bearer\s+[A-Za-z0-9\-._~+/]+={0,2}"
        # Private Keys
        ssh_pattern = r"-----BEGIN (RSA|OPENSSH) PRIVATE KEY-----[\s\S]+?-----END \1 PRIVATE KEY-----"
        
        sanitized = re.sub(aws_pattern, "[REDACTED_AWS_KEY]", content)
        sanitized = re.sub(bearer_pattern, "[REDACTED_BEARER_TOKEN]", sanitized)
        sanitized = re.sub(ssh_pattern, "[REDACTED_PRIVATE_KEY]", sanitized)
        return sanitized

    def ingest_all(self):
        """Scan and ingest all relevant files in the vault."""
        if not self.vault_path.exists():
            logger.warning("Vault path %s does not exist", self.vault_path)
            return
            
        print(f"🔍 Scanning Obsidian vault at {self.vault_path}...")
        
        counts = {"person": 0, "project": 0, "decision": 0, "note": 0}
        
        # 0. Convert raw PDFs to Markdown
        try:
            import opendataloader_pdf
            for search_folder in ["Research", "Assets", "Notes"]:
                pdf_dir = self.vault_path / self.agent_prefix / search_folder
                if not pdf_dir.exists():
                    continue
                for pdf_path in pdf_dir.glob("*.pdf"):
                    md_path = pdf_path.with_suffix(".md")
                    if not md_path.exists():
                        self._convert_pdf_to_md(pdf_path, md_path)
        except ImportError:
            logger.warning("opendataloader_pdf not installed. Skipping PDF ingestion.")

        # 0.5 Process LLM Exports (ChatGPT, Claude, etc.)
        llm_exports_dir = self.vault_path / self.agent_prefix / "LLM_Exports"
        llm_archive_dir = self.vault_path / self.agent_prefix / "LLM_Archive"
        if llm_exports_dir.exists():
            parser = LLMHistoryParser(output_dir=llm_archive_dir)
            for json_path in llm_exports_dir.glob("*.json"):
                print(f"🧠 Parsing LLM Export: {json_path.name}...")
                processed = parser.process_export_file(json_path)
                print(f"✅ Extracted/Updated {processed} LLM threads to {llm_archive_dir.name}")

        # 1. Process structured knowledge directories
        for folder, entity_type in [
            ("People", "person"),
            ("Projects", "project"),
            ("Decisions", "decision"),
            ("Notes", "note"),
            ("LLM_Archive", "note")
        ]:
            dir_path = self.vault_path / self.agent_prefix / folder
            if not dir_path.exists():
                continue
                
            for file_path in dir_path.glob("*.md"):
                if self._ingest_file(file_path, entity_type):
                    counts[entity_type] += 1

        # 1b. Index Canvas files and managed attachments
        canvas_dir = self.vault_path / self.agent_prefix / "Canvas"
        if canvas_dir.exists():
            for canvas_path in canvas_dir.glob("*.canvas"):
                self._index_canvas(canvas_path)

        assets_dir = self.vault_path / self.agent_prefix / "Assets"
        if assets_dir.exists():
            for asset_path in assets_dir.rglob("*"):
                if asset_path.is_file():
                    if asset_path.suffix == ".redirect":
                        continue
                    
                    remote_route = f"{self.agent_prefix}/Assets/{asset_path.name}"
                    # Attempt to mirror to cloud
                    if self.file_resolver.mirror(str(asset_path), remote_route):
                        self.file_resolver.redirect(str(asset_path), remote_route)
                        logger.info("Breadcrumbed and migrated asset to S3: %s", asset_path.name)
                        asset_path = asset_path.with_suffix(".redirect")
                        
                    rel_path = str(asset_path.relative_to(self.vault_path))
                    if hasattr(self.db, "upsert_obsidian_managed_file"):
                        self.db.upsert_obsidian_managed_file(
                            vault_relative_path=rel_path,
                            managed_relative_path=str(asset_path.relative_to(self.vault_path / self.agent_prefix)),
                            uuid=None,
                            entity_type="asset",
                            wiki_page_type=None,
                            file_ext=asset_path.suffix.lower(),
                            content_hash=None,
                            last_vault_mtime=asset_path.stat().st_mtime,
                            last_vault_size=asset_path.stat().st_size,
                            last_db_revision_id=None,
                            last_sync_direction="vault_to_db",
                            sync_status="synced",
                            conflict_state="none",
                            source_origin="managed",
                            tombstoned=False,
                            metadata={"asset": True},
                        )

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
            raw_text = doc_path.read_text(encoding="utf-8")[:50000]
            text = self._filter_pii_and_secrets(raw_text)
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
                
                # Extract Triples into the Knowledge Graph
                try:
                    async def embed_sentences(sentences: List[str]) -> List[List[float]]:
                        # Simple naive wrapper for the semantic chunker using the same API key
                        import urllib.request, json
                        data = {"input": sentences, "model": "text-embedding-3-small"}
                        req = urllib.request.Request("https://api.openai.com/v1/embeddings", 
                            data=json.dumps(data).encode("utf-8"), headers={
                                "Authorization": f"Bearer {api_key}",
                                "Content-Type": "application/json"
                            })
                        with urllib.request.urlopen(req) as resp:
                            r = json.loads(resp.read().decode("utf-8"))
                            return [item["embedding"] for item in r["data"]]

                    loop = asyncio.get_event_loop()
                    chunks = loop.run_until_complete(semantic_chunk_text(doc_path.read_text(encoding="utf-8")[:50000], embed_sentences, 500))
                    
                    for i, chunk in enumerate(chunks):
                        logger.info(f"Ingesting structured semantic chunk {i+1}/{len(chunks)} into GraphManager.")
                        asyncio.run(self.graph_manager.add_episode(
                            content=chunk,
                            source_type="text",
                            name=f"{doc_path.stem} (Chunk {i+1})",
                            group_id="research"
                        ))
                    logger.info(f"GraphManager recursively extracted relationships for {doc_path.stem}")
                except Exception as ex:
                    logger.error(f"GraphManager ingestion failed for {doc_path.stem}: {ex}")

                # Check if generated audio needs to be synthesized
                # The user specified generating audio only manually, but we show how here securely via instructions.
                # Write the briefing to the vault
                brief_path.write_text(f"---\ntags: [briefing, auto-generated]\nsource: {doc_path.name}\n---\n\n# Study Briefing: {doc_path.stem}\n\n*Note: Use the 'podcast' tool on this file to automatically synthesize a deep-dive audio discussion.*\n\n{brief_content}", encoding="utf-8")
                return True
        except Exception as e:
            logger.error(f"Failed to generate briefing for {doc_path.name}: {e}")
            return False

    def _convert_pdf_to_md(self, pdf_path: Path, md_path: Path):
        """Convert a PDF file to Structured Markdown using OpenDataLoader."""
        print(f"📄 Converting PDF to Markdown: {pdf_path.name}...")
        try:
            import opendataloader_pdf
            import uuid
            opendataloader_pdf.convert(
                input_path=[str(pdf_path)],
                output_dir=str(pdf_path.parent),
                format="markdown,json"
            )
            # Add frontmatter to the newly generated MD so Hermes manages it
            if md_path.exists():
                content = md_path.read_text(encoding="utf-8")
                new_uuid = str(uuid.uuid4())
                frontmatter = f"---\nuuid: {new_uuid}\ntags: [pdf-extraction]\nsource_pdf: {pdf_path.name}\n---\n\n"
                md_path.write_text(frontmatter + content, encoding="utf-8")
                print(f"✅ Extracted Markdown for {pdf_path.name}")
        except Exception as e:
            logger.error(f"Failed to convert PDF %s: %s", pdf_path.name, e)

    def _ingest_file(self, file_path: Path, entity_type: str) -> bool:
        """Ingest a single file and update the database. Returns True if successful."""
        try:
            raw_content = file_path.read_text(encoding="utf-8")
            content = self._filter_pii_and_secrets(raw_content)
            fm, body = self._parse_frontmatter(content)
            compiled_truth, timeline = self._parse_knowledge_body(body)
            
            uuid_str = fm.get("uuid")
            if not uuid_str:
                return False # Skip files without UUID (not managed by Hermes)
                
            # If there's an append-only timeline, push it natively to the graph
            if timeline:
                try:
                    asyncio.run(self.graph_manager.add_episode(
                        content=timeline,
                        source_type="text",
                        name=f"Timeline updates for {file_path.stem}",
                        group_id="personal"
                    ))
                except Exception as ex:
                    logger.warning(f"Failed to ingest timeline into graph for {file_path.stem}: {ex}")
                
            # Relative path for DB
            rel_path = str(file_path.relative_to(self.vault_path))
            metadata = extract_markdown_metadata(content)
            
            # Update DB based on type
            if entity_type == "person":
                self.db.save_knowledge_person(
                    name=fm.get("name") or file_path.stem,
                    role=fm.get("role"),
                    organization=fm.get("organization"),
                    details=compiled_truth,
                    uuid=uuid_str,
                    file_path=rel_path
                )
            elif entity_type == "project":
                self.db.save_knowledge_project(
                    name=fm.get("name") or file_path.stem,
                    description=compiled_truth,
                    status=fm.get("status", "active"),
                    uuid=uuid_str,
                    file_path=rel_path
                )
            elif entity_type == "decision":
                self.db.save_knowledge_decision(
                    title=fm.get("title") or file_path.stem,
                    rationale=compiled_truth,
                    status=fm.get("status", "active"),
                    uuid=uuid_str,
                    file_path=rel_path
                )
            elif entity_type == "note":
                self.db.save_knowledge_note(
                    content=compiled_truth,
                    tags=fm.get("tags", []),
                    uuid=uuid_str,
                    file_path=rel_path
                )
            if hasattr(self.db, "upsert_obsidian_managed_file"):
                self.db.upsert_obsidian_managed_file(
                    vault_relative_path=rel_path,
                    managed_relative_path=str(file_path.relative_to(self.vault_path / self.agent_prefix)),
                    uuid=uuid_str,
                    entity_type=entity_type,
                    wiki_page_type=None,
                    file_ext=file_path.suffix.lower(),
                    content_hash=compute_content_hash(content),
                    last_vault_mtime=file_path.stat().st_mtime,
                    last_vault_size=file_path.stat().st_size,
                    last_db_revision_id=None,
                    last_sync_direction="vault_to_db",
                    sync_status="synced",
                    conflict_state="none",
                    source_origin="managed",
                    tombstoned=False,
                    metadata=metadata,
                )
            if hasattr(self.db, "replace_obsidian_attachment_refs"):
                refs = []
                for target in metadata.get("embeds", []) + metadata.get("markdown_links", []):
                    refs.append({
                        "target_path": target,
                        "target_type": "embed" if target in metadata.get("embeds", []) else "markdown",
                        "exists": True,
                        "mime_type": None,
                    })
                self.db.replace_obsidian_attachment_refs(rel_path, refs)
            if hasattr(self.db, "record_obsidian_sync_event"):
                self.db.record_obsidian_sync_event(
                    event_type="vault_ingest",
                    path=rel_path,
                    direction="vault_to_db",
                    status="ok",
                    detail=f"Ingested {entity_type} from Obsidian",
                    metadata={"entity_type": entity_type, "path": rel_path},
                )
            return True
        except Exception as e:
            logger.error("Failed to ingest %s: %s", file_path, e)
            return False

    def _index_canvas(self, canvas_path: Path) -> None:
        try:
            content = canvas_path.read_text(encoding="utf-8")
            refs = extract_canvas_refs(content)
            rel_path = str(canvas_path.relative_to(self.vault_path))
            if hasattr(self.db, "upsert_obsidian_managed_file"):
                self.db.upsert_obsidian_managed_file(
                    vault_relative_path=rel_path,
                    managed_relative_path=str(canvas_path.relative_to(self.vault_path / self.agent_prefix)),
                    uuid=None,
                    entity_type="canvas",
                    wiki_page_type=None,
                    file_ext=canvas_path.suffix.lower(),
                    content_hash=compute_content_hash(content),
                    last_vault_mtime=canvas_path.stat().st_mtime,
                    last_vault_size=canvas_path.stat().st_size,
                    last_db_revision_id=None,
                    last_sync_direction="vault_to_db",
                    sync_status="synced",
                    conflict_state="none",
                    source_origin="managed",
                    tombstoned=False,
                    metadata={"node_count": len(refs)},
                )
            if hasattr(self.db, "replace_obsidian_canvas_refs"):
                self.db.replace_obsidian_canvas_refs(rel_path, refs)
        except Exception as e:
            logger.error("Failed to index canvas %s: %s", canvas_path, e)

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
