#!/usr/bin/env python3
import sys
import os
import json
from pathlib import Path

def save_to_research(title, content, url, vault_path=None):
    """Save a source into the Obsidian Research folder."""
    if not vault_path:
        vault_path = os.environ.get("OBSIDIAN_VAULT_PATH")
        if not vault_path:
            return False, "No vault path configured."
    
    research_dir = Path(os.path.expanduser(vault_path)) / "Hermes" / "Research"
    research_dir.mkdir(parents=True, exist_ok=True)
    
    # Sanitize title for filename
    safe_title = "".join([c if c.isalnum() or c in " _-" else "_" for c in title]).strip()
    file_path = research_dir / f"{safe_title}.md"
    
    content_with_frontmatter = f"""---
title: {title}
url: {url}
date_added: {Path().stat().st_ctime}
tags: [source, discovered]
---

# {title}

{content}
"""
    file_path.write_text(content_with_frontmatter, encoding="utf-8")
    return True, str(file_path)

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: discovery_helper.py <title> <url> <content>")
        sys.exit(1)
        
    title = sys.argv[1]
    url = sys.argv[2]
    content = sys.argv[3]
    
    success, result = save_to_research(title, content, url)
    if success:
        print(f"Saved: {result}")
    else:
        print(f"Error: {result}")
        sys.exit(1)
