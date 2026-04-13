#!/usr/bin/env python3
import os
import re
import yaml
import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class RecipeInstaller:
    """
    Implements 'Thin Harness, Fat Skills' via Markdown Installation.
    Parses Markdown files mapping infrastructure (Cron, Env Keys, and Code Files)
    and autonomously provisions them to the workspace.
    """
    def __init__(self, recipes_dir: str = None):
        if not recipes_dir:
            self.recipes_dir = Path(__file__).parent.parent / "recipes"
        else:
            self.recipes_dir = Path(recipes_dir)
            
        self.hermes_dir = Path(os.environ.get("HOME", ".")) / ".hermes"

    def install(self, recipe_name: str) -> bool:
        recipe_path = self.recipes_dir / (recipe_name if recipe_name.endswith('.md') else f"{recipe_name}.md")
        if not recipe_path.exists():
            logger.error(f"Recipe {recipe_name} not found at {recipe_path}")
            return False
            
        content = recipe_path.read_text(encoding="utf-8")
        
        # 1. Parse Environment Requirements
        keys_match = re.search(r'INSTALL:\s*keys\n```(?:yaml)?\n(.*?)```', content, re.DOTALL)
        if keys_match:
            logger.info("Parsing Environment Keys...")
            new_keys = keys_match.group(1).splitlines()
            env_path = self.hermes_dir / ".env"
            
            if env_path.exists():
                env_text = env_path.read_text()
                for key_line in new_keys:
                    if ":" not in key_line: continue
                    key = key_line.split(":")[0].strip()
                    if key and f"{key}=" not in env_text:
                        logger.info(f"Adding placeholder for {key} to ~/.hermes/.env")
                        with open(env_path, "a") as f:
                            f.write(f"\n{key}=\n")
        
        # 2. Parse Scheduled Cron Jobs
        crons_match = re.search(r'INSTALL:\s*cron\n```(?:json)?\n(.*?)```', content, re.DOTALL)
        if crons_match:
            logger.info("Parsing Cron Deployments...")
            try:
                new_crons = json.loads(crons_match.group(1))
                jobs_file = self.hermes_dir / "cron" / "jobs.json"
                if jobs_file.exists():
                    with open(jobs_file, "r") as f:
                        jobs = json.load(f)
                    
                    # Merge logic (simple append if not existing)
                    existing_prompts = [j.get("prompt") for j in jobs.get("jobs", [])]
                    for nc in new_crons:
                        if nc.get("prompt") not in existing_prompts:
                            jobs.setdefault("jobs", []).append(nc)
                            
                    with open(jobs_file, "w") as f:
                        json.dump(jobs, f, indent=2)
            except Exception as e:
                logger.error("Failed to parse/deploy cron definitions: %s", e)

        # 3. Parse Executable Scripts/Files
        scripts = re.finditer(r'INSTALL:\s*file:([^\n]+)\n```(?:python)?\n(.*?)```', content, re.DOTALL)
        for s in scripts:
            target_path_str = s.group(1).strip()
            # If relative, map to the hermes agent directory space
            if target_path_str.startswith("~/.hermes"):
                target_path = Path(os.path.expanduser(target_path_str))
            else:
                target_path = Path(__file__).parent.parent / target_path_str
                
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(s.group(2).strip(), encoding="utf-8")
            logger.info(f"Deployed provision: {target_path}")

        logger.info(f"✅ Successfully provisioned 'Thin Harness' recipe: {recipe_name}")
        return True
    
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        logging.basicConfig(level=logging.INFO)
        # Assumes running from hermes-agent root
        installer = RecipeInstaller()
        installer.install(sys.argv[1])
