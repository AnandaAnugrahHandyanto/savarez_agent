#!/usr/bin/env python3
import os
import sys
import json
import yaml
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Add the agent path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from agent.graph_manager import GraphManager

HERMES_DIR = os.path.expanduser("~/.hermes")
load_dotenv(os.path.join(HERMES_DIR, ".env"))

def parse_platform_state() -> str:
    """Aggregates all configs, skills, and crons into a structured Document."""
    content = ["# Hermes Context Graph - System Manifest\n"]
    
    # 1. Config & MCPs
    config_path = os.path.join(HERMES_DIR, "cli-config.yaml")
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            cfg = yaml.safe_load(f)
            
            content.append("## Core Configuration")
            content.append(f"Default Model is {cfg.get('model', {}).get('default')}")
            
            mcps = cfg.get("mcp_servers", {})
            if mcps:
                content.append("\n## MCP Servers")
                for mcp_name, details in mcps.items():
                    content.append(f"- MCP Server `{mcp_name}` provides tool execution.")
                    
    # 2. Cron Jobs
    jobs_path = os.path.join(HERMES_DIR, "cron", "jobs.json")
    if os.path.exists(jobs_path):
        with open(jobs_path, "r") as f:
            data = json.load(f)
            jobs = data.get("jobs", [])
            content.append("\n## Cron Jobs")
            for job in jobs:
                if job.get("enabled"):
                    deps = job.get("skills", [])
                    deps_str = f". Dependencies: Depends on skills: {', '.join(deps)}" if deps else ""
                    content.append(f"- CronJob `{job.get('name')}` runs on schedule `{job.get('schedule_display')}`{deps_str}")
                    
    # 3. Skills
    skills_dir = os.path.join(HERMES_DIR, "skills")
    if os.path.exists(skills_dir) and os.path.isdir(skills_dir):
        content.append("\n## Skills")
        for skill_folder in os.listdir(skills_dir):
            skill_path = os.path.join(skills_dir, skill_folder)
            if os.path.isdir(skill_path):
                skill_md = os.path.join(skill_path, "SKILL.md")
                if os.path.exists(skill_md):
                    with open(skill_md, "r") as f:
                        lines = f.readlines()
                        desc = ""
                        # very simple extraction of first few lines for description
                        for line in lines[1:5]:
                            if line.strip() and not line.startswith("#"):
                                desc += line.strip() + " "
                        content.append(f"- Skill `{skill_folder}` provides capability: {desc.strip()[:100]}...")
                        
    return "\n".join(content)

async def main():
    print("Parsing Platform State...")
    manifest = parse_platform_state()
    
    # Save the manifest as an artifact just in case
    manifest_path = os.path.join(HERMES_DIR, "cron", "system_manifest.md")
    with open(manifest_path, "w") as f:
        f.write(manifest)
        
    print(f"Manifest written to {manifest_path}")
    print("Ingesting into Context Graph. This requires LLM calls and may take 10-30 seconds...")
    
    db_path = Path(HERMES_DIR) / "context-graph" / "kuzu_db"
    
    gm = GraphManager(db_path=db_path)
    
    res = await gm.add_episode(
        content=manifest,
        source_type="text",
        name="hermes-architecture-manifest",
        metadata={"source_description": "system-ontology-bootstrap"},
        group_id=None
    )
    
    print(f"Ingestion complete!")
    print(f"Entities Extracted: {res['entities_extracted']}")
    print(f"Edges Extracted: {res['edges_extracted']}")
    
    await gm.close()

if __name__ == "__main__":
    asyncio.run(main())
